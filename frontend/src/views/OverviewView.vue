<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { overviewApi } from '@/api/overview'
import { identityApi } from '@/api/identity'
import { analyticsApi } from '@/api/analytics'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import type { OverviewResult, OverviewSaved, OverviewScope } from '@/types/overview'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import OverviewShopCard from '@/components/OverviewShopCard.vue'

const shops = ref<Shop[]>([])
const busy = ref(false)
const error = ref('')
const success = ref('')
const result = ref<OverviewResult | null>(null)
const saved = ref<OverviewSaved | null>(null)
const history = ref<OverviewSaved[]>([])
const cursor = ref<number | null>(null)
const stale = ref(false)
const confirmClear = ref(false)
const platform = ref('')
const market = ref('')
const preset = ref('7')
const customCompare = ref(false)
const formOpen = ref(true)
let requestId = ''
let alive = true
const currencies = ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']
const scope = reactive<OverviewScope>({
  shop_ids: [],
  start_date: '',
  end_date: '',
  comparison_start: null,
  comparison_end: null,
  timezone: 'Asia/Shanghai',
  data_identity: 'user_import',
  currencies: [],
  max_age_hours: 24,
  min_quantity: 1,
  max_margin_percent: '20',
})
const available = computed(() =>
  shops.value.filter(
    (s) =>
      (!platform.value || s.platform === platform.value) &&
      (!market.value || s.market === market.value),
  ),
)
const names: Record<string, string> = {
  current: '来源未变化',
  stale: '需重新生成',
  cleared: '正文已清除',
}
const time = (value: string, zone: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    timeZone: zone,
    dateStyle: 'medium',
    timeStyle: 'long',
  }).format(new Date(value))
