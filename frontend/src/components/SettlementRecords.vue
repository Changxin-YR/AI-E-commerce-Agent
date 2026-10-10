<script setup lang="ts">
import BusinessDateTime from './BusinessDateTime.vue'
import BusinessDateRange from '@/components/BusinessDateRange.vue'
import { onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { settlementsApi as api } from '@/api/settlements'
import { ApiError, errorMessage } from '@/api/client'
import {
  settlementStatuses,
  type SettlementContent,
  type SettlementDraft,
  type SettlementPreview,
  type SettlementSaved,
  type SettlementWrite,
} from '@/types/settlements'
import { supportTime } from '@/types/support'
import FeedbackBanner from './FeedbackBanner.vue'
import SettlementResult from './SettlementResult.vue'

const props = defineProps<{
  shopId: number
  scope: SettlementDraft['scope']
  disabled: boolean
  initialId?: number
}>()
const emit = defineEmits<{ busy: [value: boolean]; invalidated: [] }>()
const rows = ref<SettlementSaved[]>([])
const cursor = ref<number | null>(null)
const saved = ref<SettlementSaved | null>(null)
const shownVersion = ref<number | null>(null)
const editing = ref<{ id: number | null; version: number; scope: SettlementDraft['scope'] } | null>(
  null,
)
const content = reactive<SettlementContent>({ statement_id: '', note: '', receipts: [] })
const preview = ref<SettlementPreview | null>(null)
const current = ref<SettlementPreview | null>(null)
const confirmed = ref(false)
const controlConfirmed = ref(false)
const controlAction = ref<'withdraw' | 'clear'>('withdraw')
const busy = ref(false)
const error = ref('')
const pending = ref<SettlementWrite | null>(null)
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
  content,
  () => {
    epoch++
    resetPreview()
  },
  { deep: true, flush: 'sync' },
)
watch(
  () => editing.value?.scope,
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
watch(
  () => [props.shopId, ...Object.values(props.scope)],
  () => {
    invalidate()
    pending.value = null
    pendingControl.value = null
    Object.assign(content, { statement_id: '', note: '', receipts: [] })
  },
  {
    flush: 'sync',
  },
)
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
function begin(record: SettlementSaved | null): void {
  const snapshot = record?.snapshot
  invalidate()
  editing.value = {
    id: record?.id ?? null,
    version: record?.version ?? 0,
    scope: { ...(snapshot?.scope ?? props.scope) },
  }
  Object.assign(
    content,
    snapshot
      ? JSON.parse(JSON.stringify(snapshot.content))
      : { statement_id: '', note: '', receipts: [] },
  )
  emit('invalidated')
}
async function inspect(): Promise<void> {
  if (!editing.value) return
  const draft: SettlementDraft = {
    scope: { ...editing.value.scope },
    settlement_id: editing.value.id,
    version: editing.value.version,
    content: JSON.parse(JSON.stringify(content)) as SettlementContent,
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
      settlement_id: editing.value.id,
      version: editing.value.version,
      content: JSON.parse(JSON.stringify(content)) as SettlementContent,
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
    let response: SettlementSaved
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
    let response: SettlementSaved
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
        Object.assign(content, { statement_id: '', note: '', receipts: [] })
        pending.value = null
      }
      controlAction.value = response.status === 'withdrawn' ? 'clear' : 'withdraw'
    }
  })
}
function addReceipt(): void {
  if (content.receipts.length >= 50) return
  content.receipts.push({
    payout_ref: '',
    receipt_ref: '',
    amount: '',
    currency: 'USD',
    received_at: new Date().toISOString(),
    timezone: 'UTC',
    note: '',
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
  <section class="form-panel section-block settlements" aria-label="结算登记">
    <h2>登记周期，核对回款。</h2>
    <p>保存周期依据和卖家到账声明，每次预览重新读取原账单。银行证据、余额和完整覆盖仍待核实。</p>
    <FeedbackBanner :message="error" />
    <p v-if="busy" role="status">正在处理结算登记…</p>
    <fieldset :disabled="busy || disabled">
      <legend class="sr-only">结算登记管理</legend>
      <div class="form-actions">
        <button class="button secondary" @click="begin(null)">新建结算登记</button>
        <button class="button secondary" @click="refresh">读取结算登记</button>
        <button v-if="pending" class="button secondary" @click="save(true)">
          回查原登记保存请求
        </button>
        <button v-if="pendingControl" class="button secondary" @click="control(true)">
          回查原登记处理请求
        </button>
      </div>
      <ul v-if="rows.length">
        <li v-for="row in rows" :key="row.id">
          <button class="text-button" @click="show(row.id)">
            结算 #{{ row.id }} · {{ settlementStatuses[row.status] }} · v{{ row.version }} ·
            {{ supportTime(row.created_at, scope.timezone) }}
          </button>
        </li>
      </ul>
      <button v-if="cursor" class="button secondary" @click="more">更多结算登记</button>
      <form v-if="editing" class="section-block" @submit.prevent="inspect">
        <h3>{{ editing.id ? `修订结算 #${editing.id}` : '新建周期与人工到账' }}</h3>
        <p>
          本次周期：{{ supportTime(editing.scope.start_at, editing.scope.timezone) }} 至
          {{ supportTime(editing.scope.end_at, editing.scope.timezone) }}（结束不含，{{
            editing.scope.timezone
          }}）
        </p>
        <div class="form-grid">
          <BusinessDateRange
            v-model:start="editing.scope.start_at"
            v-model:end="editing.scope.end_at"
            :timezone="editing.scope.timezone"
            start-label="登记周期开始（含偏移）"
            end-label="登记周期结束（含偏移）"
          />
          <div class="form-field">
            <label for="cycle-zone">登记周期时区</label
            ><input id="cycle-zone" v-model="editing.scope.timezone" required />
          </div>
          <div class="form-field">
            <label for="settlement-statement">原账单号</label
            ><input
              id="settlement-statement"
              v-model="content.statement_id"
              required
              maxlength="120"
            />
          </div>
          <div class="form-field">
            <label for="settlement-note">周期依据与核对说明</label
            ><textarea
              id="settlement-note"
              v-model="content.note"
              required
              maxlength="1000"
              rows="3"
            />
          </div>
        </div>
        <p>
          按完整原账单号读取，区分大小写；请从文件确认该账单的结算周期。回款和到账可晚于周期结束；原始结算批号在明细中保留。
        </p>
        <h4>人工到账凭据（{{ content.receipts.length }}/50）</h4>
        <p>
          填写可回查的凭据编号、到账金额与时间及核验说明。未登记表示缺少本地凭据，无法推断是否到账。
        </p>
        <article v-for="(r, i) in content.receipts" :key="i" class="receipt-editor">
          <h4>人工凭据 {{ i + 1 }}</h4>
          <div class="form-grid">
            <div class="form-field">
              <label :for="`payout-ref-${i}`">平台回款凭据号 {{ i + 1 }}</label
              ><input :id="`payout-ref-${i}`" v-model="r.payout_ref" required maxlength="120" />
            </div>
            <div class="form-field">
              <label :for="`receipt-ref-${i}`">人工到账凭据号 {{ i + 1 }}</label
              ><input :id="`receipt-ref-${i}`" v-model="r.receipt_ref" required maxlength="120" />
            </div>
            <div class="form-field">
              <label :for="`receipt-amount-${i}`">到账金额 {{ i + 1 }}</label
              ><input :id="`receipt-amount-${i}`" v-model="r.amount" required inputmode="decimal" />
            </div>
            <div class="form-field">
              <label :for="`receipt-currency-${i}`">到账币种 {{ i + 1 }}</label
              ><select :id="`receipt-currency-${i}`" v-model="r.currency">
                <option
                  v-for="c in ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']"
                  :key="c"
                >
                  {{ c }}
                </option>
              </select>
            </div>
            <BusinessDateTime
              v-model="r.received_at"
              :timezone="r.timezone"
              :label="`到账时间（含偏移）${i + 1}`"
              required
            />
            <div class="form-field">
              <label :for="`receipt-zone-${i}`">到账显示时区 {{ i + 1 }}</label
              ><input :id="`receipt-zone-${i}`" v-model="r.timezone" required />
            </div>
          </div>
          <div class="form-field">
            <label :for="`receipt-note-${i}`">凭据核验说明 {{ i + 1 }}</label
            ><textarea
              :id="`receipt-note-${i}`"
              v-model="r.note"
              required
              maxlength="500"
              rows="2"
            />
          </div>
          <button type="button" class="text-button" @click="content.receipts.splice(i, 1)">
            移除人工凭据 {{ i + 1 }}
          </button>
        </article>
        <div class="form-actions">
          <button
            type="button"
            class="button secondary"
            :disabled="content.receipts.length >= 50"
            @click="addReceipt"
          >
            添加人工到账凭据</button
          ><button class="button secondary">预览周期与回款</button>
        </div>
      </form>
      <section v-if="preview" class="section-block" aria-label="结算预览">
        <SettlementResult :result="preview.snapshot" :shop-id="shopId" />
        <label class="checkbox-label"
          ><input
            v-model="confirmed"
            type="checkbox"
          />我已核对周期、平台来源与人工到账凭据，确认保存本地登记</label
        >
        <button class="button primary" :disabled="!confirmed" @click="save()">保存结算登记</button>
      </section>
      <article v-if="saved" class="section-block" aria-label="结算登记详情">
        <h3>
          结算 #{{ saved.id }} · {{ settlementStatuses[saved.status] }} · 版本 {{ saved.version }}
        </h3>
        <p>登记依据未变表示保存后尚未发生来源变更，银行到账与完整结算仍待核实。</p>
        <RouterLink :to="`/settlements?shop=${shopId}&settlement=${saved.id}`"
          >结算登记固定链接</RouterLink
        >
        <template v-if="saved.snapshot">
          <h4>历史正文 v{{ shownVersion }}</h4>
          <SettlementResult :result="saved.snapshot" :shop-id="shopId" historical />
          <div class="form-actions">
            <button class="button secondary" @click="readCurrent">回读当前账单与凭据</button
            ><button
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
          <summary>登记历史（{{ saved.history.length }}）</summary>
          <ul>
            <li v-for="h in saved.history" :key="h.version">
              v{{ h.version }} · {{ h.action }} · {{ supportTime(h.created_at, scope.timezone) }}
              <button v-if="h.has_content" class="text-button" @click="show(saved.id, h.version)">
                读取 v{{ h.version }} 依据
              </button>
            </li>
          </ul>
        </details>
        <div v-if="saved.status !== 'cleared'" class="section-block">
          <label for="settlement-control">登记处理</label
          ><select id="settlement-control" v-model="controlAction">
            <option v-if="saved.status !== 'withdrawn'" value="withdraw">撤销登记，保留历史</option>
            <option value="clear">清除全部历史正文与依据</option>
          </select>
          <p>
            撤销会释放账单及凭据编号占用并保留历史；清除会擦除这份登记的全部历史正文，无法恢复。原始账单独立保留。
          </p>
          <label class="checkbox-label"
            ><input
              v-model="controlConfirmed"
              type="checkbox"
            />我确认处理此版本登记及上述影响</label
          ><button class="button secondary" :disabled="!controlConfirmed" @click="control()">
            确认处理登记
          </button>
        </div>
      </article>
      <section v-if="current" class="section-block" aria-label="结算当前依据">
        <h3>当前依据回读 · 尚未重新确认</h3>
        <p>沿用最近保存的人工声明，重新读取平台账单；本次读取不会更新历史登记。</p>
        <SettlementResult :result="current.snapshot" :shop-id="shopId" />
      </section>
    </fieldset>
  </section>
</template>
<style scoped>
.settlements {
  overflow-wrap: anywhere;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
fieldset {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
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
.text-button {
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--green);
  font: inherit;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.receipt-editor {
  border-top: 1px solid var(--line);
  padding-block: 16px;
}
li {
  margin-block: 10px;
}
</style>
