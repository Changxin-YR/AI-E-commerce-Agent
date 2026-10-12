<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Taro, { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import {
  checkedOverviewScope,
  type OverviewPage,
  type OverviewResult,
  type OverviewSaved,
} from '../../services/overview-policy'
import { queryString } from '../../services/task-policy'
import { supportTime } from '../../services/support-types'
import { openLink } from '../../services/navigation'
import SourceList from '../../components/SourceList.vue'
const scope = reactive({
  shop_ids: [] as number[],
  start_date: '',
  end_date: '',
  comparison_start: null as string | null,
  comparison_end: null as string | null,
  timezone: 'Asia/Shanghai',
  data_identity: 'user_import' as 'user_import' | 'synthetic',
  currencies: [] as string[],
  max_age_hours: 24,
  min_quantity: 1,
  max_margin_percent: '20',
})
const result = ref<OverviewResult>(),
  saved = ref<OverviewSaved>(),
  history = ref<OverviewSaved[]>([]),
  before = ref<number | null>(null)
const busy = ref(false),
  error = ref(''),
  notice = ref(''),
  unknown = ref(false),
  confirmClear = ref(false),
  filters = reactive({ platform: '', market: '' })
let alive = true,
  epoch = 0,
  linked: Record<string, string> = {}
const request = scopedRequest(api, () => (alive ? epoch : null))
const shops = computed(() =>
  account.shops.filter(
    (s) =>
      (!filters.platform || s.platform === filters.platform) &&
      (!filters.market || s.market === filters.market),
  ),
)
const platforms = computed(() => [
    ...new Set(account.shops.map((s) => s.platform)),
  ]),
  markets = computed(() => [...new Set(account.shops.map((s) => s.market))])
const currencies = [
  'USD',
  'CNY',
  'EUR',
  'GBP',
  'JPY',
  'CAD',
  'AUD',
  'HKD',
  'SGD',
]
useLoad((v) => {
  linked = v as Record<string, string>
})
useUnload(() => {
  alive = false
  epoch++
})
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    epoch++
    result.value = undefined
    saved.value = undefined
    history.value = []
    error.value = notice.value = ''
    confirmClear.value = false
  },
  { flush: 'sync' },
)
watch(
  () => [filters.platform, filters.market],
  () => {
    scope.shop_ids = shops.value.map((s) => s.id).slice(0, 20)
    result.value = undefined
  },
)
function dates() {
  const end = new Date()
  end.setUTCHours(0, 0, 0, 0)
  scope.end_date = end.toISOString().slice(0, 10)
  end.setUTCDate(end.getUTCDate() - 7)
  scope.start_date = end.toISOString().slice(0, 10)
}
async function perform(work: () => Promise<void>) {
  if (busy.value || !alive) return
  busy.value = true
  error.value = notice.value = ''
  try {
    await work()
  } catch (e) {
    if (alive) error.value = e instanceof Error ? e.message : '总览操作失败。'
  } finally {
    busy.value = false
  }
}
async function list(more = false) {
  const page = await request<OverviewPage>(
    `/overview/reports${more && before.value ? `?before=${before.value}` : ''}`,
  )
  history.value = more ? [...history.value, ...page.items] : page.items
  before.value = page.next_cursor
}
async function calculate() {
  await perform(async () => {
    const input = checkedOverviewScope(scope)
    result.value = await request<OverviewResult>(
      '/overview/calculate',
      'POST',
      input,
    )
    saved.value = undefined
  })
}
async function save() {
  await perform(async () => {
    if (!result.value || unknown.value) return
    unknown.value = true
    const value = await request<OverviewSaved>('/overview/reports', 'POST', {
      request_id: crypto.randomUUID(),
      scope: result.value.scope,
      expected_revisions: Object.fromEntries(
        result.value.shops.map((s) => [s.shop_id, s.source_revision]),
      ),
    })
    saved.value = await request<OverviewSaved>(`/overview/reports/${value.id}`)
    result.value = saved.value.snapshot || undefined
    await list()
    unknown.value = false
    notice.value = '总览已保存并回读。'
  })
}
async function show(id: number) {
  await perform(async () => {
    saved.value = await request<OverviewSaved>(`/overview/reports/${id}`)
    result.value = saved.value.snapshot || undefined
    confirmClear.value = false
  })
}
async function clearReport() {
  await perform(async () => {
    if (!saved.value || saved.value.status === 'cleared') return
    const id = saved.value.id
    const answer = await Taro.showModal({
      title: '清除摘要正文',
      content:
        '清除正文与来源依赖后无法恢复，保留范围、状态和审计记录，依赖的分析与待办将失效。确认继续？',
    })
    if (!answer.confirm || saved.value?.id !== id || !account.session) return
    await request<OverviewSaved>(`/overview/reports/${id}/clear`, 'POST', {
      confirm: true,
    })
    const cleared = await request<OverviewSaved>(`/overview/reports/${id}`)
    saved.value = cleared
    result.value = undefined
    confirmClear.value = false
    await list()
    notice.value = '摘要正文与来源依赖已清除，保留范围、状态和审计。'
  })
}
function toggleShop(id: number, event: unknown) {
  const checked = Boolean(
    (event as { detail: { value: boolean } }).detail.value,
  )
  scope.shop_ids = checked
    ? [...scope.shop_ids, id].slice(0, 20)
    : scope.shop_ids.filter((x) => x !== id)
}
async function openTasks(shop: number, task?: number) {
  await openLink('/', {
    shop: String(shop),
    ...(task ? { task: String(task) } : {}),
  })
}
function pickDate(field: 'start_date' | 'end_date', e: unknown) {
  scope[field] = String((e as { detail: { value: string } }).detail.value)
}
function pick(field: 'identity' | 'platform' | 'market', e: unknown) {
  const value = String((e as { detail: { value: string } }).detail.value)
  if (field === 'identity')
    scope.data_identity = value as 'user_import' | 'synthetic'
  else filters[field] = value
}
useDidShow(() => {
  void perform(async () => {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    if (!scope.start_date) dates()
    scope.shop_ids ||= shops.value.map((s) => s.id).slice(0, 20)
    if (linked.shop && Number(linked.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不同。')
    await list()
    linked = {}
  })
})
</script>
<template>
  <view class="screen"
    ><view class="hero"
      ><text class="eyebrow">SOLOOPS · OVERVIEW</text
      ><text class="title">看清每家店，再做下一步。</text
      ><text class="muted">跨店经营总览、对比区间和来源明细。</text></view
    >
    <text v-if="error" class="error">{{ error }}</text
    ><text v-if="notice" class="hint">{{ notice }}</text
    ><text v-if="unknown" class="error">保存结果待核对，请刷新历史。</text>
    <view class="card"
      ><text class="section-title">统计范围</text
      ><picker
        :range="['用户导入', '合成测试']"
        :value="scope.data_identity === 'synthetic' ? 1 : 0"
        :disabled="busy"
        @change="pick('identity', $event)"
        ><view class="field">身份：{{ scope.data_identity }}</view></picker
      ><picker
        :range="['全部平台', ...platforms]"
        :value="Math.max(0, platforms.indexOf(filters.platform) + 1)"
        :disabled="busy"
        @change="pick('platform', $event)"
        ><view class="field"
          >平台：{{ filters.platform || '全部' }}</view
        ></picker
      ><picker
        :range="['全部市场', ...markets]"
        :value="Math.max(0, markets.indexOf(filters.market) + 1)"
        :disabled="busy"
        @change="pick('market', $event)"
        ><view class="field">市场：{{ filters.market || '全部' }}</view></picker
      ><text v-for="shop in shops" :key="shop.id"
        ><switch
          :checked="scope.shop_ids.includes(shop.id)"
          :disabled="busy"
          @change="toggleShop(shop.id, $event)"
        />{{ shop.name }} · {{ shop.platform }} / {{ shop.market }}</text
      ><text class="label">起止日期（结束不含）</text
      ><input v-model="scope.start_date" :disabled="busy" /><input
        v-model="scope.end_date"
        :disabled="busy"
      /><text class="label">统计时区</text
      ><input v-model="scope.timezone" :disabled="busy" /><picker
        :range="currencies"
        :disabled="busy"
        @change="
          scope.currencies = [
            $event.detail.value !== undefined
              ? currencies[Number($event.detail.value)]
              : '',
          ]
        "
        ><view class="field"
          >币种：{{ scope.currencies.join(', ') || '全部币种分别汇总' }}</view
        ></picker
      ><text class="label">库存有效小时 / 低毛利最低件数 / 毛利上限</text
      ><input
        v-model.number="scope.max_age_hours"
        type="number"
        :disabled="busy"
      /><input
        v-model.number="scope.min_quantity"
        type="number"
        :disabled="busy"
      /><input v-model="scope.max_margin_percent" :disabled="busy" /><button
        class="primary"
        :disabled="busy || !scope.shop_ids.length"
        @tap="calculate"
      >
        生成跨店总览
      </button></view
    >
    <view v-if="result" class="card"
      ><text class="section-title"
        >结果 ·
        {{ supportTime(result.calculated_at, result.scope.timezone) }}</text
      ><text
        >本期 {{ result.scope.start_date }} →
        {{ result.scope.end_date }}，来源身份
        {{ result.scope.data_identity }}</text
      ><text v-for="line in result.summary" :key="line">{{ line }}</text
      ><text v-for="limit in result.limitations" :key="limit" class="hint">{{
        limit
      }}</text
      ><view v-for="total in result.totals" :key="total.currency" class="card"
        ><text class="section-title">{{ total.currency }} 汇总</text
        ><text
          >销售 {{ total.sales || '未知' }} · 已知子集 {{ total.known_sales }} ·
          对比 {{ total.comparison_sales || '未知' }}</text
        ><text
          >变化 {{ total.sales_change || '未知' }}（{{
            total.sales_change_percent || '未知'
          }}%） · 观察订单 {{ total.observed_orders }}</text
        ><text
          >已知商品毛利 {{ total.gross_profit || '未知' }} · 子集
          {{ total.known_gross_profit }} · 退款
          {{ total.refunds || '未知' }}</text
        ><text v-for="w in total.warnings" :key="w" class="hint">{{
          w
        }}</text></view
      ><button :disabled="busy || unknown" @tap="save">保存总览</button
      ><view v-for="shop in result.shops" :key="shop.shop_id" class="card"
        ><text class="section-title"
          >{{ shop.shop_name }} · {{ shop.platform }} / {{ shop.market }}</text
        ><text
          >库存低于阈值 {{ shop.inventory_low ?? '未知' }} · 库存未知
          {{ shop.inventory_unknown }} · 消息
          {{ shop.message_count ?? '未知' }} · 来源版本
          {{ shop.source_revision }}</text
        ><text v-for="group in shop.currencies" :key="group.currency"
          >{{ group.currency }}：订单 {{ group.current.orders ?? '未知' }} ·
          销售 {{ group.current.analysis.summary.sales || '未知' }} · 毛利
          {{ group.current.analysis.summary.gross_profit || '未知' }} · Top SKU
          {{ group.current.top_skus.join('、') || '暂无' }}</text
        ><SourceList :sources="shop.sources" :shop-id="shop.shop_id" /><button
          v-for="task in shop.tasks"
          :key="task.id"
          @tap="openTasks(shop.shop_id, task.id)"
        >
          待办 #{{ task.id }} · {{ task.kind }} · {{ task.status }} /
          {{ task.source_status }}</button
        ><button v-if="shop.tasks_has_more" @tap="openTasks(shop.shop_id)">
          更多待办
        </button></view
      ></view
    >
    <view v-if="saved" class="card"
      ><view class="row"
        ><text class="section-title">摘要 #{{ saved.id }}</text
        ><text class="badge">{{ saved.status }}</text></view
      ><text class="hint"
        >保存于 {{ supportTime(saved.created_at, saved.scope.timezone) }} · 范围
        {{ saved.scope.start_date }} → {{ saved.scope.end_date }}</text
      ><template v-if="saved.status !== 'cleared'"
        ><checkbox-group
          @change="confirmClear = Boolean(($event.detail.value || []).length)"
          ><label class="label"
            ><checkbox
              value="clear"
              :checked="confirmClear"
              :disabled="busy"
            />清除后正文与来源依赖不可恢复，仅保留范围、状态与审计</label
          ></checkbox-group
        ><button
          class="danger"
          :disabled="busy || !confirmClear"
          @tap="clearReport"
        >
          清除所选摘要正文
        </button></template
      ><text v-else class="hint"
        >正文与来源依赖已清除，仅保留范围、状态与审计。</text
      ></view
    >
    <view class="card"
      ><text class="section-title">已保存总览</text
      ><button :disabled="busy" @tap="list()">刷新历史</button
      ><text v-if="!history.length" class="muted">暂无保存总览。</text
      ><button
        v-for="item in history"
        :key="item.id"
        :disabled="busy"
        @tap="show(item.id)"
      >
        #{{ item.id }} · {{ item.status }} · {{ item.scope.start_date }} →
        {{ item.scope.end_date }}</button
      ><button v-if="before" :disabled="busy" @tap="list(true)">
        加载更早摘要
      </button></view
    >
  </view>
</template>
