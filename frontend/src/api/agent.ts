import { request } from './client'
import type {
  AgentAction,
  AgentBudget,
  AgentInput,
  AgentRun,
  ModelStatus,
  SkillDefinition,
} from '@/types/agent'
const root = (shop: number) => `/shops/${shop}/agent`
export const agentApi = {
  skills: (shop: number) => request<SkillDefinition[]>(`${root(shop)}/skills`),
  model: (shop: number) => request<ModelStatus>(`${root(shop)}/model`),
  runs: (shop: number) => request<AgentRun[]>(`${root(shop)}/runs`),
  get: (shop: number, id: number) => request<AgentRun>(`${root(shop)}/runs/${id}`),
  start: (shop: number, data: AgentInput) =>
    request<AgentRun>(`${root(shop)}/runs`, { method: 'POST', body: JSON.stringify(data) }),
  act: (run: AgentRun, action: AgentAction, budget?: AgentBudget, authorizationId?: number) =>
    request<AgentRun>(`${root(run.shop_id)}/runs/${run.id}`, {
      method: 'POST',
      body: JSON.stringify({
        version: run.version,
        action,
        budget,
        authorization_id: authorizationId,
      }),
    }),
}
