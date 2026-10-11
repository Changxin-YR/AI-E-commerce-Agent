# SoloOps R2 跨端 UI 行为契约

本页由 `contracts/ui-contract.json` 生成；修改 JSON 后运行 `python scripts/validate_ui_contract.py --write-doc`，CI 检查两者一致。

现有 R2 页面/API 的静态契约；不构成移动业务实现或跨端 E2E 证据。

## 五个移动主入口

- 首页：今日 AI 运营、经营分析、跨店经营总览
- 待办：今日 AI 运营、受控 Agent
- AI：受控 Agent、B1 低毛利受控复核、AI Listing
- 客服：AI 客服
- 我的：店铺与经营资料、文件导入、库存快照、新品利润测算、费用与映射、渠道账单、订单账单核对、结算与回款、经营规则与授权、受控测试外发、定时运营、商品质量、商品本地修订、登录

## 必须保留的显示语义

- `not_submitted`：仅本地结果，未向外部平台提交；不代表已发布或已发送。
- `seller_reported`：卖家自报操作证据；不等于渠道确认或买家收件。
- `stale`：来源已变化或过期，须重新核对；历史结果仍保留原口径。
- `candidate`：AI 生成候选仅供审阅，不代表操作已经执行。
- `approval`：审批通过仅授予当前节点执行许可，不代表外部操作成功。
- `completed_check`：事项 completed 表示已完成核对；异常解除需新有效来源复检支持。
- `money`：金额使用服务端 Decimal 字符串与币种；客户端不以浮点重新汇总；缺费用不称净利润。
- `time`：UTC 持久时间按明确 IANA 时区显示，统计区间为 [start,end)。
- `scheduler`：API 可达、enabled 配置和历史周期均不能单独证明调度进程正在运行。
- `unknown`：未知状态保留原值并提示重新核对，禁止推断成功或显示可执行危险动作。

## 页面、字段、API 与操作

19 个原业务路由另加登录映射；B1 复用 `/agent`。Flutter/Taro 业务路由均尚未实现。下列字段和请求签名来自现有 OpenAPI；条件还须服从实际服务层。

### r2.home · 今日 AI 运营

Web：`/`；SO-002, SO-004, SO-005, SO-068。

预览后保存候选，逐项审批；complete 仅完成核对，新来源 recheck 才能支持 resolved。

显示字段：`WorkPage.items`、`WorkPage.recent_runs`、`WorkPage.counts`、`WorkPage.view_counts`、`WorkPage.read_at`、`TaskOutput.id`、`TaskOutput.version`、`TaskOutput.status`、`TaskOutput.source_status`、`TaskOutput.business_state`。

