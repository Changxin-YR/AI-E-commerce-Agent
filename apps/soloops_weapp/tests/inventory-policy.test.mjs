import test from 'node:test'
import assert from 'node:assert/strict'
import {
  inventoryScope,
  inventoryTasks,
} from '../src/services/inventory-policy.ts'
test('inventory links preserve identity, channel, SKU and bounded freshness', () => {
  assert.deepEqual(
    inventoryScope({
      identity: 'synthetic',
      channel: 'amazon',
      sku: 'A&B',
      max_age_hours: '720',
    }),
    {
      data_identity: 'synthetic',
      channel: 'amazon',
      search: 'A&B',
      max_age_hours: 720,
      offset: 0,
    },
  )
  for (const query of [
    { identity: 'other' },
    { channel: 'bad' },
    { max_age_hours: '0' },
    { max_age_hours: '721' },
    { max_age_hours: '1.5' },
    { sku: 'x'.repeat(121) },
  ])
    assert.throws(() => inventoryScope(query))
})
test('inventory tasks match exact SKU and low-stock kind, excluding cleared evidence', () => {
  const tasks = [
    { id: 1, kind: 'low_inventory', snapshot: { object_label: 'A' } },
    { id: 2, kind: 'low_margin', snapshot: { object_label: 'A' } },
    { id: 3, kind: 'low_inventory', snapshot: null },
    { id: 4, kind: 'low_inventory', snapshot: { object_label: 'AA' } },
  ]
  assert.deepEqual(
    inventoryTasks(tasks, 'A').map((task) => task.id),
    [1],
  )
})
