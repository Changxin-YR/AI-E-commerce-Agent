<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { operationsApi } from '@/api/operations'
import { errorMessage } from '@/api/client'
import type { OperationTask } from '@/types/operations'
import { businessLabels } from '@/types/operations'
import FeedbackBanner from './FeedbackBanner.vue'
import TaskReviewEvidence from './TaskReviewEvidence.vue'

const props = defineProps<{ task: OperationTask; timezone: string; disabled: boolean }>()
const emit = defineEmits<{ updated: [OperationTask]; dirty: [boolean]; working: [boolean] }>()
const description = ref('')
const evidenceRef = ref('')
const occurredAt = ref('')
const confirmed = ref(false)
const busy = ref(false)
const error = ref('')
let generation = 0
let active = true
const dirty = computed(
  () => !!(description.value || evidenceRef.value || occurredAt.value || confirmed.value),
)
const editable = computed(
  () => !!props.task.snapshot && ['open', 'deferred', 'completed'].includes(props.task.status),
)
watch(dirty, (value) => emit('dirty', value))
watch([description, evidenceRef, occurredAt], () => {
  confirmed.value = false
})
watch(
  () => props.task,
  () => {
    generation++
    description.value = evidenceRef.value = occurredAt.value = error.value = ''
    confirmed.value = busy.value = false
    emit('dirty', false)
    emit('working', false)
  },
)
onUnmounted(() => {
  active = false
  generation++
})

function clearDraft(): void {
  description.value = evidenceRef.value = occurredAt.value = ''
  confirmed.value = false
}

async function act(action: 'record_evidence' | 'wait_source' | 'recheck'): Promise<void> {
  if (
    busy.value ||
    props.disabled ||
    !editable.value ||
    (action !== 'record_evidence' && dirty.value)
  )
    return
  const current = ++generation
  const target = props.task
  const evidence =
    action === 'record_evidence'
      ? {
          description: description.value,
          evidence_ref: evidenceRef.value,
          occurred_at: occurredAt.value,
          confirmed: confirmed.value,
        }
      : undefined
  busy.value = true
  emit('working', true)
  error.value = ''
  try {
    const result = await operationsApi.change(
      target.shop_id,
      target.id,
      target.version,
      action,
      target.note,
      target.due_at,
      evidence,
    )
    if (active && current === generation) emit('updated', result)
  } catch (cause) {
    if (active && current === generation) error.value = errorMessage(cause)
  } finally {
    if (active && current === generation) {
      busy.value = false
      emit('working', false)
    }
  }
}
</script>

<template>
  <section class="follow-up" aria-label="异常业务复核">
    <h3>
      业务进展 ·
      {{
        businessLabels[
          task.business_state ??
            (task.status === 'completed' ? 'checked_pending' : 'pending_review')
        ]
      }}
    </h3>
    <p>
      完成核对仅保存本地处理状态。复检会固定原对象、渠道、身份、规则和范围，读取新导入依据；外部操作仍由卖家完成。
    </p>
    <p v-if="task.review?.recheck && !task.review_current" role="status">
      存档结论已因来源、规则变化或时效失效，请更新来源后重新复检。
    </p>
    <TaskReviewEvidence
      v-if="task.review"
      :review="task.review"
      :shop-id="task.shop_id"
      :timezone="timezone"
    />
    <template v-if="task.snapshot">
      <p v-if="!editable">批准或重新打开事项后，可以登记人工证据并复检。</p>
      <fieldset :disabled="disabled || busy || !editable">
        <legend>登记人工操作证据</legend>
        <div class="form-field">
          <label for="review-description">操作说明（卖家自报）</label
          ><textarea id="review-description" v-model="description" maxlength="1000" rows="3" />
        </div>
        <div class="form-field">
          <label for="review-reference">操作依据或凭据编号</label
          ><input id="review-reference" v-model="evidenceRef" maxlength="500" />
        </div>
        <div class="form-field">
          <label for="review-occurred">操作发生时间（含时区偏移）</label
          ><input
            id="review-occurred"
            v-model="occurredAt"
            placeholder="2026-10-10T18:00:00+08:00"
          />
        </div>
        <label class="confirmation"
          ><input
            v-model="confirmed"
            type="checkbox"
          />我确认这是人工自报记录，外部结果仍需有效来源复检</label
        >
        <div class="form-actions">
          <button
            class="button primary"
            :disabled="
              !confirmed || !description.trim() || !evidenceRef.trim() || !occurredAt.trim()
            "
            @click="act('record_evidence')"
          >
            登记操作证据
          </button>
          <button class="button secondary" :disabled="dirty" @click="act('wait_source')">
            等待来源更新
          </button>
          <button class="button secondary" :disabled="dirty" @click="act('recheck')">
            按原事项复检新来源
          </button>
          <button v-if="dirty" class="button secondary" @click="clearDraft">清空未保存证据</button>
        </div>
      </fieldset>
    </template>
    <FeedbackBanner :message="error" />
  </section>
</template>

<style scoped>
.follow-up {
  margin-top: 1.5rem;
  overflow-wrap: anywhere;
}
fieldset {
  border: 0;
  padding: 0;
  margin: 1rem 0;
  min-width: 0;
}
.confirmation {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}
.confirmation input {
  width: auto;
  flex: 0 0 auto;
}
.form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}
</style>
