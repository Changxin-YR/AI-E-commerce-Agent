// route: /settlements
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import { ApiError } from '../../services/client'
import { queryString, requestId } from '../../services/task-policy'
import { openLink as openRoute } from '../../services/navigation'
import { supportTime } from '../../services/support-types'
import SourceList from '../../components/SourceList.vue'
import {
  availableActions,
  canEdit,
  channels,
  checkedContent,
  checkedDraft,
  checkedScope,
  controlBody,
  controls,
  emptyReceipt,
  emptySettlementContent,
  emptySettlementScope,
  identities,
  isCurrentVersion,
  maxReceipts,
  payoutStatuses,
  revisionActions,
  settlementStatuses,
  statEntryTypes,
  statusCounts,
  trimmedAmount,
  type ControlAction,
  type SettlementContent,
  type SettlementControlBody,
  type SettlementCurrent,
  type SettlementDraftBody,
  type SettlementHistoryEntry,
  type SettlementPage,
  type SettlementPreview,
  type SettlementSaved,
  type SettlementScope,
  type SettlementSnapshot,
  type SettlementWriteBody,
} from '../../services/settlement-policy'

const scope = reactive<SettlementScope>(emptySettlementScope())
const content = reactive<SettlementContent>(emptySettlementContent())
const records = ref<SettlementSaved[]>([])
const cursor = ref<number | null>(null)
const saved = ref<SettlementSaved>()
const shownVersion = ref<number | null>(null)
const editing = reactive({
  id: 0,
  version: 0,
  scope: emptySettlementScope(),
  open: false,
})
const preview = ref<SettlementPreview>()
const readBack = ref<SettlementPreview>()
const confirmed = ref(false)
const controlOpen = ref(false)
const controlConfirmed = ref(false)
const controlAction = ref<ControlAction>('withdraw')
const busy = ref(false)
const error = ref('')
const notice = ref('')
const pending = ref<SettlementWriteBody>()
const pendingControl = ref<{
  settlement_id: number
  action: ControlAction
  body: SettlementControlBody
} | null>(null)
let alive = true
let epoch = 0
let linked: Record<string, string> = {}
const request = scopedRequest(api, () => (alive ? epoch : null))
const timezone = computed(
  () =>
    account.shops.find((s) => s.id === account.shopId)?.timezone ||
    'Asia/Shanghai',
)
const actions = computed(() => availableActions(saved.value?.status || ''))
const statusSummary = computed(() =>
  records.value.length
    ? `已读取 ${records.value.length} 份：${statusCounts(
        records.value.map(
          (item) => settlementStatuses[item.status] || '状态未知',
        ),
      )
        .map((item) => `${item.key} ${item.count}`)
        .join(' · ')}`
    : '',
)

useLoad((params) => {
  linked = params as Record<string, string>
})
useUnload(() => {
  alive = false
  epoch++
})
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    epoch++
    reset()
    error.value = '请返回工作台登录并选择店铺。'
  },
  { flush: 'sync' },
)
watch(scope, () => {
  records.value = []
  cursor.value = null
  saved.value = undefined
  shownVersion.value = null
  readBack.value = undefined
  controlOpen.value = false
  error.value = ''
  notice.value = ''
})

function reset() {
  records.value = []
  cursor.value = null
  saved.value = undefined
  shownVersion.value = null
  readBack.value = undefined
  preview.value = undefined
  confirmed.value = false
  controlOpen.value = false
  controlConfirmed.value = false
  editing.open = false
  editing.id = 0
  editing.version = 0
  Object.assign(content, emptySettlementContent())
  error.value = ''
  notice.value = ''
}

async function perform(work: () => Promise<void>) {
  if (busy.value || !alive) return
  const token = epoch
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await work()
  } catch (cause) {
    if (alive && token === epoch)
      error.value =
        cause instanceof Error
          ? cause.message
          : '结算操作未完成，请回读记录核对。'
  } finally {
    if (alive) busy.value = false
  }
}

function base(shop: number) {
  return `/shops/${shop}/settlements`
}

