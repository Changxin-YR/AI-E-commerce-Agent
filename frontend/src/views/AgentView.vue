<script setup lang="ts">
import BusinessDateRange from '@/components/BusinessDateRange.vue'
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { useRecordLink } from '@/composables/useRecordLink'
import { useSession } from '@/composables/useSession'
import { loadDemoScope } from '@/composables/demoScope'
import {
  scopeQuery,
  linkedId,
  linkedShop,
  revealRecord,
  applyLinkedScope,
  returnTaskQuery,
} from '@/composables/deepLink'
import { identityApi } from '@/api/identity'
import { agentApi } from '@/api/agent'
import { listingsApi } from '@/api/listings'
import { supportApi } from '@/api/support'
import { ApiError, errorMessage, type StreamEvent } from '@/api/client'
import type {
  AgentAction,
  AgentBudget,
  AgentInput,
  AgentRun,
  ModelStatus,
  SkillDefinition,
} from '@/types/agent'
import { agentLabels } from '@/types/agent'
import type { Shop } from '@/types/identity'
import type { ProductFacts } from '@/types/listings'
import type { MessageFacts } from '@/types/support'
import { supportTime } from '@/types/support'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import AgentRunReview from '@/components/AgentRunReview.vue'
import AgentAnswer from '@/components/AgentAnswer.vue'
import AgentStreamPreview from '@/components/AgentStreamPreview.vue'
import SupportModelContext from '@/components/SupportModelContext.vue'
import OperationModelContext from '@/components/OperationModelContext.vue'
import InternalAuthorizations from '@/components/InternalAuthorizations.vue'
import { authorizationsApi, type InternalAuthorization } from '@/api/authorizations'

const route = useRoute()
const advanced = ref(false)
const previousTurns = ref<AgentRun[]>([])
const showHistory = ref(false)
const confirmSave = ref(false)
const chatThread = ref<HTMLElement | null>(null)
const composerOptions = ref<HTMLDetailsElement | null>(null)
async function openDataSettings(): Promise<void> {
  if (!composerOptions.value) return
  showHistory.value = false
  composerOptions.value.open = true
  await nextTick()
  const identity = composerOptions.value.querySelector<HTMLSelectElement>('[data-data-identity]')
  identity?.closest('details')?.setAttribute('open', '')
  identity?.focus()
}
function closeOptions(): void {
  composerOptions.value?.removeAttribute('open')
  composerOptions.value?.querySelector('summary')?.focus()
}
function toggleHistory(): void {
  composerOptions.value?.removeAttribute('open')
  showHistory.value = !showHistory.value
}
async function scrollToAnswer(): Promise<void> {
  await nextTick()
  if (chatThread.value) chatThread.value.scrollTop = chatThread.value.scrollHeight
}
async function newConversation(): Promise<void> {
  if (busy.value || controlling.value) return
  selected.value = null
  previousTurns.value = []
  showHistory.value = false
  confirmSave.value = false
  form.goal = ''
  form.previous_question = ''
  error.value = ''
  resetConsent()
  await recordLink.write({ shop: shopId.value })
}
function submitShortcut(event: KeyboardEvent): void {
  if (event.key !== 'Enter' || event.isComposing || !(event.ctrlKey || event.metaKey)) return
  event.preventDefault()
  if (!busy.value && !controlling.value) (event.target as HTMLTextAreaElement).form?.requestSubmit()
}
const simpleTemplates = ['question', 'listing_model', 'support_model', 'daily_model']
function toggleMode(): void {
  advanced.value = !advanced.value
  if (!advanced.value && !simpleTemplates.includes(form.template)) form.template = 'question'
  form.response_mode = advanced.value ? 'workflow' : 'chat'
  resetConsent()
}
const suggestions = [
  { template: 'question', label: '看看销售表现', question: '汇总当前统计范围的销售额和已知毛利。' },
  {
    template: 'listing_model',
    label: '写商品文案',
    question: '根据这个商品的事实，帮我写标题和描述。',
  },
  {
    template: 'support_model',
    label: '帮我回复客户',
    question: '根据客户消息和政策，帮我准备回复。',
  },
  {
    template: 'daily_model',
    label: '今天要关注什么',
    question: '检查今日经营数据，告诉我需要关注哪些事项。',
  },
] as const
function useSuggestion(item: (typeof suggestions)[number]): void {
  composerOptions.value?.removeAttribute('open')
  showHistory.value = false
  form.template = item.template
  form.goal = item.question
}
async function ask(): Promise<void> {
  if (!form.goal.trim() || busy.value || controlling.value || model.value?.status !== 'configured')
    return
  // The visible send disclosure authorizes this request only. Never auto-approve writes.
  form.response_mode = 'chat'
  form.previous_question = selected.value?.input?.goal ?? ''
  form.allow_model = true
  form.allow_analysis_data = form.template === 'question'
  form.allow_listing_data = form.template === 'listing_model'
  form.allow_support_data = form.template === 'support_model'
  form.allow_operation_data = form.template === 'daily_model'
  await start()
  if (selected.value?.status === 'succeeded' && !error.value) form.goal = ''
  resetConsent()
  await scrollToAnswer()
}
const { session } = useSession()
const recordLink = useRecordLink()
const restoring = ref(true)
const rulesKey = ref(0)
function resetConsent(): void {
  form.allow_model = false
  form.allow_analysis_data = false
  form.allow_listing_data = false
  form.allow_support_data = false
  form.allow_operation_data = false
  form.authorization_id = null
}
function restoreInput(run: AgentRun): void {
  resetConsent()
  if (!run.input) return
  const input = run.input
  form.template = input.template
  form.goal = input.goal
  form.product_id = input.product_id
  form.message_id = input.message_id
  form.response_language = input.response_language ?? 'auto'
  form.margin_cost_mode = input.margin_cost_mode
  Object.assign(form.scope, input.scope)
  Object.assign(form.budget, run.budget)
  form.support_context = null
  form.expected_operation_hash = null
  rulesKey.value++
}
async function rememberRun(): Promise<void> {
  if (selected.value)
    await recordLink.write({
      shop: shopId.value,
      execution: selected.value.id,
      ...returnTaskQuery(route.query, shopId.value),
    })
}
async function changeShop(): Promise<void> {
  if (Number(route.query.shop) === shopId.value) return
  await recordLink.write({ shop: shopId.value })
  await restoreRoute()
}
function canNavigate(allowReading = false): boolean {
  if (!starting.value && !controlling.value && !driving.value && (allowReading || !busy.value))
    return true
  error.value = '任务正在请求处理中，请等待当前步骤结束或先暂停任务。'
  return false
}
onBeforeRouteLeave(() => canNavigate(true))
onBeforeRouteUpdate((to) => recordLink.isOwn(to.fullPath, false) || canNavigate())
const focusGrant = ref<number | undefined>()
const focusShop = ref(0)
import AppliedRules from '@/components/AppliedRules.vue'
import { applyRule, type BusinessRule } from '@/api/businessRules'

