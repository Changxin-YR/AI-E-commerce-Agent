import test from 'node:test'
import assert from 'node:assert/strict'
import {
  availableActions,
  canEdit,
  checkedContent,
  checkedDraft,
  checkedInstant,
  checkedReceipt,
  checkedScope,
  checkedTimezone,
  controlBody,
  emptySettlementScope,
  isCurrentVersion,
  localIso,
  receiptKeys,
  settlementActionIds,
  trimmedAmount,
  zoneOffsetMinutes,
} from '../src/services/settlement-policy.ts'

function scope(overrides = {}) {
  return {
    data_identity: 'user_import',
    channel: 'generic',
    start_at: '2026-10-01T00:00:00+08:00',
    end_at: '2026-10-02T00:00:00+08:00',
    timezone: 'Asia/Shanghai',
    ...overrides,
  }
}

function receipt(overrides = {}) {
  return {
    payout_ref: 'PO-1',
    receipt_ref: 'RC-1',
    amount: '1200.50',
    currency: 'USD',
    received_at: '2026-10-12T09:30:00+08:00',
    timezone: 'Asia/Shanghai',
    note: '银行流水截图核对',
    ...overrides,
  }
}

function content(overrides = {}) {
  return {
    statement_id: 'ST-2026-10',
    note: '按平台 10 月结算文件登记周期',
    receipts: [receipt()],
    ...overrides,
  }
}

test('settlement scope accepts a bounded explicit-offset window without mutating input', () => {
  const input = scope()
  const checked = checkedScope(input)
  assert.equal(checked.start_at, '2026-10-01T00:00:00+08:00')
  assert.equal(checked.end_at, '2026-10-02T00:00:00+08:00')
  assert.equal(checked.timezone, 'Asia/Shanghai')
  assert.equal(input.start_at, '2026-10-01T00:00:00+08:00')
  // 366 天为上限，结束不含。
  checkedScope(
    scope({
      start_at: '2025-10-01T00:00:00+08:00',
      end_at: '2026-10-02T00:00:00+08:00',
    }),
  )
})

test('settlement scope rejects reversed, empty, malformed and oversized windows', () => {
  for (const dates of [
    {
      start_at: '2026-10-02T00:00:00+08:00',
      end_at: '2026-10-01T00:00:00+08:00',
    },
    {
      start_at: '2026-10-01T00:00:00+08:00',
      end_at: '2026-10-01T00:00:00+08:00',
    },
    {
      start_at: '2025-10-01T00:00:00+08:00',
      end_at: '2026-10-03T00:00:00+08:00',
    },
    { start_at: '2026/10/01 00:00:00', end_at: '2026-10-02T00:00:00+08:00' },
    { start_at: '', end_at: '2026-10-02T00:00:00+08:00' },
    { start_at: '2026-10-01T00:00:00', end_at: '2026-10-02T00:00:00+08:00' },
  ])
    assert.throws(() => checkedScope(scope(dates)), /周期|ISO 时间/)
})

test('settlement scope keeps identity, channel and IANA timezone rules', () => {
  assert.equal(
    checkedScope(scope({ data_identity: 'synthetic' })).data_identity,
    'synthetic',
  )
  assert.equal(
    checkedScope(
      scope({
        channel: 'amazon',
        timezone: 'UTC',
        start_at: '2026-10-01T00:00:00Z',
        end_at: '2026-10-02T00:00:00Z',
      }),
    ).channel,
    'amazon',
  )
  assert.throws(
    () => checkedScope(scope({ data_identity: 'live' })),
    /数据身份/,
  )
  assert.throws(() => checkedScope(scope({ channel: 'tiktok' })), /来源渠道/)
  for (const timezone of ['Mars/Base', '', 'UTC+8'])
    assert.throws(() => checkedScope(scope({ timezone })), /周期显示时区/)
  assert.throws(
    () => checkedScope(scope({ start_at: '1999-10-01T00:00:00+08:00' })),
    /年份/,
  )
})

