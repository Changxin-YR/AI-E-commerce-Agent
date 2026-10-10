<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { outboundApi } from '@/api/outbound'
import { errorMessage } from '@/api/client'
import { mailLabels, type OutboundMail } from '@/types/outbound'
import FeedbackBanner from './FeedbackBanner.vue'
const props = defineProps<{ mail: OutboundMail; timezone: string }>()
const emit = defineEmits<{ updated: [mail: OutboundMail] }>()
const busy = ref(false)
const error = ref('')
const subject = ref('')
const body = ref('')
const editing = ref(false)
const confirmed = ref(false)
const hours = ref(1)
const receipt = ref('')
const evidence = ref('')
const received = ref(false)
const qqMail = computed(() => props.mail.provider === 'qq_smtp')
const editable = computed(
  () => props.mail.status === 'draft' && props.mail.source_status === 'current',
)
const active = computed(() => props.mail.approvals.find((g) => g.status === 'active'))
const label = (value: string) => mailLabels[value] ?? value
const time = (value: string | null) =>
  value ? new Date(value).toLocaleString('zh-CN', { timeZone: props.timezone, hour12: false }) : '—'
watch(
  () => [props.mail.id, props.mail.version],
  () => {
    subject.value = props.mail.subject ?? ''
    body.value = props.mail.body ?? ''
    editing.value = false
    confirmed.value = received.value = false
    evidence.value = receipt.value = error.value = ''
  },
  { immediate: true },
)
watch(hours, () => {
  confirmed.value = false
})
async function run(work: () => Promise<OutboundMail>): Promise<void> {
  if (busy.value) return
  busy.value = true
  error.value = ''
  const id = props.mail.id
  try {
    const result = await work()
    if (props.mail.id === id) emit('updated', result)
  } catch (cause) {
    error.value = `${errorMessage(cause)} 外发状态以刷新回读为准。`
  } finally {
    busy.value = false
    confirmed.value = false
  }
}
async function approve(mode: 'once' | 'preauthorized'): Promise<void> {
  if (!confirmed.value) return
  const mail = props.mail
  await run(async () => {
    const approved = await outboundApi.approve(mail, mode, hours.value)
    const grant = approved.approvals.find((g) => g.status === 'active')
    if (mode === 'once' && grant) return outboundApi.send(approved, grant.id)
    return approved
  })
}
function refresh(): void {
  void run(() => outboundApi.get(props.mail.shop_id, props.mail.id))
}
function toggleEdit(): void {
  editing.value = !editing.value
  confirmed.value = false
}
function reject(): void {
  void run(() => outboundApi.reject(props.mail))
}
function save(): void {
  void run(() => outboundApi.edit(props.mail, subject.value, body.value))
}
function send(): void {
  const grant = active.value
  if (grant) void run(() => outboundApi.send(props.mail, grant.id))
}
function revoke(): void {
  const grant = active.value
  if (grant) void run(() => outboundApi.revoke(props.mail, grant.id))
}
function reconcile(): void {
  void run(() => outboundApi.reconcile(props.mail, receipt.value))
}
function attest(): void {
  if (received.value) void run(() => outboundApi.receipt(props.mail, evidence.value))
}
</script>
<template>
  <section class="form-panel section-block mail-review" aria-label="R2 外发预览">
    <div class="section-title">
      <h2>摘要 #{{ mail.id }} · {{ label(mail.status) }}</h2>
      <span class="outline-label">R2 · 外部邮件</span>
    </div>
    <FeedbackBanner :message="error" />
    <p>
      关联运营检查 #{{ mail.run_id }} · {{ label(mail.source_status) }} · 通道
      {{ label(mail.channel_status) }}
    </p>
    <dl class="mail-addresses">
      <dt>发件人</dt>
      <dd>{{ mail.sender }}</dd>
      <dt>收件人</dt>
      <dd>{{ mail.recipient }}</dd>
    </dl>
    <p class="mail-warning">
      审批时原状态：尚未提交；目标动作：向上述邮箱提交 1
      封邮件。每份摘要最多提交一次，邮件不可撤回。撤销授权只停止尚未提交的动作，已开始的提交仍可能送达。
    </p>
    <p v-if="qqMail">
      QQ 邮箱发送额度与限制以邮箱服务为准。每次只发往上述一个收件地址，无附件、抄送或密送。
    </p>
    <p v-else>
      预计费用：由你的 Resend 套餐和配额决定，本系统无法核定实际账单。无附件、抄送或密送。
    </p>
    <template v-if="mail.body !== null">
      <h3>{{ mail.subject }}</h3>
      <pre class="mail-body">{{ mail.body }}</pre>
      <details>
        <summary>审批内容摘要与时间</summary>
        <p>{{ mail.content_hash }}</p>
        <p>{{ time(mail.created_at) }} · {{ timezone }}</p>
      </details>
    </template>
    <p v-else>来源内容已清除，保留提交状态与必要审计。已发送邮件不能从收件箱撤回。</p>
    <fieldset :disabled="busy">
      <div class="button-row">
        <button class="button secondary small" @click="refresh">刷新外发记录</button>
        <button v-if="editable" class="button secondary small" @click="toggleEdit">
          修改待发正文
        </button>
        <button v-if="editable" class="button secondary small" @click="reject">拒绝此发送</button>
      </div>
      <form v-if="editing" class="mail-editor" @submit.prevent="save">
        <label>邮件主题<input v-model="subject" required maxlength="200" /></label>
        <label
          >邮件全文<textarea v-model="body" required maxlength="12000" rows="10"></textarea>
        </label>
        <p>保存修改会使已有审批失效。</p>
        <button class="button secondary small">保存正文</button>
      </form>
      <div v-if="editable && !editing && mail.channel_status === 'active'" class="action-confirm">
        <label
          >预授权有效小时（1—24）<input v-model.number="hours" type="number" min="1" max="24"
        /></label>
        <p>独立预授权仅适用于当前地址、全文与检查记录，限 1 次。单次批准在 10 分钟内有效。</p>
        <label class="check-label"
          ><input v-model="confirmed" type="checkbox" />我已核对地址和全文，确认 R2
          邮件不可撤回及可能产生通道费用</label
        >
        <div class="button-row">
          <button class="button primary" :disabled="!confirmed" @click="approve('once')">
            单次批准并提交</button
          ><button
            class="button secondary"
            :disabled="!confirmed"
            @click="approve('preauthorized')"
          >
            创建限一次预授权
          </button>
        </div>
      </div>
      <div v-if="active && !editing" class="action-confirm">
        <p>
          有效审批 #{{ active.id }} · 剩余 1 次 · 到期 {{ time(active.expires_at) }}（{{
            timezone
          }}）
        </p>
        <div class="button-row">
          <button class="button primary" @click="send">按有效授权提交一次</button
          ><button class="button secondary" @click="revoke">撤销此授权</button>
        </div>
      </div>
      <div v-if="mail.dispatch_at" class="source-detail">
        <h3>提交与回执</h3>
        <p>提交时间 {{ time(mail.dispatch_at) }}（{{ timezone }}）</p>
        <template v-if="qqMail">
          <p>邮件标识 Message-ID：{{ mail.smtp_message_id }}</p>
          <p>
            SMTP 提交结果：{{
              mail.provider_event ? label(mail.provider_event) : label(mail.status)
            }}
          </p>
          <p>
            QQ SMTP
            无回执查询接口。请核对收件箱和垃圾箱中的地址、主题、全文及邮件标识，再记录实际收件证据。人工声明不改变服务器提交状态，未知结果不会自动重发。
          </p>
        </template>
        <template v-else>
          <p>通道回执：{{ mail.receipt_id ?? '尚未取得' }} · {{ label(mail.provider_event) }}</p>
          <p>通道接受或报告送达不等于实际收件；未知态先回查，系统不会重复提交。</p>
        </template>
        <template v-if="mail.body !== null && !qqMail"
          ><label
            >可选：从通道后台取得的邮件 ID<input
              v-model="receipt"
              maxlength="36"
              placeholder="仅用于只读核对" /></label
          ><button
            class="button secondary small"
            :disabled="mail.status === 'sending'"
            @click="reconcile"
          >
            只读回查通道
          </button>
          <p>
            最近回查 {{ time(mail.checked_at) }}。自动发现只查最近 100 封中的最多 5
            个候选；未匹配保持原状态。
          </p></template
        >
        <form
          v-if="
            (mail.status === 'accepted' || (qqMail && mail.status === 'unknown')) &&
            mail.body !== null
          "
          class="mail-editor"
          @submit.prevent="attest"
        >
          <label
            >实际收件证据说明<textarea
              v-model="evidence"
              minlength="5"
              maxlength="500"
              rows="3"
              required
              placeholder="例如：收件人确认的收到时间、主题与可复查证据位置"
            ></textarea>
          </label>
          <label class="check-label"
            ><input
              v-model="received"
              type="checkbox"
            />我已核对收件人实际收到此邮件，此项为人工证据声明</label
          >
          <button class="button secondary small" :disabled="!received">记录实际收件证据</button>
        </form>
        <p v-if="mail.received_at">
          人工收件声明 {{ time(mail.received_at) }}：{{ mail.receipt_evidence }}
        </p>
        <p v-else>尚无实际收件证据。</p>
      </div>
      <details v-if="mail.approvals.length">
        <summary>审批与消耗记录（{{ mail.approvals.length }}）</summary>
        <p v-for="grant in mail.approvals" :key="grant.id">
          #{{ grant.id }} · {{ grant.mode === 'once' ? '单次审批' : '独立预授权' }} ·
          {{ label(grant.status) }} · 消耗 {{ grant.used_count }}/1 · 到期
          {{ time(grant.expires_at) }}
        </p>
      </details>
    </fieldset>
  </section>
</template>
<style scoped>
.mail-review {
  overflow-wrap: anywhere;
}
.mail-review fieldset {
  border: 0;
  padding: 0;
  min-width: 0;
  margin-top: 20px;
}
.mail-review p {
  margin: 14px 0;
  line-height: 1.7;
}
.mail-addresses {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 12px 24px;
  margin: 20px 0;
}
.mail-addresses dd {
  margin: 0;
}
.mail-body {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: inherit;
  line-height: 1.8;
  background: #f4f5ef;
  padding: 20px;
  border-radius: 6px;
}
.mail-warning {
  border-left: 3px solid #9e702d;
  padding: 12px 16px;
  background: #faf4e8;
}
.mail-editor,
.mail-editor label:not(.check-label) {
  display: grid;
  gap: 12px;
  margin: 16px 0;
}
.mail-review textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 4px;
  font: inherit;
  resize: vertical;
}
.action-confirm > label:not(.check-label) {
  display: grid;
  gap: 8px;
  max-width: 260px;
}
.check-label {
  margin: 16px 0;
}
@media (max-width: 760px) {
  .mail-addresses {
    grid-template-columns: 1fr;
    gap: 8px;
  }
  .mail-addresses dd {
    margin-bottom: 8px;
  }
}
</style>
