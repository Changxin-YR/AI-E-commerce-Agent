// route: /outbound
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Taro, { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import {
  activeApproval,
  approvalHours,
  createRecipient,
  mailActions,
  mailEdit,
  mailLabel,
  receiptEvidence,
  receiptId,
  verificationCode,
  type MailChannel,
  type OutboundMail,
} from '../../services/outbound-policy'
import type { OperationRun } from '../../services/operation-types'
import { supportTime } from '../../services/support-types'
import SourceList from '../../components/SourceList.vue'

const channel = ref<MailChannel>(),
  messages = ref<OutboundMail[]>([]),
  runs = ref<OperationRun[]>([]),
  selected = ref<OutboundMail>(),
  before = ref<number | null>(null)
const busy = ref(false),
  error = ref(''),
  notice = ref(''),
  confirmConnect = ref(false),
  confirmApprove = ref(false),
  hasApproval = ref(false),
  hasReceipt = ref(false),
  unknown = ref(false)
const scope = reactive({
  data_identity: 'user_import' as 'user_import' | 'synthetic',
  channel: 'generic' as string,
})
const form = reactive({
  run_id: 0,
  recipient: '',
  code: '',
  hours: 1,
  subject: '',
  body: '',
  editing: false,
  receipt: '',
  evidence: '',
})
const actions = computed(() =>
  selected.value
    ? mailActions(selected.value)
    : {
        edit: false,
        reject: false,
        approve: false,
        dispatch: false,
        revoke: false,
        reconcile: false,
        receipt: false,
      },
)
const grant = computed(() =>
  selected.value ? activeApproval(selected.value) : undefined,
)
const dirty = computed(
  () =>
    !!selected.value &&
    form.editing &&
    (form.subject !== (selected.value.subject ?? '') ||
      form.body !== (selected.value.body ?? '')),
)
const channels = ['generic', 'shopify', 'amazon', 'other']
let alive = true,
  epoch = 0,
  linked: Record<string, string> = {}
const request = scopedRequest(api, () => (alive ? epoch : null))
const base = () => `/shops/${account.shopId}/outbound`
const time = (value: string | null | undefined) =>
  value
    ? supportTime(
        value,
        account.shops.find((s) => s.id === account.shopId)?.timezone || 'UTC',
      )
    : '—'

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
    reset()
    channel.value = undefined
    messages.value = []
    runs.value = []
    selected.value = undefined
    before.value = null
    notice.value = ''
  },
  { flush: 'sync' },
)
watch(
  () => [scope.data_identity, scope.channel],
  () => {
    runs.value = []
    form.run_id = 0
    selected.value = undefined
  },
)
watch(
  () => dirty.value || hasApproval.value || hasReceipt.value || unknown.value,
  (protect) => {
    if (!alive) return
    if (protect)
      Taro.enableAlertBeforeUnload({
        message: '有未保存正文或待核对外发操作，请确认后离开。',
      })
    else Taro.disableAlertBeforeUnload()
  },
)
function reset() {
  form.recipient = ''
  form.code = ''
  form.hours = 1
  form.subject = ''
  form.body = ''
  form.editing = false
  form.receipt = ''
  form.evidence = ''
  confirmConnect.value = false
  confirmApprove.value = false
  hasApproval.value = false
  hasReceipt.value = false
}
function adopt(item: OutboundMail) {
  selected.value = item
  messages.value = [item, ...messages.value.filter((x) => x.id !== item.id)]
  form.subject = item.subject ?? ''
  form.body = item.body ?? ''
  form.editing = false
  form.receipt = ''
  form.evidence = ''
  confirmApprove.value = false
  hasReceipt.value = false
}
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
      error.value = cause instanceof Error ? cause.message : '外发操作失败。'
  } finally {
    busy.value = false
  }
}
async function load() {
  await perform(async () => {
    const shop = account.shopId
    const [connection, page, found] = await Promise.all([
      request<MailChannel>(`${base()}/channel`),
      request<{
        items: OutboundMail[]
        next_before_id: number | null
      }>(`${base()}/messages`),
      request<OperationRun[]>(
        `/shops/${shop}/operations/runs?data_identity=${scope.data_identity}&channel=${scope.channel}`,
      ),
    ])
    channel.value = connection
    messages.value = page.items
    before.value = page.next_before_id
    runs.value = found.filter((item) => item.source_status === 'current')
    form.run_id = runs.value[0]?.id ?? 0
    form.recipient = connection.recipient
    selected.value = undefined
    if (linked.mail) await read(Number(linked.mail))
    linked = {}
  })
}
async function more() {
  await perform(async () => {
    if (!before.value) return
    const page = await request<{
      items: OutboundMail[]
      next_before_id: number | null
    }>(`${base()}/messages?before_id=${before.value}`)
    messages.value = [...messages.value, ...page.items]
    before.value = page.next_before_id
  })
}
async function read(id: number) {
  if (!Number.isInteger(id) || id <= 0) throw new Error('外发记录编号无效。')
  const item = await request<OutboundMail>(`${base()}/messages/${id}`)
  adopt(item)
}
async function show(id: number) {
  await perform(async () => {
    if (dirty.value) throw new Error('请先保存或关闭正文编辑。')
    await read(id)
  })
}
async function connect() {
  await perform(async () => {
    if (!confirmConnect.value) return
    const answer = await Taro.showModal({
      title: '连接并发送验证邮件',
      content:
        '将向本人测试邮箱发送 1 封验证邮件，邮件不可撤回，可能产生通道费用。确认继续？',
    })
    if (!answer.confirm || !alive) return
    hasApproval.value = true
    channel.value = await request<MailChannel>(
      `${base()}/channel/connect`,
      'POST',
      {
        confirmed: true,
      },
    )
    hasApproval.value = false
    confirmConnect.value = false
    form.code = ''
    notice.value = '验证邮件已提交，请用本人邮箱读取 8 位验证码。'
  })
}
async function verify() {
  await perform(async () => {
    if (!channel.value?.id) return
    const code = verificationCode(form.code)
    channel.value = await request<MailChannel>(
      `${base()}/channel/${channel.value.id}/verify`,
      'POST',
      { code },
    )
    notice.value = `通道状态：${mailLabel(channel.value.status)}。`
  })
}
async function revokeChannel() {
  await perform(async () => {
    if (!channel.value?.id) return
    const id = channel.value.id
    const answer = await Taro.showModal({
      title: '撤销通道连接',
      content: '撤销后无法继续外发，已提交的邮件不受影响。确认继续？',
    })
    if (!answer.confirm || !alive || channel.value?.id !== id) return
    channel.value = await request<MailChannel>(
      `${base()}/channel/${id}/revoke`,
      'POST',
    )
    selected.value = undefined
    notice.value = '通道连接已撤销并回读。'
  })
}
async function create() {
  await perform(async () => {
    if (!form.run_id) throw new Error('请选择当前有效的运营检查。')
    const recipient = createRecipient(
      channel.value?.provider ?? '',
      form.recipient,
    )
    hasApproval.value = true
    const item = await request<OutboundMail>(`${base()}/messages`, 'POST', {
      run_id: form.run_id,
      recipient,
    })
    adopt(item)
    hasApproval.value = false
    unknown.value = false
    notice.value = '外发预览已生成并回读，请核对地址与全文。'
  })
}
async function edit() {
  await perform(async () => {
    if (!selected.value || !actions.value.edit) return
    const value = mailEdit(form.subject, form.body)
    hasApproval.value = true
    adopt(
      await request<OutboundMail>(
        `${base()}/messages/${selected.value.id}`,
        'PATCH',
        { version: selected.value.version, ...value },
      ),
    )
    hasApproval.value = false
    notice.value = '正文已保存并回读，原审批已失效。'
  })
}
async function approve(mode: 'once' | 'preauthorized') {
  await perform(async () => {
    if (!selected.value || !confirmApprove.value || !actions.value.approve)
      return
    const id = selected.value.id
    const hours = approvalHours(form.hours)
    const answer = await Taro.showModal({
      title: mode === 'once' ? '单次批准并提交' : '创建限一次预授权',
      content:
        mode === 'once'
          ? '将按当前地址与全文提交 1 封邮件，提交不可撤回。确认继续？'
          : `将创建 1 次预授权（${hours} 小时有效），不会立即提交。确认继续？`,
    })
    if (!answer.confirm || !alive || selected.value?.id !== id) return
    hasApproval.value = true
    let item = await request<OutboundMail>(
      `${base()}/messages/${id}/approve`,
      'POST',
      {
        version: selected.value.version,
        mode,
        valid_hours: hours,
        confirmed: true,
      },
    )
    if (mode === 'once') {
      const active = activeApproval(item)
      if (!active) throw new Error('审批未生效，请刷新回读后再决定。')
      item = await request<OutboundMail>(
        `${base()}/messages/${id}/send`,
        'POST',
        {
          version: item.version,
          approval_id: active.id,
        },
      )
    }
    adopt(item)
    hasApproval.value = false
    notice.value =
      mode === 'once' ? '已按单次批准提交并回读。' : '预授权已创建并回读。'
  })
}
async function dispatch() {
  await perform(async () => {
    if (!selected.value || !grant.value || !actions.value.dispatch) return
    const id = selected.value.id
    const answer = await Taro.showModal({
      title: '按有效授权提交一次',
      content: '每份摘要最多提交一次，邮件不可撤回。确认继续？',
    })
    if (!answer.confirm || !alive || selected.value?.id !== id) return
    hasApproval.value = true
    adopt(
      await request<OutboundMail>(`${base()}/messages/${id}/send`, 'POST', {
        version: selected.value.version,
        approval_id: grant.value.id,
      }),
    )
    hasApproval.value = false
  })
}
async function revokeApproval() {
  await perform(async () => {
    if (!selected.value || !grant.value) return
    const id = selected.value.id,
      approval = grant.value.id
    const answer = await Taro.showModal({
      title: '撤销此授权',
      content: '撤销只停止尚未提交的动作，已开始的提交仍可能送达。确认继续？',
    })
    if (!answer.confirm || !alive || selected.value?.id !== id) return
    adopt(
      await request<OutboundMail>(
        `${base()}/messages/${id}/approvals/${approval}/revoke`,
        'POST',
      ),
    )
  })
}
async function reject() {
  await perform(async () => {
    if (!selected.value || !actions.value.reject) return
    const id = selected.value.id
    const answer = await Taro.showModal({
      title: '拒绝此发送',
      content: '拒绝后该摘要不再外发，原始检查记录保留。确认继续？',
    })
    if (!answer.confirm || !alive || selected.value?.id !== id) return
    adopt(
      await request<OutboundMail>(`${base()}/messages/${id}/reject`, 'POST', {
        version: selected.value.version,
      }),
    )
  })
}
async function reconcile() {
  await perform(async () => {
    if (!selected.value || !actions.value.reconcile) return
    const value = receiptId(form.receipt)
    unknown.value = true
    adopt(
      await request<OutboundMail>(
        `${base()}/messages/${selected.value.id}/reconcile`,
        'POST',
        { receipt_id: value },
      ),
    )
    unknown.value = false
    notice.value = '已只读回查通道并回读记录。'
  })
}
async function attest() {
  await perform(async () => {
    if (!selected.value || !hasReceipt.value || !actions.value.receipt) return
    const value = receiptEvidence(form.evidence)
    adopt(
      await request<OutboundMail>(
        `${base()}/messages/${selected.value.id}/receipt`,
        'POST',
        { confirmed: true, evidence: value },
      ),
    )
    hasReceipt.value = false
    notice.value = '人工收件证据已记录并回读，通道状态不变。'
  })
}
function pickRun(event: unknown) {
  const index = Number((event as { detail: { value: number } }).detail.value)
  form.run_id = runs.value[index]?.id ?? 0
  selected.value = undefined
}
function pickScope(field: 'identity' | 'channel', event: unknown) {
  const value = String((event as { detail: { value: string } }).detail.value)
  if (field === 'identity')
    scope.data_identity = value as 'user_import' | 'synthetic'
  else scope.channel = value
}
useDidShow(() => {
  if (!account.session || !account.shopId) return
  void load()
})
</script>
<template>
  <view class="screen"
    ><view class="hero"
      ><text class="eyebrow">SOLOOPS · 受控测试外发</text
      ><text class="title">审阅摘要，再批准一次。</text
      ><text class="muted"
        >隔离替身通道、独立 R2 审批与人工收件证据。</text
      ></view
    >
    <text v-if="error" class="error">{{ error }}</text
    ><text v-if="notice" class="hint">{{ notice }}</text
    ><text v-if="unknown" class="error">结果未知，请刷新回读后再操作。</text>
    <view class="card"
      ><text class="section-title">检查范围</text
      ><picker
        :range="['用户导入', '合成测试']"
        :value="scope.data_identity === 'synthetic' ? 1 : 0"
        :disabled="busy"
        @change="pickScope('identity', $event)"
        ><view class="field">数据身份：{{ scope.data_identity }}</view></picker
      ><picker
        :range="['通用 / 自建表', 'Shopify', 'Amazon', '其他']"
        :value="Math.max(0, channels.indexOf(scope.channel))"
        :disabled="busy"
        @change="pickScope('channel', $event)"
        ><view class="field">来源渠道：{{ scope.channel }}</view></picker
      ><button :disabled="busy" @tap="load">刷新通道与记录</button></view
    >
    <view v-if="channel" class="card"
      ><view class="row"
        ><text class="section-title">本人测试邮箱</text
        ><text class="badge">{{ mailLabel(channel.status) }}</text></view
      ><text v-if="!channel.configured" class="hint"
        >尚未配置此店铺的外发通道。QQ
        邮箱需发件地址、客户端授权码与本人验证邮箱；Resend
        需密钥和已验证域名。</text
      ><template v-else
        ><text
          >{{ channel.provider === 'qq_smtp' ? 'QQ 邮箱' : 'Resend' }} ·
          {{ channel.sender }} → {{ channel.recipient }}</text
        ><text class="hint"
          >验证邮件只发往本人邮箱且不含经营数据；账号 24 小时最多 10
          份摘要、间隔至少 60 秒。</text
        ><template
          v-if="!['active', 'verifying', 'unknown'].includes(channel.status)"
          ><text class="label"
            >验证邮件主题：{{ channel.verification_subject }}</text
          ><text class="hint">{{ channel.verification_template }}</text
          ><checkbox-group
            @change="
              confirmConnect = Boolean(($event.detail.value || []).length)
            "
            ><label class="label"
              ><checkbox
                value="connect"
                :checked="confirmConnect"
                :disabled="busy"
              />我控制以上账号与测试邮箱，批准发送 1
              封验证邮件，理解邮件不可撤回及可能产生通道费用</label
            ></checkbox-group
          ><button
            class="primary"
            :disabled="busy || !confirmConnect"
            @tap="connect"
          >
            连接并发送验证邮件
          </button></template
        ><template v-if="['verifying', 'unknown'].includes(channel.status)"
          ><text class="label"
            >邮箱验证码（8 位数字，15 分钟有效，最多 5 次）</text
          ><input
            v-model="form.code"
            type="number"
            :maxlength="8"
            :disabled="busy"
          /><button :disabled="busy" @tap="verify">
            验证本人测试邮箱
          </button></template
        ><button
          v-if="channel.id && channel.status !== 'revoked'"
          class="danger"
          :disabled="busy"
          @tap="revokeChannel"
        >
          撤销此通道连接
        </button></template
      ></view
    >
    <view class="card"
      ><text class="section-title">准备待审摘要</text
      ><text v-if="!runs.length" class="muted"
        >当前范围暂无已保存检查，请先在巡检页生成并保存运行。</text
      ><picker
        :range="runs.map((run) => `检查 #${run.id} · ${run.source_status}`)"
        :disabled="busy || !runs.length"
        :value="
          Math.max(
            0,
            runs.findIndex((run) => run.id === form.run_id),
          )
        "
        @change="pickRun($event)"
        ><view class="field"
          >关联检查：{{ form.run_id ? `#${form.run_id}` : '未选择' }}</view
        ></picker
      ><template v-if="channel?.provider === 'qq_smtp'"
        ><text class="label">收件邮箱（默认本人邮箱）</text
        ><input
          v-model="form.recipient"
          :maxlength="254"
          :disabled="busy" /></template
      ><button
        class="primary"
        :disabled="busy || !form.run_id || channel?.status !== 'active'"
        @tap="create"
      >
        生成外发预览
      </button></view
    >
    <view class="card"
      ><text class="section-title">外发记录</text
      ><text v-if="!messages.length" class="muted">暂无外发记录。</text
      ><button
        v-for="item in messages"
        :key="item.id"
        :disabled="busy"
        @tap="show(item.id)"
      >
        #{{ item.id }} · {{ mailLabel(item.status) }} ·
        {{ mailLabel(item.source_status) }}</button
      ><button v-if="before" :disabled="busy" @tap="more">
        加载更早记录
      </button></view
    >
    <view v-if="selected" class="card"
      ><view class="row"
        ><text class="section-title">摘要 #{{ selected.id }}</text
        ><text class="badge">{{ mailLabel(selected.status) }}</text></view
      ><text class="hint"
        >关联检查 #{{ selected.run_id }} · 来源
        {{ mailLabel(selected.source_status) }} · 通道
        {{ mailLabel(selected.channel_status) }} · 版本
        {{ selected.version }}</text
      ><text
        >发件人 {{ selected.sender }} → 收件人 {{ selected.recipient }}</text
      ><text class="hint"
        >审批时原状态：尚未提交；目标动作：向上方邮箱提交 1
        封邮件。每份摘要最多提交一次，邮件不可撤回；撤销授权只停止尚未提交的动作。</text
      ><template v-if="selected.body !== null"
        ><text class="label">{{ selected.subject }}</text
        ><text class="hint">{{ selected.body }}</text
        ><text class="label">内容哈希：{{ selected.content_hash }}</text
        ><text class="hint"
          >创建于 {{ time(selected.created_at) }}（{{
            account.shops.find((s) => s.id === account.shopId)?.timezone
          }}）</text
        ></template
      ><text v-else class="hint"
        >来源内容已清除，保留提交状态与必要审计；已发出邮件不能从收件箱撤回。</text
      ><button :disabled="busy" @tap="show(selected.id)">刷新外发记录</button
      ><template v-if="actions.edit"
        ><button :disabled="busy" @tap="form.editing = !form.editing">
          {{ form.editing ? '取消修改' : '修改待发正文' }}</button
        ><button class="danger" :disabled="busy" @tap="reject">
          拒绝此发送</button
        ><template v-if="form.editing"
          ><text class="label">邮件主题</text
          ><input
            v-model="form.subject"
            :maxlength="200"
            :disabled="busy"
          /><text class="label">邮件全文</text
          ><textarea
            v-model="form.body"
            :maxlength="12000"
            :disabled="busy"
          /><text class="hint">保存修改会使已有审批失效。</text
          ><button class="primary" :disabled="busy" @tap="edit">
            保存正文
          </button></template
        ><template v-else-if="actions.approve"
          ><text class="label">预授权有效小时（1–24）</text
          ><input
            v-model.number="form.hours"
            type="number"
            :disabled="busy"
          /><text class="hint"
            >独立预授权仅适用于当前地址、全文与检查记录，限 1 次；单次批准在 10
            分钟内有效。</text
          ><checkbox-group
            @change="
              confirmApprove = Boolean(($event.detail.value || []).length)
            "
            ><label class="label"
              ><checkbox
                value="approve"
                :checked="confirmApprove"
                :disabled="busy"
              />我已核对地址和全文，确认 R2
              邮件不可撤回及可能产生通道费用</label
            ></checkbox-group
          ><button
            class="primary"
            :disabled="busy || !confirmApprove"
            @tap="approve('once')"
          >
            单次批准并提交</button
          ><button
            :disabled="busy || !confirmApprove"
            @tap="approve('preauthorized')"
          >
            创建限一次预授权
          </button></template
        ></template
      >
      <template v-if="actions.dispatch && grant"
        ><text
          >有效审批 #{{ grant.id }} · 剩余
          {{ grant.max_uses - grant.used_count }} 次 · 到期
          {{ time(grant.expires_at) }}</text
        ><button class="primary" :disabled="busy" @tap="dispatch">
          按有效授权提交一次</button
        ><button :disabled="busy" @tap="revokeApproval">
          撤销此授权
        </button></template
      >
      <template v-if="selected.dispatch_at"
        ><text class="label">提交与回执</text
        ><text>提交时间 {{ time(selected.dispatch_at) }}</text
        ><template v-if="selected.provider === 'qq_smtp'"
          ><text>Message-ID：{{ selected.smtp_message_id || '未取得' }}</text
          ><text
            >SMTP 提交结果：{{
              selected.provider_event
                ? mailLabel(selected.provider_event)
                : mailLabel(selected.status)
            }}</text
          ><text class="hint"
            >QQ SMTP
            无回执查询接口。请核对收件箱与垃圾箱中的地址、主题、全文和邮件标识，再记录人工收件证据；人工声明不改变服务器提交状态，未知结果不会自动重发。</text
          ></template
        ><template v-else
          ><text
            >通道回执：{{ selected.receipt_id || '尚未取得' }} ·
            {{ mailLabel(selected.provider_event) }}</text
          ><text class="hint"
            >通道接受或报告送达不等于实际收件；未知态先回查，系统不会重复提交。</text
          ><template v-if="selected.body !== null"
            ><text class="label">可选：通道后台邮件 ID（只读核对）</text
            ><input
              v-model="form.receipt"
              :maxlength="36"
              :disabled="busy"
            /><button
              :disabled="busy || selected.status === 'sending'"
              @tap="reconcile"
            >
              只读回查通道</button
            ><text class="hint"
              >最近回查 {{ time(selected.checked_at) }}；自动发现只查最近 100
              封中的最多 5 个候选，未匹配保持原状态。</text
            ></template
          ></template
        ><template v-if="actions.receipt"
          ><text class="label">实际收件证据说明（5–500 字）</text
          ><textarea
            v-model="form.evidence"
            :maxlength="500"
            :disabled="busy"
          /><checkbox-group
            @change="hasReceipt = Boolean(($event.detail.value || []).length)"
            ><label class="label"
              ><checkbox
                value="receipt"
                :checked="hasReceipt"
                :disabled="busy"
              />我已核对收件人实际收到此邮件，此项为人工证据声明</label
            ></checkbox-group
          ><button :disabled="busy || !hasReceipt" @tap="attest">
            记录实际收件证据
          </button></template
        ><text v-if="selected.received_at" class="hint"
          >人工收件声明 {{ time(selected.received_at) }}：{{
            selected.receipt_evidence
          }}</text
        ><text v-else class="hint">尚无实际收件证据。</text></template
      >
      <template v-if="selected.approvals.length"
        ><text class="label"
          >审批与消耗记录（{{ selected.approvals.length }}）</text
        ><text v-for="item in selected.approvals" :key="item.id"
          >#{{ item.id }} ·
          {{ item.mode === 'once' ? '单次审批' : '独立预授权' }} ·
          {{ mailLabel(item.status) }} · 消耗 {{ item.used_count }}/{{
            item.max_uses
          }}
          · 到期 {{ time(item.expires_at) }}</text
        ></template
      ></view
    >
  </view>
</template>
