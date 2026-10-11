<template>
  <PageShell
    title="测试外发管理"
    subtitle="受控 R2 测试外发：逐份摘要审阅全文后最多提交一封邮件；系统不会自动重发。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load"
  >
    <text class="warn">
      本页只做界面与接口联调，不自动外发；真实提交必须具备有效的通道验证、当前审批与明确的人工确认。
    </text>
    <FactLine label="所属店铺" :value="shopName" />
    <FactLine label="业务时区" :value="zone" />

    <text class="section-title">摘要范围</text>
    <view class="field">
      <text class="field__label">摘要数据身份</text>
      <picker mode="selector" :range="identityOptions" range-key="label" :value="identityIndex" @change="identity = identityOptions[Number(pickerValue($event))]?.key ?? 'user_import'">
        <view class="field__picker">{{ labelOf(importIdentities, identity) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">摘要来源渠道</text>
      <picker mode="selector" :range="channelOptions" range-key="label" :value="channelIndex" @change="channel = channelOptions[Number(pickerValue($event))]?.key ?? 'generic'">
        <view class="field__picker">{{ labelOf(importChannels, channel) }}</view>
      </picker>
    </view>
    <view class="row">
      <ActionButton label="刷新通道与记录" variant="primary" :disabled="busy" @tap="load" />
    </view>
    <text v-if="uncertain" class="warn">操作结果待回读，请刷新通道后继续。</text>

    <text class="section-title">发送通道</text>
    <template v-if="channelInfo !== null">
      <FactLine label="配置" :value="channelInfo.configured === true ? '已配置' : '尚未配置'" />
      <FactLine label="通道" :value="channelInfo.provider" />
      <FactLine label="状态" :value="labelOf(mailLabels, channelInfo.status)" />
      <FactLine label="发件地址" :value="channelInfo.sender" />
      <FactLine label="测试收件地址" :value="channelInfo.recipient" />
      <FactLine label="验证有效期" :value="channelInfo.verification_expires_at" :zone="zone" />
      <FactLine label="完成验证时间" :value="channelInfo.verified_at" :zone="zone" />
      <FactLine label="通道回执" :value="channelInfo.receipt_id" />
      <text class="hint">由部署者为当前账号与店铺配置发送通道、凭据和测试收件邮箱。</text>
      <view class="row">
        <ActionButton label="连接并请求验证邮件" :disabled="busy || !channelInfo.configured" @tap="connectChannel" />
        <ActionButton v-if="channelInfo.id !== null && channelInfo.id !== undefined" label="撤销通道" :disabled="busy" @tap="revokeChannel" />
      </view>
      <view class="field">
        <text class="field__label">邮箱验证码（8 位）</text>
        <input class="field__input" :value="verifyCode" :disabled="busy" @input="verifyCode = inputValue($event)" />
      </view>
      <ActionButton
        label="验证测试邮箱"
        :disabled="busy || channelInfo.id === null || channelInfo.id === undefined"
        @tap="verifyChannel"
      />
      <FactLine label="验证邮件主题" :value="channelInfo.verification_subject" />
      <text class="hint">验证邮件模板：{{ factText(channelInfo.verification_template) }}</text>
      <text class="hint">
        验证码邮件由通道服务发出，仅用于确认测试收件邮箱可达；未配置或未验证时不得提交业务邮件。
      </text>
    </template>
    <text v-else class="hint">尚未读取到通道信息，请刷新。</text>

    <text class="section-title">创建待审摘要</text>
    <view class="field">
      <text class="field__label">当前来源的运营检查</text>
      <picker mode="selector" :range="runOptions" range-key="label" :value="runIndex" @change="runIndex = Number(pickerValue($event))">
        <view class="field__picker">{{ runOptions[runIndex]?.label ?? '暂无可选检查' }}</view>
      </picker>
    </view>
    <view class="row">
      <ActionButton label="回读选中检查与依据" :disabled="busy || selectedRun === null" @tap="inspectRun" />
    </view>
    <FactLine v-if="selectedRun" label="检查状态 / 来源" :value="`${selectedRun.status} / ${selectedRun.source_status}`" />
    <FactLine v-if="selectedRun" label="检查时间" :value="selectedRun.created_at" :zone="zone" />
    <view class="field">
      <text class="field__label">收件邮箱</text>
      <input class="field__input" :value="recipient" :disabled="busy" @input="recipient = inputValue($event)" />
    </view>
    <ActionButton label="创建摘要并审阅全文" block :disabled="busy || selectedRun === null" @tap="createMessage" />

    <text class="section-title">发送记录</text>
    <view v-if="messages.length === 0 && !busy" class="card">
      <text class="hint">尚无发送记录。创建摘要后可在本页审阅全文与审批。</text>
    </view>
    <view v-for="item in messages" :key="item.id" class="card">
      <text class="card__title" @tap="openMessage(item.id)">
        #{{ item.id }} · {{ item.subject === null || item.subject === undefined ? '正文已清除' : item.subject }}
      </text>
      <text class="hint">
        {{ labelOf(mailLabels, item.status) }} · 来源{{ labelOf(mailLabels, item.source_status) }} ·
        通道{{ labelOf(mailLabels, item.channel_status) }} · 内容版本 {{ item.version }}
      </text>
      <text class="hint">{{ item.recipient }} · {{ businessTimeText(item.created_at, zone) }}</text>
      <ActionButton label="打开摘要" :disabled="busy" @tap="openMessage(item.id)" />
    </view>
    <ActionButton v-if="nextBeforeId !== null" label="加载更多发送记录" :disabled="busy" @tap="loadMoreMessages" />

    <template v-if="mail !== null">
      <text class="section-title">外发摘要 #{{ mail.id }}</text>
      <view class="row">
        <ActionButton label="回读当前发送记录" :disabled="busy" @tap="openMessage(mail.id)" />
      </view>
      <text v-if="mustRead" class="warn">请先回读状态。提交结果未知时使用回执核对，系统不会自动重发。</text>
      <FactLine label="状态" :value="labelOf(mailLabels, mail.status)" />
      <FactLine label="来源 / 通道" :value="`${labelOf(mailLabels, mail.source_status)} / ${labelOf(mailLabels, mail.channel_status)}`" />
      <FactLine label="发件人" :value="mail.sender" />
      <FactLine label="收件人" :value="mail.recipient" />
      <FactLine label="内容版本" :value="mail.version" />
      <FactLine label="风险等级 / 提交上限" :value="`${mail.risk} / ${mail.max_submissions}`" />
      <FactLine label="来源运营检查" :value="mail.run_id" />
      <ActionButton label="查看来源运营检查" :disabled="busy" @tap="openPage('/pages/agent/index')" />
      <text class="hint">
        每份摘要最多提交一封邮件。批准绑定当前地址、全文与来源；邮件提交后无法撤回。通道费用依服务配置而定。
      </text>
      <FactLine label="内容校验摘要" :value="mail.content_hash" />

      <template v-if="mail.subject !== null || mail.body !== null">
        <text class="section-title">邮件全文</text>
        <FactLine label="主题" :value="mail.subject" />
        <text class="hint">正文：{{ factText(mail.body) }}</text>
      </template>
      <text v-else class="warn">来源正文已清除，提交状态和必要审计仍保留。</text>

      <view class="row">
        <ActionButton :label="editing ? '取消编辑' : '编辑主题与全文'" :disabled="busy || lockedMail" @tap="toggleEdit" />
        <ActionButton label="拒绝此发送" :disabled="busy || lockedMail" @tap="rejectMail" />
      </view>
      <template v-if="editing">
        <view class="field">
          <text class="field__label">邮件主题</text>
          <input class="field__input" :value="subject" :disabled="busy" @input="subject = inputValue($event)" />
        </view>
        <view class="field">
          <text class="field__label">邮件全文</text>
          <textarea class="field__input" :value="body" :disabled="busy" @input="body = inputValue($event)" />
        </view>
        <text class="hint">保存正文后，已有审批会失效。</text>
        <ActionButton label="保存正文版本" variant="primary" :disabled="busy" @tap="saveContent" />
      </template>

      <text class="section-title">审批与授权</text>
      <view v-if="activeApproval !== null" class="card">
        <text class="card__title">有效审批</text>
        <FactLine label="审批 / 方式" :value="`#${activeApproval.id} · ${activeApproval.mode === 'once' ? '单次批准' : '预授权'}`" />
        <FactLine label="限用次数 / 已用" :value="`${activeApproval.max_uses} / ${activeApproval.used_count}`" />
        <FactLine label="到期" :value="activeApproval.expires_at" :zone="zone" />
      </view>
      <text v-else class="hint">当前没有有效审批；提交前必须先保存单次批准或创建限一次预授权。</text>
      <view class="field">
        <text class="field__label">预授权有效小时（1–24）</text>
        <input class="field__input" type="number" :value="validHours" :disabled="busy || lockedMail" @input="validHours = inputValue($event)" />
      </view>
      <view class="card" @tap="approveConfirmed = !approveConfirmed">
        <text class="chip" :class="{ 'chip--active': approveConfirmed }">
          {{ approveConfirmed ? '已审阅' : '未审阅' }} · 已审阅地址与完整正文，确认一次邮件提交及通道费用
        </text>
      </view>
      <view class="row">
        <ActionButton label="保存单次批准" :disabled="busy || lockedMail || !approveConfirmed" @tap="approve('once')" />
        <ActionButton label="创建限一次预授权" :disabled="busy || lockedMail || !approveConfirmed" @tap="approve('preauthorized')" />
        <ActionButton
          v-if="activeApproval !== null"
          label="按有效授权提交一次"
          variant="primary"
          :disabled="busy || lockedMail || activeApproval === null"
          @tap="sendMail"
        />
        <ActionButton v-if="activeApproval !== null" label="撤销此授权" :disabled="busy" @tap="revokeApproval" />
      </view>

      <text class="section-title">提交与回执</text>
      <FactLine label="提交时间" :value="mail.dispatch_at" :zone="zone" />
      <FactLine label="通道回执" :value="mail.receipt_id" />
      <FactLine label="通道事件" :value="labelOf(mailLabels, mail.provider_event)" />
      <FactLine label="上次回查时间" :value="mail.checked_at" :zone="zone" />
      <text class="hint">
        SMTP 不提供通道回执查询。请核对收件箱或垃圾箱中的地址、主题、全文与 Message-ID，再填写实际收件证据。
        通道接受或报告送达仍需核实实际收件。
      </text>
      <view class="field">
        <text class="field__label">通道后台邮件 ID（可选，UUID）</text>
        <input class="field__input" :value="receiptQuery" :disabled="busy" @input="receiptQuery = inputValue($event)" />
      </view>
      <ActionButton label="只读回查发送结果" :disabled="busy || mail.dispatch_at === null" @tap="reconcile" />
      <view class="field">
        <text class="field__label">实际收件证据</text>
        <textarea class="field__input" :value="receiptEvidence" :disabled="busy" @input="receiptEvidence = inputValue($event)" />
      </view>
      <view class="card" @tap="receiptConfirmed = !receiptConfirmed">
        <text class="chip" :class="{ 'chip--active': receiptConfirmed }">
          {{ receiptConfirmed ? '已核对' : '未核对' }} · 已核对实际收件，此项为人工证据声明
        </text>
      </view>
      <ActionButton
        label="记录人工收件证据"
        block
        :disabled="busy || !receiptConfirmed"
        @tap="recordReceipt"
      />
      <FactLine label="人工收件声明时间" :value="mail.received_at" :zone="zone" />
      <FactLine label="收件证据" :value="mail.receipt_evidence" />

      <text class="section-title">审批与消耗历史</text>
      <view v-for="approval in mail.approvals ?? []" :key="approval.id" class="card">
        <text class="card__title">#{{ approval.id }} · {{ approval.mode === 'once' ? '单次批准' : '预授权' }} · {{ labelOf(mailLabels, approval.status) }}</text>
        <text class="hint">
          已用 {{ approval.used_count }} / {{ approval.max_uses }} 次
        </text>
        <text class="hint">创建 {{ businessTimeText(approval.created_at, zone) }} · 到期 {{ businessTimeText(approval.expires_at, zone) }}</text>
      </view>
      <text v-if="(mail.approvals ?? []).length === 0" class="hint">尚无审批记录。</text>
    </template>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 受控测试外发：通道状态、运营摘要、邮件全文与内容指纹、编辑/审批/限次授权、
 * 单次提交、回执回查与人工收件证据。本页只做界面与接口联调，不自动外发。
 * 接口（来自 contracts/ui-contract.json 的 r2.outbound 与后端 operations 路由）：
 *   GET   /api/shops/{shop_id}/outbound/channel
 *   POST  /api/shops/{shop_id}/outbound/channel/connect
 *   POST  /api/shops/{shop_id}/outbound/channel/{channel_id}/verify
 *   POST  /api/shops/{shop_id}/outbound/channel/{channel_id}/revoke
 *   GET   /api/shops/{shop_id}/outbound/messages       POST /api/shops/{shop_id}/outbound/messages
 *   GET   /api/shops/{shop_id}/outbound/messages/{message_id}
 *   PATCH /api/shops/{shop_id}/outbound/messages/{message_id}
 *   POST  /api/shops/{shop_id}/outbound/messages/{message_id}/approve
 *   POST  /api/shops/{shop_id}/outbound/messages/{message_id}/approvals/{approval_id}/revoke
 *   POST  /api/shops/{shop_id}/outbound/messages/{message_id}/reject
 *   POST  /api/shops/{shop_id}/outbound/messages/{message_id}/send
 *   POST  /api/shops/{shop_id}/outbound/messages/{message_id}/reconcile
 *   POST  /api/shops/{shop_id}/outbound/messages/{message_id}/receipt
 *   GET   /api/shops/{shop_id}/operations/runs        （选择来源运营检查）
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import ActionButton from '../../ui/ActionButton.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import { ApiError, apiGet, apiPost, apiRequest, asObject, asRows } from '../../core/api'
import { businessTimeText, factText } from '../../core/format'
import { importChannels, importIdentities, labelOf } from '../../core/labels'
import { openPage } from '../../core/links'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

/** 通道、摘要、审批与回执状态标签：与 Flutter outbound_page.dart 的 mailLabels 一致。 */
const mailLabels: Record<string, string> = {
  not_configured: '未配置',
  disconnected: '尚未连接',
  verifying: '等待邮箱验证码',
  active: '已验证 / 有效',
  configuration_changed: '配置已变化',
  domain_unverified: '发送域未验证',
  sender_unverified: '发送账号验证未通过',
  smtp_accepted: 'SMTP 已接受',
  expired: '已过期',
  locked: '验证次数用尽',
  revoked: '已撤销',
  draft: '等待审批',
  sending: '提交中',
  unknown: '结果未知，请回查',
  accepted: '通道已接受',
  rejected: '已拒绝',
  cancelled: '已取消',
  used: '已消耗',
  invalidated: '已失效',
  channel_unavailable: '通道不可用',
  current: '当前来源',
  stale: '来源已变化',
  cleared: '正文已清除',
  submitted: '已取得回执',
  sent: '通道已发出',
  delivered: '通道报告送达',
  bounced: '退信',
  failed: '发送失败',
  complained: '投诉',
  delivery_delayed: '投递延迟',
}

interface ChannelOutput {
  configured: boolean
  provider: string
  id?: number | null
  status: string
  sender: string
  recipient: string
  receipt_id?: string | null
  verified_at?: string | null
  verification_expires_at?: string | null
  verification_subject: string
  verification_template: string
}

interface ApprovalOutput {
  id: number
  mode: string
  status: string
  max_uses: number
  used_count: number
  expires_at: string
  created_at: string
}

interface MailOutput {
  id: number
  shop_id: number
  channel_id: number
  provider: string
  smtp_message_id?: string | null
  run_id: number
  sender: string
  recipient: string
  subject?: string | null
  body?: string | null
  content_hash: string
  status: string
  source_status: string
  channel_status: string
  version: number
  risk: string
  max_submissions: number
  dispatch_at?: string | null
  receipt_id?: string | null
  provider_event: string
  checked_at?: string | null
  received_at?: string | null
  receipt_evidence?: string | null
  created_at: string
  approvals: ApprovalOutput[]
}

interface OperationRun {
  id: number
  status: string
  source_status: string
  created_at: string
}

const identity = ref('user_import')
const channel = ref('generic')
const channelInfo = ref<ChannelOutput | null>(null)
const verifyCode = ref('')
const runs = ref<OperationRun[]>([])
const runIndex = ref(0)
const recipient = ref('')
const messages = ref<MailOutput[]>([])
const nextBeforeId = ref<number | null>(null)
const mail = ref<MailOutput | null>(null)
const editing = ref(false)
const subject = ref('')
const body = ref('')
const approveConfirmed = ref(false)
const validHours = ref('1')
const receiptQuery = ref('')
const receiptEvidence = ref('')
const receiptConfirmed = ref(false)
const uncertain = ref(false)
const busy = ref(false)
const error = ref('')
const successText = ref('')
const ready = ref(false)

const zone = computed(() => shopTimezone())
const shopName = computed(() => state.shops.find((shop) => shop.id === state.shopId)?.name ?? '未知')
const identityOptions = computed(() => Object.entries(importIdentities).map(([key, label]) => ({ key, label })))
const identityIndex = computed(() => Math.max(0, Object.keys(importIdentities).indexOf(identity.value)))
const channelOptions = computed(() => Object.entries(importChannels).map(([key, label]) => ({ key, label })))
const channelIndex = computed(() => Math.max(0, Object.keys(importChannels).indexOf(channel.value)))
const runOptions = computed(() => runs.value.map((run) => ({
  key: `${run.id}`,
  label: `检查 #${run.id} · ${labelOf(mailLabels, run.status)} · ${run.created_at}`,
})))
const selectedRun = computed<OperationRun | null>(() => runs.value[runIndex.value] ?? null)
/** 正文已提交或已失效时锁定编辑与审批动作。 */
const lockedMail = computed(() => {
  const current = mail.value
  if (current === null) return true
  return current.status !== 'draft' || current.source_status !== 'current'
})
/** 结果未知或提交中必须先回读状态。 */
const mustRead = computed(() => {
  const current = mail.value
  if (current === null) return false
  return current.status === 'sending' || current.status === 'unknown'
})
const activeApproval = computed<ApprovalOutput | null>(() => {
  const current = mail.value
  if (current === null) return null
  return (current.approvals ?? []).find((item) => item.status === 'active') ?? null
})

function success(text: string): void {
  successText.value = text
  void Taro.showToast({ title: text, icon: 'none' })
}

/** 写操作：断线/超时提示“结果未知，请回读”，不推断成功。 */
async function writeAction(action: () => Promise<void>, done: string, hint: string): Promise<void> {
  let unknown = false
  const message = await perform(async () => {
    try {
      await action()
    } catch (caught) {
      unknown = caught instanceof ApiError && caught.kind === 'network_unknown'
      throw caught
    }
  })
  if (message === '') {
    success(done)
    return
  }
  error.value = unknown ? `${message} 结果未知，请回读${hint}核对后再决定。` : message
  if (unknown) uncertain.value = true
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  await load()
})

async function load(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    channelInfo.value = asObject<ChannelOutput>(await apiGet(shopPath('/outbound/channel')))
    const page = asObject<{ items: MailOutput[]; next_before_id: number | null }>(
      await apiGet(shopPath('/outbound/messages')),
    )
    messages.value = asRows<MailOutput>(page?.items)
    nextBeforeId.value = page?.next_before_id ?? null
    const runValue = await apiGet<OperationRun[] | { items?: OperationRun[] }>(shopPath('/operations/runs'))
    runs.value = Array.isArray(runValue) ? asRows<OperationRun>(runValue) : asRows<OperationRun>(runValue?.items)
    if (runIndex.value >= runs.value.length) runIndex.value = 0
    if (recipient.value === '' && channelInfo.value !== null) recipient.value = channelInfo.value.recipient
    uncertain.value = false
  })
  error.value = message
}