function dates(): void {
  if (preset.value === 'custom') return
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: scope.timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(new Date())
    const get = (type: string) => parts.find((p) => p.type === type)!.value
    const end = `${get('year')}-${get('month')}-${get('day')}`
    scope.end_date = end
    scope.start_date = new Date(Date.parse(`${end}T00:00:00Z`) - Number(preset.value) * 86400000)
      .toISOString()
      .slice(0, 10)
  } catch {
    /* Invalid timezone is validated on submit. */
  }
}
function reset(): void {
  result.value = null
  saved.value = null
  stale.value = false
  success.value = ''
  confirmClear.value = false
  requestId = ''
}
watch(scope, reset, { deep: true })
watch([platform, market], () => {
  scope.shop_ids = available.value.map((s) => s.id).slice(0, 20)
})
watch(() => scope.timezone, dates)
watch(preset, dates)
watch(customCompare, (value) => {
  if (!value) {
    scope.comparison_start = null
    scope.comparison_end = null
  }
  reset()
})
async function action(work: () => Promise<void>): Promise<void> {
  busy.value = true
  error.value = ''
  success.value = ''
  try {
    await work()
  } catch (cause) {
    if (alive) error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function loadHistory(more = false): Promise<void> {
  const page = await overviewApi.list(more ? (cursor.value ?? undefined) : undefined)
  if (!alive) return
  history.value = more ? [...history.value, ...page.items] : page.items
  cursor.value = page.next_cursor
}
async function run(): Promise<void> {
  await action(async () => {
    reset()
    const input = JSON.parse(JSON.stringify(scope)) as OverviewScope
    const loaded = await overviewApi.calculate(input)
    if (alive) {
      result.value = loaded
      requestId = crypto.randomUUID()
      formOpen.value = false
    }
  })
}
async function save(): Promise<void> {
  if (!result.value) return
  const current = result.value
  await action(async () => {
    const response = await overviewApi.save(current, requestId)
    if (!alive) return
    saved.value = response
    result.value = response.snapshot
    stale.value = response.status !== 'current'
    await loadHistory()
    success.value = '摘要已保存，可刷新后回读。库存按保存时刻再次核验。'
  })
}
async function show(id: number): Promise<void> {
  await action(async () => {
    const response = await overviewApi.get(id)
    if (!alive) return
    saved.value = response
    result.value = response.snapshot
    stale.value = response.status !== 'current'
    confirmClear.value = false
    formOpen.value = false
  })
}
async function refresh(): Promise<void> {
  await action(async () => {
    await loadHistory()
    if (saved.value) {
      saved.value = await overviewApi.get(saved.value.id)
      result.value = saved.value.snapshot
      stale.value = saved.value.status !== 'current'
    } else if (result.value) {
      const current = result.value
      const versions = await Promise.all(current.shops.map((s) => analyticsApi.revision(s.shop_id)))
      stale.value =
        current.shops.some((s, i) => versions[i] !== s.source_revision) ||
        !!(current.valid_until && Date.parse(current.valid_until) <= Date.now())
      // Hide an unsaved snapshot on source changes; a cleared batch must not remain on screen.
      if (stale.value) {
        result.value = null
        error.value = '来源或库存时效已变化，请重新生成。'
      }
    }
  })
}
async function clear(): Promise<void> {
  if (!saved.value || !confirmClear.value) return
  await action(async () => {
    saved.value = await overviewApi.clear(saved.value!.id)
    result.value = null
    confirmClear.value = false
    await loadHistory()
    success.value = '摘要正文与来源依赖已清除，保留范围、状态和审计。'
  })
}
function focused(): void {
  if (!busy.value) void refresh()
}
onMounted(async () => {
  dates()
  window.addEventListener('focus', focused)
  await action(async () => {
    shops.value = await identityApi.shops()
    scope.shop_ids = shops.value.map((s) => s.id).slice(0, 20)
    await loadHistory()
  })
})
onUnmounted(() => {
  alive = false
  window.removeEventListener('focus', focused)
})
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>看清每家店，再做下一步。</h1>
      <p>跨店经营总览与日、周、月摘要。每个数字都能回到来源。</p>
    </div>
    <span class="outline-label">文件覆盖 · 本地规则</span>
  </div>
  <FeedbackBanner :message="error" /><FeedbackBanner :message="success" kind="success" />
  <p v-if="!shops.length && !busy">
    还没有店铺。请先<RouterLink to="/settings">添加经营资料</RouterLink>，再<RouterLink
      to="/imports"
      >导入数据</RouterLink
    >。
  </p>
  <details
    v-if="shops.length"
    class="section-block overview-form"
    :open="formOpen"
    @toggle="formOpen = ($event.target as HTMLDetailsElement).open"
  >
    <summary>01 / 选择店铺与统计范围</summary>
    <form @submit.prevent="run">
      <fieldset :disabled="busy" class="analysis-fields">
        <label
          >平台筛选<select v-model="platform">
            <option value="">所有已登记平台</option>
            <option v-for="p in [...new Set(shops.map((s) => s.platform))]" :key="p" :value="p">
              {{ p }}
            </option>
          </select></label
        >
        <label
          >市场筛选<select v-model="market">
            <option value="">所有已登记市场</option>
            <option v-for="m in [...new Set(shops.map((s) => s.market))]" :key="m" :value="m">
              {{ m }}
            </option>
          </select></label
        >
        <div class="full-width">
          <p>选择店铺（最多 20 家）</p>
          <div class="shop-options">
            <label v-for="shop in available" :key="shop.id" class="check-label"
              ><input v-model="scope.shop_ids" type="checkbox" :value="shop.id" />{{ shop.name }} ·
              {{ shop.platform }} / {{ shop.market }}</label
            >
          </div>
        </div>
        <label
          >数据身份<select v-model="scope.data_identity">
            <option value="user_import">用户导入数据</option>
            <option value="synthetic">合成测试数据</option>
          </select></label
        >
        <label
          >日期快捷范围<select v-model="preset">
            <option value="1">前一完整日 · 日报</option>
            <option value="7">最近 7 个完整日 · 周报</option>
            <option value="30">最近 30 个完整日 · 月报</option>
            <option value="custom">自选区间</option>
          </select></label
        >
        <label
          >统计时区<input v-model="scope.timezone" required placeholder="Asia/Shanghai"
        /></label>
        <label
          >统计币种<select
            :value="scope.currencies[0] ?? ''"
            @change="
              scope.currencies = ($event.target as HTMLSelectElement).value
                ? [($event.target as HTMLSelectElement).value]
                : []
            "
          >
            <option value="">全部币种，分别汇总</option>
            <option v-for="c in currencies" :key="c">{{ c }}</option>
          </select></label
        >
        <label
          >开始日期（计入）<input
            v-model="scope.start_date"
            type="date"
            required
            :disabled="preset !== 'custom'"
        /></label>
        <label
          >结束日期（不计入）<input
            v-model="scope.end_date"
            type="date"
            required
            :disabled="preset !== 'custom'"
        /></label>
        <label class="check-label full-width"
          ><input
            v-model="customCompare"
            type="checkbox"
          />自选对比区间（默认对比此前相同日历天数）</label
        >
        <template v-if="customCompare"
          ><label>对比开始日期<input v-model="scope.comparison_start" type="date" required /></label
          ><label
            >对比结束日期（不计入）<input
              v-model="scope.comparison_end"
              type="date"
              required /></label
        ></template>
        <label
          >库存有效小时<input
            v-model.number="scope.max_age_hours"
            type="number"
            min="1"
            max="720"
            required
        /></label>
        <label
          >低毛利最低购买件数<input
            v-model.number="scope.min_quantity"
            type="number"
            min="1"
            max="1000000"
            required
        /></label>
        <label
          >低毛利率上限（%）<input
            v-model="scope.max_margin_percent"
            type="text"
            inputmode="decimal"
            required
        /></label>
      </fieldset>
      <p class="muted">
        本页检查口径独立；经营规则页的约束用于今日运营与 Agent。空白数据保持未知。
      </p>
      <button class="button primary" :disabled="busy || !scope.shop_ids.length">
        {{ busy ? '正在处理…' : '生成经营总览' }}
      </button>
    </form>
  </details>
  <section v-if="saved" class="data-note">
    <h2>摘要 #{{ saved.id }} · {{ names[saved.status] }}</h2>
    <p>保存于 {{ time(saved.created_at, saved.scope.timezone) }}</p>
  </section>
  <section v-if="result" aria-label="经营总览结果">
    <p v-if="stale" role="alert" class="analysis-answer">
      历史来源或库存时效已变化，以下为保存时的结果；请重新生成后判断当前经营。
    </p>
    <div class="section-block">
      <div class="section-title">
        <h2>02 / 按币种核对经营</h2>
        <span class="outline-label">{{
          result.scope.data_identity === 'synthetic' ? '合成测试数据' : '用户导入数据'
        }}</span>
      </div>
      <p>分析完成：{{ time(result.calculated_at, result.scope.timezone) }}</p>
      <p>
        本期 {{ result.scope.start_date }} → {{ result.scope.end_date }}；对比
        {{ result.scope.comparison_start }} → {{ result.scope.comparison_end }}（终点均不含）
      </p>
      <p v-if="result.valid_until">
        快照下一核验点：{{ time(result.valid_until, result.scope.timezone) }}。此后需重新生成。
      </p>
      <div class="overview-totals">
        <article
          v-for="total in result.totals"
          :key="total.currency"
          class="total-card"
          :aria-label="`${total.currency} 汇总`"
        >
          <span class="eyebrow">{{ total.currency }} · 净销售额</span
          ><strong>{{ total.sales ?? '未知 / 不完整' }}</strong>
          <p>可验证子集 {{ total.known_sales }}</p>
          <p>对比期 {{ total.comparison_sales ?? '未知 / 不完整' }}</p>
          <p>
            差额 {{ total.sales_change ?? '未知' }} ·
            {{
              total.sales_change_percent === null ? '变化率未知' : `${total.sales_change_percent}%`
            }}
          </p>
          <p>已观察支付订单 {{ total.observed_orders }}</p>
          <p>
            已知商品毛利 {{ total.gross_profit ?? '未知 / 不完整' }}<br />已知子集
            {{ total.known_gross_profit }}
          </p>
          <p>行退款 {{ total.refunds ?? '未知 / 不完整' }} · 已知子集 {{ total.known_refunds }}</p>
          <details>
            <summary>汇总覆盖说明</summary>
            <p>计入店铺 ID：{{ total.shop_ids.join('、') }}</p>
            <p v-for="warning in total.warnings" :key="warning">{{ warning }}</p>
          </details>
        </article>
      </div>
      <details>
        <summary>口径与未获取项</summary>
        <p v-for="item in result.limitations" :key="item">{{ item }}</p>
      </details>
    </div>
    <section class="section-block">
      <h2>03 / 当次经营摘要</h2>
      <p v-for="line in result.summary" :key="line">{{ line }}</p>
      <button v-if="!saved" class="button primary" :disabled="busy || stale" @click="save">
        保存本地摘要
      </button>
      <p>保存时重新核验来源；摘要不会触发外发或创建待办。</p>
    </section>
    <OverviewShopCard
      v-for="shop in result.shops"
      :key="shop.shop_id"
      :shop="shop"
      :timezone="result.scope.timezone"
    />
  </section>
  <section class="section-block">
    <div class="section-title">
      <h2>已保存的经营摘要</h2>
      <button class="button secondary small" :disabled="busy" @click="refresh">
        刷新摘要与来源状态
      </button>
    </div>
    <p v-if="!history.length">尚未保存摘要。完成一次总览后可保存并回读。</p>
    <div v-for="item in history" :key="item.id" class="batch-history">
      <span
        >#{{ item.id }} · {{ item.scope.start_date }} → {{ item.scope.end_date }} ·
        {{ names[item.status] }}</span
      ><button class="button secondary small" :disabled="busy" @click="show(item.id)">
        查看摘要 #{{ item.id }}
      </button>
    </div>
    <button
      v-if="cursor"
      class="button secondary small"
      :disabled="busy"
      @click="action(() => loadHistory(true))"
    >
      加载更早摘要
    </button>
    <div v-if="saved && saved.status !== 'cleared'" class="clear-report">
      <label class="check-label"
        ><input v-model="confirmClear" type="checkbox" :disabled="busy" />清除摘要 #{{
          saved.id
        }}
        的正文，保留范围与审计</label
      ><button class="button secondary small" :disabled="busy || !confirmClear" @click="clear">
        清除所选摘要正文
      </button>
    </div>
  </section>
</template>
<style scoped>
.overview-form summary {
  font-size: 19px;
  font-weight: 600;
  cursor: pointer;
}
.overview-form label.check-label {
  display: flex;
  align-items: center;
}
.shop-options {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
}
.overview-totals {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  margin: 24px 0;
}
.total-card {
  padding: 24px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #f5f7ef;
  overflow-wrap: anywhere;
}
.total-card strong {
  display: block;
  font-size: clamp(24px, 3vw, 34px);
  margin: 14px 0;
  color: var(--green);
}
.total-card p,
section p {
  line-height: 1.7;
}
.data-note {
  display: block;
}
.clear-report {
  display: grid;
  gap: 14px;
  margin-top: 24px;
}
@media (max-width: 760px) {
  .overview-totals {
    grid-template-columns: 1fr;
  }
  .shop-options {
    display: grid;
  }
}
</style>
