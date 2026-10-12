import test from 'node:test'
import assert from 'node:assert/strict'
import {
  checkedExpenseContent,
  checkedExpenseScope,
  checkedFeeRuleContent,
  decimalText,
  emptyExpense,
  expenseActions,
  linkedOrder,
  localIso,
  ruleActions,
  zoneOffsetMinutes,
} from '../src/services/expense-policy.ts'

function content(overrides = {}) {
  return {
    label: '十月仓储费',
    category: 'storage',
    amount: '120.5000',
    currency: 'CNY',
    occurred_at: '2026-10-12T09:30:00+08:00',
    timezone: 'Asia/Shanghai',
    evidence_ref: 'INV-2026-10-0001',
    evidence_note: '仓库账单第 3 行',
    allocation: 'shop',
    order_line_id: null,
    expected_source_row_id: null,
    expected_source_revision: null,
    reason: '按账单首次录入',
    ...overrides,
  }
}
function orderLine(overrides = {}) {
  return {
    ...content({
      allocation: 'order_line',
      order_line_id: 77,
      expected_source_row_id: 501,
      expected_source_revision: 12,
      currency: 'USD',
    }),
    ...overrides,
  }
}
function scope(overrides = {}) {
  return {
    data_identity: 'user_import',
    channel: 'generic',
    start_at: '2026-10-01T00:00:00+08:00',
    end_at: '2026-10-08T00:00:00+08:00',
    timezone: 'Asia/Shanghai',
    ...overrides,
  }
}

test('expense offsets are derived from the chosen IANA zone', () => {
  assert.equal(
    localIso(new Date('2026-10-12T01:30:00Z'), 'Asia/Shanghai'),
    '2026-10-12T09:30:00+08:00',
  )
  assert.equal(
    localIso(new Date('2026-01-15T12:00:00Z'), 'America/New_York'),
    '2026-01-15T07:00:00-05:00',
  )
  assert.equal(
    localIso(new Date('2026-07-15T12:00:00Z'), 'America/New_York'),
    '2026-07-15T08:00:00-04:00',
  )
  assert.equal(
    zoneOffsetMinutes(new Date('2026-07-15T12:00:00Z'), 'America/New_York'),
    -240,
  )
  assert.equal(zoneOffsetMinutes(new Date('2026-01-15T12:00:00Z'), 'UTC'), 0)
  const empty = emptyExpense(
    'USD',
    'Asia/Shanghai',
    new Date('2026-10-12T01:30:00Z'),
  )
  assert.equal(empty.occurred_at, '2026-10-12T09:30:00+08:00')
  assert.equal(empty.timezone, 'Asia/Shanghai')
  assert.equal(empty.allocation, 'shop')
  assert.equal(empty.order_line_id, null)
})

test('expense content is trimmed and normalised without mutating the draft', () => {
  const draft = content({
    label: '  十月仓储费 ',
    currency: 'cny',
    amount: ' 120.5000 ',
    evidence_ref: ' INV-1 ',
    evidence_note: ' 账单第 3 行 ',
    reason: ' 首次录入 ',
  })
  const checked = checkedExpenseContent(draft)
  assert.equal(checked.label, '十月仓储费')
  assert.equal(checked.currency, 'CNY')
  assert.equal(checked.amount, '120.5000')
  assert.equal(checked.evidence_ref, 'INV-1')
  assert.equal(checked.evidence_note, '账单第 3 行')
  assert.equal(checked.reason, '首次录入')
  assert.equal(checked.occurred_at, '2026-10-12T09:30:00+08:00')
  assert.equal(draft.label, '  十月仓储费 ')
  assert.equal(draft.currency, 'cny')
})

