<script setup lang="ts">
import { ref, watch } from 'vue'
import { account, api } from '../services/session'
import { openLink, routes } from '../services/navigation'
import type { SavedAnalysis } from '../services/analytics-types'
import type { ListingVersion } from '../services/listing-types'
import type { ReplyDraft } from '../services/support-types'
import type { OperationRun } from '../services/operation-types'
const props = defineProps<{
  kind: string
  id: number
  shop: number
  path: string
  recordKey: string
}>()
const analysis = ref<SavedAnalysis>(),
  listing = ref<ListingVersion>(),
  support = ref<ReplyDraft>(),
  operation = ref<OperationRun>(),
  error = ref(''),
  busy = ref(false)
watch(
  () => [props.id, props.kind, props.shop, account.session?.session_id],
  () => {
    analysis.value = undefined
    listing.value = undefined
    support.value = undefined
    operation.value = undefined
    error.value = ''
  },
)
async function read() {
  if (busy.value || props.shop !== account.shopId) return
  busy.value = true
  error.value = ''
  analysis.value = undefined
  listing.value = undefined
  support.value = undefined
  operation.value = undefined
  try {
    const base = `/shops/${props.shop}`
    if (props.kind === 'analysis')
      analysis.value = await api.request<SavedAnalysis>(
        `${base}/analytics/saved/${props.id}`,
      )
    else if (props.kind === 'listing')
      listing.value = await api.request<ListingVersion>(
        `${base}/listings/versions/${props.id}`,
      )
    else if (props.kind === 'support')
      support.value = await api.request<ReplyDraft>(
        `${base}/support/drafts/${props.id}`,
      )
    else if (props.kind === 'operations')
      operation.value = await api.request<OperationRun>(
        `${base}/operations/runs/${props.id}`,
      )
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '结果回读失败'
  } finally {
    busy.value = false
  }
}
async function open() {
  try {
    await openLink(props.path, {
      shop: String(props.shop),
      [props.recordKey]: String(props.id),
    })
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '打开失败'
  }
}
</script>
<template>
  <view class="card"
    ><text class="label">持久结果 {{ kind }} #{{ id }}</text
    ><button :disabled="busy" @tap="read">GET 回读业务记录</button
    ><text v-if="error" class="error">{{ error }}</text>
    <view v-if="analysis"
      ><text
        >分析 #{{ analysis.id }} · {{ analysis.status }} · 来源
        {{ analysis.source_revision }}</text
      ><text>{{ analysis.snapshot?.answer || '快照已清除' }}</text
      ><text class="hint"
        >销售 {{ analysis.snapshot?.summary.sales ?? '未知' }} · 已知毛利
        {{ analysis.snapshot?.summary.gross_profit ?? '未知' }}
        {{ analysis.scope.currency }}</text
      ><text v-if="analysis.todo"
        >待办 #{{ analysis.todo.id }} · {{ analysis.todo.title }} ·
        {{ analysis.todo.status }}</text
      ></view
    >
    <view v-if="listing"
      ><text
        >Listing #{{ listing.id }} · v{{ listing.version }} ·
        {{ listing.status }} · {{ listing.source_status }} · 外部未提交</text
      ><text>{{ listing.snapshot?.proposed.title || '快照已清除' }}</text
      ><text class="prose">{{
        listing.snapshot?.proposed.description
      }}</text></view
    >
    <view v-if="support"
      ><text
        >客服草稿 #{{ support.id }} · v{{ support.version }} ·
        {{ support.status }} · {{ support.source_status }} · 外部未提交</text
      ><text class="prose">{{
        support.snapshot?.reply || '快照已清除'
      }}</text></view
    >
    <view v-if="operation"
      ><text
        >运营 #{{ operation.id }} · {{ operation.source_status }} · 来源
        {{ operation.source_revision }}</text
      ><text class="hint"
        >新增 {{ operation.snapshot?.created_candidates ?? '未知' }} / 复用
        {{ operation.snapshot?.reused_candidates ?? '未知' }}</text
      ></view
    >
    <button v-if="routes[path]" :disabled="busy" @tap="open">
      前往业务页面
    </button></view
  >
</template>
<style scoped>
.prose {
  display: block;
  white-space: pre-wrap;
}
</style>
