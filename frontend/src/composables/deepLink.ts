import { nextTick } from 'vue'
import type { Shop } from '@/types/identity'

export function linkedId(value: unknown): number | undefined {
  if (value === undefined) return undefined
  if (
    typeof value !== 'string' ||
    !/^[1-9]\d*$/.test(value) ||
    !Number.isSafeInteger(Number(value))
  )
    throw new Error('记录链接无效，请返回工作台重新打开。')
  return Number(value)
}

export function linkedShop(shops: Shop[], value: unknown): number {
  const id = linkedId(value)
  if (id !== undefined && !shops.some((shop) => shop.id === id))
    throw new Error('链接中的店铺不存在或无权访问。')
  return id ?? shops[0]?.id ?? 0
}

export async function revealRecord(id: string): Promise<void> {
  await nextTick()
  document.getElementById(id)?.scrollIntoView({ block: 'start' })
}