test('explicit offsets must match the selected IANA timezone but Z is an instant', () => {
  // +09:00 与 Asia/Shanghai 不符。
  assert.throws(
    () => checkedScope(scope({ start_at: '2026-10-01T00:00:00+09:00' })),
    /偏移与所选 IANA 时区不符/,
  )
  // Z 表示同一时刻，不做本地偏移换算。
  assert.equal(
    checkedInstant('2026-10-01T00:00:00Z', '周期开始', 'Asia/Shanghai'),
    '2026-10-01T00:00:00Z',
  )
  assert.throws(
    () => checkedInstant('2026-10-01T00:00:00', '周期开始', 'Asia/Shanghai'),
    /ISO 时间/,
  )
  assert.throws(
    () => checkedInstant('2026-10-01T00:00:00+08:00', '周期开始', 'Mars/Base'),
    /时区无效|Invalid time zone/,
  )
})

test('settlement localIso writes the explicit offset of the target zone', () => {
  const instant = new Date('2026-10-12T01:30:00Z')
  assert.equal(localIso(instant, 'Asia/Shanghai'), '2026-10-12T09:30:00+08:00')
  assert.equal(localIso(instant, 'UTC'), '2026-10-12T01:30:00+00:00')
  assert.equal(
    localIso(instant, 'America/New_York'),
    '2026-10-11T21:30:00-04:00',
  )
  assert.equal(zoneOffsetMinutes(instant, 'Asia/Shanghai'), 480)
  assert.equal(zoneOffsetMinutes(instant, 'UTC'), 0)
  assert.equal(checkedTimezone(' Asia/Shanghai '), 'Asia/Shanghai')
})

test('receipts require positive Decimal amounts, refund-safe currency and aware time', () => {
  const checked = checkedReceipt(receipt({ amount: '1200.5000' }))
  assert.equal(checked.amount, '1200.5000')
  assert.equal(checked.currency, 'usd'.toUpperCase())
  for (const amount of ['0', '0.0000', '-1', '1e3', '12.34567', '', 'abc'])
    assert.throws(() => checkedReceipt(receipt({ amount })), /到账金额/)
  assert.throws(
    () => checkedReceipt(receipt({ amount: '100000001' })),
    /不能超过/,
  )
  assert.throws(() => checkedReceipt(receipt({ currency: 'US' })), /三位字母/)
  assert.throws(
    () => checkedReceipt(receipt({ received_at: '2026-10-12T09:30:00' })),
    /到账时间/,
  )
  assert.throws(
    () => checkedReceipt(receipt({ received_at: '2026-10-12T09:30:00+09:00' })),
    /偏移与所选 IANA 时区不符/,
  )
  assert.equal(
    checkedReceipt(receipt({ received_at: '2026-10-12T01:30:00Z' }))
      .received_at,
    '2026-10-12T01:30:00Z',
  )
  assert.throws(() => checkedReceipt(receipt({ note: '   ' })), /凭据核验说明/)
  assert.throws(
    () => checkedReceipt(receipt({ payout_ref: 'x'.repeat(121) })),
    /平台回款凭据号/,
  )
})

test('settlement content limits receipts and rejects normalised duplicates', () => {
  const checked = checkedContent(content())
  assert.equal(checked.statement_id, 'ST-2026-10')
  assert.deepEqual(checked.receipts.length, 1)
  assert.deepEqual(receiptKeys(checked.receipts), ['rc-1'])
  assert.throws(
    () =>
      checkedContent(
        content({ receipts: [receipt(), receipt({ receipt_ref: ' rc-1 ' })] }),
      ),
    /不能重复登记/,
  )
  assert.throws(
    () =>
      checkedContent({
        statement_id: 'ST-1',
        note: 'n',
        receipts: Array.from({ length: 51 }, (_, index) =>
          receipt({ receipt_ref: `RC-${index}` }),
        ),
      }),
    /最多 50 笔/,
  )
  assert.throws(
    () => checkedContent(content({ statement_id: ' ' })),
    /原账单号/,
  )
  assert.throws(
    () => checkedContent(content({ note: 'x'.repeat(1001) })),
    /周期依据/,
  )
  // 范围是半开区间，回款与到账凭据可晚于周期结束。
  assert.deepEqual(checkedContent(content({ receipts: [] })).receipts, [])
})

