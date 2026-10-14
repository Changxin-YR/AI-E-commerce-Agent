import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import AgentView from '@/views/AgentView.vue'
import type { AgentRun } from '@/types/agent'
const { start, advanceStream, act, get } = vi.hoisted(() => ({
  start: vi.fn(),
  advanceStream: vi.fn(),
  act: vi.fn(),
  get: vi.fn(),
}))
vi.mock('@/api/identity', () => ({
  identityApi: {
    shops: async () => [{ id: 3, name: '测试店', currency: 'USD', timezone: 'Asia/Shanghai' }],
  },
}))
vi.mock('@/api/agent', () => ({
  agentApi: {
    start,
    advanceStream,
    act,
    get,
    runs: async () => [],
    skills: async () => [],
    model: async () => ({ status: 'configured', model: 'test-double' }),
  },
}))
vi.mock('@/api/listings', () => ({ listingsApi: { products: async () => [] } }))
vi.mock('@/api/support', () => ({ supportApi: { messages: async () => [] } }))
vi.mock('@/composables/useSession', () => ({
  useSession: () => ({ session: { value: { username: 'owner' } } }),
}))
const result = {
  id: 1,
  shop_id: 3,
  template: 'question',
  status: 'succeeded',
  reason: 'chat_answered',
  result: { chat_answer: 'Known gross profit is available; net profit is unknown.' },
  version: 2,
  source_status: 'current',
  steps: [],
  budget: {},
  input: null,
} as unknown as AgentRun
beforeEach(() => {
  vi.clearAllMocks()
  start.mockImplementation(async (_shop, input) => ({
    ...result,
    input: JSON.parse(JSON.stringify(input)),
    status: 'ready',
    version: 1,
  }))
  advanceStream.mockResolvedValue(result)
  get.mockResolvedValue(result)
})
async function open(url = '/agent?shop=3&identity=synthetic') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  await router.push(url)
  const wrapper = mount(AgentView, {
    global: {
      plugins: [router],
      stubs: {
        AppliedRules: {
          emits: ['pending', 'loaded'],
          mounted() {
            this.$emit('pending', false)
          },
          template: '<div />',
        },
        AgentRunReview: true,
        AgentStreamPreview: true,
        InternalAuthorizations: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}
it('asks directly with scoped consent and stops at the answer without approving writes', async () => {
  const wrapper = await open()
  expect(wrapper.text()).toContain('发送问题')
  expect(wrapper.findAll('input[type=checkbox]')).toHaveLength(0)
  await wrapper.get('textarea').setValue('最近7天的销售情况如何？')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(start).toHaveBeenCalledTimes(1)
  expect(start.mock.calls[0]![1]).toMatchObject({
    template: 'question',
    response_mode: 'chat',
    response_language: 'auto',
    allow_model: true,
    allow_analysis_data: true,
    scope: { data_identity: 'synthetic' },
  })
  expect(advanceStream).toHaveBeenCalledTimes(1)
  expect(act).not.toHaveBeenCalled()
  expect(wrapper.find('agent-run-review-stub').exists()).toBe(false)
  expect(wrapper.find('agent-stream-preview-stub').exists()).toBe(false)
  expect(wrapper.get('[aria-label="AI 回答"]').text()).toContain('Known gross profit')
  wrapper.unmount()
})
it('rejects blank submissions and switches between concise and advanced controls', async () => {
  const wrapper = await open()
  await wrapper.get('form').trigger('submit')
  expect(start).not.toHaveBeenCalled()
  await wrapper
    .findAll('button')
    .find((button) => button.text() === '高级执行台')!
    .trigger('click')
  expect(wrapper.text()).toContain('执行流程')
  await wrapper
    .findAll('button')
    .find((button) => button.text() === '返回简洁问答')!
    .trigger('click')
  expect(wrapper.findAll('input[type=checkbox]')).toHaveLength(0)
  wrapper.unmount()
})

it('keeps the question available for retry when answering fails', async () => {
  start.mockRejectedValueOnce(new Error('Connection lost'))
  const wrapper = await open()
  await wrapper.get('textarea').setValue('请用中文总结销售')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.get('textarea').element.value).toBe('请用中文总结销售')
  expect(act).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('opens historical workflow runs in the execution workbench', async () => {
  const initial = await open()
  await initial.get('textarea').setValue('原任务目标')
  await initial.get('form').trigger('submit')
  await flushPromises()
  const input = { ...start.mock.calls[0]![1], response_mode: 'workflow' }
  initial.unmount()
  get.mockResolvedValue({ ...result, input })
  const wrapper = await open('/agent?shop=3&execution=1')
  expect(wrapper.find('agent-run-review-stub').exists()).toBe(true)
  expect(wrapper.text()).toContain('返回简洁问答')
  expect(wrapper.get('textarea').element.value).toBe('原任务目标')
  wrapper.unmount()
})

it('starts bounded authorizations with workflow mode', async () => {
  const wrapper = await open('/agent?shop=3&mode=daily')
  wrapper.findComponent({ name: 'InternalAuthorizations' }).vm.$emit('start', {
    id: 7,
    shop_id: 3,
    scope: { data_identity: 'synthetic', channel: 'generic' },
  })
  await flushPromises()
  expect(start).toHaveBeenCalledWith(
    3,
    expect.objectContaining({
      template: 'daily',
      response_mode: 'workflow',
      authorization_id: 7,
      allow_model: false,
    }),
  )
  wrapper.unmount()
})

it('opening and dismissing save confirmation makes no approval request', async () => {
  const wrapper = await open()
  await wrapper.get('textarea').setValue('总结销售')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  await wrapper
    .findAll('button')
    .find((button) => button.text() === '保存到工作台')!
    .trigger('click')
  expect(wrapper.find('[aria-label="确认修改业务数据"]').exists()).toBe(true)
  expect(act).not.toHaveBeenCalled()
  await wrapper
    .findAll('button')
    .find((button) => button.text() === '暂不保存')!
    .trigger('click')
  expect(wrapper.find('[aria-label="确认修改业务数据"]').exists()).toBe(false)
  expect(act).not.toHaveBeenCalled()
  wrapper.unmount()
})
