import { expect, it } from 'vitest'
import { inferImportedScope } from '@/composables/importedScope'
import type { BatchSummary } from '@/types/imports'

function batch(
  identity: BatchSummary['data_identity'] = 'synthetic',
  channel: BatchSummary['source_channel'] = 'amazon',
  overrides: Partial<BatchSummary> = {},
): BatchSummary {
  return {
    shop_id: 3,
    data_identity: identity,
    source_channel: channel,
    status: 'committed',
    ...overrides,
  } as BatchSummary
}

it('fills a missing scope only from a single committed source and preserves its identity', () => {
  expect(
    inferImportedScope([batch(), batch('synthetic', 'amazon', { kind: 'orders' })], 3, {}),
  ).toEqual({ identity: 'synthetic', channel: 'amazon' })
})

it('ignores other shops and uncommitted, revoked, expired or cleared data', () => {
  expect(
    inferImportedScope(
      [
        batch('user_import', 'generic', { shop_id: 9 }),
        ...(['draft', 'preview', 'revoked', 'expired', 'cleared'] as const).map((status) =>
          batch('user_import', 'generic', { status }),
        ),
        batch(),
      ],
      3,
      {},
    ),
  ).toEqual({ identity: 'synthetic', channel: 'amazon' })
})

it('keeps the existing default when committed sources are missing or ambiguous', () => {
  expect(inferImportedScope([], 3, {})).toEqual({})
  expect(inferImportedScope([batch(), batch('user_import')], 3, {})).toEqual({})
  expect(inferImportedScope([batch(), batch('synthetic', 'shopify')], 3, {})).toEqual({})
})

it('uses explicit identity to resolve only the missing channel without switching identities', () => {
  const batches = [batch(), batch('user_import', 'shopify')]
  expect(inferImportedScope(batches, 3, { identity: 'user_import' })).toEqual({
    channel: 'shopify',
  })
  expect(inferImportedScope([batch()], 3, { identity: 'user_import' })).toEqual({})
})

it('keeps an explicit channel and complete scope unchanged', () => {
  expect(
    inferImportedScope([batch(), batch('user_import', 'shopify')], 3, { channel: 'amazon' }),
  ).toEqual({ identity: 'synthetic' })
  expect(inferImportedScope([batch()], 3, { identity: 'user_import', channel: 'generic' })).toEqual(
    {},
  )
})
