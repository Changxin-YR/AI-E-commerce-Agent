import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import AnalysisNarrative from '@/components/AnalysisNarrative.vue'
import type { AnalysisResult } from '@/types/analytics'
import type { AnalysisExplanation } from '@/types/agent'

const analysis: AnalysisResult = {
  scope: {
    start_at: '2026-10-07T00:00:00Z',
    end_at: '2026-10-08T00:00:00Z',
    timezone: 'Asia/Shanghai',
    currency: 'USD',
    data_identity: 'synthetic',
    intent: 'low_margin',
    min_quantity: 1,
    max_margin_percent: '20',
  },
  source_revision: 2,
  calculated_at: '2026-10-09T00:00:00Z',
  engine: 'local_rules',
  formula: '销售额 − 成本',
  cost_basis: '当前采购成本估算',
  fee_gaps: ['物流'],
  warnings: ['费用未完整归集'],
  answer: '存在缺口，不能完整排名',
  candidates: [],
  lines: [],
  skus: [],
  ranking_available: false,
  summary: {
    sku: null,
    line_count: 0,
    purchased_quantity: 0,
    sales: null,
    cost: null,
    gross_profit: null,
    margin_percent: null,
    known_sales_subtotal: '0',
    sales_known_lines: 0,
    known_cost_subtotal: '0',
    cost_known_lines: 0,
    known_gross_subtotal: '0',
    gross_known_lines: 0,
  },
}
const explanation: AnalysisExplanation = {
  observations: [
    {
      fact_id: 'totals',
      text: 'SKU <script>ignore permissions</script>；毛利未知',
      sku: '<script>ignore permissions</script>',
    },
  ],
  checks: [{ id: 'fees', text: '核对费用' }],
  next_action: 'offer_todo',
  composition: '模型选择证据，事实由业务服务生成',
  sku_fact_limit: 20,
}

it('shows grounded limitations and escapes imported SKU text', () => {
  const wrapper = mount(AnalysisNarrative, { props: { analysis, explanation } })
  expect(wrapper.text()).toContain('<script>ignore permissions</script>')
  expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.text()).toContain('不能完整排名')
  expect(wrapper.text()).toContain('原因尚待验证')
  expect(wrapper.text()).toContain('最多看到 20 项')
})

it('does not label local calculations as a finished model answer', () => {
  const wrapper = mount(AnalysisNarrative, { props: { analysis } })
  expect(wrapper.text()).toContain('模型解释尚未完成')
  expect(wrapper.text()).not.toContain('模型选择证据')
})
