import test from 'node:test'
import assert from 'node:assert/strict'
import { replyActions, awareTimestamp } from '../src/services/support-policy.ts'

const draft = {
  status: 'human_review', source_status: 'current', version: 3,
  snapshot: { reply: 'Please contact support.' },
  reviewed_version: 3, reviewed_at: '2026-10-11T00:00:00Z', reviewed_language: 'en',
}
test('support delivery requires persisted text and matching version/language review', () => {
  assert.equal(replyActions(draft, false, 'en').deliver, true)
  assert.equal(replyActions(draft, true, 'en').deliver, false)
  assert.equal(replyActions(draft, false, 'zh').deliver, false)
  assert.equal(replyActions({ ...draft, version: 4 }, false, 'en').deliver, false)
  assert.equal(replyActions({ ...draft, snapshot: { reply: ' ' } }, false, 'en').review, false)
})
test('stale support records allow archive only; cleared and unknown states fail closed', () => {
  const stale = replyActions({ ...draft, source_status: 'stale' }, false, 'en')
  assert.equal(stale.archive, true)
  assert.equal(stale.deliver, false)
  assert.equal(stale.edit, false)
  for (const item of [{ ...draft, source_status: 'cleared', snapshot: null }, { ...draft, status: 'future' }])
    assert.ok(Object.values(replyActions(item, false, 'en')).every(value => !value))
})
test('archived replies must reopen to edit and current reviewed delivery remains available', () => {
  const archived = replyActions({ ...draft, status: 'archived' }, false, 'en')
  assert.equal(archived.edit, false)
  assert.equal(archived.reopen, true)
  assert.equal(archived.deliver, true)
})
test('evidence timestamps require explicit timezone and normalize to UTC', () => {
  assert.equal(awareTimestamp('2026-10-11T09:00:00+08:00'), '2026-10-11T01:00:00.000Z')
  assert.throws(() => awareTimestamp('2026-10-11T09:00:00'))
  assert.throws(() => awareTimestamp('invalidZ'))
})
