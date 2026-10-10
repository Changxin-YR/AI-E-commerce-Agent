import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import MarginReviewEvidence from '@/components/MarginReviewEvidence.vue'
import type { MarginEvidence } from '@/types/agent'

it('shows separate evidence and bounded candidates while rendering source text safely', () => {
  const value: MarginEvidence = {
    scope: {
      start_at: '2026-10-01T00:00:00Z',
      end_at: '2026-10-08T00:00:00Z',
      timezone: 'UTC',
      currency: 'USD',
      data_identity: 'synthetic',
      channel: 'generic',
      intent: 'low_margin',
      min_quantity: 1,
      max_margin_percent: '20',
    },
    source_revision: 7,
    included_lines: 22,
    ranking_available: true,
    candidate_count: 22,
    candidates: ['<script>synthetic()</script>'],
    candidate_limit: 20,
    cost_basis: '卖家提供的历史成本依据',
    fee_gaps: ['运费'],
    data_gaps: [],
    recommendations: [
      {
        kind: 'pricing',
        title: '复核定价、成本与费用',
        evidence: '商品毛利已知',
        action: '批准后保存分析',
        risk: 'R1',
      },
      {
        kind: 'listing',
        title: '独立内容遗漏',
        evidence: '来源参数未出现在本地版本',
        action: '单独审批',
        risk: 'R1',
      },
    ],
    save_analysis: true,
    listing: null,
    listing_note: '外部刊登仍需人工核对',
  }
  const wrapper = mount(MarginReviewEvidence, { props: { value } })
  expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.text()).toContain('<script>synthetic()</script>')
  expect(wrapper.text()).toContain('低毛利命中 22 个 SKU')
  expect(wrapper.text()).toContain('最多显示 20 项')
  expect(wrapper.findAll('article')).toHaveLength(2)
  expect(wrapper.text()).toContain('尚无法核实净利润')
})
