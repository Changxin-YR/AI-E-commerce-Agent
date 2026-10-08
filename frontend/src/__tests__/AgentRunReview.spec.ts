import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import AgentRunReview from '@/components/AgentRunReview.vue'
import type { AgentRun } from '@/types/agent'

function run(): AgentRun {
  return {
    id: 1,
    shop_id: 2,
    template: 'daily',
    status: 'waiting_approval',
    reason: 'findings_found',
    version: 1,
    next_node: 'propose_tasks',
    source_status: 'current',
    source_revision: 1,
    input: null,
    result: null,
    steps_used: 1,
    elapsed_ms: 20,
    budget: { max_steps: 12, max_seconds: 120, max_cost_usd: '0' },
    spent_usd: '0',
    reserved_usd: '0',
    model_status: 'not_used',
    created_at: '2026-10-09T01:00:00Z',
    external_status: 'not_submitted',
    steps: [
      {
        id: 1,
        node: 'data_check',
        skill: 'data_check',
        skill_version: '1',
        status: 'completed',
        reason: '',
        next_node: 'propose_tasks',
        input: {},
        output: { text: '<script>alert(1)</script>' },
        duration_ms: 20,
        created_at: '2026-10-09T01:00:00Z',
      },
    ],
  }
}

it('blocks stale approval and removes erased step content', async () => {
  const wrapper = mount(AgentRunReview, {
    props: { run: run(), busy: false },
    global: { stubs: ['RouterLink'] },
  })
  expect(wrapper.find('script').exists()).toBe(false)
  const approve = () => wrapper.findAll('button').find((b) => b.text() === '批准当前节点')!
  await approve().trigger('click')
  expect(wrapper.emitted('action')?.[0]).toEqual(['approve'])
  await wrapper.setProps({ run: { ...run(), source_status: 'stale' } })
  expect(approve().attributes('disabled')).toBeDefined()
  await wrapper.setProps({
    run: {
      ...run(),
      status: 'blocked',
      source_status: 'cleared',
      reason: 'source_cleared',
      steps: run().steps.map((s) => ({ ...s, input: null, output: null })),
    },
  })
  expect(wrapper.text()).not.toContain('alert(1)')
  expect(wrapper.text()).toContain('正文已擦除')
})

it('does not offer retry for model result unknown', () => {
  const wrapper = mount(AgentRunReview, {
    props: {
      run: {
        ...run(),
        status: 'result_unknown',
        reason: 'model_result_unknown',
        reserved_usd: '0.01',
      },
      busy: false,
    },
    global: { stubs: ['RouterLink'] },
  })
  expect(wrapper.text()).toContain('不会自动重发')
  expect(
    wrapper.findAll('button').some((b) => b.text().includes('恢复') || b.text().includes('继续')),
  ).toBe(false)
})
