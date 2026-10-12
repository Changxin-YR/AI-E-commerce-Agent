// route: /order-reconciliation
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import { openLink as openRoute } from '../../services/navigation'
import { supportTime } from '../../services/support-types'
import SourceList from '../../components/SourceList.vue'
import {
  channels,
  checkedOrderScope,
  emptyOrderScope,
  identities,
  orderComparisonStatuses,
  statementLineLabel,
  statementLinesPerPage,
  trimmedAmount,
  type OrderComparison,
  type OrderReconciliation,
  type OrderReconciliationScope,
  type SourceChannel,
} from '../../services/statement-policy'

const scope = reactive<OrderReconciliationScope>(emptyOrderScope())
const result = ref<OrderReconciliation>()
const orderPage = ref(0)
const statementPage = ref(0)
const comparisonFilter = ref<'all' | 'sale' | 'refund'>('all')
const busy = ref(false)
const error = ref('')
const notice = ref('')
let alive = true
let epoch = 0
let linked: Record<string, string> = {}
const request = scopedRequest(api, () => (alive ? epoch : null))
const timezone = computed(
  () =>
    account.shops.find((s) => s.id === account.shopId)?.timezone ||
    'Asia/Shanghai',
)
const canRead = computed(
  () =>
    !busy.value &&
    (scope.sale_basis === 'unknown' || Boolean(scope.basis_note.trim())),
)
const comparisonSummary = computed(() => {
  if (!result.value) return ''
  const counts = new Map<string, number>()
  for (const item of result.value.comparisons)
    counts.set(item.status, (counts.get(item.status) ?? 0) + 1)
  return [...counts.entries()]
    .map(([key, count]) => `${orderComparisonStatuses[key] || key} ${count}`)
    .sort()
    .join(' · ')
})
const visibleComparisons = computed(() =>
  (result.value?.comparisons || []).filter(
    (item) =>
      comparisonFilter.value === 'all' ||
      item.entry_type === comparisonFilter.value,
  ),
)
const visibleOrders = computed(() =>
  (result.value?.orders || []).slice(
    orderPage.value * statementLinesPerPage,
    orderPage.value * statementLinesPerPage + statementLinesPerPage,
  ),
)
const visibleStatements = computed(() =>
  (result.value?.statements || []).slice(
    statementPage.value * statementLinesPerPage,
    statementPage.value * statementLinesPerPage + statementLinesPerPage,
  ),
)
const windowsOrders = computed(
  () => (result.value?.orders || []).filter((item) => item.in_window).length,
)
const linkedOrders = computed(
  () => (result.value?.orders || []).filter((item) => !item.in_window).length,
)

useLoad((params) => {
  linked = params as Record<string, string>
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
    orderPage.value = 0
    statementPage.value = 0
    comparisonFilter.value = 'all'
    error.value = '请返回工作台登录并选择店铺。'
    notice.value = ''
  },
  { flush: 'sync' },
)
watch(
  () => [
    scope.data_identity,
    scope.channel,
    scope.timezone,
    scope.start_at,
    scope.end_at,
  ],
  () => {
    scope.sale_basis = 'unknown'
    scope.basis_note = ''
    result.value = undefined
  },
  { flush: 'sync' },
)
watch(scope, () => {
  result.value = undefined
  orderPage.value = 0
  statementPage.value = 0
  error.value = ''
  notice.value = ''
})

async function perform(work: () => Promise<void>) {
  if (busy.value || !alive) return
  const token = epoch
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await work()
  } catch (cause) {
    if (alive && token === epoch)
      error.value =
        cause instanceof Error ? cause.message : '订单核对未完成，请重新读取。'
  } finally {
    if (alive) busy.value = false
  }
}

async function reconcile() {
  if (!account.session || !account.shopId)
    throw new Error('请先登录并选择店铺。')
  if (!canRead.value) return
  const shop = account.shopId
  await perform(async () => {
    const input = checkedOrderScope(scope)
    result.value = await request<OrderReconciliation>(
      `/shops/${shop}/statements/orders/reconcile`,
      'POST',
      input,
    )
    orderPage.value = 0
    statementPage.value = 0
    notice.value =
      '已读取当前来源的只读核对结果；不保存人工结论，来源变化后请重新读取。'
  })
}

