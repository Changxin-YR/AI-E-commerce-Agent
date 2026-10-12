// route: /expenses
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Taro, { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import { ApiError } from '../../services/client'
import { queryString, requestId } from '../../services/task-policy'
import { supportTime } from '../../services/support-types'
import { openLink } from '../../services/navigation'
import SourceList from '../../components/SourceList.vue'
import {
  channels,
  checkedExpenseContent,
  checkedExpenseScope,
  checkedFeeRuleContent,
  checkedTimezone,
  controls,
  currencies,
  decimalText,
  emptyExpense,
  expenseActions,
  expenseCategories,
  expenseCategoryKeys,
  expenseStatuses,
  linkedOrder,
  localIso,
  mappingStatuses,
  revisionActions,
  ruleActions,
  ruleStatuses,
  type ControlAction,
  type DataIdentity,
  type ExpenseCategory,
  type ExpenseContent,
  type ExpenseControlBody,
  type ExpenseOrder,
  type ExpenseOrders,
  type ExpensePage,
  type ExpenseSaved,
  type ExpenseSummary,
  type ExpenseWriteBody,
  type FeeRuleContent,
  type FeeRuleDraftBody,
  type FeeRulePage,
  type FeeRulePreview,
  type FeeRuleSaved,
  type FeeRuleWriteBody,
  type SourceChannel,
} from '../../services/expense-policy'

const scope = reactive({
  data_identity: 'user_import' as DataIdentity,
  channel: 'generic' as SourceChannel,
})
const rows = ref<ExpenseSaved[]>([])
const cursor = ref<number | null>(null)
const selected = ref<ExpenseSaved>()
const editorOpen = ref(false)
const editingId = ref<number | null>(null)
const draft = reactive<ExpenseContent>(emptyExpense())
const orderQuery = ref('')
const orders = ref<ExpenseOrder[]>([])
const orderRevision = ref<number | null>(null)
const confirmSave = ref(false)
const pendingWrite = ref<{ id: number | null; body: ExpenseWriteBody } | null>(
  null,
)
const pendingControl = ref<{
  id: number
  action: ControlAction
  body: ExpenseControlBody
} | null>(null)
const period = reactive({ start_at: '', end_at: '', timezone: 'UTC' })
const summary = ref<ExpenseSummary>()
const rules = ref<FeeRuleSaved[]>([])
const rulesCursor = ref<number | null>(null)
const rule = ref<FeeRuleSaved>()
const ruleEditing = ref(false)
const ruleDraft = reactive<{
  rule_id: number | null
  version: number
  content: FeeRuleContent
}>({
  rule_id: null,
  version: 0,
  content: { fee_name: '', category: 'platform', reason: '' },
})
const preview = ref<FeeRulePreview>()
const previewDraft = ref<FeeRuleDraftBody | null>(null)
const changeLimit = ref(20)
const confirmRule = ref(false)
const expenseControl = ref<ControlAction>('withdraw')
const confirmControl = ref(false)
const confirmRuleControl = ref(false)
const ruleControl = ref<ControlAction>('withdraw')
const pendingRule = ref<FeeRuleWriteBody | null>(null)
const pendingRuleControl = ref<{
  id: number
  action: ControlAction
  body: ExpenseControlBody
} | null>(null)
const busy = ref(false),
  error = ref(''),
  notice = ref(''),
  unknown = ref(false)
const identities = ['用户实际记录', '合成测试数据']
const categoryKeys = expenseCategoryKeys
const channelList = channels
const allocationRange = ['店铺费用 · 尚未分摊', '单条订单行 · 全额直接归属']
let alive = true,
  epoch = 0,
  restoring = false,
  linked: Record<string, string> = {}
const request = scopedRequest(api, () => (alive ? epoch : null))
const shop = computed(() =>
  account.shops.find((item) => item.id === account.shopId),
)
const timezone = computed(() => shop.value?.timezone || 'UTC')
const base = () => `/shops/${account.shopId}/expenses`
const ruleBase = () => `/shops/${account.shopId}/fee-rules`
const money = (value: string | null | undefined) =>
  value == null || value === '' ? '未知' : decimalText(value)
const categoryLabel = (key: ExpenseCategory | null | undefined) =>
  key ? expenseCategories[key] : '未分类'
const currentActions = computed(() =>
  selected.value ? expenseActions(selected.value.status) : [],
)
const controlRange = computed(() =>
  currentActions.value.map((action) => controls[action]),
)
const ruleActionList = computed(() =>
  rule.value ? ruleActions(rule.value.status) : [],
)
const ruleControlRange = computed(() =>
  ruleActionList.value.map((action) => controls[action]),
)
const orderLabels = computed(() =>
  orders.value.map(
    (item) =>
      `${item.order_id} / ${item.line_id} · ${item.sku} · ${item.currency} · ${item.status}`,
  ),
)
const selectedOrder = computed(() =>
  orders.value.find((item) => item.id === draft.order_line_id),
)
const ruleEditingTitle = computed(() =>
  ruleDraft.rule_id
    ? `修订规则 #${ruleDraft.rule_id} · v${ruleDraft.version}`
    : '新建映射规则',
)
// The page opens after the workspace already selected a shop.
if (shop.value) fillDraft(null)
if (!period.start_at) defaultPeriod()

function unlink() {
  draft.order_line_id = null
  draft.expected_source_row_id = null
  draft.expected_source_revision = null
  orders.value = []
  orderRevision.value = null
}
function defaultPeriod() {
  const zone = timezone.value
  const now = new Date()
  const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1))
  period.timezone = zone
  period.start_at = localIso(start, zone)
  period.end_at = localIso(now, zone)
}
function fillDraft(existing: ExpenseSaved | null) {
  const content = existing?.snapshot
    ? { ...existing.snapshot.content }
    : emptyExpense(shop.value?.currency || 'USD', timezone.value)
  Object.assign(draft, content)
  orderQuery.value = existing?.snapshot?.order_id ?? ''
  unlink()
  confirmSave.value = false
}
function reset() {
  rows.value = []
  cursor.value = null
  selected.value = undefined
  editorOpen.value = false
  editingId.value = null
  summary.value = undefined
  rules.value = []
  rulesCursor.value = null
  rule.value = undefined
  ruleEditing.value = false
  preview.value = undefined
  previewDraft.value = null
  confirmSave.value = false
  confirmControl.value = false
  confirmRule.value = false
  confirmRuleControl.value = false
  error.value = ''
}
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
    pendingWrite.value = null
    pendingControl.value = null
    pendingRule.value = null
    pendingRuleControl.value = null
    unknown.value = false
    reset()
    fillDraft(null)
    defaultPeriod()
    notice.value = ''
  },
  { flush: 'sync' },
)
watch(
  () => [scope.data_identity, scope.channel],
  () => {
    if (restoring) return
    epoch++
    reset()
  },
  { flush: 'sync' },
)
watch(
  () => [draft.allocation, orderQuery.value],
  () => {
    unlink()
    confirmSave.value = false
  },
  { flush: 'sync' },
)
watch(
  draft,
  () => {
    confirmSave.value = false
  },
  { deep: true, flush: 'sync' },
)
watch(
  ruleDraft.content,
  () => {
    preview.value = undefined
    previewDraft.value = null
    confirmRule.value = false
  },
  { deep: true, flush: 'sync' },
)
watch(
  period,
  () => {
    summary.value = undefined
    preview.value = undefined
    previewDraft.value = null
    confirmRule.value = false
  },
  { deep: true, flush: 'sync' },
)
watch(
  () =>
    editorOpen.value ||
    !!pendingWrite.value ||
    !!pendingControl.value ||
    !!pendingRule.value ||
    !!pendingRuleControl.value ||
    unknown.value,
  (protect) => {
    if (!alive) return
    if (protect)
      Taro.enableAlertBeforeUnload({
        message: '有未保存费用编辑或待核对写入，请确认后离开。',
      })
    else Taro.disableAlertBeforeUnload()
  },
)
async function perform(work: () => Promise<void>) {
  if (busy.value || !alive) return
  const token = epoch
  busy.value = true
  error.value = notice.value = ''
  try {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    await work()
  } catch (cause) {
    if (alive && token === epoch)
      error.value = cause instanceof Error ? cause.message : '费用操作失败。'
  } finally {
    if (alive) busy.value = false
  }
}
function uncertain(cause: unknown): boolean {
  if (!(cause instanceof ApiError)) return true
  return cause.status === 0 || cause.status >= 500 || cause.status === 409
}
function guardEditor() {
  if (editorOpen.value)
    throw new Error('请先保存或取消当前费用编辑，再操作其他记录。')
}
function guardUnknown() {
  if (unknown.value)
    throw new Error('上次写入结果未知，请先回查或放弃原请求，再继续写入。')
}
function accept(value: ExpenseSaved) {
  restoring = true
  scope.data_identity = value.data_identity
  scope.channel = value.channel
  restoring = false
  selected.value = value
  expenseControl.value = value.status === 'withdrawn' ? 'clear' : 'withdraw'
  confirmControl.value = false
  confirmSave.value = false
}
async function list(morePages = false) {
  const query = queryString({
    ...scope,
    ...(morePages && cursor.value ? { before: cursor.value } : {}),
  })
  const page = await request<ExpensePage>(`${base()}?${query}`)
  rows.value = morePages ? [...rows.value, ...page.items] : page.items
  cursor.value = page.next_cursor
}
async function listRules(morePages = false) {
  const query = queryString({
    ...scope,
    ...(morePages && rulesCursor.value ? { before: rulesCursor.value } : {}),
  })
  const page = await request<FeeRulePage>(`${ruleBase()}?${query}`)
  rules.value = morePages ? [...rules.value, ...page.items] : page.items
  rulesCursor.value = page.next_cursor
}
async function read(id: number) {
  accept(await request<ExpenseSaved>(`${base()}/${id}`))
}
async function loadRule(id: number) {
  const value = await request<FeeRuleSaved>(`${ruleBase()}/${id}`)
  rule.value = value
  ruleEditing.value = false
  preview.value = undefined
  previewDraft.value = null
  confirmRule.value = false
  confirmRuleControl.value = false
  ruleControl.value = value.status === 'withdrawn' ? 'clear' : 'withdraw'
}
async function refresh() {
  await perform(async () => {
    guardEditor()
    rows.value = []
    summary.value = undefined
    if (selected.value) await read(selected.value.id)
    await list()
    await listRules()
    if (pendingWrite.value || pendingControl.value || pendingRule.value)
      notice.value = '仍有待核对的写入；请回查原请求或放弃后重新核对。'
    else unknown.value = false
  })
}
function begin(existing: ExpenseSaved | null) {
  if (busy.value) return
  fillDraft(existing)
  editingId.value = existing?.id ?? null
  editorOpen.value = true
  error.value = ''
}
function cancelEdit() {
  if (busy.value) return
  editorOpen.value = false
  editingId.value = null
  unlink()
  confirmSave.value = false
}
async function show(id: number) {
  await perform(async () => {
    guardEditor()
    await read(id)
  })
}
async function submitExpense() {
  await perform(async () => {
    guardUnknown()
    if (!confirmSave.value) return
    if (!pendingWrite.value) {
      const content = checkedExpenseContent(draft)
      const editing = editingId.value
      if (editing != null) {
        if (!selected.value || selected.value.id !== editing)
          throw new Error('编辑对象已变化，请重新打开费用记录。')
        if (!['active', 'stale'].includes(selected.value.status))
          throw new Error('已撤销或已清除的费用不再提供修订。')
      }
      pendingWrite.value = {
        id: editing,
        body: {
          request_id: requestId(),
          confirm: true,
          data_identity: scope.data_identity,
          channel: scope.channel,
          version: editing != null ? selected.value!.version : 0,
          content,
        },
      }
    }
    const pending = pendingWrite.value
    unknown.value = true
    try {
      const path = pending.id != null ? `${base()}/${pending.id}` : base()
      const written = await request<ExpenseSaved>(path, 'POST', pending.body)
      pendingWrite.value = null
      unknown.value = false
      editorOpen.value = false
      editingId.value = null
      await read(written.id)
      await list()
      const value = selected.value
      notice.value = value
        ? `费用 #${value.id} 已保存并按 ID 独立回读；当前版本 ${value.version}，${expenseStatuses[value.status] || value.status}。`
        : `费用 #${written.id} 已保存并按 ID 独立回读。`
    } catch (cause) {
      if (!uncertain(cause)) {
        pendingWrite.value = null
        unknown.value = false
      }
      throw cause
    }
  })
}
async function replayWrite() {
  await perform(async () => {
    const pending = pendingWrite.value
    if (!pending) return
    const path = pending.id != null ? `${base()}/${pending.id}` : base()
    const written = await request<ExpenseSaved>(path, 'POST', pending.body)
    pendingWrite.value = null
    unknown.value = false
    editorOpen.value = false
    editingId.value = null
    await read(written.id)
    await list()
    notice.value = `原保存请求已回查，费用 #${written.id} 已按 ID 独立回读。`
  })
}
async function abandonWrite() {
  await perform(async () => {
    pendingWrite.value = null
    unknown.value = false
    await list()
    notice.value = '已放弃未确认的费用保存请求并刷新列表。'
  })
}
async function sendControl(pending: {
  id: number
  action: ControlAction
  body: ExpenseControlBody
}) {
  unknown.value = true
  try {
    const written = await request<ExpenseSaved>(
      `${base()}/${pending.id}/${pending.action}`,
      'POST',
      pending.body,
    )
    pendingControl.value = null
    unknown.value = false
    await read(written.id)
    await list()
    notice.value =
      pending.action === 'clear'
        ? `费用 #${written.id} 的正文、金额、发生时间与全部历史依据已清除；记录已独立回读。`
        : `费用 #${written.id} 已撤销并保留历史，已从有效合计排除；记录已独立回读。`
  } catch (cause) {
    if (!uncertain(cause)) {
      pendingControl.value = null
      unknown.value = false
    }
    throw cause
  }
}
async function controlExpense(action: ControlAction) {
  await perform(async () => {
    guardUnknown()
    const item = selected.value
    if (!item) return
    if (!pendingControl.value) {
      if (!expenseActions(item.status).includes(action))
        throw new Error('当前状态不提供该处理动作，请刷新后核对。')
      const answer = await Taro.showModal({
        title: action === 'clear' ? '清除费用及全部历史' : '撤销费用',
        content:
          action === 'clear'
            ? `费用 #${item.id} 的正文、金额、发生时间及全部历史依据将被擦除且无法恢复。确认继续？`
            : `费用 #${item.id} 将标记为已撤销并保留历史版本，不再计入费用合计。确认继续？`,
      })
      if (
        !answer.confirm ||
        !alive ||
        !account.session ||
        selected.value?.id !== item.id ||
        selected.value.version !== item.version
      )
        return
      pendingControl.value = {
        id: item.id,
        action,
        body: { request_id: requestId(), version: item.version, confirm: true },
      }
    }
    const pending = pendingControl.value
    if (pending) await sendControl(pending)
  })
}
async function replayControl() {
  await perform(async () => {
    const pending = pendingControl.value
    if (pending) await sendControl(pending)
  })
}
async function findOrders() {
  await perform(async () => {
    const order = orderQuery.value.trim()
    if (!order) throw new Error('请输入订单号。')
    const value = await request<ExpenseOrders>(
      `${base()}/orders?${queryString({ ...scope, order_id: order })}`,
    )
    orders.value = value.items
    orderRevision.value = value.source_revision
    if (!value.items.length)
      throw new Error('此范围没有当前订单行，请核对订单号、身份和渠道。')
  })
}
async function summarize() {
  await perform(async () => {
    const input = checkedExpenseScope({ ...scope, ...period })
    const token = JSON.stringify(period)
    const value = await request<ExpenseSummary>(
      `${base()}/summary`,
      'POST',
      input,
    )
    if (JSON.stringify(period) !== token) return
    summary.value = value
  })
}
async function showRule(id: number) {
  await perform(async () => {
    await loadRule(id)
  })
}
function beginRule(existing: FeeRuleSaved | null) {
  if (busy.value) return
  ruleDraft.rule_id = existing?.id ?? null
  ruleDraft.version = existing?.version ?? 0
  ruleDraft.content = existing?.content
    ? { ...existing.content }
    : { fee_name: '', category: 'platform', reason: '' }
  ruleEditing.value = true
  preview.value = undefined
  previewDraft.value = null
  confirmRule.value = false
  error.value = ''
}
function cancelRule() {
  if (busy.value) return
  ruleEditing.value = false
  preview.value = undefined
  previewDraft.value = null
  confirmRule.value = false
}
async function inspectRule() {
  await perform(async () => {
    const body: FeeRuleDraftBody = {
      scope: checkedExpenseScope({ ...scope, ...period }),
      rule_id: ruleDraft.rule_id,
      version: ruleDraft.version,
      content: checkedFeeRuleContent(ruleDraft.content),
    }
    const value = await request<FeeRulePreview>(
      `${ruleBase()}/preview`,
      'POST',
      body,
    )
    previewDraft.value = body
    preview.value = value
    changeLimit.value = 20
    confirmRule.value = false
  })
}
async function sendRule(body: FeeRuleWriteBody) {
  unknown.value = true
  try {
    const written = await request<FeeRuleSaved>(ruleBase(), 'POST', body)
    pendingRule.value = null
    unknown.value = false
    ruleEditing.value = false
    preview.value = undefined
    previewDraft.value = null
    confirmRule.value = false
    await loadRule(written.id)
    await listRules()
    notice.value = `规则 #${written.id} 已保存并按 ID 独立回读；当前版本 ${written.version}，${ruleStatuses[written.status] || written.status}。`
  } catch (cause) {
    if (!uncertain(cause)) {
      pendingRule.value = null
      unknown.value = false
    }
    throw cause
  }
}
async function saveRule() {
  await perform(async () => {
    guardUnknown()
    if (!preview.value || !previewDraft.value || !confirmRule.value) return
    if (!pendingRule.value)
      pendingRule.value = {
        ...previewDraft.value,
        preview_hash: preview.value.preview_hash,
        request_id: requestId(),
        confirm: true,
      }
    const body = pendingRule.value
    if (body) await sendRule(body)
  })
}
async function replayRule() {
  await perform(async () => {
    const body = pendingRule.value
    if (body) await sendRule(body)
  })
}
async function sendRuleControl(pending: {
  id: number
  action: ControlAction
  body: ExpenseControlBody
}) {
  unknown.value = true
  try {
    const written = await request<FeeRuleSaved>(
      `${ruleBase()}/${pending.id}/${pending.action}`,
      'POST',
      pending.body,
    )
    pendingRuleControl.value = null
    unknown.value = false
    await loadRule(written.id)
    await listRules()
    notice.value =
      pending.action === 'clear'
        ? `规则 #${written.id} 的收费名、类别、依据及全部历史正文已清除；记录已独立回读。`
        : `规则 #${written.id} 已撤销并停止参与分类，历史正文保留；记录已独立回读。`
  } catch (cause) {
    if (!uncertain(cause)) {
      pendingRuleControl.value = null
      unknown.value = false
    }
    throw cause
  }
}
async function controlRule(action: ControlAction) {
  await perform(async () => {
    guardUnknown()
    const item = rule.value
    if (!item) return
    if (!pendingRuleControl.value) {
      if (!ruleActions(item.status).includes(action))
        throw new Error('当前状态不提供该规则处理动作，请刷新后核对。')
      const answer = await Taro.showModal({
        title: action === 'clear' ? '清除规则及全部历史正文' : '撤销规则',
        content:
          action === 'clear'
            ? `规则 #${item.id} 的收费名、类别、依据及全部历史正文将被擦除且无法恢复。确认继续？`
            : `规则 #${item.id} 将停止参与全部窗口的分类，历史正文保留。确认继续？`,
      })
      if (
        !answer.confirm ||
        !alive ||
        !account.session ||
        rule.value?.id !== item.id ||
        rule.value.version !== item.version
      )
        return
      pendingRuleControl.value = {
        id: item.id,
        action,
        body: { request_id: requestId(), version: item.version, confirm: true },
      }
    }
    const pending = pendingRuleControl.value
    if (pending) await sendRuleControl(pending)
  })
}
async function replayRuleControl() {
  await perform(async () => {
    const pending = pendingRuleControl.value
    if (pending) await sendRuleControl(pending)
  })
}
function pickIdentity(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  scope.data_identity = index ? 'synthetic' : 'user_import'
}
function pickChannel(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  scope.channel = channelList[index] || scope.channel
}
function pickCategory(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  draft.category = categoryKeys[index] || draft.category
}
function pickCurrency(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  draft.currency = currencies[index] || draft.currency
}
function pickAllocation(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  draft.allocation = index ? 'order_line' : 'shop'
}
function pickOrder(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  const link = linkedOrder(orders.value[index], orderRevision.value)
  draft.order_line_id = link.order_line_id
  draft.expected_source_row_id = link.expected_source_row_id
  draft.expected_source_revision = link.expected_source_revision
  confirmSave.value = false
}
function pickControl(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  const action = currentActions.value[index]
  if (action) {
    confirmControl.value = false
    expenseControl.value = action
  }
}
function pickRuleCategory(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  ruleDraft.content.category = categoryKeys[index] || ruleDraft.content.category
}
function pickRuleControl(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  const action = ruleActionList.value[index]
  if (action) {
    confirmRuleControl.value = false
    ruleControl.value = action
  }
}
function stampNow() {
  try {
    draft.occurred_at = localIso(new Date(), checkedTimezone(draft.timezone))
    confirmSave.value = false
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '时区无效。'
  }
}
function draftSummary() {
  const allocation =
    draft.allocation === 'shop'
      ? '店铺未分摊'
      : selectedOrder.value
        ? `${selectedOrder.value.order_id} / ${selectedOrder.value.line_id} 全额归属`
        : '尚未选择订单行'
  return `${draft.currency} ${draft.amount || '—'} · ${categoryLabel(draft.category)} · ${allocation}`
}
async function openImports() {
  try {
    await openLink('/imports', { shop: String(account.shopId) })
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : '无法打开文件导入页面。'
  }
}
useDidShow(() => {
  void perform(async () => {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    if (linked.shop && Number(linked.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不一致。')
    if (!period.start_at) defaultPeriod()
    await list()
    await listRules()
    if (linked.expense) {
      if (!/^[1-9]\d*$/.test(linked.expense)) throw new Error('费用编号无效。')
      await read(Number(linked.expense))
    } else if (selected.value) await read(selected.value.id)
    if (linked.rule) {
      if (!/^[1-9]\d*$/.test(linked.rule)) throw new Error('规则编号无效。')
      await loadRule(Number(linked.rule))
    }
    linked = {}
  })
})
</script>
<template>
  <view class="screen">
    <view class="hero"
      ><text class="eyebrow">SOLOOPS · EXPENSES</text
      ><text class="title">实际费用，每一笔有依据。</text
      ><text class="muted"
        >记录已发生费用，保留修订历史，核对归属与来源；人工台账待与平台账单核对。</text
      ></view
    >
    <text v-if="error" class="error">{{ error }}</text
    ><text v-if="notice" class="hint">{{ notice }}</text
    ><text v-if="unknown" class="error"
      >上次写入结果待核对；请回查原请求或放弃后再继续。</text
    >
    <view class="card"
      ><view class="row"
        ><text class="section-title">{{ shop?.name || '未选择店铺' }}</text
        ><text class="badge">{{ shop?.currency }} · {{ timezone }}</text></view
      ><picker
        :range="identities"
        :value="scope.data_identity === 'synthetic' ? 1 : 0"
        :disabled="busy || editorOpen"
        @change="pickIdentity($event)"
        ><view class="select"
          >数据身份：{{
            scope.data_identity === 'synthetic'
              ? '合成测试数据'
              : '用户实际记录'
          }}</view
        ></picker
      ><picker
        :range="channelList"
        :value="Math.max(0, channelList.indexOf(scope.channel))"
        :disabled="busy || editorOpen"
        @change="pickChannel($event)"
        ><view class="select">来源渠道：{{ scope.channel }}</view></picker
      ><text class="hint"
        >费用完整性未知；店铺费用尚未分摊，单条订单行费用全额直接归属。切换身份或渠道会清空当前列表与详情。</text
      ><button :disabled="busy || editorOpen" @tap="refresh">
        刷新费用与规则</button
      ><button
        class="primary"
        :disabled="busy || editorOpen"
        @tap="begin(null)"
      >
        新增实际费用
      </button></view
    >
    <view v-if="pendingWrite" class="card"
      ><text class="section-title">待核对的费用保存</text
      ><text class="hint"
        >保存结果未知。可沿用原 request_id
        回查；服务端按请求标识幂等，重复提交不会新建费用。</text
      ><text class="hint"
        >记录：{{ pendingWrite.id == null ? '新建' : `#${pendingWrite.id}` }} ·
        {{ pendingWrite.body.content.label || '未填写名称' }} ·
        {{ pendingWrite.body.content.currency }}
        {{ pendingWrite.body.content.amount }}</text
      ><text class="hint"
        >冻结范围：{{ pendingWrite.body.data_identity }} /
        {{ pendingWrite.body.channel }} · 版本
        {{ pendingWrite.body.version }}</text
      ><button class="primary" :disabled="busy" @tap="replayWrite">
        回查原保存请求</button
      ><button :disabled="busy" @tap="abandonWrite">
        放弃并刷新列表
      </button></view
    >
    <view v-if="pendingControl" class="card"
      ><text class="section-title">待核对的费用处理</text
      ><text class="hint"
        >费用 #{{ pendingControl.id }} 的
        {{ pendingControl.action === 'clear' ? '清除' : '撤销' }}
        结果未知，版本 {{ pendingControl.body.version }}。回查沿用原
        request_id。</text
      ><button class="primary" :disabled="busy" @tap="replayControl">
        回查原处理请求</button
      ><button :disabled="busy" @tap="refresh">刷新并重新核对</button></view
    >
    <view v-if="pendingRule" class="card"
      ><text class="section-title">待核对的规则保存</text
      ><text class="hint"
        >规则写入结果未知，预览哈希
        {{ pendingRule.preview_hash.slice(0, 12) }}…。回查沿用原 request_id
        与同一预览。</text
      ><button class="primary" :disabled="busy" @tap="replayRule">
        回查原规则保存请求
      </button></view
    >
    <view v-if="pendingRuleControl" class="card"
      ><text class="section-title">待核对的规则处理</text
      ><text class="hint"
        >规则 #{{ pendingRuleControl.id }} 的
        {{ pendingRuleControl.action === 'clear' ? '清除' : '撤销' }}
        结果未知。回查沿用原 request_id 与版本
        {{ pendingRuleControl.body.version }}。</text
      ><button class="primary" :disabled="busy" @tap="replayRuleControl">
        回查原规则处理请求
      </button></view
    >
    <view v-if="editorOpen" class="card"
      ><text class="section-title">{{
        editingId == null ? '录入实际费用' : `修订费用 #${editingId}`
      }}</text
      ><text class="hint"
        >凭据编号在本店铺、身份和渠道内去重；每笔只录入一次总额，更正同一笔请修订。</text
      ><text class="label">费用名称</text
      ><input v-model="draft.label" :maxlength="100" :disabled="busy" /><text
        class="label"
        >费用类别</text
      ><picker
        :range="categoryKeys"
        :value="Math.max(0, categoryKeys.indexOf(draft.category))"
        :disabled="busy"
        @change="pickCategory($event)"
        ><view class="select">{{ categoryLabel(draft.category) }}</view></picker
      ><text class="label">实际费用金额（大于零，最多四位小数）</text
      ><input
        v-model="draft.amount"
        :maxlength="20"
        :disabled="busy"
        placeholder="0.0000"
      /><text class="label">费用币种</text
      ><picker
        :range="currencies"
        :value="Math.max(0, currencies.indexOf(draft.currency))"
        :disabled="busy"
        @change="pickCurrency($event)"
        ><view class="select">{{ draft.currency }}</view></picker
      ><text class="label">发生时间（含明确偏移）</text
      ><input
        v-model="draft.occurred_at"
        :maxlength="40"
        :disabled="busy"
        placeholder="2026-10-12T09:30:00+08:00"
      /><button :disabled="busy" @tap="stampNow">按当前时区填入现在</button
      ><text class="label">发生时区（IANA）</text
      ><input
        v-model="draft.timezone"
        :maxlength="64"
        :disabled="busy"
        placeholder="Asia/Shanghai"
      /><text class="hint"
        >发生时间的偏移必须与该 IANA 时区一致；服务端会再次校验。</text
      ><text class="label">凭据编号</text
      ><input
        v-model="draft.evidence_ref"
        :maxlength="120"
        :disabled="busy"
      /><text class="label">费用归属</text
      ><picker
        :range="allocationRange"
        :value="draft.allocation === 'order_line' ? 1 : 0"
        :disabled="busy"
        @change="pickAllocation($event)"
        ><view class="select">{{
          allocationRange[draft.allocation === 'order_line' ? 1 : 0]
        }}</view></picker
      >
      <template v-if="draft.allocation === 'order_line'"
        ><text class="label">订单号（精确匹配）</text
        ><input v-model="orderQuery" :maxlength="120" :disabled="busy" /><button
          :disabled="busy || !orderQuery.trim()"
          @tap="findOrders"
        >
          查找当前订单行</button
        ><picker
          v-if="orders.length"
          :range="orderLabels"
          :value="
            Math.max(
              0,
              orders.findIndex((item) => item.id === draft.order_line_id),
            )
          "
          :disabled="busy"
          @change="pickOrder($event)"
          ><view class="select">{{
            draft.order_line_id
              ? orderLabels[
                  Math.max(
                    0,
                    orders.findIndex((item) => item.id === draft.order_line_id),
                  )
                ]
              : '请选择并核对订单行'
          }}</view></picker
        ><text class="hint"
          >订单行费用绑定当前来源行与店铺来源版本；来源变化会被服务端拒绝，请重新查找。</text
        ><SourceList
          v-if="selectedOrder"
          :key="selectedOrder.source.row_id"
          :sources="[selectedOrder.source]"
          :shop-id="account.shopId"
      /></template>
      <text class="label">事实依据</text
      ><textarea
        v-model="draft.evidence_note"
        :maxlength="1000"
        :disabled="busy"
        placeholder="账单/收据上的可核查事实"
      /><text class="label">本次录入或修订理由</text
      ><textarea
        v-model="draft.reason"
        :maxlength="500"
        :disabled="busy"
      /><text class="hint">本次保存：{{ draftSummary() }}</text
      ><checkbox-group
        @change="confirmSave = Boolean(($event.detail.value || []).length)"
        ><label class="label"
          ><checkbox
            value="save"
            :checked="confirmSave"
            :disabled="busy"
          />我已核对金额、发生时间、凭据和归属，确认保存本版本</label
        ></checkbox-group
      ><button
        class="primary"
        :disabled="
          busy ||
          !confirmSave ||
          unknown ||
          (draft.allocation === 'order_line' && !selectedOrder)
        "
        @tap="submitExpense"
      >
        确认保存费用</button
      ><button :disabled="busy" @tap="cancelEdit">取消编辑</button></view
    >
    <view v-if="selected" class="card"
      ><view class="row"
        ><text class="section-title">费用 #{{ selected.id }}</text
        ><text class="badge"
          >{{ expenseStatuses[selected.status] || selected.status }} · v{{
            selected.version
          }}</text
        ></view
      ><text class="hint"
        >创建于 {{ supportTime(selected.created_at, timezone) }} · 身份
        {{ selected.data_identity }} · 渠道 {{ selected.channel }}</text
      >
      <template v-if="selected.snapshot"
        ><text
          >{{ selected.snapshot.content.label }} ·
          {{ categoryLabel(selected.snapshot.content.category) }} ·
          {{ selected.snapshot.content.currency }}
          {{ money(selected.snapshot.content.amount) }}</text
        ><text
          >发生时间
          {{
            supportTime(
              selected.snapshot.content.occurred_at,
              selected.snapshot.content.timezone,
            )
          }}</text
        ><text
          >归属
          {{
            selected.snapshot.content.allocation === 'shop'
              ? '店铺未分摊'
              : `${selected.snapshot.order_id || '订单未知'} / ${selected.snapshot.line_id || '行未知'} · ${selected.snapshot.sku || 'SKU 未知'} · ${selected.snapshot.order_status || '状态未知'}`
          }}</text
        ><text
          >凭据 {{ selected.snapshot.content.evidence_ref }} ·
          {{ selected.snapshot.content.evidence_note }}</text
        ><text>理由 {{ selected.snapshot.content.reason }}</text
        ><SourceList
          v-if="selected.snapshot.source"
          :sources="[selected.snapshot.source]"
          :shop-id="account.shopId"
      /></template>
      <text v-else class="hint"
        >费用正文、金额、发生时间与全部历史依据已清除。</text
      >
      <text v-if="selected.status === 'stale'" class="error"
        >关联订单来源已变化，本笔已从有效费用合计排除；请重新查找当前订单并核对，或更正为店铺费用后保存新版本。</text
      >
      <button
        v-if="selected.status === 'active' || selected.status === 'stale'"
        :disabled="busy || editorOpen"
        @tap="begin(selected)"
      >
        修订费用
      </button>
      <text class="label">版本历史（{{ selected.history.length }}）</text>
      <text v-for="entry in selected.history" :key="entry.version"
        >v{{ entry.version }} ·
        {{ revisionActions[entry.action] || entry.action }} ·
        {{ supportTime(entry.created_at, timezone) }} ·
        {{ entry.snapshot ? entry.snapshot.content.label : '无费用正文' }}</text
      >
      <template v-if="currentActions.length"
        ><text class="label">撤销或清除</text
        ><picker
          :range="controlRange"
          :value="Math.max(0, currentActions.indexOf(expenseControl))"
          :disabled="busy"
          @change="pickControl($event)"
          ><view class="select">{{ controls[expenseControl] }}</view></picker
        ><text class="hint"
          >撤销保留历史版本并从合计排除；清除会擦除全部历史正文与依据，原账单保留。</text
        ><checkbox-group
          @change="confirmControl = Boolean(($event.detail.value || []).length)"
          ><label class="label"
            ><checkbox
              value="control"
              :checked="confirmControl"
              :disabled="busy"
            />确认执行所选费用处理及全部版本影响</label
          ></checkbox-group
        ><button
          class="danger"
          :disabled="busy || !confirmControl"
          @tap="controlExpense(expenseControl)"
        >
          执行费用处理
        </button></template
      ></view
    >
    <view class="card"
      ><text class="section-title">按发生时间核对费用</text
      ><text class="hint"
        >包含开始、不含结束，最多 366 天、1000
        笔；按当前有效版本、分币种与类别统计，不换汇。</text
      ><text class="label">开始时间（含偏移）</text
      ><input v-model="period.start_at" :maxlength="40" :disabled="busy" /><text
        class="label"
        >结束时间（不含，含偏移）</text
      ><input v-model="period.end_at" :maxlength="40" :disabled="busy" /><text
        class="label"
        >核对显示时区（IANA）</text
      ><input
        v-model="period.timezone"
        :maxlength="64"
        :disabled="busy"
      /><button :disabled="busy" @tap="summarize">核对费用合计</button
      ><view v-if="summary"
        ><text
          >{{ summary.scope.start_at }} → {{ summary.scope.end_at }}（不含结束，
          {{ summary.scope.timezone }}）</text
        ><text
          >有效 {{ summary.included_count }} 笔 · 待重核
          {{ summary.stale_count }} 笔 · 已撤销
          {{ summary.withdrawn_count }} 笔</text
        ><text v-if="!summary.totals.length" class="hint"
          >此范围没有可计入费用；不表示实际费用为零。</text
        ><text
          v-for="item in summary.totals"
          :key="`${item.currency}-${item.category}-${item.allocation}`"
          >{{ item.currency }} {{ money(item.amount) }} ·
          {{ categoryLabel(item.category) }} ·
          {{ item.allocation === 'shop' ? '店铺未分摊' : '订单行直接归属' }} ·
          {{ item.count }} 笔</text
        ><text v-for="check in summary.checks" :key="check" class="hint">{{
          check
        }}</text></view
      ></view
    >
    <view class="card"
      ><text class="section-title">费用记录</text
      ><text class="hint"
        >当前店铺、身份与渠道；包含已撤销、待重核与已清除记录。</text
      ><text v-if="!rows.length" class="muted">本页暂无已加载记录。</text
      ><button
        v-for="item in rows"
        :key="item.id"
        :disabled="busy || editorOpen"
        @tap="show(item.id)"
      >
        #{{ item.id }} · {{ item.snapshot?.content.label || '正文已清除' }} ·
        {{ expenseStatuses[item.status] || item.status }} · v{{ item.version }}
        <template v-if="item.snapshot"
          >· {{ item.snapshot.content.currency }}
          {{ money(item.snapshot.content.amount) }}</template
        ></button
      ><button v-if="cursor" :disabled="busy || editorOpen" @tap="list(true)">
        继续读取更早费用
      </button></view
    >
    <view class="card"
      ><text class="section-title">收费映射规则</text
      ><text class="hint"
        >按当前店铺、身份和渠道生效；收费名去首尾空白后区分大小写完整匹配。规则适用于该范围全部日期与币种，上方时间窗口只限制差异预览。</text
      ><text v-if="!rules.length" class="muted"
        >本页暂无已加载规则；映射规则针对已提交账单的收费名，请先在文件导入提交账单。</text
      ><button v-if="!rules.length" :disabled="busy" @tap="openImports">
        打开文件导入</button
      ><button
        v-for="item in rules"
        :key="item.id"
        :disabled="busy"
        @tap="showRule(item.id)"
      >
        规则 #{{ item.id }} · {{ item.content?.fee_name || '正文已清除' }} ·
        {{ ruleStatuses[item.status] || item.status }} · v{{
          item.version
        }}</button
      ><button v-if="rulesCursor" :disabled="busy" @tap="listRules(true)">
        继续读取更早规则</button
      ><button :disabled="busy" @tap="listRules()">刷新规则列表</button
      ><button class="primary" :disabled="busy" @tap="beginRule(null)">
        新建映射规则
      </button>
      <template v-if="ruleEditing"
        ><text class="label">{{ ruleEditingTitle }}</text
        ><text class="label">完整原始收费名</text
        ><input
          v-model="ruleDraft.content.fee_name"
          :maxlength="120"
          :disabled="busy"
        /><text class="label">统一费用类别</text
        ><picker
          :range="categoryKeys"
          :value="Math.max(0, categoryKeys.indexOf(ruleDraft.content.category))"
          :disabled="busy"
          @change="pickRuleCategory($event)"
          ><view class="select">{{
            categoryLabel(ruleDraft.content.category)
          }}</view></picker
        ><text class="label">本次规则依据与理由</text
        ><textarea
          v-model="ruleDraft.content.reason"
          :maxlength="500"
          :disabled="busy"
        /><button :disabled="busy" @tap="inspectRule">预览分类变化</button
        ><button :disabled="busy" @tap="cancelRule">
          取消规则编辑
        </button></template
      >
      <view v-if="preview" class="rule-preview"
        ><text class="section-title">分类变化预览</text
        ><text
          >原规则：{{
            preview.previous
              ? `${preview.previous.fee_name} → ${categoryLabel(preview.previous.category)}`
              : '无'
          }}</text
        ><text
          >拟保存：{{ preview.proposed.fee_name }} →
          {{ categoryLabel(preview.proposed.category) }}</text
        ><text>依据：{{ preview.proposed.reason }}</text
        ><text
          >本次读取 {{ preview.statement_count }} 行账单，分类结果变化
          {{ preview.changes.length }} 行 · 来源版本
          {{ preview.source_revision }} · 预览哈希
          {{ preview.preview_hash.slice(0, 12) }}…</text
        ><text v-if="!preview.changes.length" class="hint"
          >本窗口没有分类结果变化；规则仍会应用于同范围其它日期的匹配收费项。</text
        ><view
          v-for="change in preview.changes.slice(0, changeLimit)"
          :key="change.statement_id"
          class="card"
          ><text>账单行 #{{ change.statement_id }} · {{ change.fee_name }}</text
          ><text
            >{{
              mappingStatuses[change.before.status] || change.before.status
            }}
            {{ categoryLabel(change.before.category) }} →
            {{ mappingStatuses[change.after.status] || change.after.status }}
            {{ categoryLabel(change.after.category) }}</text
          ><SourceList :sources="[change.source]" :shop-id="account.shopId"
        /></view>
        <button
          v-if="changeLimit < preview.changes.length"
          :disabled="busy"
          @tap="changeLimit += 20"
        >
          更多分类变化（共 {{ preview.changes.length }} 行）
        </button>
        <checkbox-group
          @change="confirmRule = Boolean(($event.detail.value || []).length)"
          ><label class="label"
            ><checkbox
              value="rule"
              :checked="confirmRule"
              :disabled="busy"
            />我已核对差异，确认规则适用于当前店铺、身份、渠道的全部日期与币种</label
          ></checkbox-group
        ><button
          class="primary"
          :disabled="busy || !confirmRule || unknown"
          @tap="saveRule"
        >
          保存规则并回读
        </button></view
      >
      <view v-if="rule"
        ><view class="row"
          ><text class="section-title">规则 #{{ rule.id }}</text
          ><text class="badge"
            >{{ ruleStatuses[rule.status] || rule.status }} · v{{
              rule.version
            }}</text
          ></view
        ><text class="hint"
          >创建于 {{ supportTime(rule.created_at, timezone) }} · 身份
          {{ rule.data_identity }} · 渠道 {{ rule.channel }}</text
        ><text v-if="rule.content"
          >{{ rule.content.fee_name }} →
          {{ categoryLabel(rule.content.category) }} ·
          {{ rule.content.reason }}</text
        ><text v-else class="hint">收费名、类别及全部历史正文已清除。</text
        ><button
          v-if="rule.status === 'active'"
          :disabled="busy"
          @tap="beginRule(rule)"
        >
          修订此规则</button
        ><text v-for="entry in rule.history" :key="entry.version"
          >v{{ entry.version }} ·
          {{ revisionActions[entry.action] || entry.action }} ·
          {{ supportTime(entry.created_at, timezone) }} ·
          {{
            entry.content
              ? `${entry.content.fee_name} → ${categoryLabel(entry.content.category)}`
              : '无正文'
          }}</text
        >
        <template v-if="ruleActionList.length"
          ><text class="label">规则处理</text
          ><picker
            :range="ruleControlRange"
            :value="Math.max(0, ruleActionList.indexOf(ruleControl))"
            :disabled="busy"
            @change="pickRuleControl($event)"
            ><view class="select">{{ controls[ruleControl] }}</view></picker
          ><text class="hint"
            >撤销后该规则停止参与所有窗口分类；清除同时擦除规则历史正文，原账单与人工费用保留。</text
          ><checkbox-group
            @change="
              confirmRuleControl = Boolean(($event.detail.value || []).length)
            "
            ><label class="label"
              ><checkbox
                value="rule-control"
                :checked="confirmRuleControl"
                :disabled="busy"
              />我确认处理此版本规则及上述影响</label
            ></checkbox-group
          ><button
            class="danger"
            :disabled="busy || !confirmRuleControl"
            @tap="controlRule(ruleControl)"
          >
            确认处理规则
          </button></template
        ></view
      ></view
    >
  </view>
</template>
<style>
.rule-preview {
  border-top: 1rpx solid #dce7e0;
  margin-top: 24rpx;
  padding-top: 16rpx;
}
</style>
