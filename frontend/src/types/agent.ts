import type { OperationScope } from './operations'
import type { SourceReference } from './analytics'
import type { ListingContent, ProductFacts } from './listings'

export type AgentTemplate =
  'daily' | 'analysis' | 'listing' | 'support' | 'natural' | 'question' | 'listing_model'
export type AgentAction =
  'advance' | 'pause' | 'resume' | 'cancel' | 'approve' | 'reject' | 'use_authorization'
export interface AgentBudget {
  max_steps: number
  max_seconds: number
  max_cost_usd: string
}
export interface AgentInput {
  authorization_id?: number | null
  request_id: string
  template: AgentTemplate
  scope: OperationScope
  goal: string
  product_id: number | null
  message_id: number | null
  allow_model: boolean
  allow_analysis_data?: boolean
  allow_listing_data?: boolean
  expected_product_source_row_id?: number | null
  budget: AgentBudget
}
export interface AgentStep {
  id: number
  node: string
  skill: string
  skill_version: string
  status: string
  reason: string
  next_node: string
  input: Record<string, unknown> | null
  output: Record<string, unknown> | null
  duration_ms: number
  created_at: string
}
export interface AgentRun {
  authorization_id?: number | null
  id: number
  shop_id: number
  template: string
  status: string
  reason: string
  version: number
  next_node: string
  source_status: string
  source_revision: number
  input: AgentInput | null
  result: Record<string, unknown> | null
  steps_used: number
  elapsed_ms: number
  budget: AgentBudget
  spent_usd: string
  reserved_usd: string
  model_status: string
  created_at: string
  steps: AgentStep[]
  external_status: 'not_submitted'
}
export interface SkillDefinition {
  name: string
  version: string
  purpose: string
  input_schema: Record<string, unknown>
  input_sources: string[]
  output_schema: Record<string, unknown>
  permissions: string[]
  tools: string[]
  read_scope: string
  write_scope: string
  risk: string
  side_effects: boolean
  preconditions: string[]
  idempotency: string
  max_attempts: number
  failure_policy: string
  confirmation: string
}
export interface ModelStatus {
  status: string
  provider: string
  model: string
  reason: string
  input_usd_per_million?: string | null
  output_usd_per_million?: string | null
  cost_note?: string
}
export interface AnalysisExplanation {
  observations: { fact_id: string; text: string; sku: string | null }[]
  checks: { id: string; text: string }[]
  next_action: 'finish' | 'offer_todo'
  composition: string
  sku_fact_limit: number
}
export interface ListingCandidate {
  preparation: { product: ProductFacts; active_id: number | null; before: ListingContent | null }
  candidate: ListingContent
  engine: string
}
export const agentLabels: Record<string, string> = {
  listing_model: 'AI Listing 候选',
  compose_listing: '组织商品事实文案',
  listing_candidate: '保存模型 Listing 候选',
  question: 'AI 经营问数',
  question_plan: '理解经营问题',
  explain_analysis: '组织事实解释',
  analysis_todo: '保存分析和核对待办',
  ready: '待执行',
  running: '模型调用中',
  waiting_approval: '等待审批',
  paused: '已暂停',
  cancelled: '已取消',
  rejected: '已拒绝',
  blocked: '已阻断',
  succeeded: '已完成',
  circuit_open: '已熔断',
  result_unknown: '模型结果 / 费用未确认',
  waiting_configuration: '等待模型配置',
  waiting_input: '等待补充数据',
  completed: '步骤完成',
  failed: '步骤失败',
  discarded: '结果未采纳',
  data_check: '检查数据',
  metrics: '销售与已知毛利',
  propose_tasks: '保存异常候选',
  product_context: '读取商品事实',
  listing_draft: '保存 Listing 模板草稿',
  message_context: '读取客户消息',
  support_draft: '保存人工接管草稿',
  verify: '回读核验',
  plan: '识别目标',
  end: '结束',
  daily: '今日运营流程',
  analysis: '经营分析',
  listing: 'Listing 草稿',
  support: '客服草稿',
  natural: '自然语言目标',
  not_used: '本地确定性流程',
  not_configured: '模型待配置',
  openai_responses: 'OpenAI Responses',
  dashscope_chat: '阿里云百炼（北京）',
  test_double: '测试替身',
}
export const agentReasons: Record<string, string> = {
  listing_consent_required: '请核对目标商品与参数并同意发送到模型，然后新建任务。',
  listing_needs_review: '模型建议先人工核对目标或商品事实。补充来源后可新建任务。',
  listing_candidate_ready: '已生成事实候选，请核对前后差异后批准保存草稿。',
  invalid_product_facts: '商品参数须包含 1—100 行完整事实，请整理来源后重新导入。',
  analysis_consent_required: '需要同意发送问题和匿名聚合事实；请确认数据范围后新建任务。',
  unsupported_analysis:
    '此问题超出当前范围或能力。支持销售汇总、购买数量前五与已知毛利筛选；请调整问题或表单范围。',
  invalid_model_output:
    '模型输出未通过事实与结构校验，已阻断。已知费用仍记录，原始统计可继续查看。',
  analysis_review_suggested:
    '模型建议核对以下事实。批准后保存分析及一个核对待办，可在经营分析页完成或重开。',
  analysis_explained: '证据解释已保存到本次执行记录。',
  model_input_too_large: '模型输入超过限制，请缩小统计范围。',
  use_authorization: '已绑定匹配的 R1 预授权；执行前将再次核对。',
  preauthorization_ready: '候选符合 R1 预授权，准备保存。',
  preauthorization_used: '已使用 R1 预授权保存候选并记录一次消耗。',
  authorization_unavailable: '预授权已失效或范围不符；请重新审阅，单次批准或使用新的有效授权。',
  missing_goal: '请填写运营目标后新建任务。',
  invalid_skill_output: '技能输出未通过类型校验，请人工核对。',
  no_findings: '本次检查未产生异常候选。缺数据的模块仍为未检查。',
  findings_found: '已找到需要核对的来源异常，请审阅后批准保存候选。',
  step_budget: '已达到执行步数上限。已完成步骤保留，可提高预算后恢复。',
  time_budget: '已达到累计执行时长上限。等待审批和暂停的时间不计入。',
  cost_budget: '费用余额不足或已触及上限。可调整美元预算后恢复。',
  not_configured: '请由部署者配置模型、凭据与费率；可使用本地固定流程。',
  model_consent_required: '尚未同意将目标文本发送至模型，请调整选项后新建任务。',
  source_changed: '来源已变化或过期，请用当前数据新建任务。',
  source_cleared: '依赖来源已清除，任务内容和步骤正文已擦除。',
  missing_product_facts: '商品缺少参数，请补充导入后新建任务。',
  missing_object: '缺少商品或消息，请选择对象后新建任务。',
  policy_denied: '目标涉及不允许的操作或不支持的范围，任务已停止。',
  invalid_skill: '技能元数据缺失或无效，任务已停止。',
  skill_policy_denied: '技能的权限声明不符合内置规则，任务已停止。',
  read_circuit_open: '读取失败已达到上限，请核对服务状态；此任务不会自动重试。',
  temporary_read_failure: '读取遇临时故障，将在最多三次尝试内重试。',
  model_result_unknown:
    '模型结果或费用无法核实。保留费用预留，请人工核对供应商记录；不会自动重发。',
  model_lease_expired: '模型调用中断或超时。费用预留仍保留，请人工核对后再新建任务。',
  scope_mismatch: '对象不属于所选数据身份或渠道，请重新选择。',
  conflict: '业务记录已变化，请核对业务页面后新建任务。',
}

export function sourcesIn(value: unknown): SourceReference[] {
  const found = new Map<number, SourceReference>()
  function walk(item: unknown): void {
    if (!item || typeof item !== 'object') return
    if (Array.isArray(item)) {
      item.forEach(walk)
      return
    }
    const record = item as Record<string, unknown>
    if (
      typeof record.row_id === 'number' &&
      typeof record.batch_id === 'number' &&
      typeof record.row_number === 'number' &&
      typeof record.filename === 'string'
    ) {
      found.set(record.row_id, record as unknown as SourceReference)
    }
    Object.values(record).forEach(walk)
  }
  walk(value)
  return [...found.values()]
}