test('expense amount must be a positive decimal string within server bounds', () => {
  for (const amount of ['', '0', '0.0000', '-1', '1.23456', 'abc', '1e3']) {
    assert.throws(
      () => checkedExpenseContent(content({ amount })),
      /实际费用金额/,
      `amount ${amount}`,
    )
  }
  assert.equal(
    checkedExpenseContent(content({ amount: '100000000' })).amount,
    '100000000',
  )
  assert.throws(
    () => checkedExpenseContent(content({ amount: '100000000.0001' })),
    /不能超过 100000000/,
  )
  assert.equal(
    checkedExpenseContent(content({ amount: '0.0001' })).amount,
    '0.0001',
  )
})

test('expense content requires explicit offsets matching the IANA zone', () => {
  assert.throws(
    () =>
      checkedExpenseContent(content({ occurred_at: '2026-10-12T09:30:00' })),
    /须为带明确时区偏移的 ISO 时间/,
  )
  assert.throws(
    () =>
      checkedExpenseContent(
        content({ occurred_at: '2026-10-12 09:30:00+08:00' }),
      ),
    /须为带明确时区偏移的 ISO 时间/,
  )
  assert.throws(
    () =>
      checkedExpenseContent(
        content({ occurred_at: '2026-10-12T09:30:00+00:00' }),
      ),
    /偏移与所选 IANA 时区不符/,
  )
  assert.throws(
    () =>
      checkedExpenseContent(
        content({ occurred_at: '1999-12-31T09:30:00+08:00' }),
      ),
    /年份须在 2000—2100 之间/,
  )
  assert.throws(
    () => checkedExpenseContent(content({ timezone: 'UTC+8' })),
    /发生时区无效/,
  )
  assert.throws(
    () => checkedExpenseContent(content({ timezone: '' })),
    /发生时区无效/,
  )
  assert.equal(
    checkedExpenseContent(
      content({ occurred_at: '2026-10-12T01:30:00Z', timezone: 'UTC' }),
    ).occurred_at,
    '2026-10-12T01:30:00Z',
  )
})

test('expense content enforces evidence text and currency codes', () => {
  for (const [overrides, message] of [
    [{ label: '' }, /费用名称须为 1–100 个字符/],
    [{ label: 'x'.repeat(101) }, /费用名称须为 1–100 个字符/],
    [{ evidence_ref: '' }, /凭据编号须为 1–120 个字符/],
    [{ evidence_note: ' ' }, /事实依据须为 1–1000 个字符/],
    [{ reason: '' }, /本次录入或修订理由须为 1–500 个字符/],
    [{ currency: 'US' }, /费用币种须为三位字母代码/],
    [{ category: 'customs' }, /费用类别无效/],
    [{ allocation: 'sku' }, /费用归属无效/],
  ])
    assert.throws(() => checkedExpenseContent(content(overrides)), message)
})

test('expense allocation binds order lines and rejects mixed links', () => {
  const linked = checkedExpenseContent(orderLine())
  assert.equal(linked.allocation, 'order_line')
  assert.equal(linked.order_line_id, 77)
  assert.equal(linked.expected_source_row_id, 501)
  assert.equal(linked.expected_source_revision, 12)
  for (const overrides of [
    { order_line_id: null },
    { expected_source_row_id: null },
    { expected_source_revision: null },
    { order_line_id: 0 },
    { expected_source_revision: -1 },
  ])
    assert.throws(
      () => checkedExpenseContent(orderLine(overrides)),
      /订单行费用须先查找并绑定当前来源行与店铺来源版本/,
    )
  for (const overrides of [
    { order_line_id: 1 },
    { expected_source_row_id: 1 },
    { expected_source_revision: 0 },
  ])
    assert.throws(
      () => checkedExpenseContent(content(overrides)),
      /店铺费用不关联订单/,
    )
})

