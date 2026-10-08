<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { linkedId, linkedShop, revealRecord } from '@/composables/deepLink'
import { identityApi } from '@/api/identity'
import { analyticsApi } from '@/api/analytics'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import type { AnalysisResult, AnalysisScope, SavedAnalysis } from '@/types/analytics'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import AnalysisEvidence from '@/components/AnalysisEvidence.vue'

const shops = ref<Shop[]>([])
const route = useRoute()
const shopId = ref(0)
const busy = ref(false)
const error = ref('')
const success = ref('')
const result = ref<AnalysisResult | null>(null)
const history = ref<SavedAnalysis[]>([])
const selectedSaved = ref<SavedAnalysis | null>(null)
const questions = ['查看销售与已知毛利', '销量前五的 SKU', '哪些商品销量高但已知毛利低']
const question = ref(questions[0]!)
const scope = reactive<AnalysisScope>({
  start_at: new Date(Date.now() - 30 * 86400000).toISOString(),
  end_at: new Date().toISOString(),
  timezone: 'Asia/Shanghai',
  currency: 'USD',
  data_identity: 'user_import',
  intent: 'summary',
  min_quantity: 1,
  max_margin_percent: '20',
})
const stateNames: Record<string, string> = {
  current: '已保存',
  stale: '需重新计算',
  cleared: '来源已清除',
  open: '待核对',
  completed: '已核对完成',
}
const outdated = ref(false)
const stale = computed(
  () => outdated.value || (!!selectedSaved.value && selectedSaved.value.status !== 'current'),
)
function resetResult(): void {
  outdated.value = false
  result.value = null
  selectedSaved.value = null
  success.value = ''
}
watch(scope, resetResult)
watch(question, resetResult)
async function action(work: () => Promise<void>): Promise<void> {
  busy.value = true
  error.value = ''
  success.value = ''
  try {
    await work()
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function selectShop(): Promise<void> {
  resetResult()
  history.value = []
  const shop = shops.value.find((item) => item.id === shopId.value)
  if (!shop) return
  scope.currency = shop.currency
  scope.timezone = shop.timezone
  await action(async () => {
    history.value = await analyticsApi.saved(shopId.value)
  })
}
onMounted(async () => {
  window.addEventListener('focus', checkFreshness)
  await action(async () => {
    shops.value = await identityApi.shops()
  })
  try {
    shopId.value = linkedShop(shops.value, route.query.shop)
    await selectShop()
    const id = linkedId(route.query.analysis)
    if (id) {
      await show({ id })
      await revealRecord('linked-analysis')
    }
  } catch (cause) {
    error.value = errorMessage(cause)
  }
})
onUnmounted(() => window.removeEventListener('focus', checkFreshness))
function checkFreshness(): void {
  if (!busy.value && shopId.value) void refreshHistory()
}
async function run(): Promise<void> {
  await action(async () => {
    resetResult()
    result.value = await analyticsApi.ask(shopId.value, { ...scope }, question.value)
  })
}
async function save(): Promise<void> {
  if (!result.value) return
  await action(async () => {
    selectedSaved.value = await analyticsApi.save(shopId.value, result.value!)
    history.value = await analyticsApi.saved(shopId.value)
    success.value = '分析已保存，可刷新页面后查看。'
  })
}
async function todo(item: SavedAnalysis): Promise<void> {
  await action(async () => {
    const updated = await analyticsApi.todo(shopId.value, item.id)
    history.value = await analyticsApi.saved(shopId.value)
    if (selectedSaved.value?.id === item.id) selectedSaved.value = updated
    success.value = '核对待办已保存，证据关联至此分析。'
  })
}
async function refreshHistory(): Promise<void> {
  await action(async () => {
    history.value = await analyticsApi.saved(shopId.value)
    if (selectedSaved.value) {
      selectedSaved.value = await analyticsApi.getSaved(shopId.value, selectedSaved.value.id)
      result.value = selectedSaved.value?.snapshot ?? null
    }
    if (result.value)
      outdated.value = (await analyticsApi.revision(shopId.value)) !== result.value.source_revision
  })
}
async function changeTodo(actionName: 'complete' | 'reopen'): Promise<void> {
  if (!selectedSaved.value?.todo || busy.value) return
  await action(async () => {
    selectedSaved.value = await analyticsApi.changeTodo(
      shopId.value,
      selectedSaved.value!,
      actionName,
    )
    history.value = await analyticsApi.saved(shopId.value)
    success.value = '核对待办状态已保存。'
  })
}
async function show(item: Pick<SavedAnalysis, 'id'>): Promise<void> {
  await action(async () => {
    selectedSaved.value = await analyticsApi.getSaved(shopId.value, item.id)
    result.value = selectedSaved.value.snapshot
    outdated.value = selectedSaved.value.status !== 'current'
  })
}
async function rerun(item: SavedAnalysis): Promise<void> {
  Object.assign(scope, item.scope)
  question.value =
    questions[item.scope.intent === 'sales' ? 1 : item.scope.intent === 'low_margin' ? 2 : 0]!
  await nextTick()
  await run()
}
function money(value: string | null): string {
  return value ?? '未知 / 缺数据'
}
function time(value: string, timezone: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: timezone,
    dateStyle: 'medium',
    timeStyle: 'long',
  }).format(new Date(value))
}
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>让每笔毛利，有据可查。</h1>
      <p>单店铺、单币种与明确时间窗，从订单行核对经营判断。</p>
    </div>
    <span class="outline-label">经营分析</span>
  </div>
  <FeedbackBanner :message="error" /><FeedbackBanner :message="success" kind="success" />
  <p v-if="shopId">
    <RouterLink :to="{ path: '/agent', query: { shop: shopId, mode: 'question' } }">
      打开 AI 经营问数，确认范围与模型预算
    </RouterLink>
  </p>
  <p v-if="!shops.length && !busy">
    还没有店铺，请先<RouterLink to="/settings">添加经营资料</RouterLink>，再<RouterLink
      to="/imports"
      >导入商品和订单</RouterLink
    >。
  </p>
  <form v-else class="section-block" @submit.prevent="run">
    <h2>01 / 确认统计范围</h2>
    <fieldset :disabled="busy" class="analysis-fields">
      <label
        >分析店铺<select v-model="shopId" @change="selectShop">
          <option v-for="shop in shops" :key="shop.id" :value="shop.id">{{ shop.name }}</option>
        </select></label
      >
      <label
        >数据身份<select v-model="scope.data_identity">
          <option value="user_import">用户导入数据</option>
          <option value="synthetic">合成测试数据</option>
        </select></label
      >
      <label
        >统计币种<select v-model="scope.currency">
          <option
            v-for="currency in ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']"
            :key="currency"
          >
            {{ currency }}
          </option>
        </select></label
      >
      <label>显示时区<input v-model="scope.timezone" required placeholder="Asia/Shanghai" /></label>
      <label
        >起点（含时区，计入）<input
          v-model="scope.start_at"
          required
          placeholder="2026-10-01T00:00:00+08:00"
      /></label>
      <label
        >终点（含时区，不计入）<input
          v-model="scope.end_at"
          required
          placeholder="2026-11-01T00:00:00+08:00"
      /></label>
      <label class="full-width"
        >受控问题<input
          v-model="question"
          list="supported-questions"
          required
          maxlength="200" /><datalist id="supported-questions">
          <option v-for="item in questions" :key="item" :value="item" /></datalist
      ></label>
      <div class="button-row full-width">
        <button
          v-for="item in questions"
          :key="item"
          class="button secondary small"
          type="button"
          @click="question = item"
        >
          {{ item }}
        </button>
      </div>
      <label
        >低毛利筛选：最低购买数量<input
          v-model.number="scope.min_quantity"
          type="number"
          min="1"
          max="1000000"
          required
      /></label>
      <label
        >低毛利筛选：毛利率上限 %<input
          v-model="scope.max_margin_percent"
          type="number"
          min="-1000"
          max="100"
          step="0.01"
          required
      /></label>
    </fieldset>
    <p>
      起止时间使用 ISO 8601 格式；Z 表示 UTC，也可填写 +08:00。最长 366 天、最多 10000
      行。本页快捷计算支持上方三个问题；自由表述请使用 AI 经营问数。
    </p>
    <button class="button primary" :disabled="busy || !shopId">
      {{ busy ? '处理中…' : '计算并查看证据' }}
    </button>
  </form>
  <template v-if="result">
    <section class="section-block" aria-label="分析结果">
      <div class="section-title">
        <h2>02 / 销售与已知商品毛利</h2>
        <button class="button secondary" :disabled="busy || !!stale" @click="save">保存分析</button>
      </div>
      <p v-if="stale" role="alert" class="feedback error">
        此分析需重新计算，以下仅为历史快照，不能作为现值。
      </p>
      <p>
        {{ result.scope.data_identity === 'synthetic' ? '合成测试数据' : '用户导入数据' }} ·
        {{ result.scope.currency }} · 数据版本 {{ result.source_revision }}
      </p>
      <p>
        {{ time(result.scope.start_at, result.scope.timezone) }} 至
        {{ time(result.scope.end_at, result.scope.timezone) }}（不含终点）
      </p>
      <p>
        计算完成：{{
          time(result.calculated_at, result.scope.timezone)
        }}；数据截至时间请查看各来源导出时间，未知时无法推断。
      </p>
      <div class="analysis-metrics">
        <div>
          <span>原购买数量</span><strong>{{ result.summary.purchased_quantity }}</strong
          ><small>{{ result.summary.line_count }} 行已支付 / 含退款</small>
        </div>
        <div>
          <span>净销售额</span><strong>{{ money(result.summary.sales) }}</strong
          ><small
            >可核对子集 {{ result.summary.known_sales_subtotal }} ·
            {{ result.summary.sales_known_lines }} 行</small
          >
        </div>
        <div>
          <span>估算采购成本</span><strong>{{ money(result.summary.cost) }}</strong
          ><small
            >可核对子集 {{ result.summary.known_cost_subtotal }} ·
            {{ result.summary.cost_known_lines }} 行</small
          >
        </div>
        <div>
          <span>已知商品毛利（估算）</span><strong>{{ money(result.summary.gross_profit) }}</strong
          ><small
            >配对完整子集 {{ result.summary.known_gross_subtotal }} ·
            {{ result.summary.gross_known_lines }} 行</small
          >
        </div>
      </div>
      <p class="analysis-answer">{{ result.answer }}</p>
      <p v-if="result.candidates.length">符合当前问题：{{ result.candidates.join('、') }}</p>
      <p>{{ result.formula }}</p>
      <p>{{ result.cost_basis }}</p>
      <p>费用缺口：{{ result.fee_gaps.join('、') }}。</p>
      <ul>
        <li v-for="warning in result.warnings" :key="warning">{{ warning }}</li>
      </ul>
      <div class="table-scroll">
        <table>
          <caption>
            SKU 汇总 ·
            {{
              result.scope.currency
            }}
            · 按 SKU 展示
          </caption>
          <thead>
            <tr>
              <th>SKU</th>
              <th>原购买数量</th>
              <th>净销售额</th>
              <th>估算采购成本</th>
              <th>已知毛利</th>
              <th>毛利率</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in result.skus" :key="item.sku!">
              <td>{{ item.sku }}</td>
              <td>{{ item.purchased_quantity }}</td>
              <td>{{ money(item.sales) }}</td>
              <td>{{ money(item.cost) }}</td>
              <td>{{ money(item.gross_profit) }}</td>
              <td>
                {{ item.margin_percent === null ? '未知 / 不适用' : `${item.margin_percent}%` }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <section v-if="selectedSaved" id="linked-analysis" class="data-note" aria-label="分析核对待办">
      <div>
        <h3>分析 #{{ selectedSaved.id }}</h3>
        <p v-if="selectedSaved.todo">
          待办 #{{ selectedSaved.todo.id }} · {{ stateNames[selectedSaved.todo.status] }} · 版本
          {{ selectedSaved.todo.version }}
        </p>
        <div v-if="selectedSaved.todo && selectedSaved.status === 'current'" class="button-row">
          <button
            v-if="selectedSaved.todo.status === 'open'"
            class="button secondary"
            :disabled="busy || stale"
            @click="changeTodo('complete')"
          >
            标记核对完成
          </button>
          <button
            v-if="selectedSaved.todo.status === 'completed'"
            class="button secondary"
            :disabled="busy || stale"
            @click="changeTodo('reopen')"
          >
            重新打开核对待办
          </button>
        </div>
      </div>
    </section>
    <AnalysisEvidence :result="result" :shop-id="shopId" />
  </template>
  <section v-if="shopId" class="section-block">
    <div class="section-title">
      <h2>03 / 已保存分析与待办 · 最近 50 条</h2>
      <button class="button secondary small" :disabled="busy" @click="refreshHistory">
        刷新保存记录
      </button>
    </div>
    <p v-if="!history.length">尚未保存分析。计算后可保存来源和统计口径，再创建核对待办。</p>
    <article v-for="item in history" :key="item.id" class="batch-history">
      <div>
        <h3>分析 #{{ item.id }} · {{ stateNames[item.status] }}</h3>
        <p>
          {{ time(item.created_at, item.scope.timezone) }} · {{ item.scope.currency }} ·
          {{ item.scope.data_identity === 'synthetic' ? '合成测试数据' : '用户导入数据' }}
        </p>
        <p v-if="item.todo">
          待办 #{{ item.todo.id }} · {{ item.todo.title }} · {{ stateNames[item.todo.status] }}
        </p>
      </div>
      <div class="button-row">
        <button class="button secondary small" :disabled="busy" @click="rerun(item)">
          按此范围重算
        </button>
        <button
          class="button secondary small"
          :disabled="busy || item.status === 'cleared'"
          @click="show(item)"
        >
          查看分析 #{{ item.id }}</button
        ><button
          class="button secondary small"
          :disabled="busy || item.status !== 'current' || !!item.todo"
          @click="todo(item)"
        >
          创建核对待办
        </button>
      </div>
    </article>
  </section>
</template>
