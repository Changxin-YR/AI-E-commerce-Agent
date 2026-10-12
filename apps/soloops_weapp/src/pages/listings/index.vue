<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Taro, { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { queryString } from '../../services/task-policy'
import { openLink } from '../../services/navigation'
import {
  listingStatus,
  sourceStatus,
  type ListingVersion,
  type ProductFacts,
  type ProductWorkspace,
} from '../../services/listing-types'
import { listingActions } from '../../services/listing-policy'
import type { ManualDelivery } from '../../services/delivery-policy'
import { supportTime } from '../../services/support-types'
import SourceList from '../../components/SourceList.vue'
import ReviewedDelivery from '../../components/ReviewedDelivery.vue'

const products = ref<ProductFacts[]>([]),
  history = ref<ListingVersion[]>([]),
  workspace = ref<ProductWorkspace>(),
  selected = ref<ListingVersion>()
const search = ref(''),
  offset = ref(0),
  busy = ref(false),
  error = ref(''),
  notice = ref(''),
  confirmed = ref(false),
  unknown = ref(false)
const content = reactive({ title: '', description: '' })
const params = ref<Record<string, string>>({})
const dirty = computed(
  () =>
    !!selected.value?.snapshot &&
    (content.title !== selected.value.snapshot.proposed.title ||
      content.description !== selected.value.snapshot.proposed.description),
)
const actions = computed(() =>
  selected.value
    ? listingActions(selected.value, dirty.value, confirmed.value)
    : null,
)
const timezone = computed(
  () =>
    account.shops.find((s) => s.id === account.shopId)?.timezone ||
    'Asia/Shanghai',
)
let epoch = 0
let alive = true
const base = () => `/shops/${account.shopId}/listings`
watch(content, () => {
  confirmed.value = false
})
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    epoch++
    products.value = []
    history.value = []
    workspace.value = undefined
    selected.value = undefined
    unknown.value = false
    params.value = {}
    confirmed.value = false
    error.value = ''
    notice.value = ''
  },
)
useLoad((value) => {
  // The operations destination adds shop/identity/channel context; this page
  // scopes products by shop, so only the shop and the linked product are read.
  params.value = value as Record<string, string>
})
useUnload(() => {
  alive = false
  epoch++
})
function checked(event: unknown) {
  return Boolean((event as { detail: { value: boolean } }).detail.value)
}
async function perform(work: () => Promise<void>) {
  if (busy.value) return
  if (!account.session || !account.shopId) {
    error.value = '请先登录并选择店铺。'
    return
  }
  const token = epoch
  busy.value = true
  error.value = ''
  notice.value = ''
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
function adopt(value: ListingVersion) {
  selected.value = value
  Object.assign(
    content,
    value.snapshot?.proposed || { title: '', description: '' },
  )
  confirmed.value = false
}
async function guardDiscard() {
  if (!dirty.value) return true
  const token = epoch
  const answer = await Taro.showModal({
    title: '替换未保存文案',
    content: '此操作会替换当前尚未保存的标题和描述，是否继续？',
  })
  return answer.confirm && token === epoch && alive
}
async function read(id: number) {
  const value = await api.request<ListingVersion>(`${base()}/versions/${id}`)
  adopt(value)
  workspace.value = undefined
  if (value.snapshot && value.source_status === 'current')
    workspace.value = await api.request<ProductWorkspace>(
      `${base()}/products/${value.snapshot.product.product_id}`,
    )
}
async function listProducts(page = 0) {
  products.value = await api.request<ProductFacts[]>(
    `${base()}/products?${queryString({ q: search.value, offset: page })}`,
  )
  offset.value = page
}
async function listHistory() {
  history.value = await api.request<ListingVersion[]>(`${base()}/versions`)
}
async function find(page = 0) {
  await perform(() => listProducts(page))
}
async function choose(id: number) {
  await perform(async () => {
    if (!(await guardDiscard())) return
    workspace.value = await api.request<ProductWorkspace>(
      `${base()}/products/${id}`,
    )
    selected.value = undefined
    unknown.value = false
  })
}
async function inspect(id: number) {
  await perform(async () => {
    if (!(await guardDiscard())) return
    await read(id)
    unknown.value = false
  })
}
async function refresh() {
  await perform(async () => {
    if (!(await guardDiscard())) return
    await listHistory()
    await listProducts(offset.value)
    if (selected.value) await read(selected.value.id)
    else if (workspace.value)
      workspace.value = await api.request<ProductWorkspace>(
        `${base()}/products/${workspace.value.product.product_id}`,
      )
    unknown.value = false
  })
}
async function mutate(kind: 'generate' | 'revise' | 'approve' | 'reject') {
  await perform(async () => {
    if (unknown.value) throw new Error('请先刷新核对上次操作结果。')
    const current = selected.value,
      product = workspace.value,
      token = epoch
    let path: string, data: object
    if (kind === 'generate') {
      if (!product || !(await guardDiscard())) return
      path = `${base()}/generate`
      data = {
        product_id: product.product.product_id,
        expected_source_row_id: product.product.source.row_id,
        expected_active_id: product.active_id,
      }
    } else {
      if (!current || !actions.value) return
      if (kind === 'revise') {
        if (!product || !actions.value.revise) return
        if (
          !content.title.trim() ||
          content.title.length > 240 ||
          content.description.length > 4000
        )
          throw new Error('标题须为1–240字，描述最多4000字。')
        path = `${base()}/versions/${current.id}/revise`
        data = {
          expected_version: current.version,
          expected_active_id: product.active_id,
          content: { ...content },
        }
      } else {
        if (!actions.value[kind]) return
        const answer = await Taro.showModal({
          title: kind === 'approve' ? '批准本地版本' : '拒绝此版本',
          content: `店铺 #${account.shopId}，SKU ${current.snapshot?.product.sku}，版本 #${current.id}。${kind === 'approve' ? '批准后替代当前本地版本；平台外部未提交。' : '保留版本记录，可在来源有效时另存待审版本。'}`,
        })
        if (!answer.confirm || token !== epoch || !alive) return
        path = `${base()}/versions/${current.id}/decision`
        data = {
          expected_version: current.version,
          decision: kind,
          facts_confirmed: kind === 'approve' && confirmed.value,
        }
      }
    }
    unknown.value = true
    const result = await api.request<ListingVersion>(path, 'POST', data)
    adopt(result)
    await read(result.id)
    await listHistory()
    unknown.value = false
    notice.value =
      kind === 'approve'
        ? '已GET回读，本地版本生效，外部未提交。'
        : '已保存并GET回读，请核对文案与处理状态。'
  })
}
async function agent() {
  await perform(async () => {
    if (!workspace.value || !(await guardDiscard())) return
    await openLink('/agent', {
      shop: String(account.shopId),
      mode: 'listing_model',
      product: String(workspace.value.product.product_id),
    })
  })
}
async function delivery(): Promise<ManualDelivery> {
  if (!selected.value || !actions.value?.deliver)
    throw new Error('请先审批当前版本。')
  return api.request<ManualDelivery>(
    `${base()}/versions/${selected.value.id}/delivery?expected_version=${selected.value.version}`,
  )
}
useDidShow(() => {
  void perform(async () => {
    if (dirty.value) {
      notice.value = '保留未保存编辑；刷新前将请求确认。'
      return
    }
    await listProducts(offset.value)
    await listHistory()
    if (params.value.shop && Number(params.value.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不同。')
    const id = Number(params.value.listing || selected.value?.id)
    if (id > 0) await read(id)
    else if (Number(params.value.product) > 0)
      workspace.value = await api.request<ProductWorkspace>(
        `${base()}/products/${Number(params.value.product)}`,
      )
    params.value = {}
    unknown.value = false
  })
})
</script>
<template>
  <view class="screen">
    <view class="hero"
      ><text class="eyebrow">SOLOOPS · LISTING</text
      ><text class="title">文案来自商品事实。</text
      ><text class="muted">生成候选，核对差异，批准本地版本。</text></view
    >
    <view v-if="error" class="error">{{ error }}</view
    ><view v-if="notice" class="hint">{{ notice }}</view
    ><view v-if="unknown" class="error"
      >上次操作结果待核对，请刷新历史后继续。</view
    >
    <view class="card"
      ><text class="section-title">查找商品</text
      ><input
        v-model="search"
        :maxlength="120"
        :disabled="busy"
        placeholder="SKU / 商品名"
      /><button :disabled="busy" @tap="find(0)">查找</button
      ><text v-if="!products.length" class="muted"
        >没有匹配商品，请先导入商品文件。</text
      ><button
        v-for="product in products"
        :key="product.product_id"
        :disabled="busy"
        @tap="choose(product.product_id)"
      >
        {{ product.sku }} · {{ product.name }} ·
        {{ product.source.data_identity }}</button
      ><view class="row"
        ><button :disabled="busy || offset === 0" @tap="find(offset - 50)">
          上一页</button
        ><text>{{ offset / 50 + 1 }}</text
        ><button
          :disabled="busy || products.length < 50"
          @tap="find(offset + 50)"
        >
          下一页
        </button></view
      ></view
    >
    <view v-if="workspace" class="card"
      ><text class="section-title"
        >{{ workspace.product.sku }} · {{ workspace.product.name }}</text
      ><text class="prose">{{ workspace.product.facts || '商品参数缺失' }}</text
      ><text class="hint"
        >当前本地版本 #{{ workspace.active_id || '无' }} ·
        {{ workspace.active_version?.snapshot?.proposed.title }}</text
      ><SourceList
        :sources="[workspace.product.source]"
        :shop-id="account.shopId"
      /><button
        class="primary"
        :disabled="busy || unknown"
        @tap="mutate('generate')"
      >
        从事实生成草稿</button
      ><button :disabled="busy" @tap="agent">准备 AI Listing 候选</button
      ><button
        v-for="version in workspace.versions"
        :key="version.id"
        :disabled="busy"
        @tap="inspect(version.id)"
      >
        商品版本 #{{ version.id }} ·
        {{ listingStatus[version.status] || version.status }}
      </button></view
    >
    <view v-if="selected" class="card"
      ><text class="section-title"
        >版本 #{{ selected.id }} · 第{{ selected.number }}版 · 状态v{{
          selected.version
        }}</text
      ><text
        >{{ listingStatus[selected.status] || selected.status }} ·
        {{
          sourceStatus[selected.source_status] || selected.source_status
        }}</text
      ><text class="hint"
        >{{ selected.engine }} ·
        {{ supportTime(selected.created_at, timezone) }} · R1 · 外部未提交</text
      >
      <template v-if="selected.snapshot"
        ><text class="label"
          >店铺 #{{ selected.shop_id }} /
          {{ selected.snapshot.product.sku }}</text
        ><text class="hint"
          >原版本 #{{
            selected.base_version_id || '导入商品原文'
          }}；审批后更新本地文案。恢复方式：来源有效的历史文案可另存待审版本。</text
        ><text class="label">修改前</text
        ><text>{{ selected.snapshot.before.title }}</text
        ><text class="prose">{{
          selected.snapshot.before.description || '无描述'
        }}</text
        ><text class="label">拟议版本</text
        ><text>{{ selected.snapshot.proposed.title }}</text
        ><text class="prose">{{
          selected.snapshot.proposed.description || '无描述'
        }}</text
        ><text class="hint">{{
          selected.snapshot.before.title === selected.snapshot.proposed.title &&
          selected.snapshot.before.description ===
            selected.snapshot.proposed.description
            ? '与原文相同'
            : '有文字变化，请逐段核对'
        }}</text
        ><text class="label">商品事实</text
        ><text>{{ selected.snapshot.product.name }}</text
        ><text class="prose">{{ selected.snapshot.product.facts }}</text
        ><text
          v-for="gap in selected.snapshot.missing"
          :key="gap"
          class="hint"
          >{{ gap }}</text
        ><text
          v-for="block in selected.snapshot.blockers"
          :key="block"
          class="error"
          >{{ block }}</text
        ><SourceList
          :sources="[selected.snapshot.product.source]"
          :shop-id="account.shopId"
        />
        <view v-if="actions?.revise && workspace"
          ><text class="label">编辑并另存待审版本</text
          ><text class="hint"
            >保留完整商品名和参数，调整完整参数行顺序。真实性、适用性与平台合规需人工核对。</text
          ><input
            v-model="content.title"
            :maxlength="240"
            :disabled="busy"
          /><textarea
            v-model="content.description"
            :maxlength="4000"
            :disabled="busy"
          /><text v-if="dirty" class="hint"
            >编辑尚未保存，保存后需重新审批。</text
          ><button :disabled="busy || unknown" @tap="mutate('revise')">
            保存为待审版本
          </button></view
        >
        <view v-if="selected.status === 'draft'"
          ><view class="row"
            ><text>已逐项核对事实和完整差异</text
            ><switch
              :checked="confirmed"
              :disabled="busy || dirty"
              @change="confirmed = checked($event)" /></view
          ><button
            class="primary"
            :disabled="busy || unknown || !actions?.approve"
            @tap="mutate('approve')"
          >
            批准并在本地生效</button
          ><button
            :disabled="busy || unknown || !actions?.reject"
            @tap="mutate('reject')"
          >
            拒绝此版本
          </button></view
        >
        <ReviewedDelivery
          :context-key="`${selected.id}:${selected.version}:${selected.source_status}`"
          :allowed="!!actions?.deliver"
          :disabled="busy || dirty || unknown"
          :load-artifact="delivery"
        /> </template
      ><text v-else class="muted"
        >来源与派生文案已清除，保留版本和审批记录。</text
      ><text v-if="selected.decided_at" class="hint"
        >审批时间 {{ supportTime(selected.decided_at, timezone) }}</text
      ></view
    >
    <view class="card"
      ><view class="row"
        ><text class="section-title">版本历史</text
        ><button :disabled="busy" @tap="refresh">刷新回读</button></view
      ><text v-if="!history.length" class="muted">尚无文案版本。</text
      ><button
        v-for="item in history"
        :key="item.id"
        :disabled="busy"
        @tap="inspect(item.id)"
      >
        #{{ item.id }} · {{ item.snapshot?.product.sku || '内容已清除' }} ·
        {{ listingStatus[item.status] || item.status }} ·
        {{ sourceStatus[item.source_status] || item.source_status }}
      </button></view
    >
  </view>
</template>
<style scoped>
.prose {
  display: block;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