const shops = ref<Shop[]>([])
const shopId = ref(0)
const runs = ref<AgentRun[]>([])
const selected = ref<AgentRun | null>(null)
const skills = ref<SkillDefinition[]>([])
const model = ref<ModelStatus | null>(null)
const products = ref<ProductFacts[]>([])
const messages = ref<MessageFacts[]>([])
const query = ref('')
const rulesPending = ref(true)
const activeRule = ref(false)
function rulesLoaded(rule: BusinessRule): void {
  applyRule(form.scope, rule)
  activeRule.value = rule.active
}
const error = ref('')
const busy = ref(false)
const starting = ref(false)
const controlling = ref(false)
const driving = ref(false)
const streamText = ref('')
const streamMessage = ref('')
const streaming = ref(false)
const streamInterrupted = ref(false)
let alive = true
let loadEpoch = 0
let inspectEpoch = 0
const form = reactive<AgentInput>({
  request_id: '',
  response_mode: 'chat',
  response_language: 'auto',
  previous_question: '',
  template: 'question',
  margin_cost_mode: 'seller_history',
  goal: '',
  product_id: null,
  message_id: null,
  allow_model: false,
  allow_analysis_data: false,
  allow_listing_data: false,
  allow_support_data: false,
  allow_operation_data: false,
  expected_operation_hash: null,
  support_context: null,
  budget: { max_steps: 12, max_seconds: 120, max_cost_usd: '0.10' },
  scope: {
    start_at: new Date(Date.now() - 7 * 86400000).toISOString(),
    end_at: new Date().toISOString(),
    timezone: 'Asia/Shanghai',
    currency: 'USD',
    data_identity: 'user_import',
    intent: 'low_margin',
    channel: 'generic',
    max_age_hours: 24,
    min_quantity: 1,
    max_margin_percent: '20',
  },
})
const initialInput = JSON.parse(JSON.stringify(form)) as AgentInput
const usesModel = computed(() =>
  ['natural', 'question', 'listing_model', 'support_model', 'daily_model'].includes(form.template),
)
watch(
  () => form.template,
  () => {
    if (usesModel.value && Number(form.budget.max_cost_usd) === 0) form.budget.max_cost_usd = '0.10'
    if (!usesModel.value) form.budget.max_cost_usd = '0'
    if (form.template === 'daily_model' && !form.goal.trim())
      form.goal = '检查今日经营数据，汇总库存、订单和待处理消息，给出下一步核对建议。'
  },
  { flush: 'sync' },
)
function resetStream(): void {
  streamText.value = ''
  streamMessage.value = ''
  streamInterrupted.value = false
}
function resetForm(): void {
  Object.assign(form, {
    ...initialInput,
    scope: { ...initialInput.scope },
    budget: { ...initialInput.budget },
  })
}
const marginStart = computed(() => {
  const end = Date.parse(form.scope.end_at)
  return Number.isFinite(end) ? new Date(end - 7 * 86400000).toISOString() : ''
})
watch(
  () => [
    shopId.value,
    form.template,
    form.goal,
    form.product_id,
    form.message_id,
    form.expected_operation_hash,
    JSON.stringify(form.support_context),
    JSON.stringify(products.value),
    JSON.stringify(form.scope),
    JSON.stringify(form.budget),
  ],
  () => {
    resetConsent()
  },
)
const productOptions = computed(() =>
  products.value.filter((p) => p.source.data_identity === form.scope.data_identity),
)
const otherProducts = computed(() =>
  products.value.filter((p) => p.source.data_identity !== form.scope.data_identity),
)
async function useAvailableProducts(): Promise<void> {
  if (busy.value || controlling.value || !otherProducts.value.length) return
  const product = otherProducts.value[0]!
  form.scope.data_identity =
    product.source.data_identity === 'synthetic' ? 'synthetic' : 'user_import'
  form.product_id = product.product_id
  await recordLink.write({ ...route.query, identity: form.scope.data_identity })
}
const selectedProduct = computed(() =>
  productOptions.value.find((p) => p.product_id === form.product_id),
)
const messageOptions = computed(() =>
  messages.value.filter(
    (m) => m.source.data_identity === form.scope.data_identity && m.channel === form.scope.channel,
  ),
)