async function list(more = false) {
  if (!account.session || !account.shopId)
    throw new Error('请先登录并选择店铺。')
  const input = checkedScope(scope)
  const query = queryString({
    data_identity: input.data_identity,
    channel: input.channel,
    before: more && cursor.value ? cursor.value : '',
  })
  const page = await request<SettlementPage>(`${base(account.shopId)}?${query}`)
  records.value = more ? [...records.value, ...page.items] : page.items
  cursor.value = page.next_cursor
}

async function show(id: number, version?: number) {
  if (!account.shopId) throw new Error('请先登录并选择店铺。')
  const target = version
    ? `${base(account.shopId)}/${id}?version=${version}`
    : `${base(account.shopId)}/${id}`
  const value = await request<SettlementSaved>(target)
  saved.value = value
  shownVersion.value = version ?? value.content_version
  readBack.value = undefined
  controlOpen.value = false
  controlConfirmed.value = false
  controlAction.value = value.status === 'withdrawn' ? 'clear' : 'withdraw'
}

function begin(record?: SettlementSaved) {
  const snapshot = record?.snapshot
  preview.value = undefined
  confirmed.value = false
  readBack.value = undefined
  editing.open = true
  editing.id = record?.id || 0
  editing.version = record?.version || 0
  editing.scope = { ...(snapshot?.scope || scope) }
  Object.assign(
    content,
    snapshot
      ? (JSON.parse(JSON.stringify(snapshot.content)) as SettlementContent)
      : emptySettlementContent(),
  )
}

function draft(): SettlementDraftBody {
  return checkedDraft({
    scope: { ...editing.scope },
    settlement_id: editing.id || null,
    version: editing.version,
    content: JSON.parse(JSON.stringify(content)) as SettlementContent,
  })
}

async function inspect() {
  if (!account.shopId) throw new Error('请先登录并选择店铺。')
  await perform(async () => {
    preview.value = undefined
    confirmed.value = false
    const body = draft()
    const value = await request<SettlementPreview>(
      `${base(account.shopId)}/preview`,
      'POST',
      body,
    )
    preview.value = value
    notice.value = '预览已按当前账单与人工凭据重新计算，保存前请核对。'
  })
}

async function save(retry = false) {
  if (!account.shopId) throw new Error('请先登录并选择店铺。')
  if (!retry) {
    if (!preview.value || !confirmed.value) return
    pending.value = {
      ...draft(),
      preview_hash: preview.value.preview_hash,
      request_id: requestId(),
      confirm: true,
    }
  }
  const body = pending.value
  if (!body) return
  await perform(async () => {
    let value: SettlementSaved
    try {
      value = await request<SettlementSaved>(base(account.shopId), 'POST', body)
    } catch (cause) {
      // 只有确定性 4xx 才允许修正后新建 request_id；结果未知保留同次恢复入口。
      if (
        cause instanceof ApiError &&
        cause.status >= 400 &&
        cause.status < 500
      )
        pending.value = undefined
      throw cause
    }
    const id = value.id
    saved.value = await request<SettlementSaved>(
      `${base(account.shopId)}/${id}`,
    )
    shownVersion.value = saved.value.content_version
    pending.value = undefined
    preview.value = undefined
    confirmed.value = false
    editing.open = false
    await list()
    notice.value = '已按登记编号独立回读结算登记与版本。'
  })
}

async function readCurrent() {
  if (!account.shopId || !saved.value) return
  await perform(async () => {
    const id = saved.value?.id || 0
    const value = await request<SettlementCurrent>(
      `${base(account.shopId)}/${id}/current`,
    )
    saved.value = value.record
    shownVersion.value = value.record.content_version
    readBack.value = value.preview || undefined
    controlOpen.value = false
    notice.value = value.preview
      ? '当前依据已重新计算；本次读取不会更新历史登记。'
      : '该登记没有可回读的正文依据。'
  })
}