async function loadMoreMessages(): Promise<void> {
  const cursor = nextBeforeId.value
  if (cursor === null) return
  const message = await perform(async () => {
    const page = asObject<{ items: MailOutput[]; next_before_id: number | null }>(
      await apiGet(shopPath('/outbound/messages'), { before_id: cursor }),
    )
    const incoming = asRows<MailOutput>(page?.items)
    messages.value = [
      ...messages.value,
      ...incoming.filter((item) => !messages.value.some((old) => old.id === item.id)),
    ]
    nextBeforeId.value = page?.next_before_id ?? null
  })
  error.value = message
}

async function connectChannel(): Promise<void> {
  const modal = await Taro.showModal({
    title: '连接发送通道',
    content: '确认向上述测试邮箱提交一封验证邮件。此操作由部署者配置的通道发出，请核对地址后继续。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    channelInfo.value = asObject<ChannelOutput>(
      await apiPost(shopPath('/outbound/channel/connect'), { confirmed: true }),
    )
    await load()
  }, '已请求验证邮件，请到测试邮箱读取 8 位验证码。', '发送通道')
}

async function verifyChannel(): Promise<void> {
  const current = channelInfo.value
  if (current === null || current.id === null || current.id === undefined) return
  await writeAction(async () => {
    if (!/^\d{8}$/.test(verifyCode.value.trim())) throw new Error('请填写 8 位验证码。')
    channelInfo.value = asObject<ChannelOutput>(
      await apiPost(shopPath(`/outbound/channel/${current.id}/verify`), { code: verifyCode.value.trim() }),
    )
    await load()
  }, '测试邮箱验证结果已回读，请核对通道状态。', '发送通道')
}