状态字典：task、business、source、external、provenance。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `POST /api/shops/{shop_id}/operations/preview` | OperationScope-Input | session, scope, web_origin, risk, readback, csrf, version, source, seller_evidence |
| `POST /api/shops/{shop_id}/operations/runs` | RunInput | session, scope, web_origin, risk, readback, csrf, version, source, seller_evidence |
| `GET /api/shops/{shop_id}/operations/runs` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, seller_evidence |
| `GET /api/shops/{shop_id}/operations/runs/{run_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, seller_evidence |
| `GET /api/shops/{shop_id}/operations/tasks` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, seller_evidence |
| `GET /api/shops/{shop_id}/operations/tasks/{task_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, seller_evidence |
| `POST /api/shops/{shop_id}/operations/tasks/{task_id}` | TaskInput；approve, reject, ignore, defer, complete, reopen, edit, record_evidence, wait_source, recheck | session, scope, web_origin, risk, readback, csrf, version, source, seller_evidence |
| `GET /api/workbench` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, seller_evidence |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.settings · 店铺与经营资料

Web：`/settings`；SO-001, SO-074。

读取既有记录、查看依据并按服务端允许的操作维护；原页面来源、版本和审批规则保持。

显示字段：`ProfileOutput.display_name`、`ProfileOutput.currency`、`ProfileOutput.timezone`、`ProfileOutput.version`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `GET /api/profile` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `PUT /api/profile` | ProfileInput | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/onboarding` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops` | ShopInput | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.imports · 文件导入

Web：`/imports`；SO-001, SO-008, SO-027, SO-041。

现有 Web 原始 bytes 上传；Taro multipart 薄适配是后续阶段。大文件移交已有 Web 有界导入流程。

显示字段：`BatchOutput.id`、`BatchOutput.shop_id`、`BatchOutput.data_identity`、`BatchOutput.status`、`BatchOutput.version`、`BatchOutput.total_rows`、`BatchOutput.error_rows`、`BatchOutput.mapping`、`BatchOutput.required_reviews`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `GET /api/imports/catalog` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, file_boundary |
| `GET /api/imports/templates/{kind}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, file_boundary |
| `GET /api/imports/mappings` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, file_boundary |
| `POST /api/imports/mappings` | MappingTemplateInput | session, scope, web_origin, risk, readback, csrf, version, file_boundary |
| `POST /api/shops/{shop_id}/imports` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, web_origin, risk, readback, csrf, version, file_boundary |
| `GET /api/shops/{shop_id}/imports` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, file_boundary |
| `GET /api/imports/{batch_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, file_boundary |
| `POST /api/imports/{batch_id}/preview` | PreviewInput | session, scope, web_origin, risk, readback, csrf, version, file_boundary |
| `POST /api/imports/{batch_id}/commit` | CommitInput | session, scope, web_origin, risk, readback, csrf, version, file_boundary |
| `POST /api/imports/{batch_id}/revoke` | VersionInput | session, scope, web_origin, risk, readback, csrf, version, file_boundary |
| `POST /api/imports/{batch_id}/clear` | VersionInput | session, scope, web_origin, risk, readback, csrf, version, file_boundary |
| `GET /api/imports/{batch_id}/errors.csv` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, file_boundary |
| `POST /api/shops/{shop_id}/import-groups` | GroupInput | session, scope, web_origin, risk, readback, csrf, version, file_boundary |
| `GET /api/shops/{shop_id}/import-groups` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, file_boundary |
| `GET /api/import-groups/{group_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, file_boundary |
| `POST /api/import-groups/{group_id}/revoke` | VersionInput | session, scope, web_origin, risk, readback, csrf, version, file_boundary |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.analytics · 经营分析

Web：`/analytics`；SO-052, SO-053, SO-057。

保留销售、成本口径、费用缺口、原始行引用及旧快照；卖家历史成本依据另存版本，重算生成新结果。

显示字段：`AnalysisResult.scope`、`AnalysisResult.source_revision`、`AnalysisResult.formula`、`AnalysisResult.cost_basis`、`AnalysisResult.fee_gaps`、`AnalysisResult.summary`、`AnalysisResult.lines`、`AnalysisResult.ranking_available`。

状态字典：analysis。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `GET /api/shops/{shop_id}/analytics/order-costs/{row_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/analytics/order-costs/{row_id}` | CostWrite；upsert, revoke | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/analytics/revision` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops/{shop_id}/analytics/saved/{analysis_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/analytics/calculate` | AnalysisInput-Input | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/analytics/ask` | QuestionInput | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/analytics/saved` | SaveInput | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/analytics/saved` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/analytics/saved/{analysis_id}/todo` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/analytics/sources/{row_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/analytics/saved/{analysis_id}/todo/action` | TodoAction；complete, reopen | session, scope, web_origin, risk, readback, csrf, version |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.listings · AI Listing

Web：`/listings`；SO-018, SO-067。

生成/修订候选 → 当前版本事实确认 → 本地批准 → GET delivery 校验后复制/CSV。

显示字段：`ListingOutput.id`、`ListingOutput.shop_id`、`ListingOutput.number`、`ListingOutput.version`、`ListingOutput.status`、`ListingOutput.source_status`、`ListingOutput.snapshot`、`ListingOutput.external_status`、`ListingSnapshot.product`、`ListingSnapshot.before`、`ListingSnapshot.proposed`、`ListingSnapshot.missing`、`ListingSnapshot.blockers`、`ListingContent.title`、`ListingContent.description`、`ListingDelivery.plain_text`、`ListingDelivery.csv_text`、`ListingDelivery.filename`、`ListingDelivery.source`。

状态字典：listing、source、external。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `GET /api/shops/{shop_id}/listings/products` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, listing_review |
| `GET /api/shops/{shop_id}/listings/products/{product_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, listing_review |
| `GET /api/shops/{shop_id}/listings/versions` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, listing_review |
| `GET /api/shops/{shop_id}/listings/versions/{listing_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, listing_review |
| `POST /api/shops/{shop_id}/listings/generate` | GenerateInput | session, scope, web_origin, risk, readback, csrf, version, source, listing_review |
| `POST /api/shops/{shop_id}/listings/versions/{listing_id}/revise` | ReviseInput | session, scope, web_origin, risk, readback, csrf, version, source, listing_review |
| `POST /api/shops/{shop_id}/listings/versions/{listing_id}/decision` | DecisionInput；approve, reject | session, scope, web_origin, risk, readback, csrf, version, source, listing_review |
| `GET /api/shops/{shop_id}/listings/versions/{listing_id}/delivery` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, listing_review |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.support · AI 客服

Web：`/support`；SO-031, SO-032, SO-033。

订单/政策核验 → 多意图草稿 → 敏感人工接管 → 全文审阅 → 人工交付 → 自报证据；编辑使旧审阅失效。

显示字段：`ReplyOutput.id`、`ReplyOutput.version`、`ReplyOutput.status`、`ReplyOutput.source_status`、`ReplyOutput.snapshot`、`ReplyOutput.reviewed_version`、`ReplyOutput.reviewed_language`、`ReplyOutput.external_status`、`ReplySnapshot.message`、`ReplySnapshot.orders`、`ReplySnapshot.order_verified`、`ReplySnapshot.policies`、`ReplySnapshot.intents`、`ReplySnapshot.reasons`、`ReplySnapshot.handoff_summary`、`ReplySnapshot.reply`、`ReplySnapshot.model_facts`。

状态字典：support、source、external、provenance。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `GET /api/shops/{shop_id}/support/messages` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, support_review, seller_evidence |
| `GET /api/shops/{shop_id}/support/messages/{message_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, support_review, seller_evidence |
| `POST /api/shops/{shop_id}/support/messages/{message_id}/generate` | GenerateReply | session, scope, web_origin, risk, readback, csrf, version, source, support_review, seller_evidence |
| `GET /api/shops/{shop_id}/support/policies` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, support_review, seller_evidence |
| `POST /api/shops/{shop_id}/support/policies` | PolicyInput | session, scope, web_origin, risk, readback, csrf, version, source, support_review, seller_evidence |
| `POST /api/shops/{shop_id}/support/policies/{policy_id}/clear` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, web_origin, risk, readback, csrf, version, source, support_review, seller_evidence |
| `GET /api/shops/{shop_id}/support/drafts` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, support_review, seller_evidence |
| `GET /api/shops/{shop_id}/support/drafts/{draft_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, support_review, seller_evidence |
| `POST /api/shops/{shop_id}/support/drafts/{draft_id}/edit` | EditReply | session, scope, web_origin, risk, readback, csrf, version, source, support_review, seller_evidence |
| `POST /api/shops/{shop_id}/support/drafts/{draft_id}/action` | ReplyAction；handoff, archive, reopen | session, scope, web_origin, risk, readback, csrf, version, source, support_review, seller_evidence |
| `POST /api/shops/{shop_id}/support/drafts/{draft_id}/review` | ReviewReply | session, scope, web_origin, risk, readback, csrf, version, source, support_review, seller_evidence |
| `GET /api/shops/{shop_id}/support/drafts/{draft_id}/delivery` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, support_review, seller_evidence |
| `GET /api/shops/{shop_id}/support/drafts/{draft_id}/manual-actions` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, support_review, seller_evidence |
| `POST /api/shops/{shop_id}/support/drafts/{draft_id}/manual-actions` | RecordManualAction | session, scope, web_origin, risk, readback, csrf, version, source, support_review, seller_evidence |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.inventory · 库存快照

Web：`/inventory`；SO-041。

无库存快照显示未知或未检查，不能显示零库存。

显示字段：`InventoryOutput.shop_id`、`InventoryOutput.checked_at`、`InventoryOutput.scope`、`InventoryOutput.items`、`InventoryOutput.note`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `GET /api/shops/{shop_id}/inventory` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.agent · 受控 Agent

Web：`/agent`；SO-003, SO-060, SO-062, SO-067, SO-068。

模型候选与持久业务结果分开；费用未知不重发；刷新按 run ID 回读。

显示字段：`AgentOutput.id`、`AgentOutput.shop_id`、`AgentOutput.template`、`AgentOutput.status`、`AgentOutput.version`、`AgentOutput.next_node`、`AgentOutput.source_status`、`AgentOutput.steps`、`AgentOutput.budget`、`AgentOutput.result`、`AgentOutput.external_status`、`AgentOutput.reason`、`AgentOutput.spent_usd`、`AgentOutput.reserved_usd`、`AgentOutput.model_status`、`StepOutput.id`、`StepOutput.node`、`StepOutput.skill`、`StepOutput.status`、`StepOutput.reason`、`StepOutput.output`。

状态字典：agent、source、external。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `GET /api/shops/{shop_id}/agent/skills` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, budget |
| `GET /api/shops/{shop_id}/agent/model` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, budget |
| `POST /api/shops/{shop_id}/agent/runs` | StartAgent-Input | session, scope, web_origin, risk, readback, csrf, version, source, budget |
| `GET /api/shops/{shop_id}/agent/runs` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, budget |
| `GET /api/shops/{shop_id}/agent/runs/{run_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, budget |
| `POST /api/shops/{shop_id}/agent/runs/{run_id}` | AgentAction；advance, pause, resume, cancel, approve, reject, use_authorization | session, scope, web_origin, risk, readback, csrf, version, source, budget |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.profit · 新品利润测算

Web：`/profit`；SO-054。

读取既有记录、查看依据并按服务端允许的操作维护；原页面来源、版本和审批规则保持。

显示字段：`SavedStudyOutput.id`、`SavedStudyOutput.title`、`SavedStudyOutput.currency`、`SavedStudyOutput.data_identity`、`SavedStudyOutput.result`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `POST /api/shops/{shop_id}/profit/calculate` | StudyInput-Input | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/profit/saved` | SaveStudyInput | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/profit/saved` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops/{shop_id}/profit/saved/{study_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `DELETE /api/shops/{shop_id}/profit/saved/{study_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, web_origin, risk, readback, csrf, version |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.expenses · 费用与映射

Web：`/expenses`；SO-056。

读取既有记录、查看依据并按服务端允许的操作维护；原页面来源、版本和审批规则保持。

显示字段：`ExpenseSaved.id`、`ExpenseSaved.shop_id`、`ExpenseSaved.channel`、`ExpenseSaved.data_identity`、`ExpenseSaved.status`、`ExpenseSaved.version`、`ExpenseSaved.snapshot`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `POST /api/shops/{shop_id}/expenses` | ExpenseWrite | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/expenses` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops/{shop_id}/expenses/orders` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/expenses/summary` | ExpenseScope | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/expenses/{expense_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/expenses/{expense_id}` | ExpenseWrite | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/expenses/{expense_id}/{action}` | ExpenseControl | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/fee-rules/preview` | FeeRuleDraft | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/fee-rules` | FeeRuleWrite | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/fee-rules` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops/{shop_id}/fee-rules/{rule_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/fee-rules/{rule_id}/{action}` | ExpenseControl | session, scope, web_origin, risk, readback, csrf, version |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.statements · 渠道账单

Web：`/statements`；SO-055, SO-056。

读取既有记录、查看依据并按服务端允许的操作维护；原页面来源、版本和审批规则保持。

显示字段：`StatementReconciliation.scope`、`StatementReconciliation.source_revision`、`StatementReconciliation.totals`、`StatementReconciliation.comparisons`、`StatementReconciliation.checks`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `POST /api/shops/{shop_id}/statements/reconcile` | ExpenseScope | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/statement-reviews/preview` | ReviewDraft | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/statement-reviews` | ReviewWrite | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/statement-reviews` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops/{shop_id}/statement-reviews/{review_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops/{shop_id}/statement-reviews/{review_id}/current` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/statement-reviews/{review_id}/{action}` | ExpenseControl | session, scope, web_origin, risk, readback, csrf, version |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.order_reconciliation · 订单账单核对

Web：`/order-reconciliation`；SO-027, SO-055, SO-056。

读取既有记录、查看依据并按服务端允许的操作维护；原页面来源、版本和审批规则保持。

显示字段：`OrderReconciliation.scope`、`OrderReconciliation.coverage`、`OrderReconciliation.comparisons`、`OrderReconciliation.checks`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `POST /api/shops/{shop_id}/statements/orders/reconcile` | OrderReconciliationScope | session, scope, web_origin, risk, readback, csrf, version |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.settlements · 结算与回款

Web：`/settlements`；SO-055。

读取既有记录、查看依据并按服务端允许的操作维护；原页面来源、版本和审批规则保持。

显示字段：`SettlementSaved.id`、`SettlementSaved.shop_id`、`SettlementSaved.status`、`SettlementSaved.version`、`SettlementSaved.content_version`、`SettlementSaved.snapshot`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `POST /api/shops/{shop_id}/settlements/preview` | SettlementDraft | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/settlements` | SettlementWrite | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/settlements` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops/{shop_id}/settlements/{settlement_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops/{shop_id}/settlements/{settlement_id}/current` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/settlements/{settlement_id}/{action}` | ExpenseControl | session, scope, web_origin, risk, readback, csrf, version |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.rules · 经营规则与授权

Web：`/rules`；SO-066, SO-067。

读取既有记录、查看依据并按服务端允许的操作维护；原页面来源、版本和审批规则保持。

显示字段：`RuleRevision.version`、`RuleRevision.shop_id`、`RuleRevision.channel`、`RuleRevision.data_identity`、`RuleRevision.active`、`RuleRevision.values`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `POST /api/shops/{shop_id}/authorizations` | CreateAuthorization | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/authorizations` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops/{shop_id}/authorizations/{grant_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/authorizations/{grant_id}/revoke` | RevokeAuthorization | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/authorizations/{grant_id}/uses/{use_id}/revert` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/business-rules` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/business-rules` | RuleChange；save, revoke, reset, restore | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/business-rules/history` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops/{shop_id}/business-rules/{version}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.outbound · 受控测试外发

Web：`/outbound`；SO-031, SO-067。

原测试外发页面及审批保留映射，M0-A 不发邮件。accepted 只表示提供商接收，收件证据另记。

显示字段：`MailOutput.id`、`MailOutput.shop_id`、`MailOutput.status`、`MailOutput.source_status`、`MailOutput.version`、`MailOutput.recipient`、`MailOutput.approvals`、`MailOutput.receipt_id`、`MailOutput.provider_event`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `GET /api/shops/{shop_id}/outbound/channel` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, external, source |
| `POST /api/shops/{shop_id}/outbound/channel/connect` | ConfirmMail | session, scope, web_origin, risk, readback, csrf, version, external, source |
| `POST /api/shops/{shop_id}/outbound/channel/{channel_id}/verify` | VerifyMailbox | session, scope, web_origin, risk, readback, csrf, version, external, source |
| `POST /api/shops/{shop_id}/outbound/channel/{channel_id}/revoke` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, web_origin, risk, readback, csrf, version, external, source |
| `GET /api/shops/{shop_id}/outbound/messages` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, external, source |
| `POST /api/shops/{shop_id}/outbound/messages` | CreateMail | session, scope, web_origin, risk, readback, csrf, version, external, source |
| `GET /api/shops/{shop_id}/outbound/messages/{message_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, external, source |
| `PATCH /api/shops/{shop_id}/outbound/messages/{message_id}` | EditMail | session, scope, web_origin, risk, readback, csrf, version, external, source |
| `POST /api/shops/{shop_id}/outbound/messages/{message_id}/approve` | ApproveMail | session, scope, web_origin, risk, readback, csrf, version, external, source |
| `POST /api/shops/{shop_id}/outbound/messages/{message_id}/approvals/{approval_id}/revoke` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, web_origin, risk, readback, csrf, version, external, source |
| `POST /api/shops/{shop_id}/outbound/messages/{message_id}/reject` | MailVersion | session, scope, web_origin, risk, readback, csrf, version, external, source |
| `POST /api/shops/{shop_id}/outbound/messages/{message_id}/send` | SendMail | session, scope, web_origin, risk, readback, csrf, version, external, source |
| `POST /api/shops/{shop_id}/outbound/messages/{message_id}/reconcile` | ReconcileMail | session, scope, web_origin, risk, readback, csrf, version, external, source |
| `POST /api/shops/{shop_id}/outbound/messages/{message_id}/receipt` | ReceiptEvidence | session, scope, web_origin, risk, readback, csrf, version, external, source |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.overview · 跨店经营总览

Web：`/overview`；SO-002。

读取既有记录、查看依据并按服务端允许的操作维护；原页面来源、版本和审批规则保持。

显示字段：`OverviewSaved.id`、`OverviewSaved.status`、`OverviewSaved.created_at`、`OverviewSaved.scope`、`OverviewSaved.snapshot`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `POST /api/overview/calculate` | OverviewScope-Input | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/overview/reports` | OverviewSave | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/overview/reports` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/overview/reports/{report_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/overview/reports/{report_id}/clear` | OverviewClear | session, scope, web_origin, risk, readback, csrf, version |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.schedules · 定时运营

Web：`/schedules`；SO-006。

API 可达、enabled 配置和历史周期均不能单独证明调度进程正在运行。

显示字段：`ScheduleOutput.id`、`ScheduleOutput.shop_id`、`ScheduleOutput.status`、`ScheduleOutput.version`、`ScheduleOutput.config`、`ScheduleOutput.next_run_at`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `GET /api/shops/{shop_id}/schedules/status` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops/{shop_id}/schedules` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/schedules` | CreateSchedule | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/schedules/history` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/schedules/history/{item_id}/read` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/schedules/{schedule_id}` | ScheduleAction；pause, resume, revoke, edit | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/schedules/{schedule_id}/check` | ManualCheck | session, scope, web_origin, risk, readback, csrf, version |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.product_quality · 商品质量

Web：`/product-quality`；SO-014。

读取既有记录、查看依据并按服务端允许的操作维护；原页面来源、版本和审批规则保持。

显示字段：`QualitySaved.id`、`QualitySaved.shop_id`、`QualitySaved.status`、`QualitySaved.scope`、`QualitySaved.snapshot`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `POST /api/shops/{shop_id}/product-quality/preview` | QualityScope | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/product-quality/reports` | QualitySave | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/product-quality/reports` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops/{shop_id}/product-quality/reports/{report_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/product-quality/reports/{report_id}/clear` | QualityClear | session, scope, web_origin, risk, readback, csrf, version |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.product_edits · 商品本地修订

Web：`/product-edits`；SO-008, SO-014, SO-067。

读取既有记录、查看依据并按服务端允许的操作维护；原页面来源、版本和审批规则保持。

显示字段：`EditSaved.id`、`EditSaved.shop_id`、`EditSaved.version`、`EditSaved.status`、`EditSaved.snapshot`、`EditSaved.output_batch_id`、`EditSaved.current_count`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `POST /api/shops/{shop_id}/product-edits` | EditCreate | session, scope, web_origin, risk, readback, csrf, version |
| `GET /api/shops/{shop_id}/product-edits` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `GET /api/shops/{shop_id}/product-edits/{edit_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope |
| `POST /api/shops/{shop_id}/product-edits/{edit_id}/approve` | EditDecision | session, scope, web_origin, risk, readback, csrf, version |
| `POST /api/shops/{shop_id}/product-edits/{edit_id}/{action}` | EditControl | session, scope, web_origin, risk, readback, csrf, version |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.login · 登录

Web：`/login`；SO-074。

读取既有记录、查看依据并按服务端允许的操作维护；原页面来源、版本和审批规则保持。

显示字段：`SessionOutput.user_id`、`SessionOutput.username`。

状态字典：采用服务端原值及未知状态策略。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `POST /api/auth/login` | LoginInput | web_origin, risk, readback |
| `GET /api/auth/session` | 无 JSON 请求模型；按路由参数/原字节协议 | session |
| `POST /api/auth/logout` | 无 JSON 请求模型；按路由参数/原字节协议 | session, web_origin, risk, readback, csrf, version |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

### r2.b1 · B1 低毛利受控复核

Web：`/agent`；SO-003, SO-018, SO-053, SO-057, SO-067, SO-068。

template=margin_review；精确7天范围。缺证据允许停止；低毛利不自动等同内容缺陷；analysis_todo 与 listing_draft 两次审批，verify 回读真实 record_id。

显示字段：`AgentOutput.id`、`AgentOutput.shop_id`、`AgentOutput.template`、`AgentOutput.status`、`AgentOutput.version`、`AgentOutput.source_status`、`AgentOutput.next_node`、`AgentOutput.steps`、`AgentOutput.result`、`AgentOutput.budget`、`AgentOutput.external_status`、`AgentOutput.reason`、`AgentOutput.spent_usd`、`AgentOutput.reserved_usd`、`AgentOutput.model_status`、`StepOutput.id`、`StepOutput.node`、`StepOutput.skill`、`StepOutput.status`、`StepOutput.reason`、`StepOutput.output`。

状态字典：agent、source、external。

| API | 请求模型 / 动作值 | 前置条件 |
|---|---|---|
| `POST /api/shops/{shop_id}/agent/runs` | StartAgent-Input | session, scope, web_origin, risk, readback, csrf, version, source, budget, b1_two_nodes |
| `GET /api/shops/{shop_id}/agent/runs` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, budget, b1_two_nodes |
| `GET /api/shops/{shop_id}/agent/runs/{run_id}` | 无 JSON 请求模型；按路由参数/原字节协议 | session, scope, source, budget, b1_two_nodes |
| `POST /api/shops/{shop_id}/agent/runs/{run_id}` | AgentAction；advance, pause, resume, cancel, approve, reject, use_authorization | session, scope, web_origin, risk, readback, csrf, version, source, budget, b1_two_nodes |

空状态：没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。

## 状态字典

### source

- `current`：来源有效
- `stale`：来源已变化或过期，须重新核对；历史结果仍保留原口径。
- `cleared`：来源已清除

### external

- `not_submitted`：仅本地结果，未向外部平台提交；不代表已发布或已发送。

### provenance

- `seller_reported`：卖家自报操作证据；不等于渠道确认或买家收件。

### agent

- `ready`：ready
- `running`：running
- `waiting_approval`：waiting_approval
- `paused`：paused
- `cancelled`：cancelled
- `rejected`：rejected
- `blocked`：blocked
- `succeeded`：succeeded
- `circuit_open`：circuit_open
- `result_unknown`：result_unknown
- `waiting_configuration`：waiting_configuration
- `waiting_input`：waiting_input

### listing

- `draft`：待审批草稿
- `approved`：本地已批准
- `rejected`：已拒绝
- `superseded`：已被新版本替代

### support

- `draft`：待审阅草稿
- `human_review`：需要人工接管
- `archived`：已存档

### task

- `pending_approval`：待审批
- `open`：待处理
- `deferred`：已延期
- `completed`：已完成核对
- `ignored`：已忽略
- `rejected`：已拒绝

### business

- `pending_review`：pending_review
- `checked_pending`：checked_pending
- `evidence_recorded`：evidence_recorded
- `awaiting_source`：awaiting_source
- `resolved`：resolved
- `still_anomalous`：still_anomalous
- `ignored`：ignored
- `cleared`：cleared

### analysis

- `current`：当前依据
- `stale`：来源待核对
- `cleared`：来源已清除

## 前置条件字典

- `web_origin`：现有写请求必须 X-SoloOps-Client: web；若有 Origin 须命中允许列表。登录也受此限制。
- `session`：使用当前有效服务端会话；现有 Web Cookie，不把客户端来源头视为身份。
- `scope`：后端校验当前用户及店铺归属；切店使在途响应失效。
- `csrf`：当前已认证写请求需正确 X-CSRF-Token；来源头和可选 Origin 规则见 web_origin。移动认证尚未实现。
- `version`：提交服务端要求的 version / expected_version / 预览哈希；409 后回读，不覆盖新版本。
- `source`：核对来源时效、身份、币种、渠道和覆盖区间；stale/cleared 阻止批准或交付。
- `risk`：R0–R3 由服务端受控业务服务判定；R3 不可审批绕过。
- `budget`：Agent 受技能白名单、步数、时长、费用、授权范围和幂等键限制。
- `listing_review`：批准当前草稿前确认商品事实和差异；交付须为当前有效的已批准版本。
- `support_review`：敏感混合意图人工接管；交付前全文审阅、语言确认且 reviewed_version == version。
- `seller_evidence`：自报须有操作时间、凭据引用、确认和版本；不能产生平台成功回执。
- `b1_two_nodes`：分析存档与 Listing 候选分别审批；第二节点拒绝保留第一结果；核对独立内容证据。
- `external`：真实外发需新的明确授权、已验证通道与收件对象、全文批准和单次去重；M0-A 不调用。
- `readback`：写入中防重入；断线结果未知先按记录 ID / request_id 回读，不能自动重放副作用。
- `file_boundary`：沿用每片 2 MiB / 2000 行及导入组 40 MiB / 40000 行 / 20 片；小程序上传适配尚未开发。

## 错误处理

- `unauthenticated`：401：重新登录后只回读记录，不重放写入。
- `forbidden`：403：停止操作，核对权限/CSRF/来源。
- `not_found`：404：对象不可用，不泄露他店资源。
- `conflict`：409：回读当前版本及来源，重新审阅。
- `validation`：422：显示字段问题与修复入口。
- `network_unknown`：断线/超时：写结果未知，按 ID 回查后决策。
- `server_error`：显示服务端 request_id 与可执行恢复提示，不回显敏感正文。

## 核验边界

19 个业务路由、登录及 B1；核心四 MVP/B1 的状态、审批和人工交付语义人工对照源码。

动态按钮和服务层全部前置条件不能由静态扫描证明；未来各端需真实操作/回读测试。

当前校验只证明结构、路由覆盖、API/字段引用及必要语义存在；各端设备行为和真实业务状态一致性为 NOT_TESTED。
