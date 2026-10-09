# 功能实现矩阵

需求基线：SoloOps V1.0（2026-10-08）。P0 23 项、P1 26 项、P2 25 项。状态描述当前交付切片，不代表整个长期模块完成。

| SO | 模块 | 优先级 | P0 切片 / 后续范围 | 实现位置 | 测试证据 | 当前状态 |
|---|---|---|---|---|---|---|
| SO-001 | 个人卖家初始化与经营资料 | P0 | 经营资料、店铺、模板/映射/预览/错误行/批次 | backend/app/services/profile.py、imports.py；frontend/src/views/ImportsView.vue | tests/test_identity.py、test_imports.py；frontend/e2e/imports.spec.ts | 初始化、商品/订单/消息/库存及通用渠道账单导入、映射与来源清除合成数据本地通过；更多真实渠道模板后续扩展 |
| SO-002 | 跨店铺经营总览与运营日报 | P0 | 按店铺/登记平台/市场/日期/币种总览、日周月摘要与依据 | services/overview.py、overview_calculation.py；OverviewView.vue、OverviewShopCard.vue | test_overview.py；OverviewShopCard.spec.ts、overview.spec.ts | 跨店分币种销售/订单/退款/已知商品毛利与对比、当前库存/消息/未结待办回顾、持久摘要及依赖清除合成本地通过；实际净利润、营销及实时平台数据待后续 |
| SO-003 | 自然语言 AI 运营总控 | P0 | 受控目标理解、事实生成与审批任务 | services/agent.py、agent_model.py、analysis_explanation.py、listing_composition.py、support_composition.py；AgentView.vue | test_agent.py、test_analysis_model.py、test_listing_model.py、test_support_model.py；模型业务 E2E | 路由、问数、Listing 和客服模型协议与审批回读已用替身通过；客服发送绑定消息/政策版本与人工订单核验，强制敏感接管；百炼真实合成路由与 Listing 已通过；运营聚合概览与审批回读已用替身通过；四条 MVP 真实模型质量仍待独立验证 |
| SO-004 | 一键今日运营 | P0 | 已导入数据巡检与真实内部动作 | services/agent.py、agent_skills.py、operations.py、operation_explanation.py；AgentView.vue | test_agent.py、test_operations.py、test_operations_model.py；agent.spec.ts、operations-model.spec.ts | 检查→数据分支→审批→候选保存→回读核验本地通过，逐项处理复用工作台；聚合事实模型概览、全部分支/缺失保留、快照授权与审批回读经 test_operations_model.py、operations-model.spec.ts 合成替身通过 |
| SO-005 | 主动异常发现与运营待办 | P0 | 有证据、可处理、去重的异常待办 | services/operations.py、workbench.py；OperationTaskReview.vue、WorkInbox.vue | 重跑/并发/状态/来源失效及清除测试 | 主动运行后的四类核对候选、来源/建议/固定标签、审批/拒绝/延期/忽略/完成/重开本地通过；统一清单筛选、计数及精确对象深链本地通过；完整异常集与 Agent 委托待继续 |
| SO-006 | 定时运营与经营通知 | P1 | 本地周期巡检、日周月经营报表、启停修改、通知和恢复 | services/schedules.py、scheduler.py、schedule_clock.py、schedule_reports.py、overview.py；SchedulesView.vue | test_schedules.py、test_schedule_reports.py；ScheduleEditor.spec.ts、schedules.spec.ts 桌面/手机 | 合成数据本地通过：UTC/IANA 日历、唯一周期、多 worker、24 小时有界恢复、巡检逐次审批、免打扰/已读/历史；专用自然日/周/月报按分币种与明确对比期存档，通知深链回读及依赖清除；业务事件/紧急提醒、评论/营销监测和外部通知待继续 |
| SO-007 | 多平台店铺授权与同步 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-008 | 统一商品主档与 SKU 映射 | P0 | 店铺+SKU 商品事实、已知成本与人工修订来源 | backend/app/models/imports.py、services/imports.py、product_edits.py | test_imports.py、test_product_edits.py | 导入/版本/撤销和人工名称/参数独立来源合成数据本地通过；完整 SPU/变体/仓库映射与平台运营待继续 |
| SO-009 | 商品批量采集与在线素材采集 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-010 | AI 选品研究与商品机会池 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-011 | Amazon 专项选品工具 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-012 | 竞品研究与持续监测 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-013 | VOC 客户评论洞察 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-014 | 商品信息质量与批量运营 | P1 | 当前主档质量检查、报告与名称/参数本地批量修订 | services/product_quality.py、product_quality_rules.py、product_edits.py；ProductQualityView.vue、ProductEditsView.vue、ProductEditReview.vue | test_product_quality.py 17 项、test_product_edits.py 21 项；ProductQuality.spec.ts 6 项、ProductEdits.spec.ts 7 项；两页桌面/手机 E2E | 合成数据本地通过：质量规则/报告、50 商品草稿→差异→审批→独立人工来源→回读/失败明细、幂等与事务、完整祖先撤销/清除；品牌/编码/图片/类目/平台明确未检查；价格/库存/素材变更及多店同步待继续 |
| SO-015 | 多渠道 Listing 刊登 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-016 | 单 SKU / 批量 / 整店商品搬家 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-017 | 价格跟踪、自动调价与价格同步 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-018 | AI Listing 创建、编辑与批量优化 | P0 | 商品事实→模型候选→比较→审批→本地版本 | services/listings.py、listing_composition.py、agent.py；ListingCandidatePreview.vue、ListingsView.vue | test_listing_model.py、test_listings.py；listing-model.spec.ts、listings.spec.ts | 事实编号编排、全部参数保留、绑定来源的双授权、费用与候选审批、本地版本回读已用协议/业务替身验证；百炼真实合成调用及事实覆盖已通过；真实商品质量、批量与平台发布待后续 |
| SO-019 | 多语种本地化与跨境文案规范 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-020 | AI 灵感图、商品图与图像编辑 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-021 | AI 商品营销视频 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-022 | 统一营销素材库 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-023 | 品牌、促销、营销邮件与营销策划 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-024 | 广告运营与效果优化 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-025 | 社交媒体内容、SEO 与 GEO | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-026 | TikTok 达人运营 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-027 | 统一多平台订单总表 | P0 | 店铺+订单+订单行与状态/金额/时间 | backend/app/models/imports.py、services/imports.py | tests/test_imports.py；frontend/e2e/imports.spec.ts | 订单行导入/去重/溯源切片合成数据本地通过；完整订单运营待继续 |
| SO-028 | 可配置的自动审单规则 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-029 | 订单编辑与批量操作 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-030 | AI 订单巡检与异常处理 | P0 | 导入订单异常与有依据的内部待办 | services/operation_checks.py、operations.py | test_operations.py | 已支付来源未履约/部分履约→核对事项→审批/处理本地通过；当前超时/物流状态未知；运营模型概览保留来源核对建议，逐项证据审批合成通过 |
| SO-031 | 统一客户消息与邮件中心 | P0 | 手工/导入消息与已核验订单关联 | services/imports.py、support.py；SupportView.vue | test_support.py；support.spec.ts | 手工/CSV/Excel 消息、搜索、原文/源行、核验订单及存档本地通过；真实渠道与完整消息运营待继续 |
| SO-032 | 多语言 AI 客服与人工接管 | P0 | 多意图、依据检索、草稿与人工接管 | services/support_rules.py、support_composition.py、support.py；SupportModelContext.vue、SupportCandidatePreview.vue、SupportReply.vue | test_support_model.py、test_support.py；SupportModelContext.spec.ts、support-model.spec.ts | 模型与规则多意图并集、受控事实/政策编号、双授权、人工接管、候选审阅/审批保存/编辑/存档及清除合成替身通过；真实客服模型质量、自动语言检测、多轮及外发待继续 |
| SO-033 | 客服知识库完整管理 | P0 | 政策/FAQ 来源版本、检索和拒答 | models/support.py、services/support.py；SupportPolicies.vue | 政策范围/版本/过期/冲突/清除；test_support_model.py 政策到期门禁 | 手工政策/FAQ、出处与有效期、主题筛选、本地与模型候选引用及无依据提示本地通过；模型调用前/回包后/审批/保存复验，全部已发送政策登记清除依赖；语义检索、批量运营与真实问答评估待继续 |
| SO-034 | 客服自动化规则与效能度量 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-035 | 售后、退货、退款与争议 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-036 | 买家档案与客户分析 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-037 | 内部客户风险标签与黑名单 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-038 | 一键邀评、自动邀评和售后关怀 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-039 | 交易风险与异常行为监测 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-040 | 自营仓、海外仓与平台仓管理 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-041 | 库存明细与库存流水 | P0 | 可选库存快照、时效和阈值 | services/inventory.py、operation_checks.py；InventoryView.vue | test_inventory.py、test_operations.py；库存与运营 E2E | 导入/时效/阈值/来源及今日运营低库存候选本地通过，过期未知且不能批准；多仓与流水按后续范围实施 |
| SO-042 | 跨平台库存同步与差异处理 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-043 | AI 补货与滞销管理 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-044 | 供应商、工厂采购与采购单 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-045 | 订单履约：自营仓与海外仓 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-046 | 平台仓的跨渠道多渠道履单 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-047 | 物流商、地址与打印配置 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-048 | 自动物流分配与购买面单规则 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-049 | 头程物流询价与货件管理 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-050 | 跨境申报与品类合规资料辅助 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-051 | 仓储与供应链优化 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-052 | 销售、订单和经营报表 | P0 | 导入数据内单店与跨店分币种统计、日历区间对比 | services/profit_calculation.py、overview_calculation.py；AnalyticsView.vue、OverviewView.vue | test_analytics.py、test_overview.py；analytics.spec.ts、overview.spec.ts | 订单行销售/退款/来源、分店币种订单去重、前日/七日/三十日/自选对比与摘要合成本地通过；全量覆盖与实时统计须实际来源 |
| SO-053 | 实际成本与商品/店铺利润 | P0 | 订单行、采购成本和缺失费用的已知毛利 | services/profit_calculation.py | Decimal、缺口、币种、退款、阈值与来源测试 | 当前采购成本估算历史已知毛利基础通过；费用归集和实际历史成本待继续 |
| SO-054 | 独立新品利润计算器 | P0 | 单币种单件已知毛利、费用假设、情景对比与敏感性 | services/profit.py、profit_rules.py；ProfitView.vue | test_profit.py 18 项；profit.spec.ts 桌面/手机；ProfitScenarioEditor.spec.ts | P0 最小切片合成数据本地通过：九类未知/零费用、依据、最多五方案、条件保本价、存档与清除；多币种换算与复杂费率后续扩展 |
| SO-055 | 渠道账单、结算与回款 | P1 | 通用渠道账单 CSV/Excel、销售款/退款/费用/回款原行、历史与分类合计 | services/imports.py、statements.py、repositories/statements.py；ImportsView.vue、StatementsView.vue | test_statements.py；Statements.spec.ts、statements.spec.ts 桌面/手机 | 通用文件首片本地通过：预览确认/覆盖、原行历史、范围隔离、UTC/Decimal、撤销恢复与清除；回款到账、结算周期与余额核对、真实平台适配待实现 |
| SO-056 | 平台费用映射、自定义费用与对账差异 | P1 | 人工费用版本台账、店铺/订单行归属、分币种合计与账单费用差异 | services/expenses.py、statements.py、evidence.py；ExpensesView.vue、StatementResult.vue | test_expenses.py、test_statements.py；费用/账单组件及桌面手机 E2E | 人工费用及通用账单核对本地通过：同范围明确凭据精确匹配，一致/金额差异/单边缺失/币种差异/重复歧义、原行与费用版本回读；平台收费类别规则、复杂分摊、物流/订单金额差异和人工核对结论存档待实现 |
| SO-057 | AI 自然语言经营问数和异常解释 | P0 | 销售/购买量前五/低毛利问题理解、匿名事实解释、来源与待办 | services/analysis_explanation.py、agent.py、analytics.py；AnalysisNarrative.vue | test_analysis_model.py 28 项；AnalysisNarrative.spec.ts、analysis-model.spec.ts | Responses 可配置适配、事实编号校验、确定性金额与来源、双重数据授权、费用/未知态、审批待办合成及协议替身通过；百炼通道已接入，问数真实模型理解质量待单独验证，精确净利润仍缺费用依据 |
| SO-058 | 运营变更版本、A/B 测试与效果评估 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-059 | 多币种、汇率、税费与数据完整性 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-060 | 内置运营 Skills | P0 | 有元数据/权限/风险/去重声明的内置技能 | services/agent_skills.py；schemas/agent.py | 元数据篡改、范围拒绝、问数/Listing/客服审批去重与审计回滚测试 | 十一项固定技能覆盖既有 P0 能力，新增客服依据读取与模型候选保存；完整元数据、工具白名单和审批回读本地通过；运营模型复用检查与保存候选技能，全部分支、权限与审批回读合成通过 |
| SO-061 | 第三方 Skills 安装与生命周期管理 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-062 | 可配置运营工作流 | P0 | 技能、分支、审批、暂停恢复和记录 | services/agent.py；AgentView.vue、AgentRunReview.vue | 条件分支/审批/去重/预算/暂停恢复/取消/E2E | 固定流程节点、数据分支、审批、核验与失败状态合成本地通过；固定 daily 流程持久定时触发、计划启停修改及原审批回读合成本地通过；业务事件/通用模板复制条件修改等完整范围待继续 |
| SO-063 | 跨平台连接器中心 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-064 | 浏览器扩展/页面内 AI 助手 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-065 | 软件使用助手与新手引导 | P1 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-066 | 经营规则、偏好与可验证的业务记忆 | P0 | 分范围经营约束、偏好依据、版本、恢复和有限授权 | services/business_rules.py、authorizations.py、outbound.py；RulesView.vue、InternalAuthorizations.vue、OutboundView.vue | 规则/R1/R2 服务、组件与 E2E 测试 | 阈值版本与 R1 有界预授权本地通过；R2 按全文/地址/检查绑定限一次、1—24 小时预授权，可撤销并回读消耗；文本偏好仍为人工参考 |
| SO-067 | 审批、操作前预览与回退边界 | P0 | 对象/差异/依据/风险预览及权限化审批 | services/listings.py、operations.py、authorizations.py、outbound.py；OutboundMailReview.vue | test_authorizations.py、test_outbound.py；outbound.spec.ts | R1 审批/候选撤回及 R2 全文预览、修改失效、单次/预授权、提交门禁本地通过；邮件不可撤回，真实外发凭据与送达待验证，统一清单可定位原审批全文与指定 R1 授权；更多长期动作继续；新增商品修订逐项差异、整批审批、来源恢复阻断、拒绝/撤销及清除，经 test_product_edits.py 与桌面/手机验证 |
| SO-068 | 任务状态、执行记录和异常恢复 | P0 | 持久执行、统一清单、恢复与未知结果 | services/agent.py、workbench.py、analytics.py、support.py、outbound.py；AgentRunReview.vue | test_support_model.py、test_analysis_model.py、test_listing_model.py、test_workbench.py；模型业务/外发 E2E | 十类统一记录与原入口、问数/Listing/客服的费用预留、未知不重发、在途取消清除及持久回读合成替身通过；客服政策到期和当前来源门禁通过；新增定时周期、未读通知、回滚恢复/故障暂停回读经 test_schedules.py 与 schedules.spec.ts 通过；真实邮件通道仍待授权；商品批量修订持久逐项失败、UUID 回读、历史成功与当前来源计数可核验 |
| SO-069 | 授权的开发者 OpenAPI | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-070 | 移动端轻量运营能力 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-071 | 外部经营数据与提醒渠道 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-072 | 独立站买家智能导购扩展 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-073 | 独立站内容维护与基础建站辅助 | P2 | 保留冻结稿完整需求，P0 稳定后按优先级实现 | — | — | 未实现 |
| SO-074 | 账号、基础权限、系统设置与隐私管理 | P0 | 登录恢复、权限、隐私、批次与派生数据清理 | services/auth.py、imports.py；repositories/analytics.py、listings.py、support.py | 身份/导入/分析/Listing/客服集成测试与 E2E | 身份、源内容及依赖分析/待办/Listing/客服草稿擦除本地通过；长期留存待用户确认 |

四条 MVP 的模型协议与本地持久业务闭环均已用合成替身验证；百炼真实合成路由和 MVP-02 事实编排通过。正在回审全部 P0 本地适用验收；真实模型全面质量及 P0-External 送达证据仍待对应授权，尚不宣称完整长期模块完成。

E2E-01—07 全部保留在需求冻结稿第 8 节，目前均未完整验收。P0-External 缺少用户授权的发送通道与测试收件箱，处于待授权验证状态。
