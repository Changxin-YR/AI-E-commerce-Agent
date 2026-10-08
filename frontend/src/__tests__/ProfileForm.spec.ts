import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ProfileForm from '@/components/ProfileForm.vue'
import { identityApi } from '@/api/identity'

vi.mock('@/api/identity', () => ({ identityApi: { saveProfile: vi.fn() } }))

describe('profile editing', () => {
  it('retains entered values and reports a rejected stale edit', async () => {
    vi.mocked(identityApi.saveProfile).mockRejectedValue(
      new Error('经营资料已在其他页面更新，请刷新后重试'),
    )
    const wrapper = mount(ProfileForm, {
      props: {
        profile: {
          display_name: '合成资料',
          target_market: 'US',
          business_model: '零售',
          category: '家居',
          currency: 'USD',
          timezone: 'Asia/Shanghai',
          language: 'zh-CN',
          version: 1,
        },
      },
    })
    await wrapper.get('#display-name').setValue('我的新资料')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('其他页面更新')
    expect((wrapper.get('#display-name').element as HTMLInputElement).value).toBe('我的新资料')
    expect(wrapper.emitted('saved')).toBeUndefined()
    expect(wrapper.get('button').attributes('disabled')).toBeUndefined()
  })
})
