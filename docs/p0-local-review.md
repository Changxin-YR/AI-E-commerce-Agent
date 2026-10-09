# P0 本地逻辑复核

复核日期：2026-10-09。基线为冻结稿第 14、21—23、25—30 节。本报告记录合成数据和替身下可重复的真实本地记录与权限行为，完整模块范围继续保留在 74 项功能矩阵中。

## 四条 MVP 的可重复操作

| MVP | 实际本地链路 | 当前证据 |
|---|---|---|
| MVP-01 | 导入订单/可选数据 → 聚合发送预览及双授权 → 九分支概览 → 候选事实/来源审阅 → 审批保存 → 回读检查/待办 → 工作台批准和完成 → 刷新/清除 | test_operations_model.py；operations-model.spec.ts 桌面/手机，operations.spec.ts 状态与去重 |
| MVP-02 | 商品事实 → 发送版本绑定 → 模型排列完整事实 → 差异预览 → 保存待审候选 → 独立审批本地生效 → 回读版本 | test_listing_model.py、test_listings.py；listing-model.spec.ts、listings.spec.ts |
| MVP-03 | 消息/政策与人工核验关联 → 双授权 → 多意图和规则并集 → 候选/敏感接管 → 审批草稿 → 编辑/存档 → 回读/清除 | test_support_model.py、test_support.py；support-model.spec.ts、support.spec.ts |
| MVP-04 | 固定范围问题 → 模型选择意图 → 确定性计算 → 匿名事实解释 → 来源及缺失 → 审批核对待办 → 回读/完成 | test_analysis_model.py、test_analytics.py；analysis-model.spec.ts、analytics.spec.ts |

以上模型网络使用 HTTP MockTransport 或仅注册于隔离测试 launcher 的模型替身；数据库、服务、审批和浏览器业务操作真实执行。已有百炼真实合成验证只覆盖路由和 Listing 参数编排，其他实际模型质量未由这些测试证明。

## 23 个 P0 模块的最低能力

| SO | 当前支持四条 MVP 的最小能力 | 验证位置 |
|---|---|---|
| SO-001 | 账号经营资料、店铺与四类数据导入 | test_identity.py、test_imports.py；imports.spec.ts |
| SO-002 | 跨店按币种总览、比较、日周月摘要与来源 | test_overview.py；overview.spec.ts |
| SO-003 | 目标分类、受控模型组织、确定性技能及审批 | test_agent.py、四类模型测试；agent.spec.ts |
| SO-004 | 今日运营数据分支、模型聚合概览、保存和复核 | test_operations_model.py；operations-model.spec.ts |
| SO-005 | 四类有证据候选、固定标签与处理状态 | test_operations.py、test_workbench.py；operations.spec.ts |
| SO-008 | 店铺/SKU 商品主档、成本与版本化来源 | test_imports.py、test_listings.py |
| SO-018 | Listing 候选、差异、事实检查、审批和本地版本 | test_listing_model.py；listing-model.spec.ts |
| SO-027 | 店铺/订单/行导入、状态与金额分摊 | test_imports.py、test_analytics.py |
| SO-030 | 来源未履约/部分履约订单形成核对候选 | test_operations.py、test_operations_model.py |
| SO-031 | 手工/导入客户消息、原文和已核验订单关联 | test_support.py；support.spec.ts |
| SO-032 | 意图并集、规则接管、候选草稿、编辑和存档 | test_support_model.py；support-model.spec.ts |
| SO-033 | 政策/FAQ 范围、版本、来源、有效期与冲突 | test_support.py、test_support_model.py |
| SO-041 | 可选快照、显式阈值、过期未知 | test_inventory.py、test_operations.py |
| SO-052 | 订单行销售/退款、币种和来源统计 | test_analytics.py、test_overview.py |
| SO-053 | 当前采购成本估历史已知毛利，费用缺口可见 | test_analytics.py；analytics.spec.ts |
| SO-054 | 独立单币种新品费用假设、方案比较与存档 | test_profit.py；profit.spec.ts |
| SO-057 | 固定范围经营问数、受控事实解释和核对待办 | test_analysis_model.py；analysis-model.spec.ts |
| SO-060 | 十一项技能元数据、白名单、权限与回读 | test_agent.py、四类模型测试 |
| SO-062 | 持久固定流程、按数据分支、审批、预算暂停/恢复 | test_agent.py；agent.spec.ts |
| SO-066 | 有来源的版本化经营规则与有界 R1/R2 授权 | test_business_rules.py、test_authorizations.py、test_outbound.py |
| SO-067 | 内部差异/事实审批与受控测试邮件全文门禁 | test_listings.py、test_operations.py、test_outbound.py |
| SO-068 | 执行状态、统一清单、去重、未知不重发和回读 | test_agent.py、test_workbench.py、test_outbound.py |
| SO-074 | 登录恢复、资源范围隔离、批次及派生内容清除 | test_identity.py、各业务清除测试 |

SO-062 的完整工作流编辑、SO-033 的语义检索、自动语言检测、长期多仓库存等仍是后续模块范围；目前实现满足四条 MVP 所需的有界最小能力。涉及真实经营结论的数据真实性与完整性继续由卖家来源决定。

## A-01—A-32 的证据边界

- A-01—A-12、A-14—A-32：31 项本地适用行为已在后端、组件及浏览器测试中验证；逐项实现和测试名保留在 acceptance-matrix.md。A-11/A-28 明确使用超时/未知回执替身，不声称真实外部送达。
- A-13：真实测试邮件送达仍缺本人发送账号、验证收件箱和授权，标为阻塞待验证。默认关闭的本地 R2 流程、审批、一次提交和回查已有替身验证。
- 真实模型全面质量、真实平台授权读写、真实业务文件、历史成本/完整费用和跨币种换算没有被标为已验。questions.md 保留这些条件；七条长期 E2E 均维持后续完整验收状态。

本地逻辑已具备继续 P1 独立开发的回归基线；下一项按冻结稿 SO-006 先做可暂停、可回读、重启可恢复的本地定时运营与站内通知。外部渠道接入遵循实际授权，不扩大已有一次性模型测试许可。