test('settlement draft keeps new/update version semantics', () => {
  assert.equal(
    checkedDraft({
      scope: scope(),
      settlement_id: 7,
      version: 3,
      content: content(),
    }).version,
    3,
  )
  assert.equal(
    checkedDraft({
      scope: scope(),
      settlement_id: null,
      version: 0,
      content: content(),
    }).settlement_id,
    null,
  )
  assert.throws(
    () =>
      checkedDraft({
        scope: scope(),
        settlement_id: null,
        version: 2,
        content: content(),
      }),
    /新建登记版本必须为零/,
  )
  assert.throws(
    () =>
      checkedDraft({
        scope: scope(),
        settlement_id: 0,
        version: 0,
        content: content(),
      }),
    /登记编号无效/,
  )
  assert.throws(
    () =>
      checkedDraft({
        scope: scope(),
        settlement_id: 3,
        version: -1,
        content: content(),
      }),
    /版本无效/,
  )
})

test('settlement actions follow the server control contract', () => {
  assert.deepEqual(availableActions('active'), ['withdraw', 'clear'])
  assert.deepEqual(availableActions('stale'), ['withdraw', 'clear'])
  assert.deepEqual(availableActions('withdrawn'), ['clear'])
  assert.deepEqual(availableActions('cleared'), [])
  assert.deepEqual(availableActions('unknown'), [])
  assert.deepEqual(controlBody(4, 'req-1'), {
    request_id: 'req-1',
    version: 4,
    confirm: true,
  })
  assert.throws(() => controlBody(0, 'req-1'), /版本无效/)
  assert.throws(() => controlBody(1.5, 'req-1'), /版本无效/)
})

test('records expose current-version and editability gates', () => {
  const record = {
    status: 'active',
    content_version: 3,
    snapshot: { source_revision: 1 },
  }
  assert.equal(isCurrentVersion(record, 3), true)
  assert.equal(isCurrentVersion(record, 2), false)
  assert.equal(isCurrentVersion(record, null), false)
  assert.equal(canEdit(record), true)
  assert.equal(canEdit({ ...record, status: 'stale' }), true)
  assert.equal(canEdit({ ...record, status: 'withdrawn' }), false)
  assert.equal(canEdit({ ...record, status: 'cleared' }), false)
  assert.equal(canEdit({ ...record, snapshot: null }), false)
})

test('empty settlement scope and Decimal display stay explicit', () => {
  const value = emptySettlementScope(
    'Asia/Shanghai',
    new Date('2026-10-12T01:30:00Z'),
  )
  assert.equal(value.end_at, '2026-10-12T09:30:00+08:00')
  assert.equal(value.start_at, '2026-09-12T09:30:00+08:00')
  assert.equal(value.timezone, 'Asia/Shanghai')
  assert.equal(trimmedAmount('1200.5000'), '1200.5')
  assert.equal(trimmedAmount('1200'), '1200')
  assert.equal(trimmedAmount('0.0000'), '0')
  assert.equal(trimmedAmount(null), '未知')
  assert.equal(trimmedAmount(''), '未知')
})

test('contract action ids stay aligned with the r2 contract entries', () => {
  // 覆盖 contracts/ui-contract.json 的 r2.settlements 6 个 action_id。
  assert.deepEqual(Object.values(settlementActionIds), [
    'preview_api_shops__shop_id__settlements_preview_post',
    'write_api_shops__shop_id__settlements_post',
    'page_api_shops__shop_id__settlements_get',
    'get_api_shops__shop_id__settlements__settlement_id__get',
    'read_current_api_shops__shop_id__settlements__settlement_id__current_get',
    'control_api_shops__shop_id__settlements__settlement_id___action__post',
  ])
})
