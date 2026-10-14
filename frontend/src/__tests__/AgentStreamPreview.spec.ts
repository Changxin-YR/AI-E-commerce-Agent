import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import AgentStreamPreview from '@/components/AgentStreamPreview.vue'

it('shows incoming output as unverified text and preserves an interrupted state', async () => {
  const wrapper = mount(AgentStreamPreview, {
    props: { text: '{"text":"库存', message: '正在执行当前步骤', active: true, interrupted: false },
  })
  expect(wrapper.text()).toContain('内容待校验')
  expect(wrapper.find('details').attributes('open')).toBeUndefined()
  await wrapper.setProps({
    text: '<script>alert(1)</script>',
    active: false,
    interrupted: true,
    message: '连接中断',
  })
  expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.find('pre').text()).toContain('<script>')
  expect(wrapper.text()).toContain('不会自动重发')
  expect(wrapper.attributes('aria-busy')).toBe('false')
})

it('shows readable selections as their actual completed tokens arrive', async () => {
  const wrapper = mount(AgentStreamPreview, {
    props: { text: '{"check_ids":["low_in', message: '正在生成', active: true, interrupted: false },
  })
  expect(wrapper.get('[aria-label="AI 生成预览"]').text()).not.toContain('核对库存与补货')
  await wrapper.setProps({
    text: '{"check_ids":["low_inventory","fees"],"next_action":"offer_todo"}',
  })
  const preview = wrapper.get('[aria-label="AI 生成预览"]')
  expect(preview.text()).toContain('核对库存与补货')
  expect(preview.text()).toContain('补充费用依据')
  expect(preview.text()).toContain('提交待办供审批')
  expect(preview.text()).toContain('待校验')
})
