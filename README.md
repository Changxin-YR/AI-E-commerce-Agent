# SoloOps 重点上下文

本分支只存稳定要求、当前状态和下一步，业务代码在 main，不要将 context-memory 合并到 main。更新：2026-10-08。

## 用户要求与授权

- 完整按 docs/requirements/SoloOps-V1.0.md 实现，先 P0 的 23 个最小模块/四条 MVP 和 A-01—A-32 本地适用验收，再 P1/P2。全部 74 SO、32 验收项保留，不将计划写成实现。
- 简体中文；Vue 3 + TypeScript、FastAPI/Python、MySQL；接口→业务服务→repository 三层，可读小函数和明确类型。Agent 只能调用受控业务服务。
- 每功能先检索 GitHub/官方资料并记来源/许可证/适配，再前后端/迁移/测试、更新 docs、提交推送。用户已授权 main 与 context-memory 推送，不强推。
- 用户已授权按上下文压力创建新本地项目聊天继续；交接前落盘推送，交接后原聊天停止修改，避免同时改工作区。
- 真实事实、账号授权、模型预算集中记 docs/questions.md，不能由模型代用户确认；缺凭据不称真实 LLM 已验证，缺通道授权不外发。

## 当前提交与环境

- 仓库：https://github.com/Changxin-YR/AI-E-commerce-Agent.git 。GitHub connector 已核对这是当前账号有 admin/push 权限的目标仓库。
- 当前功能提交 ab83fd6a5261bc72da03a4720d11fb8d98b1be99，已推送 main。主题：traceable profit analysis and source-aware saved todos。
- main 当前 HEAD a212b88dd8808293c8aa590f52992c62d75f608e（补充 CI 证据），已推送。
- GitHub CI：https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37798933063 ，已确认 completed / success，功能提交 ab83fd6 在 Ubuntu / MySQL 全部通过。
- 上一导入迭代 138f09c/f0ea342 已通过 Ubuntu CI。
- backend/.venv Python 3.11，frontend/node_modules 已装，Docker MySQL 8.4：开发 3307、隔离测试 3308。
- 密钥与本机配置在忽略的 .env、backend/.env、.local/test.env，不打印、不提交。
- Windows 优先 .venv/Scripts/python -m pytest/ruff/mypy/alembic；网络、MySQL/Docker、Vitest 常需 require_escalated。pytest 与 Playwright 都清理 _test，必须串行。
- Playwright 自动启动 8001/5174；日常开发 8000/5173。.local/verify_analytics_migration.py 是忽略的本机验证脚本。
- Firecrawl 已确认 402，用官方网页检索或 GitHub connector，不反复调用计费接口。
- 本次自动审批曾因 origin 信任关系未核实拒绝推送；经 connector 确认仓库/权限、远程旧 HEAD 与交接一致，检查提交仅代码/合成测试/文档、配置被忽略后，同一 git push 再审通过。后续推送沿用明确目标与授权事实。

## 已实现

账号 CLI 创建/恢复、登录/退出、Cookie/CSRF、过期与锁定，资料 version 并发控制，拥有者/店铺隔离与审计。

商品/订单 CSV、XLSX 导入：候选映射、人工映射、个人模板、预览/行级修正、覆盖确认、批次/源行持久化、去重、乱序撤销/清除。examples/imports 全为合成数据，两种平台风格列名尚无真实平台验证。

确定性分析：单店铺、单币种、数据身份、明确时间窗；销量/销售额/当前成本估算毛利、SKU 汇总、低毛利阈值、来源与费用缺口、保存分析、幂等核对待办。数据版本失效和清除来源批次的派生清理已经真正接通。

界面 /analytics，AnalyticsView.vue + AnalysisEvidence.vue，绿色工作台。三个受控问题明确标为本地规则：查看销售与已知毛利、销量前五的 SKU、哪些商品销量高但已知毛利低；其他问题返回 unsupported_question。尚无真实模型适配器与模型调用，MVP-04 的 AI 解释部分未完成，四条 MVP 均不能标完整完成。

## 关键规则