function accept(run: AgentRun): void {
  if (!alive || shopId.value !== run.shop_id) return
  if (!selected.value || (selected.value.id === run.id && run.version >= selected.value.version)) {
    selected.value = run
    if (streamMessage.value && !streamInterrupted.value)
      streamMessage.value = runStatusMessage(run.status)
    if (run.source_status === 'cleared') resetStream()
    if (!run.input) resetForm()
  }
}
function runStatusMessage(status: string): string {
  return status === 'waiting_approval'
    ? '回答已生成。'
    : status === 'succeeded'
      ? '回答已完成。'
      : `当前状态：${agentLabels[status] ?? status}`
}
async function readOptions(): Promise<void> {
  if (!shopId.value) return
  const shop = shopId.value
  try {
    const [p, m] = await Promise.all([
      listingsApi.products(shop, query.value, 0),
      supportApi.messages(shop, query.value),
    ])
    if (alive && shopId.value === shop) {
      products.value = p
      messages.value = m
    }
  } catch (cause) {
    error.value = errorMessage(cause)
  }
}
async function loadShop(): Promise<void> {
  if (!shopId.value || driving.value) return
  const epoch = ++loadEpoch
  previousTurns.value = []
  confirmSave.value = false
  inspectEpoch++
  selected.value = null
  resetStream()
  resetForm()
  products.value = []
  messages.value = []
  form.product_id = null
  form.message_id = null
  resetConsent()
  model.value = null
  runs.value = []
  const shop = shops.value.find((s) => s.id === shopId.value)
  if (shop) {
    form.scope.timezone = shop.timezone
    form.scope.currency = shop.currency
  }
  busy.value = true
  error.value = ''
  try {
    const id = shopId.value
    const [history, registry, status] = await Promise.all([
      agentApi.runs(id),
      agentApi.skills(id),
      agentApi.model(id),
    ])
    if (!alive || epoch !== loadEpoch || id !== shopId.value) return
    runs.value = history
    skills.value = registry
    model.value = status
    await readOptions()
  } catch (cause) {
    if (alive && epoch === loadEpoch) error.value = errorMessage(cause)
  } finally {
    if (alive && epoch === loadEpoch) busy.value = false
  }
}
async function refresh(): Promise<void> {
  if (!shopId.value || controlling.value) return
  const shop = shopId.value
  try {
    const history = await agentApi.runs(shop)
    if (shopId.value !== shop) return
    runs.value = history
    if (previousTurns.value.length) {
      const ids = previousTurns.value.map((turn) => turn.id)
      const refreshed = await Promise.all(ids.map((id) => agentApi.get(shop, id)))
      if (shopId.value !== shop) return
      previousTurns.value = refreshed
    }
    if (selected.value) accept(await agentApi.get(shop, selected.value.id))
  } catch (cause) {
    error.value = errorMessage(cause)
  }
}
async function inspect(id: number, remember = true): Promise<void> {
  if (busy.value) return
  previousTurns.value = []
  confirmSave.value = false
  resetStream()
  const epoch = ++inspectEpoch
  const shop = shopId.value
  try {
    const run = await agentApi.get(shop, id)
    if (alive && epoch === inspectEpoch && shop === shopId.value) {
      selected.value = run
      restoreInput(run)
      advanced.value =
        run.input?.response_mode !== 'chat' || !simpleTemplates.includes(form.template)
      if (!advanced.value) form.goal = ''
      showHistory.value = false
      void scrollToAnswer()
      if (
        run.input?.product_id &&
        !products.value.some((p) => p.product_id === run.input?.product_id)
      ) {
        try {
          products.value.push((await listingsApi.workspace(shop, run.input.product_id)).product)
        } catch {
          error.value = '任务商品已不可用；历史依据可在执行记录中查看，重新运行前请重新选择。'
        }
      }
      if (run.input?.message_id && !messages.value.some((m) => m.id === run.input?.message_id)) {
        try {
          messages.value.push((await supportApi.workspace(shop, run.input.message_id)).message)
        } catch {
          error.value = '任务消息已不可用；历史依据可在执行记录中查看，重新运行前请重新选择。'
        }
      }
      if (remember) await rememberRun()
    }
  } catch (cause) {
    if (alive && epoch === inspectEpoch && shop === shopId.value) {
      selected.value = null
      error.value =
        cause instanceof ApiError && cause.status === 404
          ? '任务不存在或当前店铺无权访问，请从本店执行记录重新打开。'
          : errorMessage(cause)
    }
  }
}
function receiveStream(event: StreamEvent): void {
  if (!alive || !event.data || typeof event.data !== 'object') return
  if (
    selected.value?.source_status === 'cleared' ||
    ['cancelled', 'paused'].includes(selected.value?.status ?? '')
  )
    return
  if (event.event === 'delta' && 'text' in event.data && typeof event.data.text === 'string')
    streamText.value += event.data.text
  if (event.event === 'status' && 'message' in event.data && typeof event.data.message === 'string')
    streamMessage.value = event.data.message
}
async function advance(run: AgentRun): Promise<void> {
  streaming.value = true
  streamInterrupted.value = false
  streamMessage.value = `正在执行：${agentLabels[run.next_node] ?? '当前步骤'}`
  if (streamText.value) streamText.value += '\n'
  try {
    const result = await agentApi.advanceStream(run, receiveStream)
    accept(result)
    const status = selected.value?.status ?? result.status
    streamMessage.value = runStatusMessage(status)
  } catch (cause) {
    streamInterrupted.value = true
    streamMessage.value = errorMessage(cause)
    throw cause
  } finally {
    streaming.value = false
  }
}
async function drive(): Promise<void> {
  driving.value = true
  try {
    // One server-bounded node per request. Refreshing or revisiting never starts work.
    for (let i = 0; i < 100 && alive && driving.value && selected.value?.status === 'ready'; i++) {
      await advance(selected.value)
    }
  } finally {
    driving.value = false
  }
}
async function start(): Promise<void> {
  if (busy.value || !shopId.value || rulesPending.value) return
  starting.value = true
  busy.value = true
  error.value = ''
  if (!advanced.value && selected.value)
    previousTurns.value = [...previousTurns.value, selected.value].slice(-12)
  confirmSave.value = false
  selected.value = null
  resetStream()
  try {
    selected.value = await agentApi.start(shopId.value, {
      ...form,
      response_mode: advanced.value ? 'workflow' : 'chat',
      scope:
        form.template === 'margin_review'
          ? { ...form.scope, start_at: marginStart.value }
          : form.scope,
      expected_product_source_row_id:
        form.template === 'listing_model' ? selectedProduct.value?.source.row_id : undefined,
      request_id: crypto.randomUUID(),
    })
    await rememberRun()
    await drive()
    await refresh()
  } catch (cause) {
    error.value = errorMessage(cause)
    driving.value = false
  } finally {
    starting.value = false
    busy.value = false
  }
}
async function act(
  action: AgentAction,
  budget?: AgentBudget,
  authorizationId?: number,
): Promise<void> {
  if (!selected.value || controlling.value) return
  if (busy.value && !['pause', 'cancel'].includes(action)) return
  driving.value = false
  controlling.value = true
  error.value = ''
  const current = selected.value
  try {
    const latest = await agentApi.get(current.shop_id, current.id)
    if (action === 'advance') await advance(latest)
    else accept(await agentApi.act(latest, action, budget, authorizationId))
    if (['approve', 'resume', 'advance', 'use_authorization'].includes(action)) {
      busy.value = true
      await drive()
    }
  } catch (cause) {
    error.value = errorMessage(cause)
    driving.value = false
  } finally {
    controlling.value = false
    if (!driving.value) busy.value = false
    await refresh()
  }
}
async function requestSave(): Promise<void> {
  if (!selected.value || busy.value || controlling.value) return
  confirmSave.value = true
  await scrollToAnswer()
}
async function confirmWrite(): Promise<void> {
  if (!selected.value || busy.value || controlling.value) return
  if (selected.value.status === 'succeeded') await act('request_save')
  if (selected.value?.status !== 'waiting_approval' || error.value) return
  confirmSave.value = false
  await act('approve')
}
async function startAuthorized(grant: InternalAuthorization): Promise<void> {
  if (busy.value || controlling.value || grant.shop_id !== shopId.value) return
  starting.value = true
  busy.value = true
  error.value = ''
  selected.value = null
  resetStream()
  try {
    selected.value = await agentApi.start(grant.shop_id, {
      ...form,
      request_id: crypto.randomUUID(),
      template: 'daily',
      response_mode: 'workflow',
      previous_question: '',
      scope: grant.scope,
      authorization_id: grant.id,
      allow_model: false,
      goal: '',
      product_id: null,
      message_id: null,
    })
    await rememberRun()
    await drive()
  } catch (cause) {
    error.value = errorMessage(cause)
    driving.value = false
  } finally {
    starting.value = false
    busy.value = false
    await refresh()
  }
}
async function restoreRoute(): Promise<void> {
  restoring.value = true
  try {
    const demoScope = await loadDemoScope(shops.value, session.value?.username, route.query)
    if (!alive) return
    if (Object.keys(demoScope).length)
      await recordLink.write({ ...route.query, ...demoScope }, true)
    shopId.value = linkedShop(shops.value, route.query.shop)
    const id = linkedId(route.query.execution ?? route.query.run)
    const grantId = linkedId(route.query.authorization)
    await loadShop()
    if (!alive) return
    applyLinkedScope(form.scope, route.query)
    if (
      route.query.mode !== undefined &&
      (typeof route.query.mode !== 'string' ||
        ![
          'daily',
          'analysis',
          'listing',
          'support',
          'natural',
          'question',
          'listing_model',
          'support_model',
          'daily_model',
          'margin_review',
        ].includes(route.query.mode))
    )
      throw new Error('链接中的执行流程无效，请从当前业务页面重新打开。')
    if (
      typeof route.query.mode === 'string' &&
      [
        'daily',
        'analysis',
        'listing',
        'support',
        'natural',
        'question',
        'listing_model',
        'support_model',
        'daily_model',
        'margin_review',
      ].includes(route.query.mode)
    )
      form.template = route.query.mode as AgentInput['template']
    if (['support', 'support_model'].includes(String(route.query.mode))) {
      const messageId = linkedId(route.query.message)
      if (messageId) {
        const workspace = await supportApi.workspace(shopId.value, messageId)
        if (!alive) return
        if (!messages.value.some((m) => m.id === messageId)) messages.value.push(workspace.message)
        form.scope.data_identity =
          workspace.message.source.data_identity === 'synthetic' ? 'synthetic' : 'user_import'
        if (['generic', 'amazon', 'shopify', 'other'].includes(workspace.message.channel))
          form.scope.channel = workspace.message.channel as typeof form.scope.channel
        form.message_id = messageId
      }
    }
    if (['listing', 'listing_model', 'margin_review'].includes(String(route.query.mode))) {
      const productId = linkedId(route.query.product)
      if (productId) {
        const workspace = await listingsApi.workspace(shopId.value, productId)
        if (!alive) return
        if (!products.value.some((p) => p.product_id === productId))
          products.value.push(workspace.product)
        form.scope.data_identity =
          workspace.product.source.data_identity === 'synthetic' ? 'synthetic' : 'user_import'
        form.product_id = workspace.product.product_id
      }
    }
    if (id || grantId) selected.value = null
    advanced.value = !simpleTemplates.includes(form.template) || !!grantId
    if (id) {
      await inspect(id, false)
      if (alive) await revealRecord('linked-agent')
    }
    if (grantId) {
      const grant = await authorizationsApi.get(shopId.value, grantId)
      if (!alive) return
      focusShop.value = shopId.value
      focusGrant.value = grant.id
      await inspect(grant.origin_execution_id, false)
    }
  } catch (cause) {
    selected.value = null
    shopId.value = 0
    error.value = errorMessage(cause)
  } finally {
    restoring.value = false
  }
}
watch(
  () => route.fullPath,
  (path) => {
    if (route.path === '/agent' && !recordLink.isOwn(path)) void restoreRoute()
  },
)
onMounted(async () => {
  window.addEventListener('focus', refresh)
  try {
    shops.value = await identityApi.shops()
    if (alive) await restoreRoute()
  } catch (cause) {
    error.value = errorMessage(cause)
  }
})
watch(
  () => [JSON.stringify(form.scope), form.template, form.product_id, form.message_id],
  () => {
    if (restoring.value || busy.value || controlling.value || selected.value || !shopId.value)
      return
    try {
      applyLinkedScope({}, scopeQuery(form.scope))
    } catch {
      return
    }
    void recordLink.write(
      {
        shop: shopId.value,
        ...scopeQuery(form.scope),
        mode: form.template,
        product: form.product_id ?? undefined,
        message: form.message_id ?? undefined,
        ...returnTaskQuery(route.query, shopId.value),
      },
      true,
    )
  },
)
onUnmounted(() => {
  alive = false
  driving.value = false
  window.removeEventListener('focus', refresh)
})
</script>

