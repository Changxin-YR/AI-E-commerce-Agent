import test from 'node:test'
import assert from 'node:assert/strict'
import {
  availableActions,
  blockedOutcomes,
  canEdit,
  checkedInstant,
  checkedOrderScope,
  checkedReviewConclusion,
  checkedReviewDraft,
  checkedScope,
  checkedTimezone,
  controlBody,
  emptyOrderScope,
  emptyStatementScope,
  entryTypes,
  isCurrentVersion,
  localIso,
  mappingStatuses,
  orderActionIds,
  statementActionIds,
  statementLineLabel,
  statusCounts,
  trimmedAmount,
  zoneOffsetMinutes,
} from '../src/services/statement-policy.ts'

function scope(overrides = {}) {
  return {
    data_identity: 'user_import',
    channel: 'generic',
    start_at: '2026-09-12T00:00:00+08:00',
    end_at: '2026-10-12T00:00:00+08:00',
    timezone: 'Asia/Shanghai',
    ...overrides,
  }
}

function orderScope(overrides = {}) {
  return { ...scope(), sale_basis: 'unknown', basis_note: '', ...overrides }
}

test('statement scope accepts a bounded explicit-offset window without mutating input', () => {
  const input = scope()
  const checked = checkedScope(input)
  assert.equal(checked.start_at, '2026-09-12T00:00:00+08:00')
  assert.equal(checked.end_at, '2026-10-12T00:00:00+08:00')
  assert.equal(checked.timezone, 'Asia/Shanghai')
  assert.equal(input.start_at, '2026-09-12T00:00:00+08:00')
  checkedScope(
    scope({
      start_at: '2025-10-12T00:00:00+08:00',
      end_at: '2026-10-13T00:00:00+08:00',
    }),
  )
})

test('statement scope rejects reversed, empty, malformed and oversized windows', () => {
  for (const dates of [
    {
      start_at: '2026-10-12T00:00:00+08:00',
      end_at: '2026-09-12T00:00:00+08:00',
    },
    {
      start_at: '2026-10-12T00:00:00+08:00',
      end_at: '2026-10-12T00:00:00+08:00',
    },
    {
      start_at: '2025-10-12T00:00:00+08:00',
      end_at: '2026-10-14T00:00:00+08:00',
    },
    { start_at: '2026-09-12', end_at: '2026-10-12T00:00:00+08:00' },
    { start_at: '', end_at: '2026-10-12T00:00:00+08:00' },
  ])
    assert.throws(() => checkedScope(scope(dates)), /核对区间|ISO 时间/)
})

test('statement scope keeps identity, channel, timezone and offset rules', () => {
  assert.equal(
    checkedScope(scope({ data_identity: 'synthetic' })).data_identity,
    'synthetic',
  )
  assert.equal(
    checkedScope(
      scope({
        channel: 'shopify',
        timezone: 'UTC',
        start_at: '2026-09-12T00:00:00Z',
        end_at: '2026-10-12T00:00:00Z',
      }),
    ).channel,
    'shopify',
  )
  assert.throws(
    () => checkedScope(scope({ data_identity: 'live' })),
    /数据身份/,
  )
  assert.throws(() => checkedScope(scope({ channel: 'tiktok' })), /来源渠道/)
  for (const timezone of ['Mars/Base', '', 'UTC+8'])
    assert.throws(() => checkedScope(scope({ timezone })), /核对显示时区/)
  assert.throws(
    () => checkedScope(scope({ start_at: '2026-09-12T00:00:00+09:00' })),
    /偏移与所选 IANA 时区不符/,
  )
  // Z 表示同一时刻，不做本地偏移换算。
  assert.equal(
    checkedInstant('2026-09-12T00:00:00Z', '开始时间', 'Asia/Shanghai'),
    '2026-09-12T00:00:00Z',
  )
  assert.throws(
    () =>
      checkedInstant('1999-09-12T00:00:00+08:00', '开始时间', 'Asia/Shanghai'),
    /年份/,
  )
  assert.equal(checkedTimezone('Asia/Shanghai'), 'Asia/Shanghai')
  assert.equal(
    zoneOffsetMinutes(new Date('2026-10-12T01:30:00Z'), 'Asia/Shanghai'),
    480,
  )
  assert.equal(
    localIso(new Date('2026-10-12T01:30:00Z'), 'Asia/Shanghai'),
    '2026-10-12T09:30:00+08:00',
  )
})

