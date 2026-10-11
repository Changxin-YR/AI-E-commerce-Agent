import type { ListingVersion } from './listing-types'
export function listingActions(
  item: ListingVersion,
  dirty: boolean,
  confirmed: boolean,
) {
  const visible = Boolean(item.snapshot)
  const current = item.source_status === 'current'
  const known = ['draft', 'approved', 'rejected', 'superseded'].includes(
    item.status,
  )
  return {
    revise: visible && current && known,
    approve:
      visible &&
      current &&
      item.status === 'draft' &&
      !dirty &&
      confirmed &&
      item.snapshot!.blockers.length === 0,
    reject:
      visible &&
      ['current', 'stale'].includes(item.source_status) &&
      item.status === 'draft' &&
      !dirty,
    deliver: visible && current && item.status === 'approved' && !dirty,
  }
}
