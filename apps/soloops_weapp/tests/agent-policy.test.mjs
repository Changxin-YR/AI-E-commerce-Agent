import test from 'node:test'
import assert from 'node:assert/strict'
import {
  agentActions,
  prepareAgentInput,
  reviewedRecords,
} from '../src/services/agent-policy.ts'

test('agent gates approvals by current evidence and recovery by unreserved budget', () => {
  assert.ok(
    agentActions({
      status: 'waiting_approval',
      source_status: 'current',
      reserved_usd: '0',
    }).includes('approve'),
  )
  assert.ok(
    !agentActions({
      status: 'waiting_approval',
      source_status: 'stale',
      reserved_usd: '0',
    }).includes('approve'),
  )
  assert.ok(
    !agentActions({
      status: 'paused',
      source_status: 'current',
      reserved_usd: '0.001',
    }).includes('resume'),
  )
  assert.ok(
    agentActions({
      status: 'paused',
      source_status: 'current',
      reserved_usd: '0',
    }).includes('resume'),
  )
  for (const status of ['result_unknown', 'succeeded', 'new_state'])
    assert.deepEqual(
      agentActions({ status, source_status: 'current', reserved_usd: '0' }),
      [],
    )
})
test('B1 keeps first verified record when second approval is rejected', () => {
  const run = {
    template: 'margin_review',
    result: { record_type: 'listing', record_id: 999 },
    steps: [
      {
        node: 'verify',
        status: 'completed',
        output: { record_type: 'analysis', record_id: 21 },
      },
      { node: 'listing_draft', status: 'rejected', output: null },
    ],
  }
  assert.deepEqual(reviewedRecords(run), [
    { kind: 'analysis', id: 21, path: '/analytics', key: 'analysis' },
  ])
  run.steps.push({
    node: 'verify',
    status: 'completed',
    output: { record_type: 'listing', record_id: 32 },
  })
  assert.deepEqual(
    reviewedRecords(run).map((r) => r.id),
    [21, 32],
  )
})
test('B1 uses an exact seven-day UTC window without mutating form', () => {
  const form = {
    template: 'margin_review',
    scope: {
      start_at: '2026-09-01T00:00:00+08:00',
      end_at: '2026-10-11T18:30:00+08:00',
    },
    budget: { max_steps: 12, max_seconds: 120, max_cost_usd: '0.000001' },
  }
  const result = prepareAgentInput(form)
  assert.equal(
    Date.parse(result.scope.end_at) - Date.parse(result.scope.start_at),
    7 * 86400000,
  )
  assert.equal(form.scope.start_at, '2026-09-01T00:00:00+08:00')
  assert.throws(
    () =>
      prepareAgentInput({
        ...form,
        budget: { ...form.budget, max_cost_usd: '1e2' },
      }),
    /预算/,
  )
  assert.throws(
    () =>
      prepareAgentInput({
        ...form,
        scope: { ...form.scope, end_at: 'invalid' },
      }),
    /起止时间/,
  )
})
test('unknown source states never expose mutation actions or invalid record links', () => {
  assert.deepEqual(
    agentActions({
      status: 'ready',
      source_status: 'cleared',
      reserved_usd: '0',
    }),
    [],
  )
  assert.deepEqual(
    reviewedRecords({
      template: 'daily',
      steps: [],
      result: { record_type: 'untrusted', record_id: 1 },
    }),
    [],
  )
})
