export const feeLabels = {
  inbound: '头程物流',
  outbound: '尾程物流',
  platform: '平台费用',
  storage: '仓储',
  packaging: '包装',
  advertising: '广告',
  refund: '退款损失',
  tax: '税费',
  other: '其他及分摊费用',
} as const
export type FeeKind = keyof typeof feeLabels
export interface FeeInput {
  kind: FeeKind
  mode: 'fixed' | 'percent'
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
  data_identity: 'manual_assumption' | 'synthetic'
  scenarios: ScenarioInput[]
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
  fees: { assumption: FeeInput; amount: string | null }[]
  break_even_price: string | null
  break_even_reason: string
  sensitivity: {
    label: string
    price: string
    purchase_cost: string
    known_balance: string
    margin_percent: string | null
  }[]
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
export interface SavedStudy extends SavedStudySummary {
  result: StudyResult
}

export function newScenario(name = '方案 1'): ScenarioInput {
  return {
    name,
    price: '',
    purchase_cost: '',
    basis: '',
    fees: (Object.keys(feeLabels) as FeeKind[]).map((kind) => ({
      kind,
      mode: 'fixed',
      value: null,
      basis: '',
    })),
  }
}

// Keep monetary values as decimal text. Vue's type=number coercion is deliberately avoided.
export function decimalText(value: string | null): string {
  if (value === null) return '无法确定'
  return value.includes('.') ? value.replace(/0+$/, '').replace(/\.$/, '') : value
}
