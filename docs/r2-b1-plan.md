# R2 B1：受控低毛利复核组合设计

日期：2026-10-10。本文件为实施前设计；业务开发以前包A4准确代码CI成功为前置。

## 复用边界

现有AgentExecution已持久保存input/result、status/next_node/version、source_revision、预算/费用、模型租约及有效期；AgentStep保存技能契约、输入输出、审批事件与下一步。继续使用ready/waiting_approval/waiting_input/paused/succeeded/rejected/blocked/result_unknown/circuit_open等已有状态，无新增表或迁移。

AgentService.start按owner+request UUID及内容摘要防重复，act校验版本；每个本地节点在SAVEPOINT和defer_commits下完成业务写入与步骤记录。技能注册表固定输入/输出/权限，R0只读、R1写入逐节点批准，外部R2/R3不进入组合。只读临时故障最多3次，写入不自动重试；预算/租约未知按现有行为暂停或停止。本包最多一项分析存档和一项选定商品Listing草稿，每个写技能最多一次，无循环或动态工具名。

## 唯一新增场景

增加margin_review模板：“截至所选结束时间的最近7天低毛利复核”。页面默认当前结束时间，启动时计算精确7天起点并展示范围，服务校验7天窗口。成本选择当前成本估算或卖家历史成本依据，默认历史依据；新增独立margin_cost_mode参数，原OperationScope及原流程成本口径保持。

| 步骤/技能 | 输入和输出 | 权限及下一步 |
|---|---|---|
| metrics（已有） | 当前店铺、身份、渠道、币种、7天窗口和所选成本模式 → AnalysisResult | R0；使用原Decimal计算和低毛利候选，进入margin_evidence |
| margin_evidence（局部新增内置技能） | 已验证AnalysisResult、可选的一个商品ID → 有界建议、缺口、成本依据、商品内容核对和允许的内部动作 | R0；无订单请求补录；有核对事项进入analysis_todo；完整数据无命中且无独立内容缺口可结束 |
| analysis_todo（已有） | 当前分析范围/revision → SavedAnalysis和AnalysisTodo | R1逐节点批准；作为成本/费用核对或定价分析草稿，保持费用缺口及净利润未知，随后verify回读 |
| product_context → listing_draft（已有，可选） | 只对卖家选定且与本范围订单SKU/身份/渠道匹配的商品，核实来源与本地生效版本 → 来源事实模板草稿 | R0读取、R1单独批准；仅在确证本地版本遗漏了来源中的明确参数行时执行，随后verify |
| verify（已有） | 业务记录ID → 当前状态与可回查链接 | 回读已保存分析/待办及可选Listing；多个内部结果分别保留在步骤中并展示链接 |

## 四组证据分支

1. 无符合范围的订单：请求导入/补录并合法停止；有订单但成本/金额/币种等不完整：展示缺口，批准后保存核对分析和待办，不给完整低毛利排行。
2. 低毛利且卖家历史采购成本完整：展示逐行凭据、成本口径与费用缺口，形成可审阅的定价/成本核对分析草稿；没有完整费用不作净利润或真实改价结论。当前主档成本估算只进入成本核查建议。
3. 卖家选定商品的来源包含明确“参数名:值”行，当前有效本地Listing确实遗漏该完整参数行：作为独立商品内容证据，使用现有事实模板Listing Skill保存完整已知事实草稿；未选商品、缺来源参数、无有效基线或只能猜测类目必填项时提供人工补证指引，不生成缺失事实。
4. 成本缺口和上述内容遗漏并存：分别展示证据与风险，先批准分析核对，回读后再单独批准Listing草稿。内容修订和毛利之间不推断因果。

内容核对只比较本地批准版本和明确来源参数行；不判断外部刊登、类目要求或同义句语义。商品源行/生效版本在继续执行时重查，发生变化阻止旧分支写入。分析来源、商品来源、历史本地Listing继承来源全部加入原AgentSource清除链；旧步骤可解释且清除后不残留正文。具体分支规则放在独立margin_review服务/结构化schema，AgentService仅增加模板接线与有限下一步选择。

## 最小改动与验证

涉及schemas/agent、agent_skills、agent服务有限接线及新margin_review服务/schema；前端AgentView增加模板与成本/商品选择，AgentRunReview增加证据建议和多个结果链接的小组件。全部沿用Vue/FastAPI/MySQL及既有设计、审批和源数据服务。无新框架、数据库状态机或付费模型调用。

四组事实驱动不同分支；至少metrics/analysis_todo真实运行，内容分支额外运行product_context/listing_draft；逐个写入审批、拒绝、精确金额和来源、重启回读、重复请求、副作用幂等、跨用户店铺、来源变化、当前Listing变化、清除、权限元数据/R3篡改、有限失败和步骤/时间熔断。本地组合所有节点模型费用为0；既有模型费用不足/未知恢复使用原替身测试回归。关键桌面/390px从新模板至真实内部记录及多结果链接通过；完整回归交给准确代码CI。

官方参考：Anthropic Building effective agents（公开工程文章，版权归作者，仅借鉴有限路由与可观察工具结果）与SQLAlchemy 2.0 Session transactions（MIT，沿用SAVEPOINT与外层事务）。本机Firecrawl认证可用但额度为负，使用官方网页检索；来源记录见references.md。
