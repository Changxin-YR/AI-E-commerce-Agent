import { importsApi } from '@/api/imports'
import type { BatchSummary } from '@/types/imports'

type ImportedScopeQuery = Partial<Record<'identity' | 'channel', string>>

export function inferImportedScope(
  batches: BatchSummary[],
  shopId: number,
  query: Record<string, unknown>,
): ImportedScopeQuery {
  if (query.identity !== undefined && query.channel !== undefined) return {}
  const sources = new Map<string, ImportedScopeQuery>()
  for (const batch of batches) {
    if (batch.shop_id !== shopId || batch.status !== 'committed') continue
    if (query.identity !== undefined && query.identity !== batch.data_identity) continue
    if (query.channel !== undefined && query.channel !== batch.source_channel) continue
    sources.set(`${batch.data_identity}:${batch.source_channel}`, {
      identity: batch.data_identity,
      channel: batch.source_channel,
    })
  }
  if (sources.size !== 1) return {}
  const source = [...sources.values()][0]!
  return {
    ...(query.identity === undefined ? { identity: source.identity } : {}),
    ...(query.channel === undefined ? { channel: source.channel } : {}),
  }
}

export async function loadImportedScope(
  shopId: number,
  query: Record<string, unknown>,
): Promise<ImportedScopeQuery> {
  if (!shopId || (query.identity !== undefined && query.channel !== undefined)) return {}
  try {
    return inferImportedScope(await importsApi.list(shopId), shopId, query)
  } catch {
    // Source discovery is optional; an unavailable history must not change the chosen scope.
    return {}
  }
}