<template>
  <div class="solo-page page-agent" :class="{ 'chat-mode': !advanced }">
    <div v-if="advanced" class="page-heading">
      <div>
        <h1>有什么经营问题，直接问。</h1>
        <p>说出你的问题，AI 结合店铺资料直接给出回答。</p>
      </div>
      <button
        class="button secondary small"
        :disabled="restoring || busy || controlling"
        @click="toggleMode"
      >
        {{ advanced ? '返回简洁问答' : '高级执行台' }}
      </button>
    </div>
    <div v-if="!advanced" class="chat-heading">
      <h1>AI 经营助手</h1>
      <button
        class="button secondary small"
        :disabled="restoring || busy || controlling"
        @click="toggleHistory"
      >
        {{ showHistory ? '收起历史' : '历史对话' }}
      </button>
      <button
        class="button secondary small"
        :disabled="restoring || busy || controlling"
        @click="toggleMode"
      >
        高级执行台
      </button>
    </div>
    <FeedbackBanner :message="error" />
    <p v-if="!shops.length">先在经营资料中添加店铺，再导入商品、订单或消息。</p>
    <template v-else>
      <label class="agent-shop"
        >当前店铺<select
          v-model.number="shopId"
          :disabled="restoring || busy || controlling"
          @change="changeShop"
        >
          <option v-for="shop in shops" :key="shop.id" :value="shop.id">{{ shop.name }}</option>
        </select></label
      >
      <div
        v-if="!advanced"
        ref="chatThread"
        class="chat-thread"
        role="region"
        tabindex="0"
        aria-label="对话记录"
      >
        <AgentAnswer v-for="turn in previousTurns" :key="turn.id" :run="turn" :busy="false" />
        <AgentAnswer
          v-if="selected"
          :run="selected"
          :busy="busy || controlling"
          :can-save="true"
          :confirm-save="confirmSave"
          @save="requestSave"
          @approve="confirmWrite"
          @dismiss="confirmSave = false"
        />
        <div v-else-if="!previousTurns.length" class="chat-welcome">
          <h2>今天想了解什么？</h2>
          <p>问销售、看经营情况，或让我准备商品文案和客户回复。</p>
        </div>
        <p v-if="starting && !selected" role="status">正在查看资料并整理结论…</p>
      </div>
      <section class="section-block" :class="{ 'chat-composer': !advanced }">
        <div v-if="advanced" class="section-title">
          <h2>{{ advanced ? '启动任务' : 'AI 经营助手' }}</h2>
          <span>{{
            model?.status === 'configured'
              ? `模型已配置：${model.model}`
              : '模型待配置 · 固定流程可用'
          }}</span>
        </div>
        <p v-if="selected && advanced">
          已定位任务 #{{
            selected.id
          }}。下方表单用于新任务；历史授权不自动沿用，请重新核对范围、预算和数据许可。原任务可在执行记录中继续处理。
        </p>
        <form v-if="!advanced" class="question-form" @submit.prevent="ask">
          <fieldset :disabled="restoring || busy || controlling" class="question-fields">
            <div class="button-row">
              <button
                v-for="item in suggestions"
                :key="item.template"
                type="button"
                class="button secondary small"
                :aria-pressed="form.template === item.template"
                @click="useSuggestion(item)"
              >
                {{ item.label }}
              </button>
            </div>
            <div v-if="form.template === 'listing_model'" class="object-picker">
              <p class="selection-help">
                {{ form.scope.data_identity === 'synthetic' ? '样例资料' : '经营资料' }} ·
                {{ productOptions.length }} 个商品
              </p>
              <label
                >选择商品<select
                  v-model="form.product_id"
                  required
                  :disabled="!productOptions.length"
                  aria-describedby="product-selection-help"
                >
                  <option :value="null" disabled>
                    {{ productOptions.length ? '请选择商品' : '当前资料范围没有商品' }}
                  </option>
                  <option
                    v-for="product in productOptions"
                    :key="product.product_id"
                    :value="product.product_id"
                  >
                    {{ product.sku }} · {{ product.name }}
                  </option>
                </select></label
              >
              <p id="product-selection-help" v-if="!productOptions.length" class="selection-help">
                当前资料范围没有商品。
                <template v-if="otherProducts.length"
                  >店铺另有 {{ otherProducts.length }} 个{{
                    form.scope.data_identity === 'synthetic' ? '经营' : '样例'
                  }}商品，可切换后选择。</template
                >
                <template v-else>请先导入商品，或检查当前店铺。</template>
                <button
                  v-if="otherProducts.length"
                  type="button"
                  class="button secondary small"
                  @click="useAvailableProducts"
                >
                  使用现有 {{ otherProducts.length }} 个{{
                    form.scope.data_identity === 'synthetic' ? '经营' : '样例'
                  }}商品
                </button>
                <button type="button" class="button secondary small" @click="openDataSettings">
                  调整资料范围
                </button>
              </p>
              <p
                id="product-selection-help"
                v-else-if="selectedProduct && !selectedProduct.facts.trim()"
                class="selection-help"
              >
                该商品缺少事实资料，请先补充商品参数再生成文案。
              </p>
              <details v-if="selectedProduct" class="product-preview">
                <summary>查看商品资料</summary>
                <p>{{ selectedProduct.name }}</p>
                <p class="preserve-text">{{ selectedProduct.facts }}</p>
              </details>
            </div>
            <div v-if="form.template === 'support_model'" class="object-picker">
              <label
                >选择客户消息<select
                  v-model="form.message_id"
                  required
                  :disabled="!messageOptions.length"
                  aria-describedby="message-selection-help"
                >
                  <option :value="null" disabled>
                    {{ messageOptions.length ? '请选择消息' : '当前资料范围没有客户消息' }}
                  </option>
                  <option v-for="message in messageOptions" :key="message.id" :value="message.id">
                    {{ message.body.slice(0, 80) }}
                  </option>
                </select></label
              >
              <p id="message-selection-help" v-if="!messageOptions.length" class="selection-help">
                当前资料范围没有客户消息。请核对数据身份和渠道，或先导入消息。
                <button type="button" class="button secondary small" @click="openDataSettings">
                  调整资料范围
                </button>
              </p>
            </div>
            <label class="question-label"
              >你的问题<textarea
                @keydown="submitShortcut"
                v-model="form.goal"
                required
                maxlength="500"
                rows="3"
                placeholder="例如：最近 7 天销售怎么样？哪些商品毛利偏低？"
              />
            </label>
            <div class="composer-actions">
              <details
                ref="composerOptions"
                class="composer-options"
                @keydown.esc.stop="closeOptions"
                @toggle="showHistory = composerOptions?.open ? false : showHistory"
              >
                <summary>语言与资料设置</summary>
                <div class="composer-options-panel">
                  <button type="button" class="button secondary small" @click="closeOptions">
                    收起设置
                  </button>
                  <details class="question-settings" open>
                    <summary>对话设置</summary>
                    <label
                      >回答语言<select v-model="form.response_language">
                        <option value="auto">跟随提问中的语言要求</option>
                        <option
                          v-for="language in [
                            '简体中文',
                            '繁體中文',
                            'English',
                            '日本語',
                            '한국어',
                            'Español',
                            'Français',
                            'Deutsch',
                            'العربية',
                          ]"
                          :key="language"
                          :value="language"
                        >
                          {{ language }}
                        </option>
                      </select></label
                    >
                    <p class="question-scope">
                      {{ form.scope.data_identity === 'synthetic' ? '样例资料' : '经营资料' }} ·
                      {{ form.scope.channel }} · {{ form.scope.currency }} ·
                      {{ supportTime(form.scope.start_at, form.scope.timezone) }} 至
                      {{ supportTime(form.scope.end_at, form.scope.timezone) }}（结束不含）
                    </p>
                    <details class="question-settings">
                      <summary>调整数据范围与预算</summary>
                      <div class="analysis-fields">
                        <label
                          >数据身份<select v-model="form.scope.data_identity" data-data-identity>
                            <option value="user_import">经营资料</option>
                            <option value="synthetic">样例资料</option>
                          </select></label
                        >
                        <label
                          >检查渠道<select v-model="form.scope.channel">
                            <option value="generic">通用</option>
                            <option value="amazon">Amazon</option>
                            <option value="shopify">Shopify</option>
                            <option value="other">其他来源</option>
                          </select></label
                        >
                        <label
                          >币种<input v-model="form.scope.currency" required maxlength="3"
                        /></label>
                        <BusinessDateRange
                          v-model:start="form.scope.start_at"
                          v-model:end="form.scope.end_at"
                          :timezone="form.scope.timezone"
                          start-label="开始时间"
                          end-label="结束时间（不含）"
                        />
                        <label
                          >模型预算（USD）<input
                            v-model="form.budget.max_cost_usd"
                            type="number"
                            min="0.000001"
                            max="10"
                            step="0.000001"
                            required
                        /></label>
                      </div>
                      <AppliedRules
                        :key="rulesKey"
                        :shop="shopId"
                        :scope="form.scope"
                        @loaded="rulesLoaded"
                        @pending="rulesPending = $event"
                      />
                    </details>
                  </details>
                  <details v-if="form.template === 'daily_model'">
                    <summary>查看检查范围</summary>
                    <OperationModelContext
                      v-if="form.template === 'daily_model' && !rulesPending"
                      :shop="shopId"
                      :scope="form.scope"
                      :disabled="restoring || busy || controlling"
                      @change="form.expected_operation_hash = $event"
                    />
                  </details>
                  <details v-if="form.template === 'support_model'">
                    <summary>选择回复依据</summary>
                    <SupportModelContext
                      v-if="form.template === 'support_model'"
                      :shop="shopId"
                      :message="form.message_id"
                      :identity="form.scope.data_identity"
                      :channel="form.scope.channel"
                      :disabled="restoring || busy || controlling"
                      @change="form.support_context = $event"
                    />
                  </details>
                  <details v-if="form.template === 'listing_model' && selectedProduct">
                    <summary>将使用的商品资料</summary>
                    <p>{{ selectedProduct.name }}</p>
                    <p class="preserve-text">{{ selectedProduct.facts }}</p>
                  </details>
                  <p v-if="model && model.status !== 'configured'" role="status">
                    模型尚未配置，请联系管理员配置后提问。
                  </p>
                </div>
              </details>
              <button
                class="button primary"
                :disabled="
                  busy ||
                  controlling ||
                  !shopId ||
                  rulesPending ||
                  !form.goal.trim() ||
                  model?.status !== 'configured' ||
                  (form.template === 'listing_model' && !selectedProduct?.facts.trim()) ||
                  (form.template === 'support_model' && !form.support_context) ||
                  (form.template === 'daily_model' && !form.expected_operation_hash)
                "
              >
                {{ starting || driving ? '正在回答…' : '发送问题' }}
              </button>
            </div>
            <p class="question-disclosure">
              发送问题将使用{{
                form.template === 'listing_model'
                  ? '所选商品名称、参数'
                  : form.template === 'support_model'
                    ? '已核对的消息与政策原文'
                    : '当前范围的匿名汇总数据'
              }}，由 {{ model?.model || '配置的模型' }} 回答 · 预算上限
              {{ form.budget.max_cost_usd }} USD。
            </p>
          </fieldset>
        </form>
        <form v-else @submit.prevent="start">
          <AppliedRules
            :key="rulesKey"
            :shop="shopId"
            :scope="form.scope"
            @loaded="rulesLoaded"
            @pending="rulesPending = $event"
          />
          <fieldset class="analysis-fields" :disabled="restoring || busy || controlling">
            <label
              >执行流程<select v-model="form.template">
                <option value="daily">今日运营：检查 → 异常候选 → 核验</option>
                <option value="daily_model">AI 今日运营：检查 → 概览解释 → 审批候选</option>
                <option value="analysis">销售与已知毛利（所选身份与渠道）</option>
                <option value="margin_review">最近7天低毛利：核对依据 → 分别审批 → 内部结果</option>
                <option value="question">AI 经营问数：理解 → 计算 → 解释 → 核对待办</option>
                <option value="listing">商品事实 → Listing 模板草稿</option>
                <option value="listing_model">AI Listing：事实 → 模型候选 → 审批保存</option>
                <option value="support">消息 → 人工接管草稿</option>
                <option value="support_model">AI 客服：诉求与依据 → 候选 → 审批保存</option>
                <option value="natural">自然语言目标（需要模型）</option>
              </select></label
            >
            <label
              >数据身份<select v-model="form.scope.data_identity">
                <option value="user_import">经营资料</option>
                <option value="synthetic">样例资料</option>
              </select></label
            >
            <label
              >检查渠道<select v-model="form.scope.channel">
                <option value="generic">通用</option>
                <option value="amazon">Amazon</option>
                <option value="shopify">Shopify</option>
                <option value="other">其他来源</option>
              </select></label
            >
            <label>币种<input v-model="form.scope.currency" required maxlength="3" /></label>
            <template v-if="form.template === 'margin_review'">
              <label
                >复核成本口径<select v-model="form.margin_cost_mode">
                  <option value="seller_history">卖家确认的订单行历史成本</option>
                  <option value="current_estimate">当前商品成本回推估算</option>
                </select></label
              >
              <p class="full-width">
                截至下方结束时间的最近7天：{{
                  marginStart ? supportTime(marginStart, form.scope.timezone) : '请填写有效结束时间'
                }}
                至
                {{
                  marginStart ? supportTime(form.scope.end_at, form.scope.timezone) : '待填写'
                }}（结束不含，{{
                  form.scope.timezone
                }}）。按数据完整性选择核对分析；可选一个商品核对独立内容遗漏。各内部写入分别审批，使用本地计算。
              </p>
            </template>
            <template
              v-if="
                [
                  'listing',
                  'listing_model',
                  'support',
                  'support_model',
                  'natural',
                  'margin_review',
                ].includes(form.template)
              "
            >
              <label
                >查找商品或消息<input
                  v-model="query"
                  placeholder="关键词，最多显示 50 项"
                  @change="readOptions"
              /></label>
              <label v-if="!['support', 'support_model'].includes(form.template)"
                >目标商品<select v-model="form.product_id">
                  <option :value="null">未选择</option>
                  <option
                    v-for="product in productOptions"
                    :key="product.product_id"
                    :value="product.product_id"
                  >
                    {{ product.sku }} · {{ product.name }}
                  </option>
                </select></label
              >
              <label v-if="!['listing', 'listing_model', 'margin_review'].includes(form.template)"
                >目标消息<select v-model="form.message_id">
                  <option :value="null">未选择</option>
                  <option v-for="message in messageOptions" :key="message.id" :value="message.id">
                    {{ message.message_id }} · {{ message.body.slice(0, 60) }}
                  </option>
                </select></label
              >
            </template>
            <template
              v-if="
                ['natural', 'question', 'listing_model', 'support_model', 'daily_model'].includes(
                  form.template,
                )
              "
            >
              <label class="full-width"
                >运营目标<textarea
                  v-model="form.goal"
                  maxlength="500"
                  required
                  placeholder="例如：检查已导入订单，找出需要核对的事项"
                />
              </label>
              <p v-if="form.template === 'question'" class="full-width">
                支持销售汇总、原购买数量前五、销量高但已知毛利低。使用下方时间、币种及阈值，
                按所选身份、订单渠道和时间窗统计；商品成本使用本店同身份的当前主档。
                问题要求的范围若不同，请先修改表单。
              </p>
              <label class="full-width"
                ><span
                  ><input v-model="form.allow_model" type="checkbox" />
                  同意将本次目标文本发送至配置的
                  {{ agentLabels[model?.provider ?? ''] ?? '供应商' }}
                  模型，本次预算上限 {{ form.budget.max_cost_usd }} USD</span
                ></label
              >
              <label v-if="form.template === 'question'" class="full-width">
                <span
                  ><input v-model="form.allow_analysis_data" type="checkbox" />
                  同意发送本次范围、匿名聚合指标与费用缺口，用于组织证据解释</span
                >
              </label>
              <p v-if="form.template === 'question'" class="full-width">
                正常流程需要两次模型请求。事实包包含统计时间、币种、阈值、汇总及最多 20 项匿名 SKU
                指标； 原始订单号、SKU
                名称、文件名和买家消息留在本地。问题正文会原样发送，请核对其中内容。
                返回内容只可选择已有事实和核对建议，内部保存仍须审批。
              </p>
              <template v-if="form.template === 'daily_model'">
                <OperationModelContext
                  v-if="!rulesPending"
                  class="full-width"
                  :shop="shopId"
                  :scope="form.scope"
                  :disabled="restoring || busy || controlling"
                  @change="form.expected_operation_hash = $event"
                />
                <label class="full-width"
                  ><span>
                    <input
                      v-model="form.allow_operation_data"
                      type="checkbox"
                      :disabled="rulesPending || !form.expected_operation_hash"
                    />
                    我已核对运营范围，同意发送上述聚合检查数据用于概览解释
                  </span></label
                >
              </template>
              <template v-if="form.template === 'support_model'">
                <SupportModelContext
                  class="full-width"
                  :shop="shopId"
                  :message="form.message_id"
                  :identity="form.scope.data_identity"
                  :channel="form.scope.channel"
                  :disabled="restoring || busy || controlling"
                  @change="form.support_context = $event"
                />
                <label class="full-width">
                  <span
                    ><input
                      v-model="form.allow_support_data"
                      type="checkbox"
                      :disabled="!form.support_context"
                    />
                    我已核对上述消息原文和选中政策，同意将这些客服数据发送至配置的模型
                  </span>
                </label>
              </template>
              <div
                v-if="form.template === 'listing_model'"
                class="full-width data-note"
                aria-label="将发送的商品事实"
              >
                <h3>核对本次商品事实</h3>
                <template v-if="selectedProduct">
                  <p>商品名：{{ selectedProduct.name }}</p>
                  <p class="preserve-text">
                    {{ selectedProduct.facts || '缺少参数，请先补充商品来源。' }}
                  </p>
                  <p>
                    本地来源：批次 {{ selectedProduct.source.batch_id }} · 行
                    {{ selectedProduct.source.row_number }}
                  </p>
                </template>
                <p v-else>请先选择目标商品。</p>
                <p>
                  一次模型请求会发送上方商品名、完整参数与目标文本。SKU、成本、文件名和订单留在本地。模型选择标题参数并调整描述顺序，描述保留全部参数。品牌偏好仅供人工参考。
                </p>
                <label
                  ><input
                    v-model="form.allow_listing_data"
                    type="checkbox"
                    :disabled="!selectedProduct?.facts.trim()"
                  />我已核对上述商品事实，同意发送这些原文用于 Listing 候选</label
                >
              </div>
            </template>
          </fieldset>
          <details>
            <summary>数据窗口、规则与任务预算</summary>
            <fieldset class="analysis-fields" :disabled="restoring || busy || controlling">
              <label>业务时区（IANA）<input v-model="form.scope.timezone" required /></label>
              <BusinessDateRange
                v-model:start="form.scope.start_at"
                v-model:end="form.scope.end_at"
                :timezone="form.scope.timezone"
                start-label="订单起始时间（含时区）"
                end-label="订单结束时间（不包含）"
                :fixed-days="form.template === 'margin_review' ? 7 : undefined"
              />
              <label
                >库存时效（小时）<input
                  v-model.number="form.scope.max_age_hours"
                  :disabled="activeRule || rulesPending"
                  type="number"
                  min="1"
                  max="720"
                  required
              /></label>
              <label
                >低毛利率上限（%）<input
                  v-model="form.scope.max_margin_percent"
                  :disabled="activeRule || rulesPending"
                  type="number"
                  min="-1000"
                  max="100"
                  step="0.01"
                  required
              /></label>
              <label
                >执行步数上限<input
                  v-model.number="form.budget.max_steps"
                  type="number"
                  min="1"
                  max="100"
                  required /></label
              ><label
                >累计执行秒数上限<input
                  v-model.number="form.budget.max_seconds"
                  type="number"
                  min="1"
                  max="3600"
                  required
              /></label>
              <label
                >模型预算（USD）<input
                  v-model="form.budget.max_cost_usd"
                  type="number"
                  min="0"
                  max="10"
                  step="0.000001"
                  required
              /></label>
            </fieldset>
          </details>
          <details class="agent-model-notes">
            <summary>任务说明与模型计费</summary>
            <p>
              固定流程使用本地规则或事实模板，模型费用为 0。自然语言目标用于路由；AI
              经营问数根据确定性结果组织证据解释，AI Listing 根据商品原文组织候选，AI
              客服按消息和政策组织回复候选与接管摘要。
            </p>
            <p v-if="model?.status === 'configured'">
              {{ agentLabels[model.provider] ?? model.provider }} · {{ model.model }} · 每百万输入 /
              输出 tokens 的配置费率： {{ model.input_usd_per_million ?? '未知' }} /
              {{ model.output_usd_per_million ?? '未知' }} USD。
              每次调用前预留费用；实际用量按此费率记账，供应商账单须另核对。
              {{ model.cost_note }}
            </p>
          </details>
          <button
            class="button primary"
            :disabled="
              busy ||
              !shopId ||
              controlling ||
              rulesPending ||
              (usesModel && !form.allow_model) ||
              (form.template === 'question' && !form.allow_analysis_data) ||
              (form.template === 'daily_model' &&
                (!form.expected_operation_hash || !form.allow_operation_data)) ||
              (form.template === 'support_model' &&
                (!form.support_context || !form.allow_model || !form.allow_support_data)) ||
              (form.template === 'listing_model' &&
                (!selectedProduct || !form.allow_model || !form.allow_listing_data))
            "
          >
            {{ busy ? '正在执行…' : '启动并运行' }}
          </button>
        </form>
        <AgentStreamPreview
          v-if="streamMessage && advanced"
          :text="streamText"
          :message="streamMessage"
          :active="streaming && !['cancelled', 'paused'].includes(selected?.status ?? '')"
          :interrupted="streamInterrupted"
        />
      </section>
      <details
        v-if="advanced || showHistory"
        class="section-block"
        :class="{ 'chat-history': !advanced }"
        open
      >
        <summary>历史问答与执行记录（{{ runs.length }}）</summary>
        <div class="section-title">
          <h2>执行记录</h2>
          <button
            v-if="!advanced"
            class="button secondary"
            :disabled="restoring || busy || controlling"
            @click="newConversation"
          >
            新对话
          </button>
          <button class="button secondary" :disabled="controlling" @click="refresh">
            刷新任务
          </button>
        </div>
        <div class="button-row">
          <button
            v-for="run in runs"
            :key="run.id"
            class="button secondary small"
            :disabled="restoring || busy || controlling"
            @click="inspect(run.id)"
          >
            #{{ run.id }} · {{ agentLabels[run.template] }} · {{ agentLabels[run.status] }}
          </button>
        </div>
        <p v-if="!runs.length">尚未运行任务。启动后，实际结果会保存在这里。</p>
      </details>
      <details v-if="selected && advanced" class="section-block" open>
        <summary>查看依据、保存结果与执行详情</summary>
        <AgentRunReview
          :return-context="Number(route.query.shop) === shopId ? returnTaskQuery(route.query) : {}"
          id="linked-agent"
          v-if="selected"
          :run="selected"
          :busy="busy || controlling"
          @action="act"
        />
      </details>
      <InternalAuthorizations
        v-if="advanced"
        :focus-id="focusShop === shopId ? focusGrant : undefined"
        :shop="shopId"
        :run="selected"
        :busy="busy || controlling"
        @use="act('use_authorization', undefined, $event)"
        @start="startAuthorized"
        @inspect="inspect"
      />
      <details v-if="advanced" class="section-block">
        <summary>内置技能与权限（{{ skills.length }} 项）</summary>
        <article v-for="skill in skills" :key="skill.name" class="analysis-line">
          <h3>{{ skill.purpose }}</h3>
          <p>
            {{ skill.name }} v{{ skill.version }} · {{ skill.risk }} ·
            {{ skill.side_effects ? '内部写入需审批' : '只读' }}
          </p>
          <p>{{ skill.read_scope }}；{{ skill.write_scope }}</p>
          <p>{{ skill.failure_policy }}</p>
          <p>{{ skill.confirmation }}</p>
          <details>
            <summary>完整输入、输出与权限声明</summary>
            <pre class="agent-contract">{{ JSON.stringify(skill, null, 2) }}</pre>
          </details>
        </article>
      </details>
    </template>
  </div>
