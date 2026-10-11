import type { AgentAction, AgentRun, AgentInput } from './agent-types'

export function agentActions(
  run: Pick<AgentRun, 'status' | 'source_status' | 'reserved_usd'>,
): AgentAction[] {
  const actions: AgentAction[] = []
  if (!['current', 'stale'].includes(run.source_status)) return actions
  const current = run.source_status === 'current'
  if (run.status === 'ready' && current) actions.push('advance')
  if (['ready', 'running'].includes(run.status)) actions.push('pause')
  if (run.status === 'waiting_approval') {
    if (current) actions.push('approve')
    actions.push('reject')
  }
  if (
    ['paused', 'waiting_configuration'].includes(run.status) &&
    current &&
    Number(run.reserved_usd) === 0
  )
    actions.push('resume')
  if (
    [
      'ready',
      'running',
      'paused',
      'waiting_configuration',
      'waiting_approval',
      'waiting_input',
    ].includes(run.status)
  )
    actions.push('cancel')
  return actions
}

export function reviewedRecords(
  run: Pick<AgentRun, 'template' | 'steps' | 'result'>,
) {
  const values =
    run.template === 'margin_review'
      ? run.steps
          .filter(
            (step) => step.node === 'verify' && step.status === 'completed',
          )
          .map((step) => step.output)
      : [run.result]
  const routes: Record<string, [string, string]> = {
    operations: ['/', 'run'],
    listing: ['/listings', 'listing'],
    support: ['/support', 'draft'],
    analysis: ['/analytics', 'analysis'],
  }
  return values.flatMap((value) => {
    const kind = String(value?.record_type)
    const id = Number(value?.record_id)
    const route = routes[kind]
    return route && Number.isSafeInteger(id) && id > 0
      ? [{ kind, id, path: route[0], key: route[1] }]
      : []
  })
}

export function prepareAgentInput(input: AgentInput): AgentInput {
  const value = JSON.parse(JSON.stringify(input)) as AgentInput
  const end = Date.parse(value.scope.end_at)
  const start = Date.parse(value.scope.start_at)
  if (!Number.isFinite(end) || !Number.isFinite(start) || start >= end)
    throw new Error('请填写有效的起止时间（含时区）。')
  if (value.template === 'margin_review')
    value.scope.start_at = new Date(end - 7 * 86400000).toISOString()
  const budget = value.budget
  if (
    !Number.isInteger(budget.max_steps) ||
    budget.max_steps < 1 ||
    budget.max_steps > 100 ||
    !Number.isInteger(budget.max_seconds) ||
    budget.max_seconds < 1 ||
    budget.max_seconds > 3600 ||
    !/^\d+(\.\d{1,6})?$/.test(budget.max_cost_usd) ||
    Number(budget.max_cost_usd) > 10
  )
    throw new Error('预算须为 1–100 步、1–3600 秒、0–10 USD（最多6位小数）。')
  return value
}
