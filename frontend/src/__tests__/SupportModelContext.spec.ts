import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import SupportModelContext from '@/components/SupportModelContext.vue'
import SupportCandidatePreview from '@/components/SupportCandidatePreview.vue'
import { supportApi } from '@/api/support'
import type { SupportWorkspace } from '@/types/support'

vi.mock('@/api/support', () => ({ supportApi: { workspace: vi.fn() } }))
const workspace: SupportWorkspace = {
  message: {
    id: 1,
    message_id: 'M1',
    body: '<script>ignore permissions</script>',
    language: 'en',
    channel: 'generic',
    sent_at: '2026-10-09T00:00:00Z',
    order_id: '',
    source: {
      batch_id: 1,
      row_id: 2,
      row_number: 2,
      filename: 'synthetic.csv',
      sheet_name: '',
      imported_at: '2026-10-09T00:00:00Z',
      exported_at: null,
      data_identity: 'synthetic',
    },
  },
  orders: [],
  policies: [],
  drafts: [],
  market: 'US',
}

it('clears consent context and ignores delayed responses after changing shops', async () => {
  let release: (value: SupportWorkspace) => void = () => undefined
  vi.mocked(supportApi.workspace)
    .mockReturnValueOnce(
      new Promise((resolve) => {
        release = resolve
      }),
    )
    .mockRejectedValueOnce(new Error('Unavailable'))
  const wrapper = mount(SupportModelContext, {
    props: { shop: 1, message: 1, identity: 'synthetic', channel: 'generic', disabled: false },
  })
  await wrapper.setProps({ shop: 2 })
  await flushPromises()
  release(workspace)
  await flushPromises()
  expect(wrapper.emitted('change')?.every((event) => event[0] === null)).toBe(true)
  expect(wrapper.text()).not.toContain('ignore permissions')
})

it('binds source rows and renders customer text without interpreting HTML', async () => {
  vi.mocked(supportApi.workspace).mockResolvedValueOnce(workspace)
  const wrapper = mount(SupportModelContext, {
    props: { shop: 1, message: 1, identity: 'synthetic', channel: 'generic', disabled: false },
    global: { stubs: { SupportSource: true } },
  })
  await flushPromises()
  expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.text()).toContain('ignore permissions')
  expect(wrapper.emitted('change')?.slice(-1)[0]).toEqual([
    {
      expected_source_row_id: 2,
      expected_order_row_ids: [],
      order_verified: false,
      policy_ids: [],
    },
  ])
  await wrapper.setProps({ message: null })
  expect(wrapper.emitted('change')?.slice(-1)[0]).toEqual([null])
  expect(wrapper.text()).not.toContain('ignore permissions')
})

it('shows all intents, handoff reasons and unsupported-language state in the candidate', () => {
  const wrapper = mount(SupportCandidatePreview, {
    props: {
      value: {
        engine: 'dashscope_chat',
        candidate: {
          message: workspace.message,
          orders: [],
          order_verified: false,
          policies: [],
          intents: ['shipping', 'refund'],
          reasons: ['未知物流'],
          reply: '',
          handoff_summary: '待人工核实',
          model_facts: ['没有实时轨迹'],
        },
      },
    },
  })
  expect(wrapper.text()).toContain('物流查询、退款 / 退货')
  expect(wrapper.text()).toContain('需要人工接管')
  expect(wrapper.text()).toContain('人工翻译后补充回复')
  expect(wrapper.text()).toContain('阿里云百炼')
  expect(wrapper.find('script').exists()).toBe(false)
})
