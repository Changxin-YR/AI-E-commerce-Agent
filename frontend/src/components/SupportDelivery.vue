<script setup lang="ts">
import BusinessDateTime from './BusinessDateTime.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { supportApi } from '@/api/support'
import { errorMessage } from '@/api/client'
import { supportTime, type ReplyDraft, type ManualActionRecord } from '@/types/support'
import ReviewedDelivery from './ReviewedDelivery.vue'
import FeedbackBanner from './FeedbackBanner.vue'

const props = defineProps<{
  item: ReplyDraft
  shopId: number
  timezone: string
  disabled: boolean
}>()
const emit = defineEmits<{ updated: [ReplyDraft]; dirty: [boolean]; working: [boolean] }>()
const reviewed = computed(
  () =>
    props.item.source_status === 'current' &&
    !!props.item.reviewed_at &&
    props.item.reviewed_version === props.item.version,
)
const language = ref('')
const reviewConfirmed = ref(false)
const method = ref('')
const evidence = ref('')
const note = ref('')
const occurredAt = ref('')
const confirmed = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const records = ref<ManualActionRecord[]>([])
const loaded = ref(false)
const more = ref(false)
let epoch = 0
let requestId = crypto.randomUUID()
const formDirty = computed(
  () => !!(method.value || evidence.value || note.value || occurredAt.value || confirmed.value),
)
watch(
  () => formDirty.value || reviewConfirmed.value,
  (value) => emit('dirty', value),
)
watch(
  [method, evidence, note, occurredAt],
  () => {
    confirmed.value = false
    requestId = crypto.randomUUID()
  },
  { flush: 'sync' },
)
watch(
  language,
  () => {
    reviewConfirmed.value = false
  },
  { flush: 'sync' },
)
function clearForm(): void {
  method.value = evidence.value = note.value = occurredAt.value = ''
  confirmed.value = false
}
watch(
  () => [props.shopId, props.item.id, props.item.version, props.item.source_status],
  () => {
    epoch++
    clearForm()
    reviewConfirmed.value = busy.value = loaded.value = more.value = false
    records.value = []
    error.value = notice.value = ''
    language.value =
      props.item.reviewed_language ??
      (['en', 'zh'].includes(props.item.snapshot?.message.language ?? '')
        ? props.item.snapshot!.message.language
        : '')
    emit('dirty', false)
    emit('working', false)
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  epoch++
  emit('working', false)
  emit('dirty', false)
})
async function run(work: (current: () => boolean) => Promise<void>): Promise<void> {
  if (busy.value || props.disabled) return
  const token = ++epoch
  busy.value = true
  error.value = notice.value = ''
  emit('working', true)
  try {
    await work(() => token === epoch)
  } catch (cause) {
    if (token === epoch) error.value = errorMessage(cause)
  } finally {
    if (token === epoch) {
      busy.value = false
      emit('working', false)
    }
  }
}
async function review(): Promise<void> {
  if (!reviewConfirmed.value || !language.value || formDirty.value) return
  await run(async (current) => {
    const result = await supportApi.review(props.shopId, props.item, language.value)
    if (current()) emit('updated', result)
  })
}
async function record(): Promise<void> {
  if (!confirmed.value || !reviewed.value) return
  const data = {
    request_id: requestId,
    expected_version: props.item.version,
    occurred_at: occurredAt.value,
    method: method.value,
    evidence_ref: evidence.value,
    note: note.value,
    confirmed: confirmed.value,
  }
  await run(async (current) => {
    const result = await supportApi.recordManualAction(props.shopId, props.item.id, data)
    if (!current()) return
    clearForm()
    records.value = [result, ...records.value.filter((r) => r.id !== result.id)]
    notice.value = '人工操作自报已登记。系统外部状态仍为未提交。'
  })
}
async function history(older = false): Promise<void> {
  await run(async (current) => {
    const result = await supportApi.manualActions(
      props.shopId,
      props.item.id,
      older ? records.value[records.value.length - 1]?.id : undefined,
    )
    if (!current()) return
    records.value = older ? [...records.value, ...result] : result
    loaded.value = true
    more.value = result.length === 50
  })
}
const loadDelivery = () => supportApi.delivery(props.shopId, props.item)
</script>

