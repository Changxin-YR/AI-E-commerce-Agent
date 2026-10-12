import test from 'node:test'
import assert from 'node:assert/strict'
import { checkedOverviewScope } from '../src/services/overview-policy.ts'

function scope(overrides = {}) {
  return {
    shop_ids: [3, 1],
    start_date: '2026-10-01',
    end_date: '2026-10-08',
    comparison_start: '2026-09-24',
    comparison_end: '2026-10-01',
    timezone: 'Asia/Shanghai',
    data_identity: 'user_import',
    currencies: ['USD', 'CNY'],
    max_age_hours: 24,
    min_quantity: 1,
    max_margin_percent: '20',
    ...overrides,
  }
}

test('overview scope sorts shops without mutating the caller scope', () => {
  const input = scope()
  const checked = checkedOverviewScope(input)
  assert.deepEqual(checked.shop_ids, [1, 3])
  assert.deepEqual(checked.currencies, ['USD', 'CNY'])
  assert.deepEqual(input.shop_ids, [3, 1])
  assert.deepEqual(input.currencies, ['USD', 'CNY'])
})

test('overview scope requires a 1–366 day window with an exclusive end date', () => {
  assert.deepEqual(
    checkedOverviewScope(scope({ end_date: '2026-11-01' })).end_date,
    '2026-11-01',
  )
  checkedOverviewScope(
    scope({ start_date: '2025-10-12', end_date: '2026-10-13' }),
  )
  for (const dates of [
    { start_date: '2026-10-28', end_date: '2026-10-08' },
    { start_date: '2026-10-08', end_date: '2026-10-08' },
    { start_date: '2025-10-12', end_date: '2026-10-14' },
    { start_date: '2026/10/01', end_date: '2026-10-08' },
    { start_date: '', end_date: '2026-10-08' },
  ])
    assert.throws(
      () => checkedOverviewScope(scope(dates)),
      /日期窗口须为1–366天/,
    )
})

test('overview scope rejects empty, duplicated and oversized shop selections', () => {
  for (const shop_ids of [
    [],
    [1, 1],
    Array.from({ length: 21 }, (_, i) => i + 1),
  ])
    assert.throws(
      () => checkedOverviewScope(scope({ shop_ids })),
      /请选择1–20家不重复店铺/,
    )
})

test('overview scope keeps identity and bounded freshness rules', () => {
  assert.equal(
    checkedOverviewScope(scope({ data_identity: 'synthetic' })).data_identity,
    'synthetic',
  )
  for (const invalid of [
    { data_identity: 'live' },
    { max_age_hours: 0 },
    { max_age_hours: 721 },
    { min_quantity: 0 },
    { min_quantity: 2.5 },
  ])
    assert.throws(
      () => checkedOverviewScope(scope(invalid)),
      /总览范围参数无效/,
    )
})

test('overview scope requires an IANA timezone and leaves codes to the server', () => {
  for (const timezone of ['Mars/Base', '', 'UTC+8'])
    assert.throws(
      () => checkedOverviewScope(scope({ timezone })),
      /统计时区无效/,
    )
  assert.equal(checkedOverviewScope(scope({ timezone: 'UTC' })).timezone, 'UTC')
  // The server rejects unsupported codes; the client only refuses repeats.
  assert.deepEqual(
    checkedOverviewScope(scope({ currencies: ['USD', 'BTC'] })).currencies,
    ['USD', 'BTC'],
  )
  assert.throws(
    () => checkedOverviewScope(scope({ currencies: ['USD', 'USD'] })),
    /币种范围无效/,
  )
  assert.deepEqual(
    checkedOverviewScope(scope({ currencies: [] })).currencies,
    [],
  )
})
