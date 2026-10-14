import { authApi } from '@/api/auth'
import type { Shop } from '@/types/identity'

/** Only the configured demo account receives sample defaults; explicit scope wins. */
export async function loadDemoScope(
  shops: Shop[],
  username: string | undefined,
  query: Record<string, unknown>,
): Promise<Record<string, string>> {
  const shop = shops.find((item) => item.code === 'demo-shop')
  if (!shop || !username || (query.shop !== undefined && String(query.shop) !== String(shop.id)))
    return {}
  try {
    const demo = await authApi.demo()
    if (!demo.enabled || username !== demo.username) return {}
    return {
      ...(query.shop === undefined ? { shop: String(shop.id) } : {}),
      ...(query.identity === undefined ? { identity: 'synthetic' } : {}),
      ...(query.channel === undefined ? { channel: 'generic' } : {}),
    }
  } catch {
    return {}
  }
}