<template>
  <section class="support-delivery" aria-label="客服审阅与人工交付">
    <h3>审阅当前版本</h3>
    <p>核对回复全文、订单关联、政策有效期、目标语言和全部接管原因。此确认保存 R1 本地审阅记录。</p>
    <p v-if="reviewed" role="status">
      本版本已审阅 · {{ supportTime(item.reviewed_at!, timezone) }} · {{ item.reviewed_language }}
    </p>
    <fieldset :disabled="disabled || busy || item.source_status !== 'current' || formDirty">
      <legend>全文审阅确认</legend>
      <label class="form-field"
        >回复目标语言
        <select v-model="language">
          <option value="">请选择已核对的语言</option>
          <option value="en">English</option>
          <option value="zh">中文</option>
        </select>
      </label>
      <label class="check-label"
        ><input
          v-model="reviewConfirmed"
          type="checkbox"
        />我已审阅回复全文、目标语言与全部接管提示</label
      >
      <button
        class="button secondary"
        :disabled="!reviewConfirmed || !language || !item.snapshot?.reply.trim()"
        @click="review"
      >
        确认当前版本已审阅
      </button>
    </fieldset>
    <ReviewedDelivery
      eligibility="仅当前已审阅且来源有效的客服版本可复制或下载。"
      :context-key="`${shopId}:${item.id}:${item.version}:${item.source_status}`"
      :allowed="reviewed"
      :disabled="disabled || busy || formDirty || reviewConfirmed"
      :load-artifact="loadDelivery"
    />
    <form class="manual-action-form" @submit.prevent="record">
      <fieldset :disabled="disabled || busy || !reviewed || reviewConfirmed">
        <legend>登记原渠道人工操作</legend>
        <p>
          保存你在原渠道操作的自报记录。请使用证据编号或本机文件索引，避免填写客户地址等无关资料。自报记录不等于平台回执。
        </p>
        <BusinessDateTime
          class="full-width"
          v-model="occurredAt"
          :timezone="timezone"
          label="人工操作时间（含时区）"
          required
        />
        <label class="form-field"
          >原渠道操作方式<input
            v-model="method"
            required
            minlength="2"
            maxlength="80"
            placeholder="例如：原平台消息中心人工回复"
        /></label>
        <label class="form-field"
          >人工操作证据索引<input v-model="evidence" required minlength="2" maxlength="500"
        /></label>
        <label class="form-field"
          >操作备注（可选）<textarea v-model="note" maxlength="1000" rows="2" />
        </label>
        <label class="check-label"
          ><input
            v-model="confirmed"
            type="checkbox"
          />我确认已在原渠道人工操作，此记录为本人自报</label
        >
        <div class="button-row">
          <button
            class="button primary"
            :disabled="!confirmed || !method.trim() || !evidence.trim() || !occurredAt.trim()"
          >
            登记人工操作
          </button>
          <button v-if="formDirty" type="button" class="button secondary" @click="clearForm">
            清空未保存操作
          </button>
        </div>
      </fieldset>
    </form>
    <FeedbackBanner :message="error" />
    <p v-if="notice" role="status">{{ notice }}</p>
    <section aria-label="人工操作自报记录">
      <h3>人工操作自报记录</h3>
      <button
        class="button secondary small"
        :disabled="disabled || busy || formDirty"
        @click="history()"
      >
        刷新人工操作记录
      </button>
      <p v-if="loaded && !records.length">尚无人工操作记录。</p>
      <article v-for="record in records" :key="record.id" class="source-detail">
        <p>
          自报 #{{ record.id }} · 草稿 v{{ record.draft_version }} ·
          {{ supportTime(record.occurred_at, timezone) }}
        </p>
        <template v-if="record.details"
          ><p>{{ record.details.method }}</p>
          <p class="preserve-text">{{ record.details.evidence_ref }}</p>
          <p class="preserve-text">{{ record.details.note }}</p></template
        >
        <p v-else>相关来源已清除，操作证据内容已擦除。</p>
        <p class="muted">登记于 {{ supportTime(record.recorded_at, timezone) }} · 系统外部未提交</p>
      </article>
      <button
        v-if="more"
        class="button secondary small"
        :disabled="disabled || busy || formDirty"
        @click="history(true)"
      >
        更早的人工操作
      </button>
    </section>
  </section>
</template>

<style scoped>
.support-delivery {
  display: grid;
  gap: 1rem;
  margin-top: 1.5rem;
  overflow-wrap: anywhere;
}
fieldset {
  min-width: 0;
  display: grid;
  gap: 0.8rem;
  padding: 1rem;
  border: 1px solid var(--line);
}
.form-field {
  min-width: 0;
}
input,
select,
textarea {
  max-width: 100%;
}
</style>