test('order reconciliation scope requires a declared basis note when comparable', () => {
  const pending = checkedOrderScope(orderScope())
  assert.equal(pending.sale_basis, 'unknown')
  assert.equal(pending.basis_note, '')
  const declared = checkedOrderScope(
    orderScope({
      sale_basis: 'merchandise_after_discount',
      basis_note: '  平台账单 sales 列与订单行 unit_price×quantity−discount  ',
    }),
  )
  assert.equal(declared.sale_basis, 'merchandise_after_discount')
  assert.equal(
    declared.basis_note,
    '平台账单 sales 列与订单行 unit_price×quantity−discount',
  )
  assert.throws(
    () =>
      checkedOrderScope(
        orderScope({
          sale_basis: 'merchandise_after_discount',
          basis_note: '   ',
        }),
      ),
    /金额组成依据/,
  )
  assert.throws(
    () => checkedOrderScope(orderScope({ sale_basis: 'gross_sales' })),
    /销售金额口径无效/,
  )
  assert.throws(
    () =>
      checkedOrderScope(
        orderScope({
          sale_basis: 'merchandise_after_discount',
          basis_note: 'x'.repeat(501),
        }),
      ),
    /不能超过 500/,
  )
  // 选择未知口径时保留窗口与身份约束。
  assert.throws(
    () => checkedOrderScope(orderScope({ channel: 'tiktok' })),
    /来源渠道/,
  )
})

test('review conclusions and drafts keep the new/update version semantics', () => {
  const conclusion = checkedReviewConclusion({
    outcome: 'differences_recorded',
    note: '  两笔费用差额已与平台客服确认，待下月补扣  ',
  })
  assert.equal(conclusion.outcome, 'differences_recorded')
  assert.equal(conclusion.note, '两笔费用差额已与平台客服确认，待下月补扣')
  assert.throws(
    () => checkedReviewConclusion({ outcome: 'agreed', note: 'x' }),
    /人工结论无效/,
  )
  assert.throws(
    () => checkedReviewConclusion({ outcome: 'pending', note: '  ' }),
    /核对依据与差异说明/,
  )
  assert.throws(
    () =>
      checkedReviewConclusion({ outcome: 'pending', note: 'x'.repeat(1001) }),
    /核对依据与差异说明/,
  )
  assert.equal(
    checkedReviewDraft({
      scope: scope(),
      review_id: 5,
      version: 2,
      conclusion: { outcome: 'pending', note: '待核' },
    }).version,
    2,
  )
  assert.equal(
    checkedReviewDraft({
      scope: scope(),
      review_id: null,
      version: 0,
      conclusion: { outcome: 'pending', note: '待核' },
    }).review_id,
    null,
  )
  assert.throws(
    () =>
      checkedReviewDraft({
        scope: scope(),
        review_id: null,
        version: 1,
        conclusion: { outcome: 'pending', note: '待核' },
      }),
    /新建存档版本必须为零/,
  )
  assert.throws(
    () =>
      checkedReviewDraft({
        scope: scope(),
        review_id: 0,
        version: 0,
        conclusion: { outcome: 'pending', note: '待核' },
      }),
    /存档编号无效/,
  )
  // 不可比口径的 blockers 只允许“保持待核”。
  assert.deepEqual(blockedOutcomes([]), [])
  assert.deepEqual(blockedOutcomes(['存在缺失一侧、重复凭据或异币种记录。']), [
    'consistent',
    'differences_recorded',
  ])
})

