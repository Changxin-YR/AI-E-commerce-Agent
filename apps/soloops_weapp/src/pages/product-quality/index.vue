// route: /product-quality
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Taro, { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import { queryString, requestId } from '../../services/task-policy'
import { supportTime } from '../../services/support-types'
import SourceList from '../../components/SourceList.vue'
import {
  checkedQualityScope,
  clearsQualityReport,
  coverageGaps,
  defaultQualityForm,
  dirtyQualityForm,
  identityLabels,
  productIssues,
  productMoney,
  qualityChannels,
  qualityCoverageStatus,
  qualitySavePayload,
  qualityStatus,
  qualitySummary,
  unknownResult,
  type QualityPage,
  type QualityResult,
  type QualitySaved,
} from '../../services/product-quality-policy'
import type { DataIdentity } from '../../services/business-rule-policy'

const form = reactive(defaultQualityForm())
const result = ref<QualityResult>(),
  saved = ref<QualitySaved>(),
  history = ref<QualitySaved[]>([]),
  cursor = ref<number | null>(null)
const busy = ref(false),
  error = ref(''),
  notice = ref(''),
  unknown = ref(false),
  confirmed = ref(false),
  confirmClear = ref(false),
  count = ref(10),
  pendingSave = ref<Record<string, unknown>>()
let alive = true,
  epoch = 0,
  saveId = requestId(),
  linked: Record<string, string> = {}
const request = scopedRequest(api, () => (alive ? epoch : null))
const base = () => `/shops/${account.shopId}`
const timezone = computed(
  () =>
    account.shops.find((shop) => shop.id === account.shopId)?.timezone ||
    'Asia/Shanghai',
)
const identities: DataIdentity[] = ['user_import', 'synthetic']
const channelKeys = ['', 'generic', 'shopify', 'amazon', 'other']
const channelLabels = [
  '全部导入渠道',
  '通用 / 自建表',
  'Shopify',
  'Amazon',
  '其他来源',
]
const shown = computed(() =>
  (result.value?.products ?? []).slice(0, count.value),
)
const gaps = computed(() => (result.value ? coverageGaps(result.value) : []))
const protect = computed(
  () =>
    unknown.value ||
    !!pendingSave.value ||
    confirmed.value ||
    dirtyQualityForm(form, result.value?.scope),
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
    Object.assign(form, defaultQualityForm())
    result.value = undefined
    saved.value = undefined
    history.value = []
    cursor.value = null
    count.value = 10
    confirmed.value = false
    confirmClear.value = false
    unknown.value = false
    pendingSave.value = undefined
    saveId = requestId()
    error.value = notice.value = ''
  },
  { flush: 'sync' },
)
watch(protect, (value) => {
  if (!alive) return
  if (value)
    Taro.enableAlertBeforeUnload({
      message: '有未保存的检查范围或待核对报告，离开前请确认。',
    })
  else Taro.disableAlertBeforeUnload()
})
watch(
  () => [form.data_identity, form.channel, form.sku_prefix],
  () => {
    // A preview belongs to the scope it was calculated for; never save it under new form values.
    result.value = undefined
    saved.value = undefined
    pendingSave.value = undefined
    confirmed.value = false
    confirmClear.value = false
  },
  { flush: 'sync' },
)

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
  const page = await request<QualityPage>(
    `${base()}/product-quality/reports${more && cursor.value ? `?before=${cursor.value}` : ''}`,
  )
  history.value = more ? [...history.value, ...page.items] : page.items
  cursor.value = page.next_cursor
}
function adopt(value: QualitySaved) {
  saved.value = value
  result.value = value.snapshot || undefined
  count.value = 10
  confirmed.value = false
  confirmClear.value = false
}
async function preview() {
  await perform(async () => {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    const scope = checkedQualityScope(form)
    const value = await request<QualityResult>(
      `${base()}/product-quality/preview`,
      'POST',
      scope,
    )
    result.value = value
    saved.value = undefined
    count.value = 10
    saveId = requestId()
    pendingSave.value = undefined
    unknown.value = false
    confirmed.value = false
    await loadHistory()
    notice.value = `已核对 ${value.product_count} 个商品；保存前请查看未检查项与来源。`
  })
}
async function save() {
  await perform(async () => {
    const current = result.value
    if (!current || saved.value) return
    if (unknown.value) throw new Error('上次保存结果未知，请先回查或重新检查。')
    pendingSave.value = qualitySavePayload(current, saveId, confirmed.value)
    const body = pendingSave.value
    if (!body) return
    // The old preview is hidden while revalidating; a failure must not leave it on screen.
    result.value = undefined
    confirmed.value = false
    let value: QualitySaved
    try {
      value = await request<QualitySaved>(
        `${base()}/product-quality/reports`,
        'POST',
        body,
      )
    } catch (cause) {
      if (unknownResult(cause)) unknown.value = true
      else pendingSave.value = undefined
      throw cause
    }
    const readback = await request<QualitySaved>(
      `${base()}/product-quality/reports/${value.id}`,
    )
    adopt(readback)
    pendingSave.value = undefined
    unknown.value = false
    saveId = requestId()
    await loadHistory()
    notice.value = `质量报告 #${readback.id} 已保存并按编号回读。`
  })
}
async function retrySave() {
  await perform(async () => {
    const body = pendingSave.value
    if (!body) return
    let value: QualitySaved
    try {
      value = await request<QualitySaved>(
        `${base()}/product-quality/reports`,
        'POST',
        body,
      )
    } catch (cause) {
      if (unknownResult(cause)) unknown.value = true
      else pendingSave.value = undefined
      throw cause
    }
    const readback = await request<QualitySaved>(
      `${base()}/product-quality/reports/${value.id}`,
    )
    adopt(readback)
    pendingSave.value = undefined
    unknown.value = false
    saveId = requestId()
    await loadHistory()
    notice.value = `质量报告 #${readback.id} 已按同一请求标识回查并回读。`
  })
}
async function show(id: number) {
  await perform(async () => {
    const value = await request<QualitySaved>(
      `${base()}/product-quality/reports/${id}`,
    )
    adopt(value)
    notice.value = value.snapshot
      ? `报告 #${value.id} 已按编号回读。`
      : '报告正文已清除或为空，仅保留范围、状态与审计。'
  })
}
async function clear() {
  await perform(async () => {
    const current = saved.value
    if (!current || !clearsQualityReport(current)) return
    if (unknown.value) throw new Error('上次写入结果未知，请先刷新报告核对。')
    const id = current.id
    const session = account.session?.session_id
    const answer = await Taro.showModal({
      title: '清除报告正文',
      content:
        '清除正文、SKU 前缀与来源依赖后无法恢复；报告范围、状态和审计保留。确认继续？',
    })
    if (
      !answer.confirm ||
      saved.value?.id !== id ||
      session !== account.session?.session_id ||
      !alive
    )
      return
    let value: QualitySaved
    try {
      value = await request<QualitySaved>(
        `${base()}/product-quality/reports/${id}/clear`,
        'POST',
        { confirm: true },
      )
    } catch (cause) {
      if (unknownResult(cause)) unknown.value = true
      throw cause
    }
    const readback = await request<QualitySaved>(
      `${base()}/product-quality/reports/${id}`,
    )
    adopt(readback)
    result.value = undefined
    confirmClear.value = false
    await loadHistory()
    notice.value = '报告正文与来源依赖已清除，保留范围、状态与审计。'
  })
}
function pick(field: 'data_identity' | 'channel', event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  if (field === 'data_identity')
    form.data_identity = identities[index] ?? 'user_import'
  else form.channel = channelKeys[index] ?? ''
  confirmed.value = false
}
function toggleConfirmed(event: unknown) {
  const value = (event as { detail: { value?: unknown[] } }).detail.value
  confirmed.value = Array.isArray(value) && value.length > 0
}
function toggleClear(event: unknown) {
  const value = (event as { detail: { value?: unknown[] } }).detail.value
  confirmClear.value = Array.isArray(value) && value.length > 0
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
    if (typeof linked.sku_prefix === 'string')
      form.sku_prefix = linked.sku_prefix
    await loadHistory()
    const report = Number(linked.report)
    if (Number.isInteger(report) && report > 0) await show(report)
    linked = {}
  })
})
</script>
<template>
  <view class="screen">
    <view class="hero"
      ><text class="eyebrow">SOLOOPS · PRODUCT QUALITY</text
      ><text class="title">商品资料，逐项核对。</text
      ><text class="muted"
        >从已导入的名称、参数与金额出发，保留每个核对项的依据与来源。</text
      ></view
    >
    <text v-if="error" class="error">{{ error }}</text
    ><text v-if="notice" class="hint">{{ notice }}</text
    ><text v-if="unknown" class="error"
      >上次保存结果未知：可用同一请求标识回查，或重新检查后再保存，不要换请求标识重复提交。</text
    >
    <view class="card"
      ><text class="section-title">商品检查范围</text
      ><text class="hint"
        >仅检查当前导入主档；品牌、编码、图片和平台刊登要求仍需另外核验。</text
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
          >来源渠道：{{
            form.channel ? qualityChannels[form.channel] : '全部导入渠道'
          }}</view
        ></picker
      ><text class="label">SKU 前缀（可选，区分大小写，最多 120 字符）</text
      ><input
        v-model="form.sku_prefix"
        :maxlength="120"
        :disabled="busy"
        placeholder="按原始 SKU 前缀筛选"
      /><button class="primary" :disabled="busy" @tap="preview">
        检查商品信息
      </button></view
    >
    <view v-if="result" class="card"
      ><view class="row"
        ><text class="section-title">检查结果</text
        ><text class="badge">来源版本 {{ result.source_revision }}</text></view
      ><text>{{ qualitySummary(result) }}</text
      ><text class="hint"
        >核对时间 {{ supportTime(result.checked_at, timezone) }} · 预览指纹
        {{ result.preview_hash.slice(0, 12) }}… ·
        保存时服务端会重新核验全部来源。</text
      >
      <text class="label">检查覆盖</text
      ><text v-for="item in result.coverage" :key="item.code" class="hint"
        >{{ qualityCoverageStatus[item.status] || item.status }} ·
        {{ item.label
        }}<template v-if="item.reason">：{{ item.reason }}</template></text
      ><text v-if="gaps.length" class="error"
        >未检查项 {{ gaps.length }} 个：{{
          gaps.map((g) => g.label).join('、')
        }}。保存报告只记录这些项未检查，不代表已通过。</text
      ><text v-for="limit in result.limitations" :key="limit" class="hint">{{
        limit
      }}</text>
      <text class="label"
        >商品明细（共 {{ result.product_count }} 个，已显示
        {{ shown.length }} 个）</text
      ><text v-if="!result.products.length" class="muted"
        >此范围暂无商品，请导入资料或调整范围。</text
      ><view v-for="product in shown" :key="product.product_id" class="card"
        ><text class="section-title"
          >{{ product.sku }} · {{ product.name }}</text
        ><text class="hint"
          >渠道 {{ product.channel }} · 售价
          {{ productMoney(product.price, product.currency) }} · 成本
          {{ productMoney(product.unit_cost, product.cost_currency) }}</text
        ><text class="hint">参数：{{ product.facts || '参数为空' }}</text
        ><text
          v-for="line in productIssues(product)"
          :key="line"
          class="hint"
          >{{ line }}</text
        ><text v-if="!product.issues.length" class="hint"
          >当前规则下未发现问题。</text
        ><text v-if="product.similar_sku_count" class="hint"
          >相似 SKU {{ product.similar_sku_count }} 个：{{
            product.similar_skus.join('、')
          }}</text
        ><SourceList
          :sources="[product.source]"
          :shop-id="account.shopId" /></view
      ><button
        v-if="shown.length < result.products.length"
        :disabled="busy"
        @tap="count += 10"
      >
        更多商品（{{ result.products.length }}）
      </button>
      <view v-if="!saved"
        ><checkbox-group @change="toggleConfirmed($event)"
          ><label class="label"
            ><checkbox
              value="confirm"
              :checked="confirmed"
              :disabled="busy"
            />我已查看范围与未检查项，确认保存本次本地检查报告</label
          ></checkbox-group
        ><button class="primary" :disabled="busy || !confirmed" @tap="save">
          保存检查报告
        </button></view
      >
      <view v-if="pendingSave"
        ><text class="hint"
          >上次保存结果尚未确认；可用同一请求标识回查，不要重新检查后再提交。</text
        ><button :disabled="busy" @tap="retrySave">
          回查上次保存请求
        </button></view
      ></view
    >
    <view v-if="saved" class="card"
      ><view class="row"
        ><text class="section-title">质量报告 #{{ saved.id }}</text
        ><text class="badge">{{
          qualityStatus[saved.status] || saved.status
        }}</text></view
      ><text class="hint"
        >保存于 {{ supportTime(saved.created_at, timezone) }} · 范围
        {{ identityLabels[saved.scope.data_identity] }} ·
        {{
          saved.scope.channel
            ? qualityChannels[saved.scope.channel]
            : '全部导入渠道'
        }}
        · SKU 前缀 {{ saved.scope.sku_prefix || '未设置' }}</text
      ><text v-if="saved.status === 'stale'" class="hint"
        >以下为当时的检查记录，不能代表当前商品资料；请重新检查。</text
      ><template v-if="clearsQualityReport(saved)"
        ><checkbox-group @change="toggleClear($event)"
          ><label class="label"
            ><checkbox
              value="clear"
              :checked="confirmClear"
              :disabled="busy"
            />确认清除这份报告正文与来源依赖</label
          ></checkbox-group
        ><button class="danger" :disabled="busy || !confirmClear" @tap="clear">
          清除报告正文
        </button></template
      ><text v-else class="hint"
        >正文与来源依赖已清除，仅保留范围、状态与审计。</text
      ></view
    >
    <view class="card"
      ><view class="row"
        ><text class="section-title">本店历史报告</text
        ><text class="badge">{{ history.length }} 条</text></view
      ><button :disabled="busy" @tap="perform(() => loadHistory())">
        刷新报告与来源
      </button>
      <text v-if="!history.length" class="muted"
        >此店暂无已保存的检查报告。</text
      >
      <view v-for="item in history" :key="item.id" class="row"
        ><text class="hint"
          >#{{ item.id }} · {{ qualityStatus[item.status] || item.status }} ·
          {{ supportTime(item.created_at, timezone) }}</text
        ><button :disabled="busy" @tap="show(item.id)">查看报告</button></view
      >
      <button
        v-if="cursor"
        :disabled="busy"
        @tap="perform(() => loadHistory(true))"
      >
        加载更早报告
      </button></view
    >
  </view>
</template>
