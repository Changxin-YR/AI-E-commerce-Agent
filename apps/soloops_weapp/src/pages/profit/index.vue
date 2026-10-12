// route: /profit
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Taro, { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import { ApiError } from '../../services/client'
import { requestId } from '../../services/task-policy'
import { supportTime } from '../../services/support-types'
import {
  checkedStudyInput,
  copyScenario,
  currencies,
  decimalText,
  feeLabels,
  feeValue,
  hasMoreStudies,
  newScenario,
  newStudyForm,
  nextScenarioName,
  scenariosPerStudy,
  studiesPerPage,
  type FeeInput,
  type ScenarioInput,
  type SavedStudyOutput,
  type SavedStudySummary,
  type StudyResult,
  type StudySaveBody,
} from '../../services/profit-policy'

const form = reactive(newStudyForm())
const result = ref<StudyResult>()
const selected = ref<SavedStudyOutput>()
const history = ref<SavedStudySummary[]>([])
const offset = ref(0),
  more = ref(false)
const busy = ref(false),
  error = ref(''),
  notice = ref(''),
  unknown = ref(false),
  confirmClear = ref(false)
const requestKey = ref(requestId())
const pendingSave = ref<StudySaveBody | null>(null)
const modeRange = ['固定金额', '售价百分比']
const identities = ['手工假设', '合成测试数据']
let alive = true,
  epoch = 0,
  formEpoch = 0,
  linked: Record<string, string> = {}
const request = scopedRequest(api, () => (alive ? epoch : null))
const shop = computed(() =>
  account.shops.find((item) => item.id === account.shopId),
)
const timezone = computed(() => shop.value?.timezone || 'Asia/Shanghai')
const base = () => `/shops/${account.shopId}/profit`
const money = (value: string | null | undefined) =>
  value == null || value === '' ? '未知 / 未计入' : decimalText(value)

function reset() {
  result.value = undefined
  selected.value = undefined
  history.value = []
  offset.value = 0
  more.value = false
  confirmClear.value = false
  error.value = notice.value = ''
}
useLoad((value) => {
  linked = value as Record<string, string>
})
useUnload(() => {
  alive = false
  epoch++
})
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    epoch++
    reset()
    Object.assign(form, newStudyForm(shop.value?.currency || 'USD'))
    requestKey.value = requestId()
  },
  { flush: 'sync' },
)
watch(
  form,
  () => {
    formEpoch++
    result.value = undefined
    selected.value = undefined
    confirmClear.value = false
    notice.value = ''
    requestKey.value = requestId()
  },
  { deep: true, flush: 'sync' },
)
async function perform(work: () => Promise<void>) {
  if (busy.value || !alive) return
  busy.value = true
  error.value = notice.value = ''
  try {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    await work()
  } catch (cause) {
    if (alive)
      error.value =
        cause instanceof Error ? cause.message : '利润测算操作失败。'
  } finally {
    busy.value = false
  }
}
// Only an unknown outcome keeps its recovery entry; deterministic 4xx is a rejection.
function uncertain(cause: unknown): boolean {
  if (!(cause instanceof ApiError)) return true
  return cause.status === 0 || cause.status >= 500 || cause.status === 409
}
async function list(morePages = false) {
  const start = morePages ? offset.value + history.value.length : 0
  const page = await request<SavedStudySummary[]>(
    `${base()}/saved?offset=${start}`,
  )
  offset.value = start
  history.value = morePages ? [...history.value, ...page] : page
  more.value = hasMoreStudies(page)
}
async function readStudy(id: number) {
  const value = await request<SavedStudyOutput>(`${base()}/saved/${id}`)
  Object.assign(form, value.result.input)
  result.value = value.result
  selected.value = value
  confirmClear.value = false
}
async function calculate() {
  await perform(async () => {
    const input = checkedStudyInput(form)
    const token = formEpoch
    result.value = undefined
    selected.value = undefined
    confirmClear.value = false
    const value = await request<StudyResult>(
      `${base()}/calculate`,
      'POST',
      input,
    )
    // An edit during the request invalidates the answer before it is shown.
    if (token !== formEpoch) return
    result.value = value
  })
}
async function save() {
  await perform(async () => {
    if (!result.value || selected.value || unknown.value) return
    const body = pendingSave.value ?? {
      ...checkedStudyInput(form),
      request_key: requestKey.value,
    }
    pendingSave.value = body
    unknown.value = true
    try {
      const record = await request<SavedStudyOutput>(
        `${base()}/saved`,
        'POST',
        body,
      )
      pendingSave.value = null
      unknown.value = false
      await readStudy(record.id)
      await list()
      notice.value = `方案 #${record.id} 已保存并按 ID 独立回读。`
    } catch (cause) {
      if (!uncertain(cause)) {
        pendingSave.value = null
        unknown.value = false
      }
      throw cause
    }
  })
}
async function recoverSave() {
  await perform(async () => {
    const body = pendingSave.value
    if (!body) return
    const record = await request<SavedStudyOutput>(
      `${base()}/saved`,
      'POST',
      body,
    )
    pendingSave.value = null
    unknown.value = false
    await readStudy(record.id)
    await list()
    notice.value = `原保存请求已回查，方案 #${record.id} 已按 ID 独立回读。`
  })
}
async function abandonSave() {
  await perform(async () => {
    pendingSave.value = null
    unknown.value = false
    await list()
    notice.value = '已放弃未确认的保存请求并刷新历史；需要存档请重新计算。'
  })
}
async function openStudy(id: number) {
  await perform(async () => {
    confirmClear.value = false
    await readStudy(id)
  })
}
async function clearStudy() {
  await perform(async () => {
    const item = selected.value
    if (!item || !account.session || !confirmClear.value) return
    const answer = await Taro.showModal({
      title: '清除已保存方案',
      content: `方案 #${item.id} 的名称、假设、金额与依据将一并清除且无法恢复。确认继续？`,
    })
    if (!answer.confirm || !alive || selected.value?.id !== item.id) return
    const current = await request<SavedStudyOutput>(
      `${base()}/saved/${item.id}`,
    )
    if (current.created_at !== item.created_at || current.title !== item.title)
      throw new Error('方案内容已变化，请刷新历史后重新核对。')
    await request<void>(`${base()}/saved/${item.id}`, 'DELETE')
    let cleared = false
    try {
      await request<SavedStudyOutput>(`${base()}/saved/${item.id}`)
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 404) cleared = true
      else throw cause
    }
    if (!cleared) throw new Error('清除后仍能读取该方案，请刷新核实。')
    pendingSave.value = null
    unknown.value = false
    Object.assign(form, newStudyForm(form.currency))
    await list()
    notice.value = `方案 #${item.id} 的名称、假设、金额与依据已清除；列表已回读。`
  })
}
function addScenario(copyLast = false) {
  if (busy.value || form.scenarios.length >= scenariosPerStudy) return
  const name = nextScenarioName(form.scenarios)
  const last = form.scenarios[form.scenarios.length - 1]
  form.scenarios.push(
    copyLast && last ? copyScenario(last, name) : newScenario(name),
  )
}
function removeScenario(index: number) {
  if (busy.value || form.scenarios.length <= 1) return
  form.scenarios.splice(index, 1)
}
function pickCurrency(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  form.currency = currencies[index] || form.currency
}
function pickIdentity(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  form.data_identity = index ? 'synthetic' : 'manual_assumption'
}
function pickMode(fee: FeeInput, event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  fee.mode = index ? 'percent' : 'fixed'
}
function setFeeValue(fee: FeeInput, event: unknown) {
  fee.value = String(
    (event as { detail: { value: string } }).detail.value ?? '',
  ).trim()
}
function scenarioTitle(item: ScenarioInput, index: number) {
  return item.name || `方案 ${index + 1}`
}
useDidShow(() => {
  void perform(async () => {
    if (linked.shop && Number(linked.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不同，请在首页切换后重试。')
    await list()
    if (linked.study) {
      if (!/^[1-9]\d*$/.test(linked.study)) throw new Error('方案编号无效。')
      await readStudy(Number(linked.study))
    }
    linked = {}
  })
})
</script>
<template>
  <view class="screen">
    <view class="hero"
      ><text class="eyebrow">SOLOOPS · PROFIT</text
      ><text class="title">新品利润，先把假设算清。</text
      ><text class="muted"
        >独立输入成本与费用假设，比较售价方案；不读取订单，也不执行换汇。</text
      ></view
    >
    <text v-if="error" class="error">{{ error }}</text
    ><text v-if="notice" class="hint">{{ notice }}</text
    ><text v-if="unknown" class="error"
      >上次保存结果待核对，请先回查或放弃，再继续编辑。</text
    >
    <view class="card"
      ><view class="row"
        ><text class="section-title">{{ shop?.name || '未选择店铺' }}</text
        ><text class="badge">{{ shop?.currency }} · {{ timezone }}</text></view
      ><text class="hint"
        >同一试算只用一个结算币种；空白费用项会明确标为未计入，物流、平台、广告与税费的缺失不会按零处理。</text
      ></view
    >
    <view v-if="pendingSave" class="card"
      ><text class="section-title">待核对的保存请求</text
      ><text class="hint"
        >保存结果未知。可沿用原 request_key
        回查；服务端按请求标识幂等，重复提交不会新建方案。</text
      ><text class="hint"
        >名称：{{ pendingSave.title }} · 币种 {{ pendingSave.currency }} · 方案
        {{ pendingSave.scenarios.length }} 个</text
      ><button class="primary" :disabled="busy" @tap="recoverSave">
        回查原保存请求</button
      ><button :disabled="busy" @tap="abandonSave">放弃并刷新历史</button></view
    >
    <view class="card"
      ><text class="section-title">试算输入</text
      ><text class="label">试算名称</text
      ><input
        v-model="form.title"
        :maxlength="120"
        :disabled="busy"
        placeholder="新品 / SKU 与试算主题"
      /><text class="label">结算币种</text
      ><picker
        :range="currencies"
        :value="Math.max(0, currencies.indexOf(form.currency))"
        :disabled="busy"
        @change="pickCurrency($event)"
        ><view class="select">{{ form.currency }}</view></picker
      ><text class="hint"
        >更改币种仅更换标注，请自行重新核对全部金额；不执行换汇。</text
      ><text class="label">假设来源</text
      ><picker
        :range="identities"
        :value="form.data_identity === 'synthetic' ? 1 : 0"
        :disabled="busy"
        @change="pickIdentity($event)"
        ><view class="select">{{
          form.data_identity === 'synthetic' ? '合成测试数据' : '手工假设'
        }}</view></picker
      >
    </view>
    <view v-for="(scenario, index) in form.scenarios" :key="index" class="card"
      ><view class="row"
        ><text class="section-title">{{ scenarioTitle(scenario, index) }}</text
        ><text class="badge">方案 {{ index + 1 }}</text></view
      ><text class="label">方案名称</text
      ><input v-model="scenario.name" :maxlength="80" :disabled="busy" /><text
        class="label"
        >售价（{{ form.currency }}，最多四位小数）</text
      ><input
        v-model="scenario.price"
        :maxlength="20"
        :disabled="busy"
        placeholder="0.0000"
      /><text class="label">采购成本（{{ form.currency }}）</text
      ><input
        v-model="scenario.purchase_cost"
        :maxlength="20"
        :disabled="busy"
        placeholder="0.0000"
      /><text class="label">价格与采购成本依据</text
      ><textarea
        v-model="scenario.basis"
        :maxlength="500"
        :disabled="busy"
        placeholder="成本来源、报价时间、供应商与前提"
      />
      <text class="label">九类费用（留空表示未计入，必须填写依据才计入）</text>
      <view v-for="fee in scenario.fees" :key="fee.kind" class="fee">
        <text class="label">{{ feeLabels[fee.kind] }}</text>
        <picker
          :range="modeRange"
          :value="fee.mode === 'percent' ? 1 : 0"
          :disabled="busy"
          @change="pickMode(fee, $event)"
          ><view class="select"
            >计费方式：{{
              fee.mode === 'percent' ? '售价百分比' : '固定金额'
            }}</view
          ></picker
        >
        <input
          :value="fee.value || ''"
          :maxlength="20"
          :disabled="busy"
          placeholder="金额或费率，留空为未计入"
          @input="setFeeValue(fee, $event)"
        />
        <input
          v-model="fee.basis"
          :maxlength="300"
          :disabled="busy"
          placeholder="假设依据（已填金额必填）"
        />
      </view>
      <button
        v-if="form.scenarios.length > 1"
        class="danger"
        :disabled="busy"
        @tap="removeScenario(index)"
      >
        移除此方案
      </button></view
    >
    <view class="card"
      ><button
        :disabled="busy || form.scenarios.length >= scenariosPerStudy"
        @tap="addScenario(false)"
      >
        新增空白方案</button
      ><button
        :disabled="busy || form.scenarios.length >= scenariosPerStudy"
        @tap="addScenario(true)"
      >
        复制末个方案</button
      ><text class="hint"
        >最多 {{ scenariosPerStudy }} 个方案，方案名称不可重复。</text
      ><button class="primary" :disabled="busy" @tap="calculate">
        计算并比较
      </button></view
    >
    <view v-if="result" class="card"
      ><text class="section-title">计算结果 · {{ result.rule_version }}</text
      ><text class="hint"
        >计算于
        {{
          supportTime(result.calculated_at, timezone)
        }}；未保存前可继续修改输入。</text
      ><text class="hint">{{ result.scope_note }}</text
      ><text class="hint">{{ result.formula }}</text>
      <view
        v-for="item in result.scenarios"
        :key="item.assumption.name"
        class="card"
      >
        <text class="section-title">{{ item.assumption.name }}</text>
        <text
          >售价 {{ money(item.assumption.price) }} · 采购成本
          {{ money(item.assumption.purchase_cost) }}</text
        >
        <text
          >采购毛利 {{ money(item.purchase_gross) }} · 已知费用
          {{ money(item.known_fees) }} · 已知余额
          {{ money(item.known_balance) }}</text
        >
        <text
          >已知毛利率 {{ money(item.margin_percent) }}% · 固定费用
          {{ money(item.fixed_fees) }} · 费率合计
          {{ money(item.rate_percent) }}%</text
        >
        <text v-if="item.break_even_price == null" class="hint"
          >保本售价：{{ item.break_even_reason }}</text
        ><text v-else
          >保本售价 {{ money(item.break_even_price) }} ·
          {{ item.break_even_reason }}</text
        >
        <text v-for="kind in item.missing_fees" :key="kind" class="hint"
          >未计入：{{ kind }}</text
        >
        <text v-for="fee in item.fees" :key="fee.assumption.kind"
          >{{ feeLabels[fee.assumption.kind] }}：{{
            feeValue(fee.assumption)
          }}
          → {{ money(fee.amount) }}</text
        >
        <text class="label">价格敏感度</text>
        <text v-for="point in item.sensitivity" :key="point.label"
          >{{ point.label }} · 售价 {{ money(point.price) }} · 成本
          {{ money(point.purchase_cost) }} · 余额
          {{ money(point.known_balance) }} · 毛利率
          {{ money(point.margin_percent) }}%</text
        >
      </view>
      <template v-if="selected"
        ><text class="hint"
          >已存档方案 #{{ selected.id }} · 规则版本
          {{
            selected.result.rule_version
          }}。修改输入后可重新计算并另存新记录。</text
        ><checkbox-group
          @change="confirmClear = Boolean(($event.detail.value || []).length)"
          ><label class="label"
            ><checkbox
              value="clear"
              :checked="confirmClear"
              :disabled="busy"
            />确认清除所选方案及其输入依据</label
          ></checkbox-group
        ><button
          class="danger"
          :disabled="busy || !confirmClear"
          @tap="clearStudy"
        >
          清除所选方案
        </button></template
      >
      <template v-else
        ><button
          class="primary"
          :disabled="busy || unknown || !!pendingSave"
          @tap="save"
        >
          保存本次方案</button
        ><text class="hint"
          >保存会记录输入、依据与规则版本，并按 ID
          独立回读。清除后正文与依据不可恢复。</text
        ></template
      >
    </view>
    <view class="card"
      ><view class="row"
        ><text class="section-title">已保存方案</text
        ><text class="badge">每页 {{ studiesPerPage }} 条</text></view
      ><button :disabled="busy" @tap="list()">刷新历史</button
      ><text v-if="!history.length" class="muted"
        >本店铺还没有已保存的试算方案。</text
      ><button
        v-for="item in history"
        :key="item.id"
        :disabled="busy"
        @tap="openStudy(item.id)"
      >
        #{{ item.id }} · {{ item.title }} · {{ item.currency }} ·
        {{ item.data_identity === 'synthetic' ? '合成测试数据' : '手工假设' }}
        · {{ supportTime(item.created_at, timezone) }}</button
      ><button v-if="more" :disabled="busy" @tap="list(true)">
        继续读取更早方案
      </button></view
    >
  </view>
</template>
<style>
.fee {
  border-top: 1rpx solid #dce7e0;
  margin-top: 20rpx;
  padding-top: 8rpx;
}
</style>
