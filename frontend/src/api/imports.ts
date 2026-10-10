import { request } from './client'
import type {
  BatchSummary,
  Corrections,
  ImportBatch,
  ImportCatalog,
  MappingTemplate,
  ImportGroup,
  ImportManifest,
} from '@/types/imports'

export const importsApi = {
  groups: (shop: number, before?: number) =>
    request<ImportGroup[]>(`/shops/${shop}/import-groups${before ? `?before=${before}` : ''}`),
  group: (id: number) => request<ImportGroup>(`/import-groups/${id}`),
  createGroup: (
    shop: number,
    data: { options: Record<string, string>; manifest: ImportManifest },
  ) =>
    request<ImportGroup>(`/shops/${shop}/import-groups`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  revokeGroup: (id: number, version: number) =>
    request<ImportGroup>(`/import-groups/${id}/revoke`, {
      method: 'POST',
      body: JSON.stringify({ version }),
    }),
  catalog: () => request<ImportCatalog>('/imports/catalog'),
  mappings: () => request<MappingTemplate[]>('/imports/mappings'),
  saveMapping: (data: Omit<MappingTemplate, 'id'>) =>
    request<MappingTemplate>('/imports/mappings', { method: 'POST', body: JSON.stringify(data) }),
  list: (shopId: number) => request<BatchSummary[]>(`/shops/${shopId}/imports`),
  get: (id: number) => request<ImportBatch>(`/imports/${id}`),
  upload: (shopId: number, file: File, options: Record<string, string>) =>
    request<ImportBatch>(`/shops/${shopId}/imports?${new URLSearchParams(options)}`, {
      method: 'POST',
      body: file,
      headers: { 'Content-Type': 'application/octet-stream' },
    }),
  preview: (
    id: number,
    version: number,
    mapping: Record<string, string>,
    corrections: Corrections,
  ) =>
    request<ImportBatch>(`/imports/${id}/preview`, {
      method: 'POST',
      body: JSON.stringify({ version, mapping, corrections }),
    }),
  commit: (id: number, version: number, allowUpdates: boolean, reviewedFields: string[] = []) =>
    request<ImportBatch>(`/imports/${id}/commit`, {
      method: 'POST',
      body: JSON.stringify({
        version,
        allow_updates: allowUpdates,
        reviewed_fields: reviewedFields,
      }),
    }),
  withdraw: (id: number, version: number, action: 'revoke' | 'clear') =>
    request<ImportBatch>(`/imports/${id}/${action}`, {
      method: 'POST',
      body: JSON.stringify({ version }),
    }),
}
