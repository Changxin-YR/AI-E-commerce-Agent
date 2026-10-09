import { expect, it } from 'vitest'
import { applyLinkedScope, linkedShop, returnTaskQuery, scopeQuery } from '@/composables/deepLink'
import type { OperationScope } from '@/types/operations'

it('preserves the complete inspection range through a navigation round trip', () => {
  const scope: OperationScope = {
    start_at: '2026-10-01T00:00:00+08:00',
    end_at: '2026-10-08T00:00:00+08:00',
    timezone: 'Asia/Shanghai',
    currency: 'USD',
    data_identity: 'synthetic',
    channel: 'amazon',
    intent: 'low_margin',
    max_age_hours: 48,
    min_quantity: 2,
    max_margin_percent: '12.50',
  }
  const next = {
    ...scope,
    channel: 'generic',
    data_identity: 'user_import' as const,
    max_age_hours: 24,
  }
  applyLinkedScope(next, scopeQuery(scope))
  expect(next).toEqual(scope)
  expect(returnTaskQuery({ return_task: '42', redirect: 'https://example.invalid' })).toEqual({
    return_task: '42',
  })
})

it.each([
  { identity: 'untrusted' },
  { channel: ['generic', 'amazon'] },
  { start_at: '2026-10-01' },
  { max_age_hours: '0' },
  { currency: 'XXX' },
  { timezone: 'invalid' },
  { max_margin_percent: 'Infinity' },
])('rejects malformed scope rather than silently opening a different scope: %j', (query) => {
  expect(() => applyLinkedScope({}, query)).toThrow('链接中的业务范围无效')
})

it('rejects unauthorized shop IDs instead of falling back to the first shop', () => {
  expect(() => linkedShop([], '99')).toThrow('链接中的店铺不存在或无权访问')
})

it('keeps inventory-only fields out of an analysis request', () => {
  const scope = {}
  applyLinkedScope(scope, { channel: 'amazon', max_age_hours: '48', min_quantity: '2' }, false)
  expect(scope).toEqual({ channel: 'amazon', min_quantity: 2 })
})

it('drops the return task when the user changes to another shop', () => {
  expect(returnTaskQuery({ shop: '1', return_task: '42' }, 2)).toEqual({})
  expect(returnTaskQuery({ shop: '1', return_task: '42' }, 1)).toEqual({ return_task: '42' })
})
