<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { identityApi } from '@/api/identity'
import { expensesApi } from '@/api/expenses'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import { qualityChannels } from '@/types/productQuality'
import {
  expenseCategories,
  expenseStatuses,
  type ExpenseContent,
  type ExpenseSaved,
  type ExpenseScope,
  type ExpenseSummary,
  type ExpenseWrite,
} from '@/types/expenses'
import { supportTime } from '@/types/support'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import ExpenseEditor from '@/components/ExpenseEditor.vue'
import ExpenseEvidence from '@/components/ExpenseEvidence.vue'

const route = useRoute()
const revisionActions: Record<string, string> = {
  create: '录入',
  update: '修订',
  withdraw: '撤销',
  clear: '清除',
}
const shops = ref<Shop[]>([])
const shopId = ref(0)
const scope = reactive<ExpenseScope>({ data_identity: 'user_import', channel: 'generic' })
const rows = ref<ExpenseSaved[]>([])
const cursor = ref<number | null>(null)
const saved = ref<ExpenseSaved | null>(null)
const editor = ref(false)
const editing = ref<ExpenseSaved | null>(null)
const busy = ref(false)
const error = ref('')
const summary = ref<ExpenseSummary | null>(null)
const period = reactive({
  start_at: `${new Date().toISOString().slice(0, 7)}-01T00:00:00Z`,
  end_at: new Date().toISOString(),
  timezone: 'UTC',
})
const controlAction = ref<'withdraw' | 'clear'>('withdraw')
const confirmed = ref(false)
const pending = ref<{ shop: number; id?: number; body: ExpenseWrite } | null>(null)
const pendingControl = ref<{
  shop: number
  id: number
  action: 'withdraw' | 'clear'
  body: { version: number; confirm: true; request_id: string }
} | null>(null)
const selectedId = ref<number | null>(null)
const timezone = computed(() => shops.value.find((s) => s.id === shopId.value)?.timezone ?? 'UTC')
let epoch = 0
let alive = true
let restoring = false
function reset(): void {
  epoch++
  rows.value = []
  cursor.value = null
  saved.value = null
  editor.value = false
  editing.value = null
  summary.value = null
  pending.value = null
  pendingControl.value = null
  selectedId.value = null
  confirmed.value = false
  error.value = ''
}
watch(
  () => [shopId.value, scope.data_identity, scope.channel],
  () => {
    if (!restoring) reset()
  },
  { flush: 'sync' },
)
watch(controlAction, () => {
  confirmed.value = false
})
watch(
  period,
  () => {
    summary.value = null
  },
  { deep: true, flush: 'sync' },
)
async function action(work: (valid: () => boolean) => Promise<void>): Promise<void> {
  if (busy.value || !shopId.value) return
  const current = epoch
  busy.value = true
  error.value = ''
  confirmed.value = false
  try {
    await work(() => alive && current === epoch)
  } catch (cause) {
    if (alive && current === epoch) error.value = errorMessage(cause)
  } finally {
    if (alive) busy.value = false
  }
}
async function list(valid: () => boolean, before?: number): Promise<void> {
  const response = await expensesApi.list(shopId.value, { ...scope }, before)
  if (!valid()) return
  rows.value = before ? [...rows.value, ...response.items] : response.items
  cursor.value = response.next_cursor
}
function accept(response: ExpenseSaved): void {
  restoring = true
  scope.data_identity = response.data_identity
  scope.channel = response.channel
  restoring = false
  saved.value = response
  controlAction.value = response.status === 'withdrawn' ? 'clear' : 'withdraw'
  selectedId.value = response.id
  confirmed.value = false
}
async function refresh(): Promise<void> {
  await action(async (valid) => {
    rows.value = []
    summary.value = null
    saved.value = null
    editor.value = false
    editing.value = null
    if (selectedId.value) {
      const response = await expensesApi.get(shopId.value, selectedId.value)
      if (!valid()) return
      accept(response)
    }
    await list(valid)
  })
}
async function show(id: number): Promise<void> {
  await action(async (valid) => {
    saved.value = null
    editor.value = false
    editing.value = null
    selectedId.value = id
    const response = await expensesApi.get(shopId.value, id)
    if (valid()) accept(response)
  })
}
function begin(existing: ExpenseSaved | null): void {
  if (busy.value) return
  editor.value = true
  editing.value = existing
  error.value = ''
  confirmed.value = false
}
function hideContent(): void {
  saved.value = null
  rows.value = []
  summary.value = null
  editor.value = false
  editing.value = null
}
async function save(content?: ExpenseContent): Promise<void> {
  if (content)
    pending.value = {
      shop: shopId.value,
      id: editing.value?.id,
      body: {
        ...scope,
        request_id: crypto.randomUUID(),
        confirm: true,
        version: editing.value?.version ?? 0,
        content,
      },
    }
  const request = pending.value
  if (!request || busy.value) return
  await action(async (valid) => {
    hideContent()
    const response = await expensesApi.write(request.shop, request.body, request.id)
    if (!valid()) return
    pending.value = null
    accept(response)
    await list(valid)
  })
}
async function control(retry = false): Promise<void> {
  if (!retry) {
    if (!saved.value || !confirmed.value) return
    pendingControl.value = {
      shop: shopId.value,
      id: saved.value.id,
      action: controlAction.value,
      body: { version: saved.value.version, confirm: true, request_id: crypto.randomUUID() },
    }
  }
  const request = pendingControl.value
  if (!request) return
  await action(async (valid) => {
    hideContent()
    const response = await expensesApi.control(
      request.shop,
      request.id,
      request.action,
      request.body,
    )
    if (!valid()) return
    pendingControl.value = null
    accept(response)
    await list(valid)
  })
}
function abandon(): void {
  pending.value = null
  pendingControl.value = null
  void refresh()
}
async function summarize(): Promise<void> {
  const request = { ...scope, ...period }
  await action(async (valid) => {
    summary.value = null
    const response = await expensesApi.summary(shopId.value, request)
    if (
      valid() &&
      JSON.stringify(period) ===
        JSON.stringify({
          start_at: request.start_at,
          end_at: request.end_at,
          timezone: request.timezone,
        })
    )
      summary.value = response
  })
}
function focused(): void {
  if (!busy.value && !editor.value && !pending.value && !pendingControl.value) void refresh()
}
onMounted(async () => {
  try {
    const response = await identityApi.shops()
    if (!alive) return
    shops.value = response
    shopId.value =
      response.find((s) => s.id === Number(route.query.shop))?.id ?? response[0]?.id ?? 0
    const id = Number(route.query.expense)
    if (Number.isSafeInteger(id) && id > 0) selectedId.value = id
    await refresh()
  } catch (cause) {
    if (alive) error.value = errorMessage(cause)
  }
  if (alive) window.addEventListener('focus', focused)
})
onUnmounted(() => {
  alive = false
  epoch++
  window.removeEventListener('focus', focused)
})
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>实际费用，每一笔有依据。</h1>
      <p>记录已发生费用，保留修订历史，核对归属与来源。</p>
    </div>
    <RouterLink class="button secondary" :to="`/analytics?shop=${shopId}`">经营分析</RouterLink>
  </div>
  <FeedbackBanner :message="error" />
  <section class="data-note">
    <span class="note-symbol" aria-hidden="true">i</span>
    <div>
      <h3>人工费用台账 · 平台账单待核对</h3>
      <p>
        费用完整性未知。店铺费用尚未分摊，单条订单行费用全额归属；汇总仅代表当前已录入费用，无法确定净利润。
      </p>
    </div>
  </section>
  <section v-if="shops.length" class="form-panel section-block">
    <fieldset :disabled="busy">
      <legend>费用范围</legend>
      <div class="form-grid">
        <div class="form-field">
          <label for="expense-shop">所属店铺</label
          ><select id="expense-shop" v-model="shopId" @change="refresh">
            <option v-for="shop in shops" :key="shop.id" :value="shop.id">
              {{ shop.name }} · {{ shop.code }}
            </option>
          </select>
        </div>
        <div class="form-field">
          <label for="expense-identity">数据身份</label
          ><select id="expense-identity" v-model="scope.data_identity" @change="refresh">
            <option value="user_import">用户实际记录</option>
            <option value="synthetic">合成测试数据</option>
          </select>
        </div>
        <div class="form-field">
          <label for="expense-channel">来源渠道</label
          ><select id="expense-channel" v-model="scope.channel" @change="refresh">
            <option v-for="(label, key) in qualityChannels" :key="key" :value="key">
              {{ label }}
            </option>
          </select>
        </div>
      </div>
      <div class="form-actions">
        <button class="button secondary" :disabled="!!pending || !!pendingControl" @click="refresh">
          刷新费用</button
        ><button
          class="button primary"
          :disabled="!!pending || !!pendingControl"
          @click="begin(null)"
        >
          新增实际费用
        </button>
      </div>
    </fieldset>
  </section>
  <p v-if="!shops.length && !busy">
    请先在<RouterLink to="/settings">经营资料</RouterLink>添加店铺。
  </p>
  <p v-if="busy" role="status">正在读取或保存费用…</p>
  <section v-if="!busy && (pending || pendingControl)" class="form-panel section-block">
    <p>本次操作尚未确认结果。可使用原请求回查；若返回校验或版本冲突，请刷新后重新核对。</p>
    <button v-if="pending" class="button secondary" @click="save()">回查原保存请求</button
    ><button v-else class="button secondary" @click="control(true)">回查原处理请求</button
    ><button class="button secondary" @click="abandon">刷新并重新核对</button>
  </section>
  <fieldset v-if="editor" :disabled="busy">
    <ExpenseEditor
      :key="`${shopId}-${scope.data_identity}-${scope.channel}-${editing?.id ?? 0}`"
      :shop-id="shopId"
      :scope="scope"
      :existing="editing"
      @save="save"
      @cancel="editor = false"
    />
  </fieldset>
  <section v-if="saved" class="form-panel section-block" aria-label="费用详情与版本">
    <h2>费用 #{{ saved.id }} · {{ expenseStatuses[saved.status] }}</h2>
    <p>当前版本 {{ saved.version }} · 创建于 {{ supportTime(saved.created_at, timezone) }}</p>
    <RouterLink :to="`/expenses?shop=${shopId}&expense=${saved.id}`">费用固定链接</RouterLink>
    <ExpenseEvidence v-if="saved.snapshot" :snapshot="saved.snapshot" :shop-id="shopId" />
    <p v-if="saved.status === 'stale'" class="warning-text">
      关联后店铺数据发生变化，本笔已从有效费用合计排除。请重新查找当前订单并核对，或更正为店铺费用后保存新版本。
    </p>
    <p v-if="saved.status === 'cleared'">费用正文、金额、发生时间及全部历史依据已清除。</p>
    <button
      v-if="saved.status === 'active' || saved.status === 'stale'"
      class="button secondary"
      :disabled="busy"
      @click="begin(saved)"
    >
      修订费用
    </button>
    <details>
      <summary>版本历史（{{ saved.history.length }}）</summary>
      <article v-for="entry in saved.history" :key="entry.version" class="section-block">
        <h3>版本 {{ entry.version }} · {{ revisionActions[entry.action] ?? entry.action }}</h3>
        <p>{{ supportTime(entry.created_at, timezone) }} · 历史记录不重复计入费用</p>
        <ExpenseEvidence v-if="entry.snapshot" :snapshot="entry.snapshot" :shop-id="shopId" />
        <p v-else>无费用正文</p>
      </article>
    </details>
    <details v-if="saved.status !== 'cleared'">
      <summary>撤销或清除费用</summary>
      <fieldset :disabled="busy">
        <div class="form-field">
          <label for="expense-action">处理方式</label
          ><select id="expense-action" v-model="controlAction">
            <option value="withdraw" :disabled="saved.status === 'withdrawn'">
              撤销 · 保留历史，排除合计
            </option>
            <option value="clear">清除 · 擦除全部历史正文与依据</option>
          </select>
        </div>
        <label class="check-label"
          ><input v-model="confirmed" type="checkbox" />确认执行所选费用处理及全部版本影响</label
        ><button class="button secondary" :disabled="!confirmed" @click="control()">
          执行费用处理
        </button>
      </fieldset>
    </details>
  </section>
  <section v-if="shopId" class="form-panel section-block" aria-label="费用核对">
    <h2>按发生时间核对费用</h2>
    <p>包含开始、不含结束，最多 366 天、1000 笔；按当前版本统计。</p>
    <form @submit.prevent="summarize">
      <fieldset :disabled="busy">
        <div class="form-grid">
          <div class="form-field">
            <label for="expense-start">开始时间（含偏移）</label
            ><input id="expense-start" v-model="period.start_at" required />
          </div>
          <div class="form-field">
            <label for="expense-end">结束时间（含偏移）</label
            ><input id="expense-end" v-model="period.end_at" required />
          </div>
          <div class="form-field">
            <label for="expense-zone">核对显示时区（IANA）</label
            ><input id="expense-zone" v-model="period.timezone" required />
          </div>
        </div>
        <button class="button secondary">核对费用合计</button>
      </fieldset>
    </form>
    <div v-if="summary" aria-label="费用合计结果">
      <p>
        {{ supportTime(summary.scope.start_at, summary.scope.timezone) }} 至
        {{ supportTime(summary.scope.end_at, summary.scope.timezone) }}（不含结束）
      </p>
      <p>
        有效 {{ summary.included_count }} 笔 · 待重核 {{ summary.stale_count }} 笔 · 已撤销
        {{ summary.withdrawn_count }} 笔
      </p>
      <p v-if="!summary.totals.length">此范围没有可计入费用；不表示实际费用为零。</p>
      <ul>
        <li
          v-for="item in summary.totals"
          :key="`${item.currency}-${item.category}-${item.allocation}`"
        >
          {{ item.currency }} {{ item.amount }} · {{ expenseCategories[item.category] }} ·
          {{ item.allocation === 'shop' ? '店铺未分摊' : '订单行直接归属' }} · {{ item.count }} 笔
        </li>
      </ul>
      <ul>
        <li v-for="check in summary.checks" :key="check">{{ check }}</li>
      </ul>
    </div>
  </section>
  <section v-if="shopId" class="form-panel section-block" aria-label="费用记录列表">
    <h2>费用记录</h2>
    <p>当前店铺、身份和渠道；包含已撤销、待重核及已清除记录。</p>
    <p v-if="!rows.length && !busy">暂无已加载记录。</p>
    <article v-for="row in rows" :key="row.id" class="expense-row">
      <div>
        <strong>#{{ row.id }} · {{ row.snapshot?.content.label ?? '正文已清除' }}</strong>
        <p>
          {{ expenseStatuses[row.status] }} · 版本 {{ row.version
          }}<span v-if="row.snapshot">
            · {{ row.snapshot.content.currency }} {{ row.snapshot.content.amount }}</span
          >
        </p>
      </div>
      <button
        class="button secondary"
        :disabled="busy || !!pending || !!pendingControl"
        @click="show(row.id)"
      >
        查看费用 #{{ row.id }}
      </button>
    </article>
    <button
      v-if="cursor"
      class="button secondary"
      :disabled="busy"
      @click="action((valid) => list(valid, cursor ?? undefined))"
    >
      加载更早费用
    </button>
  </section>
</template>
<style scoped>
fieldset {
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}
legend {
  font-weight: 600;
  margin-bottom: 16px;
}
.page-heading > .button {
  white-space: nowrap;
}
.expense-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  padding: 1rem 0;
  border-top: 1px solid var(--line);
}
.expense-row > div {
  min-width: 0;
  overflow-wrap: anywhere;
}
:deep(.expense-evidence) {
  overflow-wrap: anywhere;
}
@media (max-width: 650px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .expense-row {
    align-items: start;
    flex-direction: column;
  }
}
</style>
