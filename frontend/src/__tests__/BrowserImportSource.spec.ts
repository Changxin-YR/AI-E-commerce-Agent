import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import BrowserImportSource from '@/components/BrowserImportSource.vue'

const worker = {
  terminate: vi.fn(),
  postMessage: vi.fn(),
  onmessage: null as ((event: MessageEvent) => void) | null,
  onerror: null as (() => void) | null,
}
beforeEach(() => {
  vi.resetAllMocks()
  vi.stubGlobal(
    'Worker',
    vi.fn(function () {
      return worker
    }),
  )
})
afterEach(() => vi.unstubAllGlobals())
async function start() {
  const prepared = vi.fn()
  const wrapper = mount(BrowserImportSource, { props: { disabled: false, onPrepared: prepared } })
  Object.defineProperty(wrapper.get('input').element, 'files', {
    value: [new File(['sku\nA'], 'synthetic.csv')],
  })
  await wrapper.get('input').trigger('change')
  return { wrapper, prepared }
}
describe('browser source worker lifecycle', () => {
  it('terminates cancellation and ignores a queued result', async () => {
    const { wrapper, prepared } = await start()
    expect(worker.postMessage).toHaveBeenCalledOnce()
    await wrapper.get('button').trigger('click')
    worker.onmessage!(
      new MessageEvent('message', { data: { result: { manifest: {}, files: [] } } }),
    )
    expect(worker.terminate).toHaveBeenCalledOnce()
    expect(prepared.mock.calls).toEqual([[null], [null]])
    expect(wrapper.emitted('busy')).toEqual([[true], [false]])
  })
  it('stops and releases on page/shop unmount', async () => {
    const { wrapper, prepared } = await start()
    wrapper.unmount()
    worker.onmessage!(
      new MessageEvent('message', { data: { result: { manifest: {}, files: [] } } }),
    )
    expect(worker.terminate).toHaveBeenCalledOnce()
    expect(prepared.mock.calls).toEqual([[null]])
  })
  it('reports worker failure with no prepared file', async () => {
    const { wrapper, prepared } = await start()
    worker.onerror!()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('本机拆分未完成')
    expect(worker.terminate).toHaveBeenCalledOnce()
    expect(prepared.mock.calls).toEqual([[null]])
  })
})