function comparisonLabel(item: OrderComparison) {
  return orderComparisonStatuses[item.status] || item.status
}

function pickIdentity(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  scope.data_identity = identities[index] || 'user_import'
}

function pickChannel(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  scope.channel = channels[index] || 'generic'
}

function pickBasis(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  scope.sale_basis = index === 1 ? 'merchandise_after_discount' : 'unknown'
  if (scope.sale_basis === 'unknown') scope.basis_note = ''
  result.value = undefined
}

function pickFilter(value: 'all' | 'sale' | 'refund') {
  comparisonFilter.value = value
}

function openPage(path: string, query: Record<string, string> = {}) {
  void openRoute(path, { shop: String(account.shopId || ''), ...query }).catch(
    (cause: unknown) => {
      error.value =
        cause instanceof Error ? cause.message : '打开业务页面失败。'
    },
  )
}

function moreOrders() {
  if (!result.value) return
  if (
    (orderPage.value + 1) * statementLinesPerPage <
    result.value.orders.length
  )
    orderPage.value++
}

function fewerOrders() {
  orderPage.value = Math.max(0, orderPage.value - 1)
}

function moreStatements() {
  if (!result.value) return
  if (
    (statementPage.value + 1) * statementLinesPerPage <
    result.value.statements.length
  )
    statementPage.value++
}

function fewerStatements() {
  statementPage.value = Math.max(0, statementPage.value - 1)
}