async function revokeChannel(): Promise<void> {
  const current = channelInfo.value
  if (current === null || current.id === null || current.id === undefined) return
  const modal = await Taro.showModal({
    title: '撤销发送通道',
    content: '撤销后停止新的提交；已开始的邮件提交仍可能送达。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    channelInfo.value = asObject<ChannelOutput>(
      await apiPost(shopPath(`/outbound/channel/${current.id}/revoke`)),
    )
    await load()
  }, '通道已撤销。', '发送通道')
}

async function inspectRun(): Promise<void> {
  const run = selectedRun.value
  if (run === null) return
  success(`已选择检查 #${run.id}（${labelOf(mailLabels, run.status)}）；创建摘要时会再次校验来源时效。`)
}

async function createMessage(): Promise<void> {
  const run = selectedRun.value
  if (run === null) {
    error.value = '请选择当前来源的运营检查。'
    return
  }
  const modal = await Taro.showModal({
    title: '创建待审摘要',
    content: '将按该检查的来源与摘要正文生成一封待审邮件，收件地址为上方填写值。',
    confirmText: '创建',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    if (recipient.value.trim() === '') throw new Error('请填写收件邮箱。')
    const value = asObject<MailOutput>(
      await apiPost(shopPath('/outbound/messages'), { run_id: run.id, recipient: recipient.value.trim() }),
    )
    if (value === null) throw new Error('创建响应无法读取，请到发送记录回读核对。')
    await openMessage(value.id)
    await load()
  }, '摘要已创建，请审阅全文后再审批。', '发送记录')
}

