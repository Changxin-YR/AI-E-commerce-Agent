import { request } from './client'
import type {
  OperationContext,
  OperationRun,
  OperationScope,
  OperationTask,
  TaskAction,
  TaskEvidenceInput,
} from '@/types/operations'

export const operationsApi = {
  preview: (shop: number, scope: OperationScope) =>
    request<OperationContext>(`/shops/${shop}/operations/preview`, {
      method: 'POST',
      body: JSON.stringify(scope),
    }),
  run: (shop: number, scope: OperationScope, requestId: string) =>
    request<OperationRun>(`/shops/${shop}/operations/runs`, {
      method: 'POST',
      body: JSON.stringify({ scope, request_id: requestId }),
    }),
  runs: (shop: number, identity: string, channel: string) =>
    request<OperationRun[]>(
      `/shops/${shop}/operations/runs?data_identity=${identity}&channel=${channel}`,
    ),
  getRun: (shop: number, id: number) =>
    request<OperationRun>(`/shops/${shop}/operations/runs/${id}`),
  tasks: (shop: number, identity: string, channel: string, offset: number) =>
    request<{ items: OperationTask[]; has_more: boolean }>(
      `/shops/${shop}/operations/tasks?data_identity=${identity}&channel=${channel}&offset=${offset}`,
    ),
  getTask: (shop: number, id: number) =>
    request<OperationTask>(`/shops/${shop}/operations/tasks/${id}`),
  change: (
    shop: number,
    id: number,
    version: number,
    action: TaskAction,
    note: string,
    due_at: string | null,
    evidence?: TaskEvidenceInput,
  ) =>
    request<OperationTask>(`/shops/${shop}/operations/tasks/${id}`, {
      method: 'POST',
      body: JSON.stringify({ version, action, note, due_at, evidence }),
    }),
}