useDidShow(() => {
  void perform(async () => {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    if (linked.shop && Number(linked.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不同，请切换店铺后重试。')
    const identity =
      linked.data_identity === 'synthetic' ? 'synthetic' : 'user_import'
    const channel: SourceChannel = channels.includes(
      linked.channel as SourceChannel,
    )
      ? (linked.channel as SourceChannel)
      : 'generic'
    Object.assign(scope, emptyOrderScope(timezone.value))
    scope.data_identity = identity
    scope.channel = channel
    result.value = undefined
    linked = {}
    notice.value = '请核实金额口径后读取；结果只读，不保存人工结论。'
  })
})
</script>

<template>
  <view class="screen">
    <view class="hero">
      <text class="eyebrow">SOLOOPS · ORDER RECONCILIATION</text>
      <text class="title">订单与账单，差异有据。</text>
      <text class="muted"
        >关联销售与退款来源，逐项查看金额差异及待补依据。</text
      >
    </view>
    <view class="card">
      <text class="hint"
        >窗口选取候选，同订单号全部当前行作为关联依据；文件覆盖完整性未知。退款缺逐笔交易信息统一待核，不计算交易差额、完整净利润或银行到账。</text
      >
      <button :disabled="busy" @tap="openPage('/statements')">
        返回账单与费用
      </button>
      <button :disabled="busy" @tap="openPage('/settlements')">
        结算与回款
      </button>
    </view>
    <text v-if="error" class="error">{{ error }}</text>
    <text v-if="notice" class="hint">{{ notice }}</text>
    <view class="card">
      <text class="section-title">核对范围与金额口径</text>
      <picker
        :range="['用户导入', '合成测试']"
        :value="identities.indexOf(scope.data_identity)"
        :disabled="busy"
        @change="pickIdentity"
        ><view class="select"
          >身份：{{
            scope.data_identity === 'synthetic' ? '合成测试' : '用户导入'
          }}</view
        ></picker
      >
      <picker
        :range="channels"
        :value="channels.indexOf(scope.channel)"
        :disabled="busy"
        @change="pickChannel"
        ><view class="select">渠道：{{ scope.channel }}</view></picker
      >
      <text class="label">开始时间（含偏移，含开始）</text>
      <input
        v-model="scope.start_at"
        :disabled="busy"
        placeholder="2026-09-12T00:00:00+08:00"
      />
      <text class="label">结束时间（含偏移，不含结束）</text>
      <input
        v-model="scope.end_at"
        :disabled="busy"
        placeholder="2026-10-12T00:00:00+08:00"
      />
      <text class="label">核对显示时区（IANA）</text>
      <input
        v-model="scope.timezone"
        :disabled="busy"
        placeholder="Asia/Shanghai"
      />
      <text class="hint"
        >包含开始、不含结束，最多 366 天；窗口与关联查询各最多 1000 行订单及
        1000 行销售/退款账单。</text
      >
      <text class="label">销售金额口径</text>
      <picker
        :range="[
          '尚未核实金额组成，仅查看待核依据',
          '已核实两侧均为退款前折后商品款',
        ]"
        :value="scope.sale_basis === 'unknown' ? 0 : 1"
        :disabled="busy"
        @change="pickBasis"
        ><view class="select">{{
          scope.sale_basis === 'unknown'
            ? '尚未核实金额组成'
            : '折后商品款（退款前）'
        }}</view></picker
      >
      <text class="hint"
        >选择可比口径表示已核实本范围两侧金额均不含运费、税费和其他调整；来源格式混杂时请保留未知。</text
      >
      <text v-if="scope.sale_basis !== 'unknown'" class="label"
        >两侧金额组成依据（原文件与列名）</text
      >
      <textarea
        v-if="scope.sale_basis !== 'unknown'"
        v-model="scope.basis_note"
        :maxlength="500"
        :disabled="busy"
        placeholder="填写原文件及列名、金额组成说明；不包含客户个人信息"
      />
      <button
        class="primary"
        :disabled="busy || !canRead"
        :loading="busy"
        @tap="reconcile"
      >
        读取销售与退款待核清单
      </button>
      <text
        v-if="scope.sale_basis !== 'unknown' && !scope.basis_note.trim()"
        class="hint"
        >选择可比口径后必须填写金额组成依据才能读取。</text
      >
    </view>
    <view v-if="result" class="card">
      <text class="section-title"
        >核对结果 · 来源版本 {{ result.source_revision }}</text
      >
      <text class="hint"
        >计算于 {{ supportTime(result.calculated_at, result.scope.timezone) }} ·
        范围 {{ supportTime(result.scope.start_at, result.scope.timezone) }} 至
        {{
          supportTime(result.scope.end_at, result.scope.timezone)
        }}（结束不含，{{ result.scope.timezone }}）</text
      >
      <text class="hint"
        >覆盖状态 {{ result.coverage }} · 销售口径
        {{ result.scope.sale_basis }} ·
        {{ result.scope.basis_note || '未填写金额组成依据' }}</text
      >
      <text v-if="comparisonSummary" class="hint"
        >比对状态：{{ comparisonSummary }}</text
      >
      <text class="hint"
        >窗口内订单行 {{ windowsOrders }} · 窗口外关联订单行
        {{ linkedOrders }} · 账单行 {{ result.statements.length }}</text
      >
      <view class="row">
        <button
          :disabled="busy || comparisonFilter === 'all'"
          @tap="pickFilter('all')"
        >
          全部（{{ result.comparisons.length }}）
        </button>
        <button
          :disabled="busy || comparisonFilter === 'sale'"
          @tap="pickFilter('sale')"
        >
          销售
        </button>
        <button
          :disabled="busy || comparisonFilter === 'refund'"
          @tap="pickFilter('refund')"
        >
          退款
        </button>
      </view>
      <text v-if="!visibleComparisons.length" class="muted"
        >当前筛选下没有可比订单或账单销售/退款行；请调整范围或导入订单与账单。</text
      >
      <view
        v-for="(item, index) in visibleComparisons"
        :key="`${item.order_id}-${item.entry_type}-${index}`"
        class="record"
      >
        <text
          >订单 {{ item.order_id }} ·
          {{ item.entry_type === 'refund' ? '退款' : '销售' }} ·
          {{ comparisonLabel(item) }}</text
        >
        <text class="hint"
          >账单行 {{ item.statement_ids.join('、') || '无' }} · 订单行
          {{ item.order_line_ids.join('、') || '无' }} · 币种
          {{ item.currency || '未知' }} · 可比订单金额
          {{ trimmedAmount(item.order_amount) }} · 差额
          {{ trimmedAmount(item.difference) }}</text
        >
        <text v-for="reason in item.reasons" :key="reason" class="hint">{{
          reason
        }}</text>
      </view>
      <text class="section-title">核对口径</text>
      <text v-for="check in result.checks" :key="check" class="hint">{{
        check
      }}</text>
    </view>
    <view v-if="result" class="card">
      <text class="section-title">订单行（{{ result.orders.length }}）</text>
      <text v-if="!result.orders.length" class="muted"
        >当前窗口没有订单行；请调整范围或先导入订单。</text
      >
      <view
        v-for="(line, index) in visibleOrders"
        :key="line.id"
        class="record"
      >
        <text
          >{{ orderPage * statementLinesPerPage + index + 1 }}. 订单
          {{ line.order_id }} / 行 {{ line.line_id }} · {{ line.sku }} ·
          {{ line.status }} · {{ line.fulfillment_status }}</text
        >
        <text class="hint"
          >{{ line.currency }} 单价 {{ trimmedAmount(line.unit_price) }} ×
          {{ line.quantity }} · 折扣 {{ trimmedAmount(line.discount) }} · 退款
          {{ trimmedAmount(line.refund) }} · 下单
          {{ supportTime(line.ordered_at, result.scope.timezone) }} ·
          {{ line.in_window ? '窗口内' : '窗口外关联' }}</text
        >
        <SourceList :sources="[line.source]" :shop-id="account.shopId" />
      </view>
      <view class="row">
        <button :disabled="busy || orderPage === 0" @tap="fewerOrders">
          上一页
        </button>
        <text
          >{{ orderPage + 1 }} /
          {{
            Math.max(1, Math.ceil(result.orders.length / statementLinesPerPage))
          }}</text
        >
        <button
          :disabled="
            busy ||
            (orderPage + 1) * statementLinesPerPage >= result.orders.length
          "
          @tap="moreOrders"
        >
          下一页
        </button>
      </view>
    </view>
    <view v-if="result" class="card">
      <text class="section-title"
        >销售/退款账单行（{{ result.statements.length }}）</text
      >
      <text v-if="!result.statements.length" class="muted"
        >当前范围没有销售或退款账单行。</text
      >
      <view
        v-for="(line, index) in visibleStatements"
        :key="line.id"
        class="record"
      >
        <text>{{
          statementLineLabel(
            line,
            statementPage * statementLinesPerPage + index,
          )
        }}</text>
        <text class="hint"
          >{{ line.currency }} {{ trimmedAmount(line.amount) }} · 发生
          {{ supportTime(line.occurred_at, result.scope.timezone) }} ·
          {{ line.in_window ? '窗口内' : '窗口外关联' }}</text
        >
        <SourceList :sources="[line.source]" :shop-id="account.shopId" />
      </view>
      <view class="row">
        <button :disabled="busy || statementPage === 0" @tap="fewerStatements">
          上一页
        </button>
        <text
          >{{ statementPage + 1 }} /
          {{
            Math.max(
              1,
              Math.ceil(result.statements.length / statementLinesPerPage),
            )
          }}</text
        >
        <button
          :disabled="
            busy ||
            (statementPage + 1) * statementLinesPerPage >=
              result.statements.length
          "
          @tap="moreStatements"
        >
          下一页
        </button>
      </view>
    </view>
    <view class="card">
      <text class="hint"
        >本页为只读核对，不保存人工结论；需要存档结论请到账单页面操作。</text
      >
      <button :disabled="busy" @tap="openPage('/statements')">
        打开账单与人工核对存档
      </button>
    </view>
  </view>
</template>
