<template>
  <PageShell
    title="新品利润测算"
    subtitle="比较售价与单件成本。金额使用所选结算币种；固定费用填单件分摊额，费率按售价计算。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load"
  >
    <FactLine label="所属店铺" :value="shopName" />
    <FactLine label="业务时区" :value="zone" />
    <text class="hint">
      空白费用表示未知；填写 0 表示明确为零，也须填写依据。未知费用不计入余额，也不当作 0。
    </text>

    <text class="section-title">编辑试算输入</text>
    <view class="field">
      <text class="field__label">试算名称</text>
      <input class="field__input" :value="title" :disabled="busy" @input="title = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">结算币种（更改币种后请重新核对金额）</text>
      <picker mode="selector" :range="currencyOptions" :value="currencyIndex" @change="currency = currencyOptions[Number(pickerValue($event))] ?? currency">
        <view class="field__picker">{{ currency }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">假设来源</text>
      <picker mode="selector" :range="identityOptions" range-key="label" :value="identityIndex" @change="identity = identityOptions[Number(pickerValue($event))]?.key ?? 'manual_assumption'">
        <view class="field__picker">{{ labelOf(identities, identity) }}</view>
      </picker>
    </view>

    <view v-for="(scenario, index) in scenarios" :key="index" class="card">
      <text class="card__title">方案 {{ index + 1 }}</text>
      <view class="field">
        <text class="field__label">方案名称</text>
        <input class="field__input" :value="scenario.name" :disabled="busy" @input="setScenario(index, { name: inputValue($event) })" />
      </view>
      <view class="field">
        <text class="field__label">售价（{{ currency }} / 件）</text>
        <input class="field__input" :value="scenario.price" :disabled="busy" @input="setScenario(index, { price: inputValue($event) })" />
      </view>
      <view class="field">
        <text class="field__label">采购成本（{{ currency }} / 件）</text>
        <input class="field__input" :value="scenario.purchaseCost" :disabled="busy" @input="setScenario(index, { purchaseCost: inputValue($event) })" />
      </view>
      <view class="row">
        <ActionButton :label="fxIndex === index ? '收起换算面板' : '用手工汇率换算采购成本'" :disabled="busy" @tap="openFx(index)" />
      </view>

      <template v-if="fxIndex === index">
        <text class="card__title">采购成本换算</text>
        <view class="field">
          <text class="field__label">原币种</text>
          <picker mode="selector" :range="currencyOptions" :value="fxCurrencyIndex" @change="setFxCurrency($event)">
            <view class="field__picker">{{ fxFrom }}</view>
          </picker>
        </view>
        <view class="field">
          <text class="field__label">原币金额</text>
          <input class="field__input" :value="fxAmount" :disabled="busy" @input="setFxAmount($event)" />
        </view>
        <view class="field">
          <text class="field__label">1 {{ fxFrom }} 对应 {{ currency }}</text>
          <input class="field__input" :value="fxRate" :disabled="busy" @input="setFxRate($event)" />
        </view>
        <view class="field">
          <text class="field__label">汇率来源、日期与报价依据</text>
          <input class="field__input" :value="fxBasis" :disabled="busy" @input="setFxBasis($event)" />
        </view>
        <text class="hint">按手工汇率换算，四舍五入到 4 位小数；确认后会替换采购成本并追加依据。</text>
        <FactLine label="换算金额" :value="fxPreview === null ? '尚未预览' : `${fxPreview} ${currency}`" />
        <text v-if="fxError" class="warn">{{ fxError }}</text>
        <view class="row">
          <ActionButton label="预览换算" :disabled="busy" @tap="previewFx(index)" />
          <ActionButton label="确认采用" variant="primary" :disabled="busy || fxPreview === null" @tap="applyFx(index)" />
          <ActionButton label="取消" :disabled="busy" @tap="closeFx" />
        </view>
      </template>

      <view class="field">
        <text class="field__label">售价、采购成本与换算依据</text>
        <input class="field__input" :value="scenario.basis" :disabled="busy" @input="setScenario(index, { basis: inputValue($event) })" />
      </view>

      <text class="card__title">费用假设</text>
      <view v-for="fee in feeKinds" :key="fee.key" class="field">
        <text class="field__label">{{ fee.label }}</text>
        <picker
          mode="selector"
          :range="feeModes"
          range-key="label"
          :value="feeModeIndex(index, fee.key)"
          @change="setFeeMode(index, fee.key, $event)"
        >
          <view class="field__picker">{{ feeModeLabel(index, fee.key) }}</view>
        </picker>
        <input
          class="field__input"
          :value="feeValue(index, fee.key)"
          :disabled="busy"
          :placeholder="feeMode(index, fee.key) === 'percent' ? '未知 · 未计入（填写百分比）' : '未知 · 未计入'"
          @input="setFee(index, fee.key, { value: inputValue($event) })"
        />
        <input
          class="field__input"
          :value="feeBasis(index, fee.key)"
          :disabled="busy"
          placeholder="费用依据（已填费用必填）"
          @input="setFee(index, fee.key, { basis: inputValue($event) })"
        />
      </view>

      <view class="row">
        <ActionButton v-if="scenarios.length > 1" label="移除此方案" :disabled="busy" @tap="removeScenario(index)" />
      </view>
    </view>

    <view class="row">
      <ActionButton label="新增方案" :disabled="busy || scenarios.length >= 5" @tap="addScenario" />
      <ActionButton label="复制末个方案" :disabled="busy || scenarios.length >= 5" @tap="copyLast" />
      <ActionButton label="计算并比较" variant="primary" :disabled="busy" @tap="calculate" />
    </view>
    <FactLine label="已存档记录" :value="savedId === null ? '尚未存档' : savedId" />
    <view class="row">
      <ActionButton label="保存本次方案 / 核对同次保存" :disabled="busy" @tap="saveStudy" />
      <ActionButton label="清除本次存档" :disabled="busy || savedId === null" @tap="clearCurrent" />
    </view>

    <template v-if="result !== null">
      <text class="section-title">{{ currentTitle }} · 假设估算</text>
      <FactLine label="币种" :value="result.input.currency" />
      <FactLine label="来源身份" :value="labelOf(identities, result.input.data_identity)" />
      <FactLine label="计算时间" :value="result.calculated_at" :zone="zone" />
      <text class="section-title">计算公式与规则版本</text>
      <FactLine label="公式" :value="result.formula" />
      <FactLine label="规则版本" :value="result.rule_version" />
      <FactLine label="口径说明" :value="result.scope_note" />

      <view v-for="(item, index) in result.scenarios" :key="index" class="card">
        <text class="card__title">{{ item.assumption.name }}</text>
        <FactLine label="采购毛利" :value="moneyText(item.purchase_gross, result.input.currency)" />
        <FactLine label="已填费用" :value="moneyText(item.known_fees, result.input.currency)" />
        <FactLine label="已知费用后余额" :value="moneyText(item.known_balance, result.input.currency)" />
        <FactLine label="余额率" :value="item.margin_percent === null ? '未知' : `${item.margin_percent}%`" />
        <FactLine label="假设保本价" :value="moneyText(item.break_even_price, result.input.currency)" />
        <text class="hint">保本价说明：{{ factText(item.break_even_reason) }}</text>
        <text v-if="(item.missing_fees ?? []).length > 0" class="warn">
          未计入：{{ (item.missing_fees ?? []).join('、') }}。缺失费用使余额与保本价仅为已知项结果。
        </text>
        <text v-else class="hint">九类费用均已填写，余额为已知项完整结果。</text>
        <FactLine label="固定费用合计" :value="moneyText(item.fixed_fees, result.input.currency)" />
        <FactLine label="售价费率合计" :value="`${item.rate_percent}%`" />

        <text class="section-title">原始输入与费用依据</text>
        <FactLine label="售价" :value="moneyText(item.assumption.price, result.input.currency)" />
        <FactLine label="采购成本" :value="moneyText(item.assumption.purchase_cost, result.input.currency)" />
        <FactLine label="依据" :value="item.assumption.basis" />
        <view v-for="fee in item.fees ?? []" :key="fee.assumption.kind">
          <FactLine
            :label="labelOf(profitFees, fee.assumption.kind)"
            :value="fee.amount === null || fee.amount === undefined ? '未知 · 未计入' : moneyText(fee.amount, result.input.currency)"
          />
          <text class="hint">
            假设值 {{ fee.assumption.value === null || fee.assumption.value === undefined ? '未知' : fee.assumption.value }}{{ fee.assumption.mode === 'percent' ? '%' : ' / 件' }} · {{ factText(fee.assumption.basis) }}
          </text>
        </view>

        <text class="section-title">售价与成本敏感性</text>
        <view v-for="point in item.sensitivity ?? []" :key="point.label">
          <FactLine :label="point.label" :value="`余额 ${moneyText(point.known_balance, result.input.currency)}`" />
          <text class="hint">
            售价 {{ point.price }} · 成本 {{ point.purchase_cost }} · 余额率 {{ point.margin_percent === null || point.margin_percent === undefined ? '无法确定' : `${point.margin_percent}%` }}
          </text>
        </view>
        <text v-if="(item.sensitivity ?? []).length === 0" class="hint">服务端未返回敏感性点，无法给出区间结论。</text>
      </view>
    </template>

    <text class="section-title">试算历史</text>
    <view class="row">
      <ActionButton label="刷新历史" :disabled="busy" @tap="load" />
    </view>
    <view v-if="history.length === 0 && !busy" class="card">
      <text class="hint">暂无试算记录。计算完成后可保存。</text>
    </view>
    <view v-for="item in history" :key="item.id" class="card">
      <text class="card__title">试算 #{{ item.id }} · {{ item.title }}</text>
      <text class="hint">
        {{ item.currency }} · {{ labelOf(identities, item.data_identity) }} · {{ businessTimeText(item.created_at, zone) }}
      </text>
      <view class="row">
        <ActionButton label="回读试算" :disabled="busy" @tap="inspect(item.id)" />
        <ActionButton label="删除存档" :disabled="busy" @tap="clearStudy(item.id)" />
      </view>
    </view>
    <view class="row">
      <ActionButton label="上一页" :disabled="busy || offset === 0" @tap="pageHistory(-1)" />
      <text class="chip">第 {{ offset / 50 + 1 }} 页</text>
      <ActionButton label="下一页" :disabled="busy || history.length < 50" @tap="pageHistory(1)" />
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 新品利润测算：1–5 个方案、9 类固定/比例费用、手工汇率预览确认、
 * 盈亏与保本/敏感性、存档与历史。
 * 接口（均来自 contracts/ui-contract.json 的 r2.profit）：
 *   POST   /api/shops/{shop_id}/profit/calculate
 *   POST   /api/shops/{shop_id}/profit/saved
 *   GET    /api/shops/{shop_id}/profit/saved
 *   GET    /api/shops/{shop_id}/profit/saved/{study_id}
 *   DELETE /api/shops/{shop_id}/profit/saved/{study_id}
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import ActionButton from '../../ui/ActionButton.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import { ApiError, apiGet, apiPost, apiRequest, asObject, asRows, newRequestId } from '../../core/api'
import { businessTimeText, factText, isDecimalInput, moneyText } from '../../core/format'
import { labelOf } from '../../core/labels'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

/** 后端 FeeKind 的九类费用（标签与 backend/app/schemas/profit.py 的 FEE_LABELS 一致）。 */
const profitFees: Record<string, string> = {
  inbound: '头程物流',
  outbound: '尾程物流',
  platform: '平台费用',
  storage: '仓储',
  packaging: '包装',
  advertising: '广告',
  refund: '退款损失',
  tax: '税费',
  other: '其他及分摊费用',
}

const identities: Record<string, string> = {
  manual_assumption: '手工假设',
  synthetic: '合成测试',
}

const feeModes = [
  { key: 'fixed', label: '每件固定额' },
  { key: 'percent', label: '售价比例 %' },
]

interface FeeInput {
  kind: string
  mode: string
  value?: string | null
  basis: string
}

interface ScenarioInput {
  name: string
  price: string
  purchase_cost: string
  basis: string
  fees: FeeInput[]
}

interface StudyInput {
  title: string
  currency: string
  data_identity: string
  scenarios: ScenarioInput[]
}

interface FeeResult {
  assumption: FeeInput
  amount?: string | null
}

interface SensitivityPoint {
  label: string
  price: string
  purchase_cost: string
  known_balance: string
  margin_percent?: string | null
}

interface ScenarioResult {
  assumption: ScenarioInput
  purchase_gross: string
  known_fees: string
  known_balance: string
  margin_percent?: string | null
  fixed_fees: string
  rate_percent: string
  missing_fees: string[]
  fees: FeeResult[]
  break_even_price?: string | null
  break_even_reason: string
  sensitivity: SensitivityPoint[]
}

interface StudyResult {
  input: StudyInput
  rule_version: string
  calculated_at: string
  formula: string
  scope_note: string
  scenarios: ScenarioResult[]
}

interface SavedStudySummary {
  id: number
  title: string
  currency: string
  data_identity: string
  created_at: string
}

interface SavedStudyOutput extends SavedStudySummary {
  result: StudyResult
}

interface FeeDraft {
  mode: string
  value: string
  basis: string
}

interface ScenarioDraft {
  name: string
  price: string
  purchaseCost: string
  basis: string
  fees: Record<string, FeeDraft>
}

const currencies = ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']
const feeKinds = Object.entries(profitFees).map(([key, label]) => ({ key, label }))

const title = ref('新品试算')
const currency = ref('USD')
const identity = ref('manual_assumption')
const scenarios = ref<ScenarioDraft[]>([createScenario('方案 1')])
const result = ref<StudyResult | null>(null)
const currentTitle = ref('')
const savedId = ref<number | null>(null)
/** 同一次保存复用的幂等键；重复提交只返回已有存档。 */
const requestKey = ref<string | null>(null)
const history = ref<SavedStudySummary[]>([])
const offset = ref(0)
const fxIndex = ref<number | null>(null)
const fxFrom = ref('CNY')
const fxAmount = ref('')
const fxRate = ref('')
const fxBasis = ref('')
const fxPreview = ref<string | null>(null)
const fxError = ref('')
const busy = ref(false)
const error = ref('')
const successText = ref('')
const ready = ref(false)

const zone = computed(() => shopTimezone())
const shopName = computed(() => state.shops.find((shop) => shop.id === state.shopId)?.name ?? '未知')
const currencyOptions = computed(() => currencies)
const currencyIndex = computed(() => Math.max(0, currencies.indexOf(currency.value)))
const identityOptions = computed(() => Object.entries(identities).map(([key, label]) => ({ key, label })))
const identityIndex = computed(() => Math.max(0, Object.keys(identities).indexOf(identity.value)))
const fxCurrencyIndex = computed(() => Math.max(0, currencies.indexOf(fxFrom.value)))

/** 新建方案草稿：九类费用全部留空表示未知。 */
function createScenario(name: string): ScenarioDraft {
  const fees: Record<string, FeeDraft> = {}
  for (const kind of Object.keys(profitFees)) fees[kind] = { mode: 'fixed', value: '', basis: '' }
  return { name, price: '', purchaseCost: '', basis: '', fees }
}

function success(text: string): void {
  successText.value = text
  void Taro.showToast({ title: text, icon: 'none' })
}

/** 写操作：断线/超时提示“结果未知，请回读”，不推断成功。 */
async function writeAction(action: () => Promise<void>, done: string, hint: string): Promise<void> {
  let unknown = false
  const message = await perform(async () => {
    try {
      await action()
    } catch (caught) {
      unknown = caught instanceof ApiError && caught.kind === 'network_unknown'
      throw caught
    }
  })
  if (message === '') {
    success(done)
    return
  }
  error.value = unknown ? `${message} 结果未知，请回读${hint}核对后再决定。` : message
}

function setScenario(index: number, patch: Partial<ScenarioDraft>): void {
  const next = [...scenarios.value]
  next[index] = { ...next[index], ...patch }
  scenarios.value = next
}

function feeDraft(index: number, kind: string): FeeDraft {
  return scenarios.value[index]?.fees[kind] ?? { mode: 'fixed', value: '', basis: '' }
}

function feeValue(index: number, kind: string): string {
  return feeDraft(index, kind).value
}

function feeBasis(index: number, kind: string): string {
  return feeDraft(index, kind).basis
}

function feeMode(index: number, kind: string): string {
  return feeDraft(index, kind).mode
}

function feeModeIndex(index: number, kind: string): number {
  const mode = feeMode(index, kind)
  const found = feeModes.findIndex((item) => item.key === mode)
  return found < 0 ? 0 : found
}

function feeModeLabel(index: number, kind: string): string {
  return feeModes[feeModeIndex(index, kind)]?.label ?? feeModes[0].label
}

function setFee(index: number, kind: string, patch: Partial<FeeDraft>): void {
  const scenario = scenarios.value[index]
  if (scenario === undefined) return
  setScenario(index, { fees: { ...scenario.fees, [kind]: { ...feeDraft(index, kind), ...patch } } })
}

function setFeeMode(index: number, kind: string, event: unknown): void {
  const mode = feeModes[Number(pickerValue(event))]?.key ?? 'fixed'
  setFee(index, kind, { mode })
}

function addScenario(): void {
  let number = scenarios.value.length + 1
  while (scenarios.value.some((item) => item.name === `方案 ${number}`)) number += 1
  scenarios.value = [...scenarios.value, createScenario(`方案 ${number}`)]
}

function copyLast(): void {
  const last = scenarios.value[scenarios.value.length - 1]
  if (last === undefined) return
  let number = scenarios.value.length + 1
  while (scenarios.value.some((item) => item.name === `方案 ${number}`)) number += 1
  scenarios.value = [...scenarios.value, { ...last, name: `方案 ${number}` }]
}

function removeScenario(index: number): void {
  scenarios.value = scenarios.value.filter((_, position) => position !== index)
  closeFx()
}

function openFx(index: number): void {
  if (fxIndex.value === index) {
    closeFx()
    return
  }
  fxIndex.value = index
  fxFrom.value = currency.value === 'CNY' ? 'USD' : 'CNY'
  fxAmount.value = scenarios.value[index]?.purchaseCost ?? ''
  fxRate.value = ''
  fxBasis.value = ''
  fxPreview.value = null
  fxError.value = ''
}

function closeFx(): void {
  fxIndex.value = null
  fxPreview.value = null
  fxError.value = ''
}

function setFxCurrency(event: unknown): void {
  fxFrom.value = currencies[Number(pickerValue(event))] ?? fxFrom.value
  invalidateFx()
}

function setFxAmount(event: unknown): void {
  fxAmount.value = inputValue(event)
  invalidateFx()
}

function setFxRate(event: unknown): void {
  fxRate.value = inputValue(event)
  invalidateFx()
}

function setFxBasis(event: unknown): void {
  fxBasis.value = inputValue(event)
  invalidateFx()
}

/** 任一输入变化都必须重新预览后才能采用。 */
function invalidateFx(): void {
  fxPreview.value = null
  fxError.value = ''
}

/** 拆出整数位与小数位；非法或负数返回 null。 */
function splitDecimal(value: string): { int: string; frac: string } | null {
  const text = value.trim()
  if (!isDecimalInput(text) || text.startsWith('-')) return null
  const [int = '0', frac = ''] = text.split('.')
  return { int: int === '' ? '0' : int, frac }
}

/**
 * 十进制字符串乘法（纯整数逐位运算，不使用浮点），结果四舍五入到 scale 位小数。
 * 用于手工汇率换算预览，确保金额不经过浮点重新计算。
 */
function decimalMultiply(left: string, right: string, scale: number): string | null {
  const a = splitDecimal(left)
  const b = splitDecimal(right)
  if (a === null || b === null) return null
  const digitsA = `${a.int}${a.frac}`
  const digitsB = `${b.int}${b.frac}`
  const buffer = new Array<number>(digitsA.length + digitsB.length).fill(0)
  for (let i = digitsA.length - 1; i >= 0; i -= 1) {
    for (let j = digitsB.length - 1; j >= 0; j -= 1) {
      const product = Number(digitsA[i]) * Number(digitsB[j]) + buffer[i + j + 1]
      buffer[i + j + 1] = product % 10
      buffer[i + j] += Math.floor(product / 10)
    }
  }
  let digits = buffer.join('').replace(/^0+(?=\d)/, '')
  const fracLength = a.frac.length + b.frac.length
  if (fracLength < scale) digits = `${digits}${'0'.repeat(scale - fracLength)}`
  if (fracLength > scale) {
    const cut = digits.length - (fracLength - scale)
    const head = digits.slice(0, cut)
    const roundDigit = Number(digits.charAt(cut))
    digits = `${head}${roundDigit >= 5 ? incrementDigits(head) : ''}`
  }
  const intPart = digits.slice(0, digits.length - scale) || '0'
  const fracPart = scale === 0 ? '' : digits.slice(digits.length - scale)
  return scale === 0 ? intPart : `${intPart}.${fracPart}`
}

/** 十进制字符串 +1（用于四舍五入进位）。 */
function incrementDigits(value: string): string {
  const digits = value.split('')
  let carry = 1
  for (let index = digits.length - 1; index >= 0 && carry > 0; index -= 1) {
    const next = Number(digits[index]) + carry
    digits[index] = `${next % 10}`
    carry = next >= 10 ? 1 : 0
  }
  return carry > 0 ? `1${digits.join('')}` : digits.join('')
}

function previewFx(index: number): void {
  fxError.value = ''
  fxPreview.value = null
  if (fxBasis.value.trim() === '') {
    fxError.value = '请填写汇率来源、日期与报价依据。'
    return
  }
  if (fxBasis.value.trim().length > 300) {
    fxError.value = '依据超过 300 字，请缩短原依据后再换算。'
    return
  }
  if (fxFrom.value === currency.value) {
    fxError.value = '原币种与结算币种相同，无需换算。'
    return
  }
  if (fxAmount.value.trim() === '' || fxRate.value.trim() === '') {
    fxError.value = '请填写原币金额与手工汇率。'
    return
  }
  const converted = decimalMultiply(fxAmount.value, fxRate.value, 4)
  if (converted === null) {
    fxError.value = '请填写非负的原币金额与手工汇率（数字，最多 4 位小数）。'
    return
  }
  const scenario = scenarios.value[index]
  const basis = scenario === undefined
    ? ''
    : `换算：${fxAmount.value.trim()} ${fxFrom.value} × ${fxRate.value.trim()} ${currency.value}/${fxFrom.value} = ${converted} ${currency.value}；${fxBasis.value.trim()}`
  if (basis.length > 500) {
    fxError.value = '换算依据与原有依据合计超过 500 字，请缩短后重试。'
    return
  }
  fxPreview.value = converted
}

function applyFx(index: number): void {
  const converted = fxPreview.value
  const scenario = scenarios.value[index]
  if (converted === null || scenario === undefined) return
  const addition = `换算：${fxAmount.value.trim()} ${fxFrom.value} × ${fxRate.value.trim()} ${currency.value}/${fxFrom.value} = ${converted} ${currency.value}；${fxBasis.value.trim()}`
  const basis = scenario.basis.trim() === '' ? addition : `${scenario.basis.trim()} ${addition}`
  if (basis.length > 500) {
    fxError.value = '换算依据与原有依据合计超过 500 字，请缩短后重试。'
    return
  }
  setScenario(index, { purchaseCost: converted, basis })
  closeFx()
  success('采购成本已按手工汇率换算并追加依据，请核对后再计算。')
}

function studyPayload(): StudyInput {
  const name = title.value.trim()
  if (name === '') throw new Error('请填写试算名称。')
  if (name.length > 120) throw new Error('试算名称不能超过 120 字。')
  const names = scenarios.value.map((item) => item.name.trim())
  if (new Set(names).size !== names.length) throw new Error('方案名称不能重复。')
  const payload: ScenarioInput[] = scenarios.value.map((scenario, index) => {
    const scenarioName = scenario.name.trim()
    if (scenarioName === '') throw new Error(`方案 ${index + 1} 缺少名称。`)
    if (!isDecimalInput(scenario.price) || scenario.price.startsWith('-')) {
      throw new Error(`方案 ${index + 1} 的候选售价须为非负数字。`)
    }
    if (!isDecimalInput(scenario.purchaseCost) || scenario.purchaseCost.startsWith('-')) {
      throw new Error(`方案 ${index + 1} 的采购成本须为非负数字。`)
    }
    if (scenario.basis.trim() === '') throw new Error(`方案 ${index + 1} 缺少售价与成本依据。`)
    if (scenario.basis.trim().length > 500) throw new Error(`方案 ${index + 1} 的依据超过 500 字。`)
    const fees: FeeInput[] = feeKinds.map((fee) => {
      const draft = scenario.fees[fee.key] ?? { mode: 'fixed', value: '', basis: '' }
      const value = draft.value.trim()
      if (value === '') return { kind: fee.key, mode: draft.mode, value: null, basis: '' }
      if (!isDecimalInput(value) || value.startsWith('-')) {
        throw new Error(`方案 ${index + 1} 的${fee.label}须为非负数字。`)
      }
      if (draft.basis.trim() === '') {
        throw new Error(`方案 ${index + 1} 的${fee.label}已填数值，必须填写假设依据。`)
      }
      if (draft.mode === 'percent' && Number(value) > 100) {
        throw new Error(`方案 ${index + 1} 的${fee.label}单项售价费率不能超过 100%。`)
      }
      return { kind: fee.key, mode: draft.mode, value, basis: draft.basis.trim() }
    })
    return {
      name: scenarioName,
      price: scenario.price.trim(),
      purchase_cost: scenario.purchaseCost.trim(),
      basis: scenario.basis.trim(),
      fees,
    }
  })
  return { title: name, currency: currency.value, data_identity: identity.value, scenarios: payload }
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  await load()
})

