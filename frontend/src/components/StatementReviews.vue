<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { statementReviewsApi as api } from '@/api/statementReviews'
import { ApiError, errorMessage } from '@/api/client'
import {
  reviewOutcomes,
  reviewStatuses,
  type ReviewConclusion,
  type ReviewDraft,
  type ReviewPreview,
  type ReviewSaved,
  type ReviewWrite,
} from '@/types/statementReviews'
import { supportTime } from '@/types/support'
import FeedbackBanner from './FeedbackBanner.vue'
import StatementResult from './StatementResult.vue'

const props = defineProps<{
  shopId: number
  scope: ReviewDraft['scope']
  disabled: boolean
  freshness: number
  initialId?: number
}>()
const emit = defineEmits<{ busy: [value: boolean]; invalidated: [] }>()
const rows = ref<ReviewSaved[]>([])
const cursor = ref<number | null>(null)
const saved = ref<ReviewSaved | null>(null)
const shownVersion = ref<number | null>(null)
const editing = ref<{ id: number | null; version: number; scope: ReviewDraft['scope'] } | null>(
  null,
)
const conclusion = reactive<ReviewConclusion>({ outcome: 'pending', note: '' })
const preview = ref<ReviewPreview | null>(null)
const current = ref<ReviewPreview | null>(null)
const confirmed = ref(false)
const controlConfirmed = ref(false)
const controlAction = ref<'withdraw' | 'clear'>('withdraw')
const busy = ref(false)
const error = ref('')
const pending = ref<ReviewWrite | null>(null)
const pendingControl = ref<{
  id: number
  action: 'withdraw' | 'clear'
  body: { request_id: string; version: number; confirm: true }
} | null>(null)
let alive = true
let epoch = 0
function resetPreview(): void {
  preview.value = null
  confirmed.value = false
}
watch(
  conclusion,
  () => {
    epoch++
    resetPreview()
  },
  { deep: true, flush: 'sync' },
)
watch(controlAction, () => {
  controlConfirmed.value = false
})
function invalidate(): void {
  epoch++
  rows.value = []
  cursor.value = null
  saved.value = null
  current.value = null
  editing.value = null
  shownVersion.value = null
  controlConfirmed.value = false
  resetPreview()
}
watch(() => [props.shopId, ...Object.values(props.scope), props.freshness], invalidate, {
  flush: 'sync',
})
async function action(work: (valid: () => boolean) => Promise<void>): Promise<void> {
  if (busy.value || props.disabled) return
  const token = epoch
  busy.value = true
  emit('busy', true)
  error.value = ''
  try {
    await work(() => alive && epoch === token)
  } catch (cause) {
    if (alive && epoch === token) error.value = errorMessage(cause)
  } finally {
    if (alive) {
      busy.value = false
      emit('busy', false)
    }
  }
}
async function refresh(): Promise<void> {
  if (busy.value || props.disabled) return
  invalidate()
  emit('invalidated')
  await action(async (valid) => {
    const response = await api.list(props.shopId, props.scope)
    if (valid()) {
      rows.value = response.items
      cursor.value = response.next_cursor
    }
  })
}
async function more(): Promise<void> {
  await action(async (valid) => {
    const response = await api.list(props.shopId, props.scope, cursor.value ?? undefined)
    if (valid()) {
      rows.value.push(...response.items)
      cursor.value = response.next_cursor
    }
  })
}
async function show(id: number, version?: number): Promise<void> {
  if (busy.value || props.disabled) return
  invalidate()
  emit('invalidated')
  await action(async (valid) => {
    const response = await api.get(props.shopId, id, version)
    if (valid()) {
      saved.value = response
      shownVersion.value = version ?? response.content_version
      controlAction.value = response.status === 'withdrawn' ? 'clear' : 'withdraw'
    }
  })
}
function begin(record: ReviewSaved | null): void {
  const snapshot = record?.snapshot
  invalidate()
  editing.value = {
    id: record?.id ?? null,
    version: record?.version ?? 0,
    scope: { ...(snapshot?.result.scope ?? props.scope) },
  }
  Object.assign(conclusion, snapshot?.conclusion ?? { outcome: 'pending', note: '' })
  emit('invalidated')
}
async function inspect(): Promise<void> {
  if (!editing.value) return
  const draft: ReviewDraft = {
    scope: { ...editing.value.scope },
    review_id: editing.value.id,
    version: editing.value.version,
    conclusion: { ...conclusion },
  }
  await action(async (valid) => {
    resetPreview()
    current.value = null
    const response = await api.preview(props.shopId, draft)
    if (valid()) preview.value = response
  })
}
async function save(retry = false): Promise<void> {
  if (!retry) {
    if (!editing.value || !preview.value || !confirmed.value) return
    pending.value = {
      scope: { ...editing.value.scope },
      review_id: editing.value.id,
      version: editing.value.version,
      conclusion: { ...conclusion },
      preview_hash: preview.value.preview_hash,
      request_id: crypto.randomUUID(),
      confirm: true,
    }
  }
  const request = pending.value
  if (!request || busy.value || props.disabled) return
  invalidate()
  emit('invalidated')
  await action(async (valid) => {
    let response: ReviewSaved
    try {
      response = await api.write(props.shopId, request)
    } catch (cause) {
      if (valid() && cause instanceof ApiError && cause.status >= 400 && cause.status < 500)
        pending.value = null
      throw cause
    }
    if (valid()) {
      saved.value = response
      shownVersion.value = response.content_version
      pending.value = null
    }
  })
}
async function readCurrent(): Promise<void> {
  const id = saved.value?.id
  if (!id || busy.value || props.disabled) return
  // Status and evidence are read under the same server transaction.
  invalidate()
  emit('invalidated')
  await action(async (valid) => {
    const response = await api.current(props.shopId, id)
    if (valid()) {
      saved.value = response.record
      shownVersion.value = response.record.content_version
      current.value = response.preview
    }
  })
}
async function control(retry = false): Promise<void> {
  if (!retry) {
    if (!saved.value || !controlConfirmed.value) return
    pendingControl.value = {
      id: saved.value.id,
      action: controlAction.value,
      body: { request_id: crypto.randomUUID(), version: saved.value.version, confirm: true },
    }
  }
  const request = pendingControl.value
  if (!request || busy.value || props.disabled) return
  invalidate()
  emit('invalidated')
  await action(async (valid) => {
    let response: ReviewSaved
    try {
      response = await api.control(props.shopId, request.id, request.action, request.body)
    } catch (cause) {
      if (valid() && cause instanceof ApiError && cause.status >= 400 && cause.status < 500)
        pendingControl.value = null
      throw cause
    }
    if (valid()) {
      saved.value = response
      shownVersion.value = response.content_version
      pendingControl.value = null
      if (response.status === 'cleared') {
        conclusion.note = ''
        pending.value = null
      }
      controlAction.value = response.status === 'withdrawn' ? 'clear' : 'withdraw'
    }
  })
}
onMounted(() => {
  window.addEventListener('focus', invalidate)
  if (props.initialId) void show(props.initialId)
})
onUnmounted(() => {
  alive = false
  epoch++
  emit('busy', false)
  window.removeEventListener('focus', invalidate)
})
</script>
<template>
  <section class="form-panel section-block statement-reviews" aria-label="人工核对存档">
    <h2>核对结论，连同依据存档。</h2>
    <p>
      保存当前窗口的人工结论与差异说明。未知分类、缺失一侧、重复凭据、异币种和类别冲突仍须待核；结论不代表完整费用、实际净利或银行到账。
    </p>
    <FeedbackBanner :message="error" />
    <p v-if="busy" role="status">正在处理核对存档…</p>
    <fieldset :disabled="busy || disabled">
      <legend class="sr-only">核对存档管理</legend>
      <div class="form-actions">
        <button class="button secondary" @click="begin(null)">新建核对结论</button>
        <button class="button secondary" @click="refresh">读取核对存档</button>
        <button v-if="pending" class="button secondary" @click="save(true)">
          回查原结论保存请求
        </button>
        <button v-if="pendingControl" class="button secondary" @click="control(true)">
          回查原结论处理请求
        </button>
      </div>
      <ul v-if="rows.length">
        <li v-for="row in rows" :key="row.id">
          <button class="text-button" @click="show(row.id)">
            核对 #{{ row.id }} · {{ reviewStatuses[row.status] }} · v{{ row.version }} ·
            {{ supportTime(row.created_at, scope.timezone) }}
          </button>
        </li>
      </ul>
      <button v-if="cursor" class="button secondary" @click="more">更多核对存档</button>
      <form v-if="editing" class="section-block" @submit.prevent="inspect">
        <h3>{{ editing.id ? `修订核对 #${editing.id}` : '新建人工核对' }}</h3>
        <p>
          本次存档范围：{{ supportTime(editing.scope.start_at, editing.scope.timezone) }} 至
          {{ supportTime(editing.scope.end_at, editing.scope.timezone) }}（结束不含，{{
            editing.scope.timezone
          }}）
        </p>
        <div class="form-field">
          <label for="review-outcome">人工结论</label
          ><select id="review-outcome" v-model="conclusion.outcome">
            <option v-for="(label, key) in reviewOutcomes" :key="key" :value="key">
              {{ label }}
            </option>
          </select>
        </div>
        <div class="form-field">
          <label for="review-note">核对依据与差异说明</label
          ><textarea
            id="review-note"
            v-model="conclusion.note"
            required
            maxlength="1000"
            rows="3"
          />
        </div>
        <p>最多 1000 字。金额差异已说明表示已记录人工解释，仍需跟进处理。</p>
        <button class="button secondary">预览结论与依据</button>
      </form>
      <section v-if="preview" class="section-block" aria-label="核对结论预览">
        <h3>{{ reviewOutcomes[preview.snapshot.conclusion.outcome] }}</h3>
        <p class="review-note">{{ preview.snapshot.conclusion.note }}</p>
        <ul v-if="preview.snapshot.blockers.length">
          <li v-for="item in preview.snapshot.blockers" :key="item">{{ item }}</li>
        </ul>
        <p>
          账单来源版本 {{ preview.snapshot.result.source_revision }} · 费用变更号
          {{ preview.snapshot.expense_revision }} · 规则变更号
          {{ preview.snapshot.result.rule_revision }}
        </p>
        <details>
          <summary>展开本次存档依据</summary>
          <StatementResult :result="preview.snapshot.result" :shop-id="shopId" />
        </details>
        <label class="checkbox-label"
          ><input
            v-model="confirmed"
            type="checkbox"
          />我已核对本窗口的来源、费用、规则和差异说明，确认保存人工结论</label
        >
        <button class="button primary" :disabled="!confirmed" @click="save()">保存核对结论</button>
      </section>
      <article v-if="saved" class="section-block" aria-label="核对存档详情">
        <h3>
          核对 #{{ saved.id }} · {{ reviewStatuses[saved.status] }} · 版本 {{ saved.version }}
        </h3>
        <p>
          有效表示保存时依据未被后续变更标记失效；是否仍待核以人工结论为准。来源、同范围费用或规则变更后必须重新确认。
        </p>
        <RouterLink :to="`/statements?shop=${shopId}&review=${saved.id}`"
          >核对存档固定链接</RouterLink
        >
        <template v-if="saved.snapshot">
          <h4>
            历史正文 v{{ shownVersion }} · {{ reviewOutcomes[saved.snapshot.conclusion.outcome] }}
          </h4>
          <p class="review-note">{{ saved.snapshot.conclusion.note }}</p>
          <p>
            存档窗口：{{
              supportTime(
                saved.snapshot.result.scope.start_at,
                saved.snapshot.result.scope.timezone,
              )
            }}
            至
            {{
              supportTime(saved.snapshot.result.scope.end_at, saved.snapshot.result.scope.timezone)
            }}（结束不含，{{ saved.snapshot.result.scope.timezone }}）
          </p>
          <details>
            <summary>展开该版本的存档依据</summary>
            <StatementResult :result="saved.snapshot.result" :shop-id="shopId" historical />
          </details>
          <div class="form-actions">
            <button class="button secondary" @click="readCurrent">回读当前来源、费用与规则</button>
            <button
              v-if="
                ['active', 'stale'].includes(saved.status) && shownVersion === saved.content_version
              "
              class="button secondary"
              @click="begin(saved)"
            >
              修订并重新核对
            </button>
          </div>
        </template>
        <p v-else>正文及全部历史依据已清除。</p>
        <details>
          <summary>结论历史（{{ saved.history.length }}）</summary>
          <ul>
            <li v-for="h in saved.history" :key="h.version">
              v{{ h.version }} · {{ h.action }} · {{ supportTime(h.created_at, scope.timezone)
              }}<template v-if="h.conclusion">
                · {{ reviewOutcomes[h.conclusion.outcome]
                }}<button class="text-button" @click="show(saved.id, h.version)">
                  读取 v{{ h.version }} 依据
                </button></template
              >
            </li>
          </ul>
        </details>
        <div v-if="saved.status !== 'cleared'" class="section-block">
          <label for="review-control">结论处理</label
          ><select id="review-control" v-model="controlAction">
            <option v-if="saved.status !== 'withdrawn'" value="withdraw">撤销结论，保留历史</option>
            <option value="clear">清除全部历史正文与依据</option>
          </select>
          <p>
            撤销后可查看历史；清除会擦除这份存档所有版本的说明和依据，无法恢复。原账单、费用及规则仍各自保留。
          </p>
          <label class="checkbox-label"
            ><input
              v-model="controlConfirmed"
              type="checkbox"
            />我确认处理此版本结论及上述影响</label
          >
          <button class="button secondary" :disabled="!controlConfirmed" @click="control()">
            确认处理结论
          </button>
        </div>
      </article>
      <section v-if="current" class="section-block" aria-label="存档当前依据">
        <h3>当前依据回读 · 尚未重新确认</h3>
        <p>此次读取不会更新历史结论。</p>
        <StatementResult :result="current.snapshot.result" :shop-id="shopId" />
      </section>
    </fieldset>
  </section>
</template>
<style scoped>
.statement-reviews {
  overflow-wrap: anywhere;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 12px;
  font: inherit;
  resize: vertical;
}
.checkbox-label {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin: 18px 0;
}
.checkbox-label input {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  min-height: 18px;
  margin-top: 3px;
  accent-color: var(--green);
}
fieldset {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.review-note {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
li {
  overflow-wrap: anywhere;
  margin-block: 10px;
}
</style>