</template>
<style scoped>
.chat-mode {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  gap: 12px;
  position: relative;
}
.chat-mode > * {
  flex-shrink: 0;
}
.chat-mode .agent-shop {
  display: flex;
  align-items: center;
  max-width: 100%;
  font-size: 12px;
  padding: 0;
  background: transparent;
  border: 0;
}
.chat-mode .agent-shop select {
  width: auto;
  min-width: 0;
  max-width: 80%;
  padding: 6px 10px;
}
.chat-mode .chat-thread {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 12px 16px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
}
.chat-mode .chat-thread > * {
  flex-shrink: 0;
}
.chat-mode .chat-composer {
  padding: 12px 16px;
  min-height: 0;
  flex-shrink: 1;
  max-height: calc(100% - 100px);
}
.chat-mode .question-form {
  max-height: 100%;
  overflow-y: auto;
}
.chat-mode .question-form :is(button, select, textarea, input, summary):focus-visible {
  outline-offset: -3px;
}
.chat-mode .question-fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.chat-mode .question-label {
  gap: 4px;
  font-size: 12px;
}
.chat-mode .question-label textarea {
  min-height: 64px;
  height: 64px;
  max-height: 120px;
  resize: none;
  padding: 8px 12px;
}
.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.composer-actions > .button {
  min-width: 96px;
  flex-shrink: 0;
}
.object-picker select {
  width: 100%;
  min-width: 0;
  text-overflow: ellipsis;
}
.object-picker label {
  gap: 4px;
  font-size: 12px;
}
.selection-help {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--muted);
}
.composer-options-panel > .button {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--surface, #fff);
}
.chat-mode .question-disclosure {
  font-size: 11px;
}
.chat-mode .question-fields > .button-row {
  flex-wrap: nowrap;
  overflow-x: auto;
  gap: 6px;
}
.chat-mode .question-fields > .button-row > button {
  flex-shrink: 0;
}
.composer-options {
  align-self: center;
}
.chat-mode .composer-options > summary {
  margin: 0;
}
.composer-options-panel {
  position: absolute;
  z-index: 10;
  top: 56px;
  bottom: 0;
  right: 0;
  width: min(520px, 100%);
  overflow-y: auto;
  background: var(--surface, #fff);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 8px 28px #0002;
}
.chat-mode .chat-history {
  position: absolute;
  z-index: 12;
  top: 60px;
  right: 0;
  width: min(520px, 100%);
  max-height: 65%;
  overflow-y: auto;
  box-shadow: 0 8px 28px #0002;
}
@media (max-width: 760px) {
  .chat-mode {
    gap: 6px;
  }
  .chat-mode .chat-heading {
    gap: 6px;
  }
  .chat-mode .chat-heading h1 {
    font-size: 17px;
    margin-right: auto;
  }
  .chat-mode .chat-heading .button {
    padding: 6px 8px;
    font-size: 11px;
  }
  .chat-mode .chat-composer {
    padding: 8px 10px;
  }
  .chat-mode .question-fields > .button-row {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    overflow: visible;
  }
  .chat-mode .question-fields > .button-row > button {
    min-width: 0;
    min-height: 36px;
    padding: 6px 8px;
  }
  .chat-mode .chat-thread {
    padding: 8px 4px;
  }
}
.chat-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.chat-heading h1 {
  font-size: 24px;
}
.chat-thread {
  max-width: 860px;
  width: 100%;
  margin: 24px auto;
  display: grid;
  gap: 20px;
}
.chat-welcome {
  padding: 48px 0 36px;
  text-align: center;
}
.chat-welcome p {
  color: var(--muted);
}
.chat-composer {
  max-width: 860px;
  width: 100%;
  margin: 0 auto;
}
.chat-thread > button {
  justify-self: start;
}

.question-fields {
  border: 0;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 20px;
  min-width: 0;
}
.question-fields label {
  display: grid;
  gap: 10px;
  min-width: 0;
}
.question-label textarea {
  min-height: 120px;
  resize: vertical;
  font-size: 16px;
  line-height: 1.7;
}
.question-fields .button[aria-pressed='true'] {
  border-color: var(--green);
  background: var(--green-soft, #edf4ee);
}
.question-scope,
.question-disclosure {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
}
.question-fields > .button {
  justify-self: end;
  min-width: 140px;
}
.question-settings > .analysis-fields {
  margin-top: 20px;
}
.question-form {
  max-width: 900px;
  margin: 0 auto;
}
.question-fields select {
  max-width: 100%;
}

.analysis-fields > * {
  min-width: 0;
}
.analysis-fields select {
  max-width: 100%;
  min-width: 0;
}
.agent-shop {
  display: grid;
  gap: 8px;
  max-width: 460px;
}
.agent-contract {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 400px;
  overflow-y: auto;
  font-size: 12px;
}
input[type='checkbox'] {
  width: 18px;
  height: 18px;
  vertical-align: middle;
  margin-right: 8px;
}
</style>