async function load(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    history.value = asRows<SavedStudySummary>(
      await apiGet(shopPath('/profit/saved'), { offset: offset.value }),
    )
  })
  error.value = message
}

function pageHistory(direction: number): void {
  offset.value = Math.max(0, offset.value + direction * 50)
  void load()
}

async function calculate(): Promise<void> {
  const message = await perform(async () => {
    const payload = studyPayload()
    const value = asObject<StudyResult>(await apiPost(shopPath('/profit/calculate'), payload))
    if (value === null) throw new Error('试算响应无法读取，请刷新重试。')
    result.value = value
    currentTitle.value = payload.title
    savedId.value = null
    // 重新计算是一次新的保存意图：下一次保存必须使用新的幂等键。
    requestKey.value = null
  })
  if (message === '') success('试算完成，请核对未计入费用与保本价口径。')
  else error.value = message
}

async function saveStudy(): Promise<void> {
  const current = result.value
  const modal = await Taro.showModal({
    title: '保存本次方案',
    content: '同一 request_key 表示同一次保存；重复提交会返回已有记录，不会重复存档。',
    confirmText: '保存',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  const key = requestKey.value ?? newRequestId()
  requestKey.value = key
  await writeAction(async () => {
    const payload = current === null ? studyPayload() : {
      title: current.input.title,
      currency: current.input.currency,
      data_identity: current.input.data_identity,
      scenarios: current.input.scenarios,
      request_key: key,
    }
    const value = asObject<SavedStudyOutput>(await apiPost(shopPath('/profit/saved'), payload))
    if (value === null) throw new Error('保存响应无法读取，请到试算历史回读核对。')
    savedId.value = value.id
    // 已保存成功：释放幂等键，修改后重新保存会另存一条记录。
    requestKey.value = null
    await load()
  }, '已保存试算；修改输入后重新计算，可另存记录。', '试算历史')
}

async function inspect(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<SavedStudyOutput>(await apiGet(shopPath(`/profit/saved/${id}`)))
    if (value === null) throw new Error('试算响应无法读取，请刷新重试。')
    result.value = value.result
    currentTitle.value = value.title
    savedId.value = value.id
    restoreDraft(value.result.input)
  })
  error.value = message
}