async function openMessage(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<MailOutput>(await apiGet(shopPath(`/outbound/messages/${id}`)))
    if (value === null) throw new Error('摘要响应无法读取，请刷新重试。')
    mail.value = value
    subject.value = value.subject ?? ''
    body.value = value.body ?? ''
    editing.value = false
    approveConfirmed.value = false
    receiptConfirmed.value = false
    receiptQuery.value = ''
    receiptEvidence.value = value.receipt_evidence ?? ''
    uncertain.value = false
  })
  error.value = message
}

function toggleEdit(): void {
  if (lockedMail.value) return
  editing.value = !editing.value
}

async function saveContent(): Promise<void> {
  const current = mail.value
  if (current === null) return
  await writeAction(async () => {
    const nextSubject = subject.value.trim()
    const nextBody = body.value
    if (nextSubject === '') throw new Error('请填写邮件主题。')
    if (/[\r\n\u0000-\u001f]/.test(nextSubject)) throw new Error('主题不能包含控制字符或换行。')
    if (nextBody.trim() === '') throw new Error('请填写邮件正文。')
    if (nextBody.length > 12000) throw new Error('邮件正文最多 12000 字。')
    const value = asObject<MailOutput>(
      await apiRequest<MailOutput>(shopPath(`/outbound/messages/${current.id}`), {
        method: 'PATCH',
        body: {
          version: current.version,
          subject: nextSubject,
          body: nextBody,
        },
      }),
    )
    if (value !== null) {
      mail.value = value
      subject.value = value.subject ?? ''
      body.value = value.body ?? ''
    }
    editing.value = false
    await load()
  }, '正文版本已保存；已有审批会失效，请重新审批。', '当前发送记录')
}