- imports.py 三层 + import_parser/import_validation/import_catalog 已完成，不重建。商品键 shop+SKU，订单键 shop+order+line，大小写敏感。
- import_batches/import_rows 是每批版本；products/order_lines 当前投影以 source_row_id 引用来源。applied_revision 表示生效顺序。
- 提交/撤销持有用户锁，MySQL 当前读避免认证阶段 RR 旧快照。旧预览返回 409。撤销从仍有效批次选最新记录，防止复活已撤销祖先。
- Decimal/Numeric(18,4)，历史 JSON 为字符串，UTC/DATETIME(6)。未知不补零，导入草稿有界、24h 失效，确认丢弃未映射列。
- 统计按订单时间 [start,end)，最长 366 天，所选身份最多 10000 行，超限拒绝不截断。paid/partially_refunded/refunded 有效，其他状态明示排除；异币种分别选择统计，不换汇。
- 销售 = qty×unit_price−discount−refund。数量是原购买量，退款归原订单时间，缺退货件数不恢复成本/库存。历史订单按当前采购成本估算，成本生效日未知，导入/导出时间不冒充生效日。
- 缺折扣/退款/成本或成本币种/身份不同，完整毛利 null；已知子集另列覆盖行数，毛利仅汇总收入和成本配对完整的行。平台/广告/物流/税费等是费用缺口，不能称净利润。
- 低毛利用最低购买量+毛利率上限；关键金额缺失或范围内有其他币种则暂停完整筛选。Decimal 精度 40，百分比仅显示舍入，阈值用原始乘积。
- saved_analyses 保存 scope/revision/snapshot/status/time，owner+scope/shop/revision 散列幂等；保存重新计算并检查 expected_revision。
- analysis_sources 关联订单与成本批次；analysis_todos 每分析唯一核对待办，open/stale/cleared 基础状态，完成/统一任务管理待继续。
- 导入提交/撤销在同事务将同店分析和待办标 stale，保守失效但不删独立内容。清除批次（包括已撤销旧批次）只清有依赖的快照/关系/待办标题，保留无源状态/版本/范围/时间和必要审计；其他店铺与独立结果保留。
- 锁顺序 user→shop→sources→derived。保存响应在 commit 前组装，避免 commit 后取待办锁再取用户锁的死锁。
- 历史列表最近 50 摘要，单条展开读取快照；原始行接口按 owner+shop 查询，清除后 404。窗口 focus/手动刷新检查版本，保存/建待办再次校验；历史范围可直接重算。
- 迁移 a32132cebd28（前版 0776318e56e3）已应用两库。MySQL 回退按依赖删表，不先删外键支撑索引。

## 验证

- pytest 全部 78 项通过（新分析 19 项），真实 MySQL：Decimal、六状态、退款、缺口、币种/身份、时间边界、两 SKU、来源、重复问数、原始阈值、并发幂等、版本失效、撤销后清除、独立快照、权限和拒答。
- Ruff 格式/规则通过；mypy 42 app 文件；Vue lint/build/type-check 通过；Vitest 3 文件/5 项；Playwright Chromium 7 项全通过。
- E2E：计算→订单/成本原始值→保存→核对待办→刷新→撤销失效→清除派生；手机未知问题/低毛利/空身份。桌面和 390×844 截图已查看，无水平溢出，产物忽略。
- 两库 upgrade/check 无漂移，隔离库 downgrade 前版→upgrade/check 通过。Starlette httpx 弃用提示仍有。
- 74 SO/32 验收行保持。A-04/05/06 及确定性 A-15/19/21/30/31 有合成本地证据；真实 AI/其他模块/外发不能冒充完成。

## 下一步立即开发

继续 MVP-02 Listing 草稿与本地审批最小纵向切片，随后 MVP-03 客服、MVP-01 今日运营，并补齐真实受控 Agent 层，不要只给计划。

1. 阅读冻结稿 SO-018、SO-067、21/22/25/26/27 和 A-01/09/24/25/26；先检索官方资料记 references。
2. 从已导入商品事实做可编辑内部 Listing 草稿，明确事实依据/缺失项/来源、原值与拟议值；保存版本、拒绝/批准/修改、本地生效与外部状态区分。审批前不把草稿当商品现值；来源变化需过期或重算。
3. 新草稿/审批/任务接入撤销与批次清除，保留必要审计，不遗漏现有隐私边界。
4. 真实模型适配、技能注册（元数据/输入/权限/风险/幂等）、预算/熔断/可恢复运行仍需实现。允许可注入适配器和明确标记的测试替身验证本地行为；真实调用等用户凭据/预算，固定模板不能称真实 LLM。
5. 每功能完成后测试、更新 development/interview/矩阵/testing/questions、提交推送；按上下文压力交接。持续按完整 P0→P1/P2 推进。

用户事实、凭据、预算、测试邮箱、许可、留存、历史成本和费用明细都在 questions.md；不要重复阻断已授权的本地开发。