/** 回读存档时把服务端输入还原到表单，金额与依据按原字符串保留。 */
function restoreDraft(input: StudyInput): void {
  title.value = input.title
  currency.value = input.currency
  identity.value = input.data_identity
  scenarios.value = (input.scenarios ?? []).map((scenario) => {
    const draft = createScenario(scenario.name)
    const fees: Record<string, FeeDraft> = draft.fees
    for (const fee of scenario.fees ?? []) {
      fees[fee.kind] = {
        mode: fee.mode,
        value: fee.value === null || fee.value === undefined ? '' : `${fee.value}`,
        basis: fee.basis ?? '',
      }
    }
    return {
      name: scenario.name,
      price: `${scenario.price}`,
      purchaseCost: `${scenario.purchase_cost}`,
      basis: scenario.basis ?? '',
      fees,
    }
  })
}

async function clearCurrent(): Promise<void> {
  const id = savedId.value
  if (id === null) return
  await clearStudy(id, true)
}

async function clearStudy(id: number, keepForm = false): Promise<void> {
  const modal = await Taro.showModal({
    title: '清除已存试算',
    content: `清除试算 #${id} 的名称、金额、假设和依据。此操作无法恢复。`,
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    await apiRequest(shopPath(`/profit/saved/${id}`), { method: 'DELETE' })
    if (savedId.value === id) savedId.value = null
    await load()
  }, keepForm ? '已清除存档；表单保留当前输入，可继续编辑。' : '存档已清除。', '试算历史')
}
</script>
