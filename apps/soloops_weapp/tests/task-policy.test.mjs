import test from 'node:test'
import assert from 'node:assert/strict'
import {
  taskActions,
  queryString,
  requestId,
} from '../src/services/task-policy.ts'
const snapshot = { title: 'Synthetic task' }
test('approval is restricted to current pending candidates', () => {
  assert.ok(
    taskActions({
      status: 'pending_approval',
      source_status: 'current',
      snapshot,
    }).includes('approve'),
  )
  assert.ok(
    !taskActions({
      status: 'open',
      source_status: 'current',
      snapshot,
    }).includes('approve'),
  )
  assert.ok(
    !taskActions({
      status: 'pending_approval',
      source_status: 'stale',
      snapshot,
    }).includes('approve'),
  )
})
test('stale tasks allow follow-up but cannot be marked complete', () => {
  const actions = taskActions({
    status: 'open',
    source_status: 'stale',
    snapshot,
  })
  assert.ok(actions.includes('record_evidence') && actions.includes('recheck'))
  assert.ok(!actions.includes('complete') && !actions.includes('edit'))
})
test('cleared and unknown states fail closed', () => {
  for (const source_status of ['cleared', 'future_status'])
    assert.deepEqual(
      taskActions({ status: 'open', source_status, snapshot }),
      [],
    )
  assert.deepEqual(
    taskActions({ status: 'unknown', source_status: 'current', snapshot }),
    [],
  )
  assert.deepEqual(
    taskActions({ status: 'open', source_status: 'current', snapshot: null }),
    [],
  )
})
test('completed check can be reopened and rechecked without implying resolution', () => {
  const actions = taskActions({
    status: 'completed',
    source_status: 'current',
    snapshot,
  })
  assert.ok(actions.includes('reopen') && actions.includes('recheck'))
  assert.ok(!actions.includes('complete'))
})
test('query values remain encoded and request ids match UUIDv4', () => {
  assert.equal(
    queryString({ cursor: 'a=b+/', shop: 3, missing: undefined, empty: '' }),
    'cursor=a%3Db%2B%2F&shop=3',
  )
  assert.match(
    requestId(),
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
  )
})
