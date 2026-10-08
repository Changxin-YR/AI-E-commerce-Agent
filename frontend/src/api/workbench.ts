import { request } from './client'
import type { WorkPage } from '@/types/workbench'

export const workbenchApi = {
  list: (filters: Record<string, string>, cursor?: string) => {
    const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => !!value))
    if (cursor) params.set('cursor', cursor)
    return request<WorkPage>(`/workbench?${params}`)
  },
}