async function control(retry = false) {
  if (!account.shopId) throw new Error('请先登录并选择店铺。')
  if (!retry) {
    if (!saved.value || !controlConfirmed.value) return
    pendingControl.value = {
      settlement_id: saved.value.id,
      action: controlAction.value,
      body: controlBody(saved.value.version, requestId()),
    }
  }
  const pendingAction = pendingControl.value
  if (!pendingAction) return
  const id = pendingAction.settlement_id
  const action = pendingAction.action
  if (!retry) {
    const answer = await Taro.showModal({
      title: action === 'clear' ? '清除结算登记' : '撤销结算登记',
      content:
        action === 'clear'
          ? '清除将擦除这份登记的全部历史正文与依据，无法恢复；原始账单独立保留。确认继续？'
          : '撤销会释放账单号与人工凭据占用并保留历史。确认继续？',
    })
    if (!answer.confirm || saved.value?.id !== id || !account.session) return
  }
  await perform(async () => {
    let value: SettlementSaved
    try {
      value = await request<SettlementSaved>(
        `${base(account.shopId)}/${id}/${action}`,
        'POST',
        pendingAction.body,
      )
    } catch (cause) {
      if (
        cause instanceof ApiError &&
        cause.status >= 400 &&
        cause.status < 500
      )
        pendingControl.value = null
      throw cause
    }
    saved.value = await request<SettlementSaved>(
      `${base(account.shopId)}/${id}`,
    )
    shownVersion.value = saved.value.content_version
    readBack.value = undefined
    pendingControl.value = null
    controlConfirmed.value = false
    controlOpen.value = false
    controlAction.value =
      saved.value.status === 'withdrawn' ? 'clear' : 'withdraw'
    if (saved.value.status === 'cleared') {
      Object.assign(content, emptySettlementContent())
      preview.value = undefined
      pending.value = undefined
      editing.open = false
    }
    await list()
    notice.value =
      value.status === 'cleared'
        ? '正文与历史依据已清除，仅保留范围、状态与审计。'
        : '登记已撤销并保留历史，可继续清除或重新登记。'
  })
}

function addReceipt() {
  if (content.receipts.length >= maxReceipts) return
  content.receipts.push(
    emptyReceipt(
      account.shops.find((s) => s.id === account.shopId)?.currency || 'USD',
      editing.scope.timezone,
    ),
  )
  confirmed.value = false
}

function removeReceipt(index: number) {
  content.receipts.splice(index, 1)
  confirmed.value = false
}

function pickIdentity(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  scope.data_identity = identities[index] || 'user_import'
}

function pickChannel(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  scope.channel = channels[index] || 'generic'
}

function shopTimezone() {
  return timezone.value
}

function historyLabel(entry: SettlementHistoryEntry) {
  return `v${entry.version} · ${revisionActions[entry.action] || entry.action} · ${supportTime(entry.created_at, scope.timezone)}`
}

function statLabel(kind: string) {
  return statEntryTypes[kind] || kind
}

function receiptLabel(index: number) {
  return `人工凭据 ${index + 1}`
}

function toggleConfirmed(event: unknown) {
  confirmed.value = Boolean(
    (event as { detail: { value: boolean } }).detail.value,
  )
}

function toggleControl(event: unknown) {
  controlConfirmed.value = Boolean(
    (event as { detail: { value: boolean } }).detail.value,
  )
}

function openLink(path: string, query: Record<string, string> = {}) {
  void openRoute(path, { shop: String(account.shopId || ''), ...query }).catch(
    (cause: unknown) => {
      error.value =
        cause instanceof Error ? cause.message : '打开业务页面失败。'
    },
  )
}

function snapshotTotals(view?: SettlementSnapshot) {
  return view?.totals || []
}