async function approve(mode: 'once' | 'preauthorized'): Promise<void> {
  const current = mail.value
  if (current === null) return
  const hours = Number(validHours.value.trim())
  await writeAction(async () => {
    if (!/^\d+$/.test(validHours.value.trim()) || hours < 1 || hours > 24) {
      throw new Error('预授权有效小时须为 1–24 的整数。')
    }
    const value = asObject<MailOutput>(
      await apiPost(shopPath(`/outbound/messages/${current.id}/approve`), {
        confirmed: true,
        version: current.version,
        mode,
        valid_hours: hours,
      }),
    )
    if (value !== null) mail.value = value
    approveConfirmed.value = false
    await load()
  }, '审批已保存，请核对有效授权后提交。', '当前发送记录')
}

async function revokeApproval(): Promise<void> {
  const current = mail.value
  const approval = activeApproval.value
  if (current === null || approval === null) return
  const modal = await Taro.showModal({
    title: `撤销审批 #${approval.id}`,
    content: '撤销后不能再按此授权提交；需要重新审批。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<MailOutput>(
      await apiPost(shopPath(`/outbound/messages/${current.id}/approvals/${approval.id}/revoke`)),
    )
    if (value !== null) mail.value = value
    await load()
  }, '授权已撤销。', '当前发送记录')
}

