<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Taro, { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import {
  checkedAnalysisScope,
  linkedAnalysisScope,
} from '../../services/analytics-policy'
import { openLink } from '../../services/navigation'
import { supportTime } from '../../services/support-types'
import type {
  AnalysisScope,
  AnalysisResult,
  SavedAnalysis,
} from '../../services/analytics-types'
import SourceList from '../../components/SourceList.vue'
import OrderCostEditor from '../../components/OrderCostEditor.vue'

const scope = reactive<AnalysisScope>({
  cost_mode: 'current_estimate',
  start_at: new Date(Date.now() - 30 * 86400000).toISOString(),
  end_at: new Date().toISOString(),
  timezone: 'Asia/Shanghai',
  currency: 'USD',
  data_identity: 'user_import',
  channel: null,
  intent: 'summary',
  min_quantity: 1,
  max_margin_percent: '20',
})
const result = ref<AnalysisResult>(),
  saved = ref<SavedAnalysis>(),
  history = ref<SavedAnalysis[]>([])
const loading = ref(false),
  costBusy = ref(false),
  costEditing = ref(false),
  error = ref(''),
  notice = ref(''),
  outdated = ref(false),
  unknown = ref(false),
  page = ref(0),
  costRow = ref(0)
const busy = computed(() => loading.value || costBusy.value)
const stale = computed(
  () => outdated.value || (!!saved.value && saved.value.status !== 'current'),
)
const questions = [
  '查看销售与已知毛利',
  '销量前五的 SKU',
  '哪些商品销量高但已知毛利低',
]
const intents = ['summary', 'sales', 'low_margin'] as const
const channels = ['', 'generic', 'shopify', 'amazon', 'other']
const money = (value: string | null | undefined) => value ?? '未知 / 缺数据'
let alive = true,
  epoch = 0,
  linked: Record<string, string> = {}
const request = scopedRequest(api, () => (alive ? epoch : null))
const base = () => `/shops/${account.shopId}/analytics`
useLoad((value) => {
  linked = value as Record<string, string>
})
useUnload(() => {
  alive = false
  epoch++
})
watch(
  scope,
  () => {
    result.value = undefined
    saved.value = undefined
    page.value = 0
    costRow.value = 0
    outdated.value = false
  },
  { flush: 'sync' },
)
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    epoch++
    result.value = undefined
    saved.value = undefined
    history.value = []
    costRow.value = 0
    costEditing.value = false
    costBusy.value = false
    unknown.value = false
    error.value = notice.value = ''
    linked = {}
  },
  { flush: 'sync' },
)
watch(
  () => costEditing.value || busy.value || unknown.value,
  (protect) => {
    if (!alive) return
    if (protect)
      Taro.enableAlertBeforeUnload({
        message: '有未保存成本或待核对操作，请确认后离开。',
      })
    else Taro.disableAlertBeforeUnload()
  },
)
async function perform(work: () => Promise<void>) {
  if (busy.value || !alive) return
  const token = epoch
  loading.value = true
  error.value = notice.value = ''
  try {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    await work()
  } catch (cause) {
    if (alive && token === epoch)
      error.value = cause instanceof Error ? cause.message : '分析操作失败。'
  } finally {
    loading.value = false
  }
}
function requireClean() {
  if (costEditing.value) throw new Error('请先保存或关闭订单成本编辑。')
}
async function read(id: number) {
  const value = await request<SavedAnalysis>(`${base()}/saved/${id}`)
  Object.assign(scope, value.scope)
  saved.value = value
  result.value = value.snapshot || undefined
  outdated.value = value.status !== 'current'
}
async function refresh() {
  await perform(async () => {
    requireClean()
    history.value = await request<SavedAnalysis[]>(`${base()}/saved`)
    if (saved.value) await read(saved.value.id)
    if (result.value)
      outdated.value =
        (await request<number>(`${base()}/revision`)) !==
        result.value.source_revision
    unknown.value = false
  })
}
async function calculate() {
  await perform(async () => {
    requireClean()
    const input = checkedAnalysisScope(scope)
    result.value = undefined
    saved.value = undefined
    costRow.value = 0
    page.value = 0
    result.value = await request<AnalysisResult>(`${base()}/ask`, 'POST', {
      scope: input,
      question: questions[intents.indexOf(input.intent)],
    })
    outdated.value = false
  })
}
async function show(id: number) {
  await perform(async () => {
    requireClean()
    await read(id)
  })
}
async function save() {
  await perform(async () => {
    requireClean()
    if (!result.value || stale.value || unknown.value) return
    unknown.value = true
    const value = await request<SavedAnalysis>(`${base()}/saved`, 'POST', {
      scope: result.value.scope,
      expected_revision: result.value.source_revision,
    })
    await read(value.id)
    history.value = await request<SavedAnalysis[]>(`${base()}/saved`)
    unknown.value = false
    notice.value = '分析报告已保存并独立回读。'
  })
}
async function todo(action: 'create' | 'complete' | 'reopen') {
  await perform(async () => {
    requireClean()
    if (!saved.value || stale.value || unknown.value) return
    const item = saved.value
    if (action !== 'create' && !item.todo) return
    const token = epoch
    const answer = await Taro.showModal({
      title: '确认核对待办',
      content: `分析 #${item.id}：${{ create: '创建核对待办', complete: '标记核对完成', reopen: '重新打开待办' }[action]}。`,
    })
    if (!answer.confirm || !alive || token !== epoch) return
    unknown.value = true
    await request(
      `${base()}/saved/${item.id}/todo${action === 'create' ? '' : '/action'}`,
      'POST',
      action === 'create'
        ? undefined
        : { expected_version: item.todo!.version, action },
    )
    await read(item.id)
    history.value = await request<SavedAnalysis[]>(`${base()}/saved`)
    unknown.value = false
    notice.value = '待办已保存并回读。'
  })
}
function changePage(delta: number) {
  if (busy.value || costEditing.value) return
  page.value += delta
  costRow.value = 0
}
function changedCost() {
  outdated.value = true
  notice.value = '成本依据已变，请重新计算；已保存报告保留原口径。'
}
function pick(
  field: 'intent' | 'channel' | 'cost_mode' | 'data_identity',
  event: unknown,
) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  if (field === 'intent') scope.intent = intents[index] || 'summary'
  else if (field === 'channel') scope.channel = channels[index] || null
  else if (field === 'cost_mode')
    scope.cost_mode = index ? 'seller_history' : 'current_estimate'
  else scope.data_identity = index ? 'synthetic' : 'user_import'
}
async function agent() {
  await perform(async () => {
    requireClean()
    if (!scope.channel || scope.cost_mode === 'seller_history')
      throw new Error('AI问数需要明确渠道和当前成本估算口径。')
    const input = checkedAnalysisScope(scope)
    await openLink('/agent', {
      shop: String(account.shopId),
      mode: 'question',
      identity: input.data_identity,
      channel: input.channel!,
      start_at: input.start_at,
      end_at: input.end_at,
      currency: input.currency,
      timezone: input.timezone,
      min_quantity: String(input.min_quantity),
      max_margin_percent: input.max_margin_percent,
      intent: input.intent,
    })
  })
}
useDidShow(() => {
  void perform(async () => {
    if (costEditing.value) {
      notice.value = '保留成本编辑，请保存或关闭后刷新。'
      return
    }
    if (linked.shop && Number(linked.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不一致。')
    const shop = account.shops.find((s) => s.id === account.shopId)
    if (!result.value) {
      scope.timezone = shop?.timezone || 'Asia/Shanghai'
      scope.currency = shop?.currency || 'USD'
      Object.assign(scope, linkedAnalysisScope(scope, linked))
    }
    history.value = await request<SavedAnalysis[]>(`${base()}/saved`)
    if (linked.analysis) {
      if (!/^[1-9]\d*$/.test(linked.analysis)) throw new Error('分析编号无效。')
      await read(Number(linked.analysis))
    } else if (saved.value) await read(saved.value.id)
    if (result.value)
      outdated.value =
        (await request<number>(`${base()}/revision`)) !==
        result.value.source_revision
    linked = {}
    unknown.value = false
  })
})
</script>
<template>
  <view class="screen">
    <view class="hero"
      ><text class="eyebrow">SOLOOPS · ANALYTICS</text
      ><text class="title">让每笔毛利，有据可查。</text
      ><text class="muted"
        >单店铺、单币种和明确时间窗，核对订单行与采购成本。</text
      ></view
    >
    <text v-if="error" class="error">{{ error }}</text
    ><text v-if="notice" class="hint">{{ notice }}</text
    ><text v-if="unknown" class="error"
      >上次写入结果待核对，请刷新历史再继续。</text
    >
    <view class="card">
      <picker
        :range="['用户导入', '合成测试']"
        :value="scope.data_identity === 'synthetic' ? 1 : 0"
        :disabled="busy || costEditing"
        @change="pick('data_identity', $event)"
        ><view class="field">身份：{{ scope.data_identity }}</view></picker
      >
      <picker
        :range="['所有渠道', 'generic', 'shopify', 'amazon', 'other']"
        :value="channels.indexOf(scope.channel || '')"
        :disabled="busy || costEditing"
        @change="pick('channel', $event)"
        ><view class="field"
          >渠道：{{ scope.channel || '所有渠道' }}</view
        ></picker
      >
      <picker
        :range="['当前成本估算', '卖家历史成本凭据']"
        :value="scope.cost_mode === 'seller_history' ? 1 : 0"
        :disabled="busy || costEditing"
        @change="pick('cost_mode', $event)"
        ><view class="field"
          >成本：{{
            scope.cost_mode === 'seller_history'
              ? '卖家历史成本凭据'
              : '当前成本估算'
          }}</view
        ></picker
      >
      <text class="label">开始时间（含时区）</text
      ><input
        v-model="scope.start_at"
        :maxlength="40"
        :disabled="busy || costEditing"
      />
      <text class="label">结束时间（不含，带时区）</text
      ><input
        v-model="scope.end_at"
        :maxlength="40"
        :disabled="busy || costEditing"
      />
      <text class="label">业务时区</text
      ><input
        v-model="scope.timezone"
        :maxlength="64"
        :disabled="busy || costEditing"
      />
      <text class="label">币种</text
      ><input
        v-model="scope.currency"
        :maxlength="3"
        :disabled="busy || costEditing"
      />
      <picker
        :range="questions"
        :value="intents.indexOf(scope.intent)"
        :disabled="busy || costEditing"
        @change="pick('intent', $event)"
        ><view class="field">{{
          questions[intents.indexOf(scope.intent)]
        }}</view></picker
      >
      <text class="label">最低购买数量</text
      ><input
        v-model.number="scope.min_quantity"
        type="number"
        :disabled="busy || costEditing"
      />
      <text class="label">毛利率上限（%）</text
      ><input
        v-model="scope.max_margin_percent"
        :maxlength="12"
        :disabled="busy || costEditing"
      />
      <button
        class="primary"
        :disabled="busy || costEditing"
        :loading="loading"
        @tap="calculate"
      >
        按当前来源计算 / 重新计算</button
      ><button :disabled="busy || costEditing" @tap="agent">
        打开 AI 经营问数
      </button>
    </view>
    <view v-if="result" class="card">
      <text class="section-title">{{ result.scope.currency }} · 经营分析</text
      ><text
        >来源版本 {{ result.source_revision }} ·
        {{ supportTime(result.calculated_at, result.scope.timezone) }}</text
      >
      <text v-if="stale" class="error"
        >来源或成本已变，当前结果需重新计算。</text
      ><text>{{ result.answer }}</text
      ><text>{{ result.formula }}</text
      ><text>{{ result.cost_basis }}</text>
      <text v-for="warning in result.warnings" :key="warning" class="error">{{
        warning
      }}</text
      ><text v-for="gap in result.fee_gaps" :key="gap" class="hint"
        >费用缺口：{{ gap }}</text
      >
      <text
        >订单行 {{ result.summary.line_count }} · 购买数量
        {{ result.summary.purchased_quantity }}</text
      >
      <text
        >销售 {{ money(result.summary.sales) }} · 已知子集
        {{ result.summary.known_sales_subtotal }}（{{
          result.summary.sales_known_lines
        }}行）</text
      >
      <text
        >采购成本 {{ money(result.summary.cost) }} · 已知子集
        {{ result.summary.known_cost_subtotal }}（{{
          result.summary.cost_known_lines
        }}行）</text
      >
      <text
        >商品毛利 {{ money(result.summary.gross_profit) }} · 已知子集
        {{ result.summary.known_gross_subtotal }}（{{
          result.summary.gross_known_lines
        }}行）</text
      ><text>毛利率 {{ money(result.summary.margin_percent) }}%</text>
      <text class="hint"
        >{{
          result.ranking_available
            ? '当前范围可核对排名'
            : '数据缺失，完整毛利排名不可用'
        }}；商品毛利不等于实际净利润。</text
      >
      <text v-for="sku in result.skus" :key="sku.sku || ''"
        >{{ sku.sku }} · 数量 {{ sku.purchased_quantity }} · 销售
        {{ money(sku.sales) }} · 成本 {{ money(sku.cost) }} · 毛利
        {{ money(sku.gross_profit) }} · 毛利率
        {{ money(sku.margin_percent) }}%</text
      >
      <text v-for="candidate in result.candidates" :key="candidate" class="hint"
        >待核候选：{{ candidate }}</text
      >
      <button
        :disabled="busy || costEditing || stale || unknown || !!saved"
        @tap="save"
      >
        保存当前报告
      </button>
      <view v-if="saved"
        ><text>报告 #{{ saved.id }} · {{ saved.status }}</text
        ><text v-if="saved.todo"
          >待办 #{{ saved.todo.id }} · {{ saved.todo.title }} ·
          {{ saved.todo.status }} / v{{ saved.todo.version }}</text
        >
        <button
          v-if="!saved.todo"
          :disabled="busy || costEditing || stale || unknown"
          @tap="todo('create')"
        >
          创建核对待办
        </button>
        <button
          v-else-if="saved.todo.status === 'open'"
          :disabled="busy || costEditing || stale || unknown"
          @tap="todo('complete')"
        >
          完成核对
        </button>
        <button
          v-else-if="saved.todo.status === 'completed'"
          :disabled="busy || costEditing || stale || unknown"
          @tap="todo('reopen')"
        >
          重开核对
        </button>
      </view>
      <text class="section-title">订单行依据</text
      ><text v-if="!result.lines.length" class="muted"
        >当前范围没有可计算订单行。</text
      >
      <view
        v-for="line in result.lines.slice(page * 20, page * 20 + 20)"
        :key="line.source.row_id"
        class="card"
      >
        <text class="label"
          >{{ line.order_id }} / {{ line.line_id }} · {{ line.sku }}</text
        ><text
          >{{ line.status }} · {{ line.included ? '纳入统计' : '未纳入统计' }} ·
          {{ supportTime(line.ordered_at, scope.timezone) }}</text
        >
        <text
          >数量 {{ line.quantity }} · 单价 {{ line.unit_price }}
          {{ line.currency }} · 折扣 {{ money(line.discount) }} · 退款
          {{ money(line.refund) }}</text
        ><text
          >销售 {{ money(line.sales) }} · 单位成本 {{ money(line.unit_cost) }} ·
          成本 {{ money(line.cost) }} · 毛利
          {{ money(line.gross_profit) }}</text
        >
        <text v-for="gap in line.gaps" :key="gap" class="error">{{ gap }}</text
        ><text v-if="line.historical_cost"
          >历史成本 v{{ line.historical_cost.version }} ·
          {{ line.historical_cost.status }} ·
          {{ line.historical_cost.evidence_ref }}</text
        >
        <SourceList
          :sources="
            line.cost_source ? [line.source, line.cost_source] : [line.source]
          "
          :shop-id="account.shopId"
        />
        <button
          v-if="costRow !== line.source.row_id"
          :disabled="busy || costEditing || stale"
          @tap="costRow = line.source.row_id"
        >
          核对 / 录入此行历史成本
        </button>
        <OrderCostEditor
          v-if="costRow === line.source.row_id"
          :key="`${account.shopId}:${line.source.row_id}`"
          :row="line.source.row_id"
          :timezone="scope.timezone"
          :disabled="loading || stale"
          @working="costBusy = $event"
          @editing="costEditing = $event"
          @changed="changedCost"
        />
      </view>
      <view class="row"
        ><button
          :disabled="busy || costEditing || page === 0"
          @tap="changePage(-1)"
        >
          上一页明细</button
        ><text>{{ page + 1 }}</text
        ><button
          :disabled="
            busy || costEditing || (page + 1) * 20 >= result.lines.length
          "
          @tap="changePage(1)"
        >
          下一页明细
        </button></view
      >
    </view>
    <view class="card"
      ><text class="section-title">历史报告</text
      ><button :disabled="busy || costEditing" @tap="refresh">
        刷新历史并核对来源</button
      ><text v-if="!history.length" class="muted">尚无已保存报告。</text
      ><button
        v-for="item in history"
        :key="item.id"
        :disabled="busy || costEditing"
        @tap="show(item.id)"
      >
        #{{ item.id }} · {{ item.status }} · {{ item.scope.currency }} ·
        {{ supportTime(item.created_at, item.scope.timezone) }}</button
      ><text v-if="saved && !saved.snapshot" class="muted"
        >报告 #{{ saved.id }} 的来源及正文已清除。</text
      ></view
    >
  </view>
</template>