useDidShow(() => {
  void perform(async () => {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    if (linked.shop && Number(linked.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不同，请切换店铺后重试。')
    Object.assign(scope, emptySettlementScope(shopTimezone()))
    Object.assign(content, emptySettlementContent())
    const id = Number(linked.settlement || 0)
    linked = {}
    await list()
    if (Number.isSafeInteger(id) && id > 0) await show(id)
  })
})
</script>

<template>
  <view class="screen">
    <view class="hero">
      <text class="eyebrow">SOLOOPS · SETTLEMENTS</text>
      <text class="title">结算周期，回款有据。</text>
      <text class="muted"
        >按原账单登记周期，逐笔回读平台记载与卖家到账声明。</text
      >
    </view>
    <view class="card">
      <text class="hint"
        >平台记载与人工到账分别保留依据；一对一同币种才计算差额。文件覆盖、期初期末余额与银行证据未知，不计算可提现余额或净利润。</text
      >
      <button :disabled="busy" @tap="openLink('/statements')">
        账单与费用核对
      </button>
      <button
        :disabled="busy"
        @tap="openLink('/imports', { kind: 'statements' })"
      >
        导入或查看账单批次
      </button>
    </view>
    <text v-if="error" class="error">{{ error }}</text>
    <text v-if="notice" class="hint">{{ notice }}</text>
    <view class="card">
      <text class="section-title">登记范围</text>
      <picker
        :range="['用户导入', '合成测试']"
        :value="identities.indexOf(scope.data_identity)"
        :disabled="busy"
        @change="pickIdentity"
        ><view class="select"
          >身份：{{
            scope.data_identity === 'synthetic' ? '合成测试' : '用户导入'
          }}</view
        ></picker
      >
      <picker
        :range="channels"
        :value="channels.indexOf(scope.channel)"
        :disabled="busy"
        @change="pickChannel"
        ><view class="select">渠道：{{ scope.channel }}</view></picker
      >
      <text class="label">周期开始（含偏移，含开始）</text>
      <input
        v-model="scope.start_at"
        :disabled="busy"
        placeholder="2026-10-01T00:00:00+08:00"
      />
      <text class="label">周期结束（含偏移，不含结束）</text>
      <input
        v-model="scope.end_at"
        :disabled="busy"
        placeholder="2026-10-12T00:00:00+08:00"
      />
      <text class="label">周期显示时区（IANA）</text>
      <input
        v-model="scope.timezone"
        :disabled="busy"
        placeholder="Asia/Shanghai"
      />
      <text class="hint"
        >周期包含开始、不含结束，最多 366 天；每份登记最多 1000 行原账单、50
        笔人工到账凭据，回款与到账可晚于周期结束。</text
      >
      <button
        class="primary"
        :disabled="busy"
        :loading="busy"
        @tap="perform(() => list())"
      >
        读取结算登记
      </button>
      <button :disabled="busy || !cursor" @tap="perform(() => list(true))">
        加载更早登记
      </button>
    </view>
    <view class="card">
      <text class="section-title">已读取登记（{{ records.length }}）</text>
      <text v-if="statusSummary" class="hint">{{ statusSummary }}</text>
      <text v-if="!records.length" class="muted"
        >没有符合当前范围的登记记录。请调整范围或先导入渠道账单。</text
      >
      <button
        v-for="item in records"
        :key="item.id"
        :disabled="busy"
        @tap="perform(() => show(item.id))"
      >
        登记 #{{ item.id }} ·
        {{ settlementStatuses[item.status] || '状态未知' }} · v{{
          item.version
        }}
        · {{ supportTime(item.created_at, scope.timezone) }}
      </button>
      <button class="primary" :disabled="busy" @tap="begin()">
        新建结算登记
      </button>
      <button v-if="pending" class="danger" :disabled="busy" @tap="save(true)">
        回查原保存请求（不更换 request_id）
      </button>
      <button
        v-if="pendingControl"
        class="danger"
        :disabled="busy"
        @tap="control(true)"
      >
        回查原处理请求（不更换 request_id）
      </button>
      <text v-if="pending" class="hint"
        >上次保存结果未知，已冻结请求标识；再次提交只会返回同一结果。</text
      >
      <text v-if="pendingControl" class="hint"
        >上次撤销/清除结果未知，已冻结请求标识与版本；再次提交只会返回同一结果。</text
      >
    </view>
    <view v-if="saved" class="card">
      <view class="row">
        <text class="section-title">结算登记 #{{ saved.id }}</text>
        <text class="badge">{{
          settlementStatuses[saved.status] || '状态未知'
        }}</text>
      </view>
      <text class="hint"
        >版本 {{ saved.version }} · 正文版本 {{ saved.content_version }} · 创建
        {{ supportTime(saved.created_at, scope.timezone) }} · 身份
        {{ saved.data_identity }} / {{ saved.channel }}</text
      >
      <text class="hint"
        >有效表示保存后来源未变；银行到账与完整结算仍待核实。</text
      >
      <template v-if="saved.snapshot">
        <text class="section-title"
          >正文 v{{ shownVersion }} · 来源版本
          {{ saved.snapshot.source_revision }}</text
        >
        <text class="hint"
          >周期
          {{
            supportTime(
              saved.snapshot.scope.start_at,
              saved.snapshot.scope.timezone,
            )
          }}
          至
          {{
            supportTime(
              saved.snapshot.scope.end_at,
              saved.snapshot.scope.timezone,
            )
          }}（结束不含，{{ saved.snapshot.scope.timezone }}）</text
        >
        <text
          >原账单号 {{ saved.snapshot.content.statement_id }} ·
          {{ saved.snapshot.content.note }}</text
        >
        <text class="hint"
          >计算于
          {{
            supportTime(
              saved.snapshot.calculated_at,
              saved.snapshot.scope.timezone,
            )
          }}</text
        >
        <button
          v-if="isCurrentVersion(saved, shownVersion)"
          :disabled="busy"
          @tap="begin(saved)"
        >
          修订并重新核对
        </button>
      </template>
      <text v-else class="muted"
        >正文及全部历史依据已清除，仅保留范围、状态与审计。</text
      >
      <button :disabled="busy" @tap="readCurrent">
        回读当前账单与凭据（不更新历史）
      </button>
      <button :disabled="busy" @tap="perform(() => list())">刷新列表</button>
    </view>
    <view v-if="saved?.snapshot" class="card">
      <text class="section-title">平台与人工金额</text>
      <text
        v-for="total in snapshotTotals(saved.snapshot)"
        :key="`${total.currency}-${total.entry_type}`"
        >{{ total.currency }} · {{ statLabel(total.entry_type) }}：
        {{ trimmedAmount(total.amount) }} （{{ total.count }} 笔）</text
      >
      <text class="section-title">回款比对</text>
      <text v-if="!saved.snapshot.comparisons.length" class="muted"
        >当前依据中没有平台回款行或人工到账凭据。</text
      >
      <view
        v-for="(row, index) in saved.snapshot.comparisons"
        :key="`${row.payout_ref}-${index}`"
        class="record"
      >
        <text
          >{{ row.payout_ref || '（缺少凭据号）' }} ·
          {{ payoutStatuses[row.status] || row.status }}</text
        >
        <text class="hint"
          >账单行 {{ row.statement_ids.join('、') || '无' }} · 人工序号
          {{ row.receipt_indexes.map((i) => i + 1).join('、') || '无' }} · 差额
          {{ trimmedAmount(row.difference) }}</text
        >
      </view>
      <text v-if="saved.snapshot.outside_cycle_ids.length" class="error"
        >周期外非回款行
        {{ saved.snapshot.outside_cycle_ids.length }} 行，请核实归属。</text
      >
      <text class="section-title">结算口径</text>
      <text v-for="check in saved.snapshot.checks" :key="check" class="hint">{{
        check
      }}</text>
      <text class="hint"
        >覆盖状态 {{ saved.snapshot.coverage_status }} · 余额状态
        {{ saved.snapshot.balance_status }} · 银行证据
        {{ saved.snapshot.bank_status }}</text
      >
    </view>
    <view v-if="saved?.snapshot" class="card">
      <text class="section-title"
        >账单行（{{ saved.snapshot.statements.length }}）</text
      >
      <text v-if="!saved.snapshot.statements.length" class="muted"
        >该原账单号在当前来源下没有明细行。</text
      >
      <view
        v-for="(line, index) in saved.snapshot.statements"
        :key="line.id"
        class="record"
      >
        <text
          >{{ index + 1 }}.
          {{ statEntryTypes[line.entry_type] || line.entry_type }} ·
          {{ line.currency }} {{ trimmedAmount(line.amount) }}</text
        >
        <text class="hint"
          >账单 {{ line.statement_id }} / 行 {{ line.line_id }} · 发生
          {{
            supportTime(line.occurred_at, saved.snapshot.scope.timezone)
          }}</text
        >
        <text v-if="line.evidence_ref || line.settlement_id" class="hint"
          >凭据 {{ line.evidence_ref || '无' }} · 原结算批号
          {{ line.settlement_id || '无' }}</text
        >
        <SourceList :sources="[line.source]" :shop-id="saved.shop_id" />
      </view>
    </view>
    <view v-if="saved?.history.length" class="card">
      <text class="section-title">登记历史（{{ saved.history.length }}）</text>
      <view v-for="entry in saved.history" :key="entry.version" class="record">
        <text>{{ historyLabel(entry) }}</text>
        <button
          v-if="entry.has_content"
          :disabled="busy"
          @tap="perform(() => show(saved!.id, entry.version))"
        >
          读取 v{{ entry.version }} 依据
        </button>
      </view>
    </view>
    <view v-if="readBack" class="card">
      <text class="section-title">当前依据回读 · 尚未重新确认</text>
      <text class="hint"
        >沿用最近保存的人工声明，重新读取平台账单；本次读取不会更新历史登记。</text
      >
      <text
        v-for="total in snapshotTotals(readBack.snapshot)"
        :key="`rb-${total.currency}-${total.entry_type}`"
        >{{ total.currency }} · {{ statLabel(total.entry_type) }}：
        {{ trimmedAmount(total.amount) }} （{{ total.count }} 笔）</text
      >
      <text
        v-for="(row, index) in readBack.snapshot.comparisons"
        :key="`rbc-${index}`"
        >{{ row.payout_ref || '（缺少凭据号）' }} ·
        {{ payoutStatuses[row.status] || row.status }}</text
      >
    </view>
    <view v-if="editing.open" class="card">
      <text class="section-title">{{
        editing.id ? `修订结算登记 #${editing.id}` : '新建周期与人工到账'
      }}</text>
      <text class="hint"
        >本次周期
        {{ supportTime(editing.scope.start_at, editing.scope.timezone) }} 至
        {{
          supportTime(editing.scope.end_at, editing.scope.timezone)
        }}（结束不含，{{ editing.scope.timezone }}）</text
      >
      <text class="label">登记周期开始（含偏移）</text>
      <input v-model="editing.scope.start_at" :disabled="busy" />
      <text class="label">登记周期结束（含偏移）</text>
      <input v-model="editing.scope.end_at" :disabled="busy" />
      <text class="label">周期时区（IANA）</text>
      <input v-model="editing.scope.timezone" :disabled="busy" />
      <text class="label">原账单号（区分大小写，按完整编号关联）</text>
      <input v-model="content.statement_id" :maxlength="120" :disabled="busy" />
      <text class="label">周期依据与核对说明</text>
      <textarea
        v-model="content.note"
        :maxlength="1000"
        :disabled="busy"
        placeholder="说明该原账单号的周期来源与核对过程，不写客户个人信息"
      />
      <text class="label"
        >人工到账凭据（{{ content.receipts.length }}/{{ maxReceipts }}）</text
      >
      <text class="hint"
        >填写可回查的凭据编号、到账金额与时间及核验说明；未登记只表示缺少本地凭据，不代表尚未到账。</text
      >
      <view
        v-for="(item, index) in content.receipts"
        :key="`receipt-${index}`"
        class="record"
      >
        <text class="section-title">{{ receiptLabel(index) }}</text>
        <text class="label">平台回款凭据号 {{ index + 1 }}</text>
        <input v-model="item.payout_ref" :maxlength="120" :disabled="busy" />
        <text class="label">人工到账凭据号 {{ index + 1 }}</text>
        <input v-model="item.receipt_ref" :maxlength="120" :disabled="busy" />
        <text class="label">到账金额（Decimal 字符串）{{ index + 1 }}</text>
        <input v-model="item.amount" :disabled="busy" placeholder="1200.50" />
        <text class="label">到账币种 {{ index + 1 }}（不换汇）</text>
        <input v-model="item.currency" :maxlength="3" :disabled="busy" />
        <text class="label">到账时间（含偏移）{{ index + 1 }}</text>
        <input
          v-model="item.received_at"
          :disabled="busy"
          placeholder="2026-10-12T09:30:00+08:00"
        />
        <text class="label">到账显示时区 {{ index + 1 }}</text>
        <input v-model="item.timezone" :disabled="busy" />
        <text class="label">凭据核验说明 {{ index + 1 }}</text>
        <textarea v-model="item.note" :maxlength="500" :disabled="busy" />
        <button class="danger" :disabled="busy" @tap="removeReceipt(index)">
          移除人工凭据 {{ index + 1 }}
        </button>
      </view>
      <button
        :disabled="busy || content.receipts.length >= maxReceipts"
        @tap="addReceipt"
      >
        添加人工到账凭据
      </button>
      <text class="hint"
        >编辑内容会清除未确认的预览；保存前必须重新预览并勾选确认。</text
      >
      <button class="primary" :disabled="busy" @tap="inspect">
        预览周期与回款
      </button>
      <button
        :disabled="busy"
        @tap="begin(editing.id && saved?.id === editing.id ? saved : undefined)"
      >
        放弃编辑并重新开始
      </button>
    </view>
    <view v-if="preview" class="card">
      <text class="section-title">预览 · 尚未保存</text>
      <text class="hint"
        >预览哈希 {{ preview.preview_hash.slice(0, 12) }}… · 来源版本
        {{ preview.snapshot.source_revision }} · 计算于
        {{
          supportTime(
            preview.snapshot.calculated_at,
            preview.snapshot.scope.timezone,
          )
        }}</text
      >
      <text
        v-for="total in snapshotTotals(preview.snapshot)"
        :key="`pv-${total.currency}-${total.entry_type}`"
        >{{ total.currency }} · {{ statLabel(total.entry_type) }}：
        {{ trimmedAmount(total.amount) }} （{{ total.count }} 笔）</text
      >
      <text
        v-for="(row, index) in preview.snapshot.comparisons"
        :key="`pc-${index}`"
        >{{ row.payout_ref || '（缺少凭据号）' }} ·
        {{ payoutStatuses[row.status] || row.status }} · 差额
        {{ trimmedAmount(row.difference) }}</text
      >
      <checkbox-group @change="toggleConfirmed">
        <label class="label"
          ><checkbox
            value="confirm"
            :checked="confirmed"
            :disabled="busy"
          />我已核对周期、平台来源与人工到账凭据，确认保存本地登记</label
        >
      </checkbox-group>
      <button class="primary" :disabled="busy || !confirmed" @tap="save()">
        保存结算登记
      </button>
    </view>
    <view v-if="saved && saved.status !== 'cleared'" class="card">
      <text class="section-title">登记处理</text>
      <text class="hint"
        >撤销会释放账单及凭据编号占用并保留历史；清除会擦除这份登记的全部历史正文，无法恢复。</text
      >
      <text v-if="!actions.length" class="muted"
        >当前状态没有可用的登记处理动作。</text
      >
      <template v-else>
        <picker
          :range="actions.map((action) => controls[action])"
          :value="Math.max(0, actions.indexOf(controlAction))"
          :disabled="busy"
          @change="
            controlAction =
              actions[Number(($event.detail.value as string) || 0)] ||
              'withdraw'
          "
          ><view class="select"
            >处理：{{ controls[controlAction] }}</view
          ></picker
        >
        <checkbox-group @change="toggleControl">
          <label class="label"
            ><checkbox
              value="control"
              :checked="controlConfirmed"
              :disabled="busy"
            />我确认处理此版本登记及上述影响</label
          >
        </checkbox-group>
        <button
          class="danger"
          :disabled="busy || !controlConfirmed"
          @tap="control()"
        >
          确认处理登记
        </button>
      </template>
    </view>
    <view v-if="saved && !canEdit(saved)" class="card">
      <text class="hint"
        >已撤销或已清除的登记不提供修订；请新建登记后重新核对。</text
      >
    </view>
  </view>
</template>