async function rejectMail(): Promise<void> {
  const current = mail.value
  if (current === null) return
  const modal = await Taro.showModal({
    title: '拒绝此发送',
    content: '拒绝后该摘要不再提交，审计记录保留。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<MailOutput>(
      await apiPost(shopPath(`/outbound/messages/${current.id}/reject`), { version: current.version }),
    )
    if (value !== null) mail.value = value
    await load()
  }, '该摘要已拒绝发送。', '当前发送记录')
}

async function sendMail(): Promise<void> {
  const current = mail.value
  const approval = activeApproval.value
  if (current === null || approval === null) return
  const modal = await Taro.showModal({
    title: '按有效授权提交一次',
    content: `将向 ${current.recipient} 提交本封邮件，并消耗审批 #${approval.id}。提交后无法撤回。`,
    confirmText: '提交',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<MailOutput>(
      await apiPost(shopPath(`/outbound/messages/${current.id}/send`), {
        version: current.version,
        approval_id: approval.id,
      }),
    )
    if (value !== null) mail.value = value
    await load()
  }, '提交请求已完成，请用回执回查核对真实结果。', '当前发送记录')
}

async function reconcile(): Promise<void> {
  const current = mail.value
  if (current === null) return
  const message = await perform(async () => {
    const query = receiptQuery.value.trim()
    const value = asObject<MailOutput>(
      await apiPost(
        shopPath(`/outbound/messages/${current.id}/reconcile`),
        query === '' ? {} : { receipt_id: query },
      ),
    )
    if (value === null) throw new Error('回查响应无法读取，请稍后重试。')
    mail.value = value
  })
  if (message === '') success('已回查通道状态，请核对事件与实际收件。')
  else error.value = message
}

async function recordReceipt(): Promise<void> {
  const current = mail.value
  if (current === null) return
  await writeAction(async () => {
    const evidence = receiptEvidence.value.trim()
    if (evidence.length < 5) throw new Error('证据至少 5 字符。')
    if (evidence.length > 500) throw new Error('证据最多 500 字符。')
    const value = asObject<MailOutput>(
      await apiPost(shopPath(`/outbound/messages/${current.id}/receipt`), {
        confirmed: true,
        evidence,
      }),
    )
    if (value !== null) mail.value = value
    receiptConfirmed.value = false
    await load()
  }, '人工收件证据已记录（人工声明，不代表通道确认）。', '当前发送记录')
}
</script>