test('statement review actions follow the server control contract', () => {
  assert.deepEqual(availableActions('active'), ['withdraw', 'clear'])
  assert.deepEqual(availableActions('stale'), ['withdraw', 'clear'])
  assert.deepEqual(availableActions('withdrawn'), ['clear'])
  assert.deepEqual(availableActions('cleared'), [])
  assert.deepEqual(availableActions(''), [])
  assert.deepEqual(controlBody(6, 'req-2'), {
    request_id: 'req-2',
    version: 6,
    confirm: true,
  })
  assert.throws(() => controlBody(0, 'req-2'), /版本无效/)
  assert.throws(() => controlBody(2.5, 'req-2'), /版本无效/)
})

test('review records expose current-version and editability gates', () => {
  const record = {
    status: 'active',
    content_version: 4,
    snapshot: { expense_revision: 2 },
  }
  assert.equal(isCurrentVersion(record, 4), true)
  assert.equal(isCurrentVersion(record, 3), false)
  assert.equal(isCurrentVersion(record, null), false)
  assert.equal(canEdit(record), true)
  assert.equal(canEdit({ ...record, status: 'stale' }), true)
  assert.equal(canEdit({ ...record, status: 'withdrawn' }), false)
  assert.equal(canEdit({ ...record, status: 'cleared' }), false)
  assert.equal(canEdit({ ...record, snapshot: null }), false)
})

test('statement default scopes are explicit-offset, aware and bounded', () => {
  const now = new Date('2026-10-12T01:30:00Z')
  const value = emptyStatementScope('Asia/Shanghai', now)
  assert.equal(value.start_at, '2026-09-12T09:30:00+08:00')
  assert.equal(value.end_at, '2026-10-12T09:30:00+08:00')
  assert.equal(value.data_identity, 'user_import')
  assert.equal(value.channel, 'generic')
  const orders = emptyOrderScope('Asia/Shanghai', now)
  assert.equal(orders.sale_basis, 'unknown')
  assert.equal(orders.basis_note, '')
  assert.equal(orders.end_at, value.end_at)
})

test('display helpers keep Decimal text and status counts explicit', () => {
  assert.equal(trimmedAmount('1200.5000'), '1200.5')
  assert.equal(trimmedAmount('0.0000'), '0')
  assert.equal(trimmedAmount(null), '未知')
  assert.deepEqual(statusCounts(['matched', 'pending', 'matched']), [
    { key: 'matched', count: 2 },
    { key: 'pending', count: 1 },
  ])
  assert.deepEqual(statusCounts([]), [])
  assert.equal(entryTypes.payout, '平台记载回款')
  assert.equal(mappingStatuses.category_conflict, '与人工费用类别冲突 · 待核')
  const line = {
    id: 9,
    statement_id: 'ST-1',
    line_id: 'L-1',
    entry_type: 'fee',
    amount: '5.00',
    currency: 'USD',
    occurred_at: '2026-10-01T00:00:00Z',
    evidence_ref: 'FEE-1',
    fee_name: '平台佣金',
    settlement_id: '',
    order_id: '',
    note: '',
  }
  const label = statementLineLabel(line, 0)
  assert.match(label, /1\. 费用/)
  assert.match(label, /账单 ST-1 \/ 行 L-1/)
  assert.match(label, /平台佣金/)
  assert.match(label, /凭据 FEE-1/)
})

test('contract action ids stay aligned with the r2 contract entries', () => {
  // 覆盖 contracts/ui-contract.json 的 r2.statements 7 个 action_id。
  assert.deepEqual(Object.values(statementActionIds), [
    'reconcile_api_shops__shop_id__statements_reconcile_post',
    'preview_api_shops__shop_id__statement_reviews_preview_post',
    'write_api_shops__shop_id__statement_reviews_post',
    'page_api_shops__shop_id__statement_reviews_get',
    'get_api_shops__shop_id__statement_reviews__review_id__get',
    'read_current_api_shops__shop_id__statement_reviews__review_id__current_get',
    'control_api_shops__shop_id__statement_reviews__review_id___action__post',
  ])
  // 覆盖 contracts/ui-contract.json 的 r2.order_reconciliation 唯一 action_id。
  assert.deepEqual(Object.values(orderActionIds), [
    'reconcile_orders_api_shops__shop_id__statements_orders_reconcile_post',
  ])
})
