import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import AgentAnswer from '@/components/AgentAnswer.vue'
import type { AgentRun } from '@/types/agent'
const run = {
  status: 'waiting_approval',
  source_status: 'current',
  input: null,
  steps: [
    {
      node: 'compose_listing',
      status: 'completed',
      output: { candidate: { title: '商品标题', description: '<script>unsafe</script>商品描述' } },
    },
  ],
} as unknown as AgentRun
it('shows completed text before approval, escapes markup and suppresses cleared content', async () => {
  const wrapper = mount(AgentAnswer, { props: { run, busy: false } })
  expect(wrapper.text()).toContain('商品标题')
  expect(wrapper.find('script').exists()).toBe(false)
  await wrapper.setProps({ run: { ...run, source_status: 'stale' } })
  expect(wrapper.text()).toContain('资料已变化')
  await wrapper.setProps({ run: { ...run, source_status: 'cleared' } })
  expect(wrapper.text()).not.toContain('商品标题')
  expect(wrapper.text()).toContain('资料已清除')
})

it('shows only the conclusion and asks for confirmation only after an explicit save request', async () => {
  const completed = {
    ...run,
    template: 'question',
    status: 'succeeded',
    reason: 'chat_answered',
    result: { chat_answer: 'Sales increased. Net profit is unknown.' },
    steps: [],
  }
  const wrapper = mount(AgentAnswer, { props: { run: completed, busy: false, canSave: true } })
  expect(wrapper.text()).toContain('Sales increased.')
  expect(wrapper.text()).not.toContain('执行')
  expect(wrapper.find('[aria-label="确认修改业务数据"]').exists()).toBe(false)
  await wrapper.get('button').trigger('click')
  expect(wrapper.emitted('save')).toHaveLength(1)
  expect(wrapper.emitted('approve')).toBeUndefined()
  await wrapper.setProps({ run: { ...completed, status: 'waiting_approval' }, confirmSave: true })
  expect(wrapper.get('[aria-label="确认修改业务数据"]').text()).toContain('创建一条')
  await wrapper
    .findAll('button')
    .find((button) => button.text() === '确认保存')!
    .trigger('click')
  expect(wrapper.emitted('approve')).toHaveLength(1)
})
