import test from 'node:test'
import assert from 'node:assert/strict'
import { listingActions } from '../src/services/listing-policy.ts'
import { safeFilename } from '../src/services/delivery-policy.ts'
const draft = {
  status: 'draft',
  source_status: 'current',
  snapshot: { blockers: [] },
}
test('Listing approval requires persisted clean content, facts consent and no blockers', () => {
  assert.equal(listingActions(draft, false, true).approve, true)
  assert.equal(listingActions(draft, true, true).approve, false)
  assert.equal(listingActions(draft, false, false).approve, false)
  assert.equal(
    listingActions(
      { ...draft, snapshot: { blockers: ['unsupported fact'] } },
      false,
      true,
    ).approve,
    false,
  )
})
test('stale drafts may be rejected, cleared and unknown records cannot be changed', () => {
  const stale = listingActions(
    { ...draft, source_status: 'stale' },
    false,
    true,
  )
  assert.equal(stale.reject, true)
  assert.equal(stale.approve, false)
  assert.equal(stale.revise, false)
  for (const item of [
    { ...draft, source_status: 'cleared', snapshot: null },
    { ...draft, status: 'future' },
  ])
    assert.ok(
      Object.values(listingActions(item, false, true)).every((value) => !value),
    )
})
test('delivery allows only clean current approved content; server rechecks active baseline', () => {
  assert.equal(
    listingActions({ ...draft, status: 'approved' }, false, false).deliver,
    true,
  )
  assert.equal(
    listingActions({ ...draft, status: 'approved' }, true, false).deliver,
    false,
  )
  assert.equal(
    listingActions({ ...draft, status: 'superseded' }, false, false).deliver,
    false,
  )
  assert.equal(
    listingActions(
      { ...draft, status: 'approved', source_status: 'stale' },
      false,
      false,
    ).deliver,
    false,
  )
})
test('share filenames discard path segments and control characters', () => {
  assert.equal(safeFilename('../../report.csv'), 'report.csv')
  assert.equal(safeFilename('C:\\secrets\\导出.csv'), '导出.csv')
  assert.equal(safeFilename('bad\nname.csv'), 'bad_name.csv')
})
