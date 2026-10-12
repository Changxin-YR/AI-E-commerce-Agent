// route: /product-edits
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Taro, { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import { requestId } from '../../services/task-policy'
import { supportTime } from '../../services/support-types'
import { openLink } from '../../services/navigation'
import SourceList from '../../components/SourceList.vue'
import type { SourceChannel } from '../../services/import-types'
import type { DataIdentity } from '../../services/business-rule-policy'
import {
  approvePayload,
  catalogFields,
  changedPreview,
  changedProducts,
  checkedEditCreate,
  controlPayload,
  editControlLabels,
  editGates,
  editItemResultLabels,
  editMaxChanges,
  editStatusLabels,
  editSummary,
  selectedCount,
  unknownResult,
  visibleProducts,
  type EditControl,
  type EditCreateInput,
  type EditPage,
  type EditSaved,
  type EditField,
} from '../../services/product-edit-policy'
import {
  checkedQualityScope,
  identityLabels,
  productMoney,
  qualityChannels,
  type QualityResult,
} from '../../services/product-quality-policy'

const form = reactive({
  data_identity: 'user_import' as DataIdentity,
  channel: 'generic',
  sku_prefix: '',
})
const bulk = reactive({ prefix: '', append: '' })
const catalog = ref<QualityResult>(),
  fields = ref<Record<number, EditField>>({}),
  saved = ref<EditSaved>(),
  history = ref<EditSaved[]>([]),
  cursor = ref<number | null>(null),
  page = ref(0),
  controlAction = ref<EditControl>('clear')
const reason = ref('')
const busy = ref(false),
  error = ref(''),
  notice = ref(''),
  unknown = ref(false),
  confirmed = ref(false),
  controlConfirmed = ref(false),
  pendingCreate = ref<EditCreateInput>()
let alive = true,
  epoch = 0,
  createId = requestId(),
  linked: Record<string, string> = {}
const request = scopedRequest(api, () => (alive ? epoch : null))
const base = () => `/shops/${account.shopId}/product-edits`
const timezone = computed(
  () =>
    account.shops.find((shop) => shop.id === account.shopId)?.timezone ||
    'Asia/Shanghai',
)
const identities: DataIdentity[] = ['user_import', 'synthetic']
const channelKeys = ['generic', 'shopify', 'amazon', 'other']
const channelLabels = ['通用 / 自建表', 'Shopify', 'Amazon', '其他来源']
const shown = computed(() =>
  visibleProducts(catalog.value?.products ?? [], page.value),
)
const changes = computed(() =>
  changedProducts(catalog.value?.products ?? [], fields.value),
)
const selectedTotal = computed(() => selectedCount(fields.value))
const canBulk = computed(() =>
  changedPreview(fields.value, bulk.prefix, bulk.append),
)
const gates = computed(() =>
  saved.value
    ? editGates(saved.value)
    : { approve: false, reject: false, withdraw: false, clear: false },
)
const controls = computed(() => {
  const list: EditControl[] = []
  if (gates.value.reject) list.push('reject')
  if (gates.value.withdraw) list.push('withdraw')
  if (gates.value.clear) list.push('clear')
  return list
})
const controlLabels = computed(() =>
  controls.value.map((action) => editControlLabels[action]),
)
const protect = computed(
  () =>
    unknown.value ||
    !!pendingCreate.value ||
    confirmed.value ||
    controlConfirmed.value ||
    changes.value.length > 0 ||
    (!!catalog.value && !!reason.value.trim()),
)

useLoad((value) => {
  linked = value as Record<string, string>
})
useUnload(() => {
  alive = false
  epoch++
})
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    epoch++
    catalog.value = undefined
    fields.value = {}
    saved.value = undefined
    history.value = []
    cursor.value = null
    page.value = 0
    reason.value = ''
    confirmed.value = controlConfirmed.value = false
    unknown.value = false
    pendingCreate.value = undefined
    createId = requestId()
    error.value = notice.value = ''
  },
  { flush: 'sync' },
)
watch(
  () => [form.data_identity, form.channel, form.sku_prefix],
  () => {
    catalog.value = undefined
    fields.value = {}
    page.value = 0
    confirmed.value = controlConfirmed.value = false
  },
  { flush: 'sync' },
)
watch(protect, (value) => {
  if (!alive) return
  if (value)
    Taro.enableAlertBeforeUnload({
      message: '有未保存的修订草稿或待核对处理，离开前请确认。',
    })
  else Taro.disableAlertBeforeUnload()
})

