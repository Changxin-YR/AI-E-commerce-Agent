import { expect, it, vi, afterEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { localTime, resolveLocalTime, exactTimeError } from '@/composables/businessTime'
import BusinessDateTime from '@/components/BusinessDateTime.vue'
import BusinessDateRange from '@/components/BusinessDateRange.vue'
import { supportTime } from '@/types/support'

afterEach(() => vi.useRealTimers())
it('keeps partially edited input readable without throwing during rendering', () => {
  expect(supportTime('invalid-local-time', 'Asia/Shanghai')).toBe('时间或时区待核对')
  expect(supportTime('2026-10-10T00:00:00Z', 'Asia/')).toBe('时间或时区待核对')
})
it('uses the chosen business timezone and crosses UTC dates', () => {
  expect(resolveLocalTime('2026-10-10T00:30', 'Asia/Shanghai')).toBe('2026-10-09T16:30:00.000Z')
  expect(localTime('2026-10-09T16:30:00Z', 'Asia/Shanghai')).toBe('2026-10-10T00:30:00')
  expect(resolveLocalTime('2026-10-10T00:30', 'Asia/Kathmandu')).toBe('2026-10-09T18:45:00.000Z')
})
it.each([
  ['2026-03-08T02:30', 'America/New_York', '不存在'],
  ['2026-11-01T01:30', 'America/New_York', '出现两次'],
  ['2026-04-05T01:45', 'Australia/Lord_Howe', '出现两次'],
  ['2011-12-30T12:00', 'Pacific/Apia', '不存在'],
])('rejects nonexistent or ambiguous local time %s', (value, zone, message) => {
  expect(() => resolveLocalTime(value, zone)).toThrow(message)
})
it('accepts both explicit offsets in a fold and preserves precise expressions', () => {
  for (const value of [
    '2026-11-01T01:30:00-04:00',
    '2026-11-01T01:30:00-05:00',
    '2026-10-10T01:02:03.123456Z',
  ])
    expect(exactTimeError(value, 'America/New_York')).toBe('')
  expect(exactTimeError('2026-02-30T12:00:00Z', 'UTC')).not.toBe('')
  expect(exactTimeError('2026-10-10T12:00:00', 'UTC')).toContain('明确偏移')
  expect(exactTimeError('2026-10-10T12:00:00Z', 'wrong/zone')).not.toBe('')
})
it('keeps rejected local edits visible and invalid, including optional values', async () => {
  const wrapper = mount(BusinessDateTime, {
    props: { modelValue: '', timezone: 'America/New_York', label: '时间' },
  })
  const input = wrapper.get('input[type="datetime-local"]')
  await input.setValue('2026-03-08T02:30')
  await wrapper.setProps({ modelValue: 'invalid-local-time' })
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('不存在')
  expect((input.element as HTMLInputElement).validity.valid).toBe(false)
  expect((input.element as HTMLInputElement).value).toBe('2026-03-08T02:30')
  await input.setValue('2026-03-08T03:30')
  expect(wrapper.emitted('update:modelValue')?.slice(-1)[0]).toEqual(['2026-03-08T07:30:00.000Z'])
})
it('changing display timezone never rewrites a precise stored instant', async () => {
  const wrapper = mount(BusinessDateTime, {
    props: {
      modelValue: '2026-10-10T01:02:03.123456Z',
      timezone: 'UTC',
      label: '时间',
      required: true,
    },
  })
  await wrapper.setProps({ timezone: 'Asia/Shanghai' })
  expect((wrapper.get('input[type="datetime-local"]').element as HTMLInputElement).value).toBe(
    '2026-10-10T09:02:03',
  )
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
})
it('quick ranges use elapsed days and clearly exclude the end', async () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-03-10T12:00:00Z'))
  const wrapper = mount(BusinessDateRange, {
    props: {
      start: '2026-03-03T12:00:00Z',
      end: '2026-03-10T12:00:00Z',
      timezone: 'America/New_York',
      startLabel: '起点',
      endLabel: '终点',
    },
  })
  await wrapper.findAll('button')[0]!.trigger('click')
  expect(wrapper.emitted('update:start')?.[0]).toEqual(['2026-03-03T12:00:00.000Z'])
  expect(wrapper.text()).toContain('不计入终点')
  expect(wrapper.text()).toContain('每天 24 小时')
})
