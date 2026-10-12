// route: /profit
export type DataIdentity = 'manual_assumption' | 'synthetic'
export type FeeKind =
  | 'inbound'
  | 'outbound'
  | 'platform'
  | 'storage'
  | 'packaging'
  | 'advertising'
  | 'refund'
  | 'tax'
  | 'other'
export type FeeMode = 'fixed' | 'percent'
export interface FeeInput {
  kind: FeeKind
  mode: FeeMode
  value: string | null
  basis: string
}
export interface ScenarioInput {
  name: string
  price: string
  purchase_cost: string
  basis: string
  fees: FeeInput[]
}
export interface StudyInput {
  title: string
  currency: string
  data_identity: DataIdentity
  scenarios: ScenarioInput[]
}
export interface StudySaveBody extends StudyInput {
  request_key: string
}
export interface FeeResult {
  assumption: FeeInput
  amount: string | null
}
export interface SensitivityPoint {
  label: string
  price: string
  purchase_cost: string
  known_balance: string
  margin_percent: string | null
}
export interface ScenarioResult {
  assumption: ScenarioInput
  purchase_gross: string
  known_fees: string
  known_balance: string
  margin_percent: string | null
  fixed_fees: string
  rate_percent: string
  missing_fees: string[]
  fees: FeeResult[]
  break_even_price: string | null
  break_even_reason: string
  sensitivity: SensitivityPoint[]
}
export interface StudyResult {
  input: StudyInput
  rule_version: string
  calculated_at: string
  formula: string
  scope_note: string
  scenarios: ScenarioResult[]
}
export interface SavedStudySummary {
  id: number
  title: string
  currency: string
  data_identity: string
  created_at: string
}
export interface SavedStudyOutput extends SavedStudySummary {
  result: StudyResult
}

export const feeKinds: FeeKind[] = [
  'inbound',
  'outbound',
  'platform',
  'storage',
  'packaging',
  'advertising',
  'refund',
  'tax',
  'other',
]
export const feeLabels: Record<FeeKind, string> = {
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
export const currencies = [
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
export const scenariosPerStudy = 5
export const studiesPerPage = 50

const MONEY = /^\d+(?:\.\d{1,4})?$/
const MONEY_LIMIT = '100000000'

export function newScenario(name = '方案 1'): ScenarioInput {
  return {
    name,
    price: '',
    purchase_cost: '',
    basis: '',
    fees: feeKinds.map((kind) => ({
      kind,
      mode: 'fixed' as FeeMode,
      value: null,
      basis: '',
    })),
  }
}
export function newStudyForm(currency = 'USD'): StudyInput {
  return {
    title: '',
    currency,
    data_identity: 'manual_assumption',
    scenarios: [newScenario()],
  }
}
export function nextScenarioName(items: ScenarioInput[]): string {
  let index = 1
  while (items.some((item) => item.name === `方案 ${index}`)) index++
  return `方案 ${index}`
}
export function copyScenario(item: ScenarioInput, name: string): ScenarioInput {
  const clone = JSON.parse(JSON.stringify(item)) as ScenarioInput
  return { ...clone, name }
}
export function hasMoreStudies(items: unknown[]): boolean {
  return items.length === studiesPerPage
}
// Decimal strings stay text end to end; no client float arithmetic.
export function decimalText(value: string | null | undefined): string {
  if (value == null || value === '') return '未知'
  return value.includes('.')
    ? value.replace(/0+$/, '').replace(/\.$/, '')
    : value
}
export function feeValue(fee: FeeInput): string {
  if (fee.value == null || fee.value === '') return '未计入'
  return fee.mode === 'percent'
    ? `${decimalText(fee.value)}%`
    : decimalText(fee.value)
}
function digits(value: string): string {
  return value.replace(/^0+/, '') || '0'
}
function greaterThan(value: string, limit: string): boolean {
  const [head, tail = ''] = value.split('.')
  const [limitHead, limitTail = ''] = limit.split('.')
  const left = digits(head)
  const right = digits(limitHead)
  if (left.length !== right.length) return left.length > right.length
  if (left !== right) return left > right
  const width = Math.max(tail.length, limitTail.length)
  return tail.padEnd(width, '0') > limitTail.padEnd(width, '0')
}
function money(value: string, label: string): string {
  const text = value.trim()
  if (!MONEY.test(text))
    throw new Error(`${label}须为最多四位小数的非负金额字符串。`)
  if (greaterThan(text, MONEY_LIMIT))
    throw new Error(`${label}不能超过 100000000。`)
  return text
}
export function checkedStudyInput(form: StudyInput): StudyInput {
  const title = form.title.trim()
  if (!title || title.length > 120)
    throw new Error('试算名称须为 1–120 个字符。')
  const currency = form.currency.trim().toUpperCase()
  if (!/^[A-Z]{3}$/.test(currency))
    throw new Error('结算币种须为三位字母代码，且不执行换汇。')
  if (!['manual_assumption', 'synthetic'].includes(form.data_identity))
    throw new Error('假设来源无效。')
  if (!form.scenarios.length || form.scenarios.length > scenariosPerStudy)
    throw new Error(`方案数量须为 1–${scenariosPerStudy} 个。`)
  const names = new Set<string>()
  const scenarios = form.scenarios.map((item, index) => {
    const label = `方案 ${index + 1}`
    const name = item.name.trim()
    if (!name || name.length > 80)
      throw new Error(`${label}名称须为 1–80 个字符。`)
    if (names.has(name)) throw new Error('方案名称不能重复。')
    names.add(name)
    const basis = item.basis.trim()
    if (!basis || basis.length > 500)
      throw new Error(`${label}的价格与采购成本依据须为 1–500 个字符。`)
    if (item.fees.length !== feeKinds.length)
      throw new Error(`${label}须包含九类费用各一次；未知项留空。`)
    const seen = new Set<string>()
    const fees = item.fees.map((fee) => {
      if (!feeKinds.includes(fee.kind))
        throw new Error(`${label}存在未知费用类别。`)
      if (seen.has(fee.kind)) throw new Error(`${label}同类费用不能重复。`)
      seen.add(fee.kind)
      if (!['fixed', 'percent'].includes(fee.mode))
        throw new Error(`${label}费用模式无效。`)
      const text = (fee.value ?? '').trim()
      const feeBasis = fee.basis.trim()
      if (!text)
        return { kind: fee.kind, mode: fee.mode, value: null, basis: feeBasis }
      const amount = money(text, `${label}${feeLabels[fee.kind]}`)
      if (!feeBasis || feeBasis.length > 300)
        throw new Error(
          `${label}${feeLabels[fee.kind]}已填金额，必须填写 1–300 字的假设依据。`,
        )
      if (fee.mode === 'percent' && greaterThan(amount, '100'))
        throw new Error(
          `${label}${feeLabels[fee.kind]}单项售价费率不能超过 100%。`,
        )
      return { kind: fee.kind, mode: fee.mode, value: amount, basis: feeBasis }
    })
    if (seen.size !== feeKinds.length)
      throw new Error(`${label}须包含九类费用各一次；未知项留空。`)
    return {
      name,
      price: money(item.price, `${label}售价`),
      purchase_cost: money(item.purchase_cost, `${label}采购成本`),
      basis,
      fees,
    }
  })
  return { title, currency, data_identity: form.data_identity, scenarios }
}