async function perform(work: () => Promise<void>) {
  if (busy.value || !alive) return
  const token = epoch
  busy.value = true
  error.value = notice.value = ''
  try {
    await work()
  } catch (cause) {
    if (alive && token === epoch)
      error.value =
        cause instanceof Error ? cause.message : '操作失败，请刷新核对。'
  } finally {
    busy.value = false
  }
}
async function loadHistory(more = false) {
  const result = await request<EditPage>(
    `${base()}${more && cursor.value ? `?before=${cursor.value}` : ''}`,
  )
  history.value = more ? [...history.value, ...result.items] : result.items
  cursor.value = result.next_cursor
}
function adopt(edit: EditSaved) {
  if (edit.snapshot) {
    form.data_identity = edit.snapshot.data_identity
    form.channel = edit.snapshot.channel
  }
  saved.value = edit
  confirmed.value = controlConfirmed.value = false
  controlAction.value = gatesFor(edit)
}
function gatesFor(edit: EditSaved): EditControl {
  const value = editGates(edit)
  if (value.reject) return 'reject'
  if (value.withdraw) return 'withdraw'
  return 'clear'
}
async function load() {
  await perform(async () => {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    if (!channelKeys.includes(form.channel)) throw new Error('请选择来源渠道。')
    const scope = checkedQualityScope({ ...form, channel: form.channel })
    const value = await request<QualityResult>(
      `/shops/${account.shopId}/product-quality/preview`,
      'POST',
      scope,
    )
    catalog.value = value
    fields.value = catalogFields(value.products)
    page.value = 0
    saved.value = undefined
    pendingCreate.value = undefined
    unknown.value = false
    confirmed.value = false
    createId = requestId()
    await loadHistory()
    notice.value = `已加载 ${value.product_count} 个商品；每批最多选择 ${editMaxChanges} 个有改动的商品。`
  })
}
function toggleSelect(id: number, event: unknown) {
  const field = fields.value[id]
  if (!field) return
  const checked = Boolean(
    (event as { detail: { value: boolean } }).detail.value,
  )
  if (checked && !field.selected && selectedTotal.value >= editMaxChanges) {
    error.value = `每批最多选择 ${editMaxChanges} 个商品。`
    return
  }
  field.selected = checked
  confirmed.value = false
}
function applyBulk() {
  for (const field of Object.values(fields.value)) {
    if (!field.selected) continue
    field.name = bulk.prefix + field.name
    if (bulk.append)
      field.facts = [field.facts, bulk.append].filter(Boolean).join('\n')
  }
  bulk.prefix = ''
  bulk.append = ''
}
async function create(retry = false) {
  await perform(async () => {
    if (!retry && unknown.value)
      throw new Error('上次保存结果未知，请先回查或重新加载商品。')
    if (!retry) {
      if (!catalog.value) throw new Error('请先加载当前商品。')
      pendingCreate.value = checkedEditCreate({
        data_identity: form.data_identity,
        channel: form.channel as SourceChannel,
        reason: reason.value,
        changes: changes.value,
        request_id: createId,
      })
    }
    const body = pendingCreate.value
    if (!body) return
    let value: EditSaved
    try {
      value = await request<EditSaved>(base(), 'POST', body)
    } catch (cause) {
      if (unknownResult(cause)) unknown.value = true
      else pendingCreate.value = undefined
      throw cause
    }
    const readback = await request<EditSaved>(`${base()}/${value.id}`)
    catalog.value = undefined
    fields.value = {}
    reason.value = ''
    pendingCreate.value = undefined
    unknown.value = false
    createId = requestId()
    adopt(readback)
    await loadHistory()
    notice.value = `修订 #${readback.id} 草稿已保存并按编号回读；审批前本地主档不变。`
  })
}
async function show(id: number) {
  await perform(async () => {
    const value = await request<EditSaved>(`${base()}/${id}`)
    adopt(value)
    notice.value = `修订 #${value.id} 已按编号回读。`
  })
}
async function approve() {
  await perform(async () => {
    const current = saved.value
    if (!current) return
    if (unknown.value) throw new Error('上次写入结果未知，请先刷新核对。')
    const body = approvePayload(current, confirmed.value)
    const answer = await Taro.showModal({
      title: '批准本地生效',
      content:
        '批准后仅本地商品主档按差异更新，金额沿用原来源，平台尚未同步；任一项来源或店铺版本变化则整批不生效。确认继续？',
    })
    if (
      !answer.confirm ||
      saved.value?.id !== current.id ||
      saved.value?.version !== current.version ||
      !alive
    )
      return
    let value: EditSaved
    try {
      value = await request<EditSaved>(
        `${base()}/${current.id}/approve`,
        'POST',
        body,
      )
    } catch (cause) {
      if (unknownResult(cause)) unknown.value = true
      throw cause
    }
    const readback = await request<EditSaved>(`${base()}/${value.id}`)
    adopt(readback)
    await loadHistory()
    notice.value =
      readback.status === 'applied'
        ? `修订 #${readback.id} 已本地生效，当前 ${readback.current_count} 项仍为主档来源。`
        : `修订 #${readback.id} 整批未生效（${editStatusLabels[readback.status] || readback.status}），请重新加载商品核对。`
  })
}
async function control() {
  await perform(async () => {
    const current = saved.value
    if (!current) return
    if (unknown.value) throw new Error('上次写入结果未知，请先刷新核对。')
    const action = controlAction.value
    const body = controlPayload(current, action, controlConfirmed.value)
    const answer = await Taro.showModal({
      title: editControlLabels[action],
      content:
        action === 'reject'
          ? '拒绝后草稿不再可批准，历史保留。确认继续？'
          : action === 'withdraw'
            ? '撤销按仍有效的历史来源恢复主档；依赖本批的后续人工修订同步失效。确认继续？'
            : '清除会擦除本批及依赖修订正文，并恢复可用来源；文件独立版本保留。确认继续？',
    })
    if (
      !answer.confirm ||
      saved.value?.id !== current.id ||
      saved.value?.version !== current.version ||
      !alive
    )
      return
    let value: EditSaved
    try {
      value = await request<EditSaved>(
        `${base()}/${current.id}/${action}`,
        'POST',
        body,
      )
    } catch (cause) {
      if (unknownResult(cause)) unknown.value = true
      throw cause
    }
    const readback = await request<EditSaved>(`${base()}/${value.id}`)
    adopt(readback)
    await loadHistory()
    notice.value = `修订 #${readback.id} 已执行${
      editControlLabels[action]
    }并回读，当前状态 ${editStatusLabels[readback.status] || readback.status}。`
  })
}
async function openQuality() {
  try {
    await openLink('/product-quality', { shop: String(account.shopId) })
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : '无法打开商品质量页。'
  }
}
function pick(field: 'data_identity' | 'channel', event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  const identity = identities[index] ?? 'user_import'
  const channel = channelKeys[index] ?? 'generic'
  const unchanged =
    field === 'data_identity'
      ? form.data_identity === identity
      : form.channel === channel
  if (unchanged) return
  const apply = () => {
    if (field === 'data_identity') form.data_identity = identity
    else form.channel = channel
  }
  if (changes.value.length || reason.value.trim()) {
    void Taro.showModal({
      title: '放弃未保存修订',
      content: '切换范围会清空当前选择与编辑内容，是否继续？',
    }).then((answer) => {
      if (answer.confirm && alive) apply()
    })
    return
  }
  apply()
}
function pickControl(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  controlAction.value = controls.value[index] ?? 'clear'
  controlConfirmed.value = false
}
function toggleConfirmed(event: unknown) {
  const value = (event as { detail: { value?: unknown[] } }).detail.value
  confirmed.value = Array.isArray(value) && value.length > 0
}
function toggleControl(event: unknown) {
  const value = (event as { detail: { value?: unknown[] } }).detail.value
  controlConfirmed.value = Array.isArray(value) && value.length > 0
}
useDidShow(() => {
  void perform(async () => {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    if (linked.shop && Number(linked.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不同。')
    if (identities.includes(linked.identity as DataIdentity))
      form.data_identity = linked.identity as DataIdentity
    if (linked.channel !== undefined && channelKeys.includes(linked.channel))
      form.channel = linked.channel
    await loadHistory()
    const id = Number(linked.edit)
    if (Number.isInteger(id) && id > 0) await show(id)
    linked = {}
  })
})
</script>
<template>
  <view class="screen">
    <view class="hero"
      ><text class="eyebrow">SOLOOPS · PRODUCT EDITS</text
      ><text class="title">商品修订，核对后生效。</text
      ><text class="muted"
        >选择商品、编写名称与参数，保存差异草稿后逐项审批；金额与外部平台保持原状。</text
      ></view
    >
    <text v-if="error" class="error">{{ error }}</text
    ><text v-if="notice" class="hint">{{ notice }}</text
    ><text v-if="unknown" class="error"
      >上次写入结果未知：请回查同一请求标识或按编号回读，不要重复提交。</text
    >
    <view class="card"
      ><text class="section-title">选择修订范围</text
      ><text class="hint"
        >每批最多
        {{ editMaxChanges }} 个商品；人工修订保留原始导入与事实依据。</text
      ><picker
        :range="['用户导入文件', '合成测试数据']"
        :value="identities.indexOf(form.data_identity)"
        :disabled="busy"
        @change="pick('data_identity', $event)"
        ><view class="field"
          >数据身份：{{ identityLabels[form.data_identity] }}</view
        ></picker
      ><picker
        :range="channelLabels"
        :value="Math.max(0, channelKeys.indexOf(form.channel))"
        :disabled="busy"
        @change="pick('channel', $event)"
        ><view class="field"
          >来源渠道：{{ qualityChannels[form.channel] || form.channel }}</view
        ></picker
      ><text class="label">SKU 前缀（可选，区分大小写）</text
      ><input
        v-model="form.sku_prefix"
        :maxlength="120"
        :disabled="busy"
      /><button class="primary" :disabled="busy" @tap="load">
        加载当前商品
      </button>
      <button :disabled="busy" @tap="openQuality">打开商品质量检查</button>
      <text class="hint"
        >加载会重置未保存的选择与编辑；切换范围同样会重置。</text
      ></view
    >
    <view v-if="pendingCreate"
      ><text class="hint"
        >上次保存结果尚未确认；可用同一请求标识回查，不要重新加载后重复提交。</text
      ><button :disabled="busy" @tap="create(true)">
        回查上次保存请求
      </button></view
    >
    <view v-if="catalog" class="card"
      ><view class="row"
        ><text class="section-title">选择与编辑</text
        ><text class="badge"
          >{{ selectedTotal }} 选中 / {{ changes.length }} 有改动</text
        ></view
      ><text class="hint"
        >已加载 {{ catalog.product_count }} 个商品 · 来源版本
        {{ catalog.source_revision }}；仅保存有改动的选中商品。</text
      ><text class="label">为选中商品填写相同改动</text
      ><input
        v-model="bulk.prefix"
        :maxlength="240"
        :disabled="busy"
        placeholder="名称前缀"
      /><textarea
        v-model="bulk.append"
        :maxlength="2000"
        :disabled="busy"
        placeholder="追加参数（每行一项）"
      /><button :disabled="busy || !canBulk" @tap="applyBulk">
        填入选中商品
      </button>
      <text class="hint"
        >填入后请逐项核对；名称最多 240 字符，参数最多 2000 字符。</text
      >
      <text v-if="!catalog.products.length" class="muted"
        >此范围暂无商品，请导入资料或调整范围。</text
      >
      <view v-for="product in shown" :key="product.product_id" class="card"
        ><view class="row"
          ><text class="label">{{ product.sku }} · {{ product.name }}</text
          ><switch
            :checked="fields[product.product_id].selected"
            :disabled="
              busy ||
              (!fields[product.product_id].selected &&
                selectedTotal >= editMaxChanges)
            "
            @change="toggleSelect(product.product_id, $event)"
        /></view>
        <template v-if="fields[product.product_id].selected"
          ><text class="label">名称（1–240 字符）</text
          ><input
            v-model="fields[product.product_id].name"
            :maxlength="240"
            :disabled="busy"
          /><text class="label">参数（最多 2000 字符）</text
          ><textarea
            v-model="fields[product.product_id].facts"
            :maxlength="2000"
            :disabled="busy"
          /><text class="hint"
            >修改前：{{ product.name }} · 参数
            {{ product.facts || '参数为空' }} · 售价
            {{ productMoney(product.price, product.currency) }}</text
          ></template
        ></view
      >
      <view class="row"
        ><button :disabled="busy || page === 0" @tap="page -= 1">上一页</button
        ><text class="hint"
          >第 {{ page + 1 }} 页，共
          {{ Math.max(1, Math.ceil(catalog.product_count / 20)) }} 页</text
        ><button
          :disabled="busy || (page + 1) * 20 >= catalog.product_count"
          @tap="page += 1"
        >
          下一页
        </button></view
      >
      <text class="label">修订依据（必填，最多 500 字）</text
      ><textarea
        v-model="reason"
        :maxlength="500"
        :disabled="busy"
        placeholder="填写核对过的规格、资料出处或纠错原因"
      /><button
        class="primary"
        :disabled="busy || !changes.length || !reason.trim()"
        @tap="create(false)"
      >
        保存修订草稿
      </button></view
    >
    <view v-if="saved" class="card"
      ><view class="row"
        ><text class="section-title">修订 #{{ saved.id }}</text
        ><text class="badge">{{
          editStatusLabels[saved.status] || saved.status
        }}</text></view
      ><text class="hint"
        >版本 {{ saved.version }} · 保存
        {{ supportTime(saved.created_at, timezone)
        }}<template v-if="saved.decided_at">
          · 处理 {{ supportTime(saved.decided_at, timezone) }}</template
        ></text
      ><text class="hint">{{ editSummary(saved) }}</text
      ><text class="hint"
        >差异指纹 {{ saved.preview_hash.slice(0, 12) }}… · 输出批次
        {{ saved.output_batch_id ?? '未生成' }}</text
      >
      <template v-if="saved.snapshot"
        ><text class="hint"
          >{{ identityLabels[saved.snapshot.data_identity] }} ·
          {{
            qualityChannels[saved.snapshot.channel] || saved.snapshot.channel
          }}
          · 依据：{{ saved.snapshot.reason }}</text
        >
        <view
          v-for="item in saved.snapshot.items"
          :key="item.product_id"
          class="card"
          ><text class="label"
            >{{ item.before.sku }} ·
            {{ editItemResultLabels[item.result] || item.result }}</text
          ><text class="hint">修改前名称：{{ item.before.name }}</text
          ><text class="hint">修改后名称：{{ item.after.name }}</text
          ><text class="hint"
            >修改前参数：{{ item.before.facts || '参数为空' }}</text
          ><text class="hint"
            >修改后参数：{{ item.after.facts || '参数为空' }}</text
          ><text class="hint"
            >{{ editItemResultLabels[item.result] || item.result }} ·
            {{ item.message }}</text
          ><SourceList :sources="[item.source]" :shop-id="saved.shop_id"
        /></view>
        <view v-if="gates.approve"
          ><checkbox-group @change="toggleConfirmed($event)"
            ><label class="label"
              ><checkbox
                value="confirm"
                :checked="confirmed"
                :disabled="busy"
              />我已逐项核对差异与事实依据，批准本批本地生效</label
            ></checkbox-group
          ><button
            class="primary"
            :disabled="busy || !confirmed"
            @tap="approve"
          >
            批准本地生效
          </button></view
        >
        <template v-if="controls.length"
          ><text class="label">拒绝、撤销与清除</text
          ><text class="hint"
            >撤销按仍有效的历史来源恢复主档；依赖本批的后续人工修订同步失效；清除会擦除本批及依赖修订正文并恢复可用来源，文件独立版本保留。</text
          ><picker
            :range="controlLabels"
            :value="Math.max(0, controls.indexOf(controlAction))"
            :disabled="busy"
            @change="pickControl($event)"
            ><view class="field"
              >处理方式：{{ editControlLabels[controlAction] }}</view
            ></picker
          ><checkbox-group @change="toggleControl($event)"
            ><label class="label"
              ><checkbox
                value="confirm"
                :checked="controlConfirmed"
                :disabled="busy"
              />确认执行所选处理及其依赖影响</label
            ></checkbox-group
          ><button
            class="danger"
            :disabled="busy || !controlConfirmed"
            @tap="control"
          >
            执行所选处理
          </button></template
        ></template
      ></view
    >
    <view class="card"
      ><view class="row"
        ><text class="section-title">本店修订记录</text
        ><text class="badge">{{ history.length }} 条</text></view
      ><button :disabled="busy" @tap="perform(() => loadHistory())">
        刷新修订与来源
      </button>
      <text v-if="!history.length" class="muted">此店暂无修订记录。</text>
      <view v-for="item in history" :key="item.id" class="row"
        ><text class="hint"
          >#{{ item.id }} · {{ editStatusLabels[item.status] || item.status }} ·
          {{ supportTime(item.created_at, timezone) }}</text
        ><button :disabled="busy" @tap="show(item.id)">查看修订</button></view
      >
      <button
        v-if="cursor"
        :disabled="busy"
        @tap="perform(() => loadHistory(true))"
      >
        加载更早修订
      </button></view
    >
  </view>
</template>
