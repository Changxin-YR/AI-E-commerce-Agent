import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ReviewedDelivery from '@/components/ReviewedDelivery.vue'
import type { ManualDelivery } from '@/types/manualDelivery'

const artifact: ManualDelivery = {
  plain_text: '合成杯 Cup\n参数: Steel',
  csv_text: '\ufeff"标题"\r\n"\'合成杯 Cup"',
  filename: 'listing-1-v2.csv',
  checked_at: '2026-10-10T00:00:00Z',
}
afterEach(() => vi.restoreAllMocks())
function clipboard(reject = false) {
  const writeText = reject
    ? vi.fn().mockRejectedValue(new Error('denied'))
    : vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
  return writeText
}
function setup(loadArtifact = vi.fn().mockResolvedValue(artifact)) {
  return mount(ReviewedDelivery, {
    props: { contextKey: '1:2:2', allowed: true, disabled: false, loadArtifact },
  })
}
describe('Reviewed manual delivery', () => {
  it('revalidates every copy and reports success only after clipboard completion', async () => {
    const write = clipboard()
    const load = vi.fn().mockResolvedValue(artifact)
    const wrapper = setup(load)
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(write).toHaveBeenCalledWith(artifact.plain_text)
    expect(wrapper.text()).toContain('已复制通用草稿')
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(load).toHaveBeenCalledTimes(2)
  })
  it('offers full readonly text on clipboard denial and clears it on failure', async () => {
    clipboard(true)
    const load = vi
      .fn()
      .mockResolvedValueOnce(artifact)
      .mockRejectedValueOnce(new Error('来源已变化'))
    const wrapper = setup(load)
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.get('textarea').element.value).toBe(artifact.plain_text)
    expect(wrapper.get('textarea').attributes('readonly')).toBeDefined()
    expect(wrapper.text()).not.toContain('已复制通用草稿')
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.find('textarea').exists()).toBe(false)
    expect(wrapper.text()).toContain('来源已变化')
  })
  it.each(['context', 'disabled', 'unmounted'])(
    'discards a late response after %s change',
    async (change) => {
      const write = clipboard()
      let finish!: (value: ManualDelivery) => void
      const load = vi.fn(
        () =>
          new Promise<ManualDelivery>((resolve) => {
            finish = resolve
          }),
      )
      const wrapper = setup(load)
      await wrapper.get('button').trigger('click')
      if (change === 'context') await wrapper.setProps({ contextKey: '2:2:2' })
      if (change === 'disabled') await wrapper.setProps({ disabled: true })
      if (change === 'unmounted') wrapper.unmount()
      finish(artifact)
      await flushPromises()
      expect(write).not.toHaveBeenCalled()
    },
  )
  it('blocks unapproved and unsaved results', async () => {
    const load = vi.fn().mockResolvedValue(artifact)
    const wrapper = setup(load)
    await wrapper.setProps({ allowed: false })
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    await wrapper.setProps({ allowed: true, disabled: true })
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    expect(load).not.toHaveBeenCalled()
  })
  it('downloads the verified UTF-8 CSV using its controlled filename', async () => {
    const create = vi.fn().mockReturnValue('blob:synthetic')
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: create })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      expect(this.download).toBe(artifact.filename)
      expect(this.href).toBe('blob:synthetic')
    })
    const wrapper = setup()
    await wrapper.findAll('button')[1]!.trigger('click')
    await flushPromises()
    expect(click).toHaveBeenCalledOnce()
    expect(create.mock.calls[0]![0]).toBeInstanceOf(Blob)
    expect(wrapper.text()).toContain('外部状态保持未提交')
  })
})
