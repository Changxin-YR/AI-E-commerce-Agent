<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { operationsApi } from '@/api/operations'
import { errorMessage } from '@/api/client'
import type { OperationTask, TaskAction } from '@/types/operations'
import { taskLabels, sourceLabels } from '@/types/operations'
import { supportTime } from '@/types/support'
import SourceEvidence from './SupportSource.vue'
import FeedbackBanner from './FeedbackBanner.vue'

const props = defineProps<{ task: OperationTask; timezone: string }>()
const emit = defineEmits<{ updated: [OperationTask]; dirty: [boolean]; working: [boolean] }>()
const note = ref('')
const due = ref('')
const error = ref('')
const busy = ref(false)
const kindLabels: Record<string, string> = {
  order_review: '订单履约核对',
  low_inventory: '库存阈值',
  message_review: '消息回复核对',
  low_margin: '已知低毛利',
}
watch(
  () => props.task,
  (t) => {
    note.value = t.note
    due.value = t.due_at ?? ''
    error.value = ''
  },
  { immediate: true },
)
const dirty = computed(
  () => note.value !== props.task.note || due.value !== (props.task.due_at ?? ''),
)
watch(dirty, (v) => emit('dirty', v))
const available = computed(() => props.task.source_status === 'current' && !!props.task.snapshot)
async function act(action: TaskAction): Promise<void> {
  busy.value = true
  emit('working', true)
  error.value = ''
  try {
    emit(
      'updated',
      await operationsApi.change(
        props.task.shop_id,
        props.task.id,
        props.task.version,
        action,
        note.value,
        due.value || null,
      ),
    )
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
    emit('working', false)
  }
}
</script>

<template>
  <section class="form-panel section-block task-review" aria-label="待办审批详情">
    <div class="section-title">
      <h2>事项 #{{ task.id }} · {{ taskLabels[task.status] }}</h2>
      <span class="status-tag">{{ sourceLabels[task.source_status] }}</span>
    </div>
    <p>负责人：当前卖家 · {{ task.risk }} 内部操作 · 外部未提交</p>
    <template v-if="task.snapshot">
      <p>
        优先级：{{ task.snapshot.severity === 'attention' ? '关注' : '待核对' }} · 内部标签：{{
          kindLabels[task.kind]
        }}
      </p>
      <h3>{{ task.snapshot.title }} · {{ task.snapshot.object_label }}</h3>
      <p>{{ task.snapshot.basis }}</p>
      <p>{{ task.snapshot.impact }}</p>
      <p><strong>建议：</strong>{{ task.snapshot.advice }}</p>
      <div v-if="available && !dirty && !busy" class="task-actions">
        <RouterLink
          v-for="destination in task.destinations ?? []"
          :key="destination.label"
          class="button secondary"
          :to="{ path: destination.path, query: destination.query }"
        >
          {{ destination.label }}
        </RouterLink>
      </div>
      <dl>
        <template v-for="(value, name) in task.snapshot.facts" :key="name"
          ><dt>{{ name }}</dt>
          <dd>{{ value }}</dd></template
        >
      </dl>
      <p v-if="task.snapshot.valid_until">
        证据有效至 {{ supportTime(task.snapshot.valid_until, timezone) }}
      </p>
      <p v-if="!available" role="status">
        来源、经营规则已变化或过期，请重新运行今日运营后核对。历史处理状态保留。
      </p>
      <details>
        <summary>查看依据（{{ task.snapshot.sources.length }} 行）</summary>
        <SourceEvidence
          v-for="source in task.snapshot.sources"
          :key="`${task.version}-${source.row_id}`"
          :shop-id="task.shop_id"
          :source="source"
        />
      </details>
      <p class="data-note">
        <span v-if="task.status === 'pending_approval'"
          >审批预览：待审批 → 待处理；为此店铺保存带规则标签的本地待办。</span
        >
        本地操作费用 0，可忽略、完成后重新打开；不更改来源订单、库存或外部消息。
      </p>
      <fieldset :disabled="busy || !available">
        <legend>处理记录</legend>
        <div class="form-field">
          <label for="task-note">处理备注</label
          ><textarea id="task-note" v-model="note" maxlength="1000" rows="3" />
        </div>
        <div class="form-field">
          <label for="task-due">截止时间（含时区偏移，可留空）</label
          ><input id="task-due" v-model="due" placeholder="2026-10-10T18:00:00+08:00" />
        </div>
        <p v-if="task.due_at">
          已保存截止：{{ supportTime(task.due_at, timezone) }}；到期后保留当前状态，需卖家处理。
        </p>
        <div class="task-actions">
          <template v-if="task.status === 'pending_approval'"
            ><button class="button primary" @click="act('approve')">批准并创建待办</button
            ><button class="button secondary" @click="act('reject')">拒绝候选</button></template
          >
          <template v-if="['open', 'deferred'].includes(task.status)"
            ><button class="button primary" @click="act('complete')">标记完成</button
            ><button class="button secondary" @click="act('defer')">
              延期至截止时间
            </button></template
          >
          <button
            v-if="['pending_approval', 'open', 'deferred'].includes(task.status)"
            class="button secondary"
            @click="act('ignore')"
          >
            忽略此事项
          </button>
          <button
            v-if="['completed', 'ignored', 'rejected', 'deferred'].includes(task.status)"
            class="button secondary"
            @click="act('reopen')"
          >
            重新打开待办
          </button>
          <button class="button secondary" :disabled="!dirty" @click="act('edit')">
            保存处理记录
          </button>
        </div>
      </fieldset>
      <button
        v-if="!available && ['pending_approval', 'open', 'deferred'].includes(task.status)"
        class="button secondary"
        :disabled="busy"
        @click="act('ignore')"
      >
        忽略此历史事项
      </button>
    </template>
    <p v-else>来源已清除，相关证据和处理备注已擦除，仅保留状态历史。</p>
    <FeedbackBanner :message="error" />
    <details>
      <summary>操作历史（最近 50 条）</summary>
      <ol>
        <li v-for="event in task.history" :key="event.version">
          {{ supportTime(event.created_at, timezone) }} · {{ taskLabels[event.from_status] }} →
          {{ taskLabels[event.to_status] }}
          <span v-if="event.action === 'revalidated'"> · 已重新核对来源</span>
          <p v-if="event.note">{{ event.note }}</p>
          <p v-if="event.due_at">截止 {{ supportTime(event.due_at, timezone) }}</p>
        </li>
      </ol>
    </details>
  </section>
</template>

<style scoped>
.task-review {
  overflow-wrap: anywhere;
}
fieldset {
  margin: 1rem 0;
  border: 0;
  padding: 0;
  min-width: 0;
}
.task-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1rem;
}
dl {
  display: grid;
  grid-template-columns: minmax(5rem, 1fr) 3fr;
  gap: 0.5rem;
}
dd {
  margin: 0;
  min-width: 0;
}
@media (max-width: 640px) {
  .section-title {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.75rem;
  }
}
</style>
