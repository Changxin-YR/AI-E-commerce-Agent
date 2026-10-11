import test from 'node:test'
import assert from 'node:assert/strict'
import {
  checkedAnalysisScope,
  linkedAnalysisScope,
  costWrite,
} from '../src/services/analytics-policy.ts'
const scope = {
  start_at: '2026-10-01T08:00:00+08:00',
  end_at: '2026-10-02T08:00:00+08:00',
  min_quantity: 1,
  max_margin_percent: '20.25',
}
test('analysis validates explicit timezone, bounded window and quantity without changing Decimal strings', () => {
  assert.equal(checkedAnalysisScope(scope).start_at, '2026-10-01T00:00:00.000Z')
  assert.equal(checkedAnalysisScope(scope).max_margin_percent, '20.25')
  for (const change of [
    { end_at: scope.start_at },
    { start_at: '2026-10-01T08:00:00' },
    { min_quantity: 0 },
    { max_margin_percent: '1.234' },
    { max_margin_percent: '101' },
  ])
    assert.throws(() => checkedAnalysisScope({ ...scope, ...change }))
})
test('cost writes freeze version and revision, preserve precision and omit content on revoke', () => {
  const page = { source_current: true, version: 2, source_revision: 7 }
  const content = {
    unit_cost: '12345678901234.1234',
    currency: 'USD',
    evidence_ref: 'receipt',
    evidence_at: '2026-10-01T08:00:00+08:00',
    confirmed: true,
  }
  const value = costWrite(page, 'upsert', content, 'id')
  assert.equal(value.content.unit_cost, content.unit_cost)
  assert.equal(value.expected_version, 2)
  assert.equal(value.expected_revision, 7)
  assert.equal(value.content.evidence_at, '2026-10-01T00:00:00.000Z')
  assert.equal('content' in costWrite(page, 'revoke', content, 'id'), false)
  assert.throws(() =>
    costWrite({ ...page, source_current: false }, 'upsert', content, 'id'),
  )
  for (const change of [
    { confirmed: false },
    { unit_cost: '-1' },
    { unit_cost: '1.12345' },
    { evidence_ref: ' ' },
  ])
    assert.throws(() =>
      costWrite(page, 'upsert', { ...content, ...change }, 'id'),
    )
})

test('analysis and AI links preserve the same scope and reject invalid identity/channel', () => {
  const base = {
    ...scope,
    timezone: 'Asia/Shanghai',
    currency: 'USD',
    data_identity: 'user_import',
    channel: 'generic',
    intent: 'summary',
  }
  const query = {
    identity: 'synthetic',
    channel: 'amazon',
    min_quantity: '5',
    max_margin_percent: '12.50',
    currency: 'CNY',
    intent: 'low_margin',
  }
  const result = linkedAnalysisScope(base, query)
  assert.equal(result.data_identity, 'synthetic')
  assert.equal(result.channel, 'amazon')
  assert.equal(result.min_quantity, 5)
  assert.equal(result.max_margin_percent, '12.50')
  assert.equal(base.channel, 'generic')
  for (const bad of [
    { identity: 'bad' },
    { channel: 'bad' },
    { timezone: 'not/a/timezone' },
    { currency: 'BAD' },
  ])
    assert.throws(() => linkedAnalysisScope(base, bad))
})