test('expense scope keeps an explicit window within 366 days', () => {
  const checked = checkedExpenseScope(scope())
  assert.equal(checked.start_at, '2026-10-01T00:00:00+08:00')
  assert.equal(checked.end_at, '2026-10-08T00:00:00+08:00')
  for (const [overrides, message] of [
    [
      { end_at: '2026-10-01T00:00:00+08:00' },
      /查询区间须大于零且不超过 366 天/,
    ],
    [
      { start_at: '2026-10-08T00:00:00+08:00' },
      /查询区间须大于零且不超过 366 天/,
    ],
    [
      { start_at: '2025-10-01T00:00:00+08:00' },
      /查询区间须大于零且不超过 366 天/,
    ],
    [
      { end_at: '2026-10-08T00:00:00' },
      /结束时间须为带明确时区偏移的 ISO 时间/,
    ],
    [
      { start_at: '2026-10-01T00:00:00Z' },
      /开始时间的偏移与所选 IANA 时区不符/,
    ],
    [{ timezone: 'Asia/Shangai' }, /核对显示时区无效/],
    [{ data_identity: 'live' }, /数据身份无效/],
    [{ channel: 'etsy' }, /来源渠道无效/],
    [{ start_at: '1999-10-01T00:00:00+08:00' }, /年份须在 2000—2101 之间/],
  ])
    assert.throws(() => checkedExpenseScope(scope(overrides)), message)
  const dst = checkedExpenseScope(
    scope({
      timezone: 'America/New_York',
      start_at: '2026-03-01T00:00:00-05:00',
      end_at: '2026-03-20T00:00:00-04:00',
    }),
  )
  assert.equal(dst.end_at, '2026-03-20T00:00:00-04:00')
})

test('fee rule content keeps bounded text and a known category', () => {
  const checked = checkedFeeRuleContent({
    fee_name: '  平台佣金 ',
    category: 'platform',
    reason: ' 按账单名称归类 ',
  })
  assert.equal(checked.fee_name, '平台佣金')
  assert.equal(checked.reason, '按账单名称归类')
  assert.throws(
    () =>
      checkedFeeRuleContent({
        fee_name: '',
        category: 'platform',
        reason: 'x',
      }),
    /完整原始收费名须为 1–120 个字符/,
  )
  assert.throws(
    () =>
      checkedFeeRuleContent({
        fee_name: 'x'.repeat(121),
        category: 'platform',
        reason: 'x',
      }),
    /完整原始收费名须为 1–120 个字符/,
  )
  assert.throws(
    () =>
      checkedFeeRuleContent({
        fee_name: 'a',
        category: 'platform',
        reason: '',
      }),
    /本次规则依据与理由须为 1–500 个字符/,
  )
  assert.throws(
    () =>
      checkedFeeRuleContent({ fee_name: 'a', category: 'fees', reason: 'x' }),
    /统一费用类别无效/,
  )
})

test('expense and rule controls fail closed outside their statuses', () => {
  assert.deepEqual(expenseActions('active'), ['withdraw', 'clear'])
  assert.deepEqual(expenseActions('stale'), ['withdraw', 'clear'])
  assert.deepEqual(expenseActions('withdrawn'), ['clear'])
  assert.deepEqual(expenseActions('cleared'), [])
  assert.deepEqual(expenseActions('unknown'), [])
  assert.deepEqual(ruleActions('active'), ['withdraw', 'clear'])
  assert.deepEqual(ruleActions('withdrawn'), ['clear'])
  assert.deepEqual(ruleActions('cleared'), [])
  assert.deepEqual(ruleActions('unknown'), [])
  assert.equal(decimalText('120.5000'), '120.5')
  assert.equal(decimalText(null), '未知')
})

test('order line linking needs the current source revision', () => {
  const linked = linkedOrder({ id: 77, source: { row_id: 501 } }, 12)
  assert.deepEqual(linked, {
    order_line_id: 77,
    expected_source_row_id: 501,
    expected_source_revision: 12,
  })
  assert.throws(() => linkedOrder(undefined, 12), /请先查找订单行/)
  assert.throws(
    () => linkedOrder({ id: 77, source: { row_id: 501 } }, null),
    /请先查找订单行/,
  )
  assert.throws(
    () => linkedOrder({ id: 77, source: { row_id: 501 } }, -1),
    /请先查找订单行/,
  )
})
