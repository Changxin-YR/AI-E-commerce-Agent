# SoloOps 重点上下文

本分支只存稳定要求、当前状态和下一步，业务代码在 main，不要将 context-memory 合并到 main。更新：2026-10-09。

## 用户要求与授权

- 完整按 docs/requirements/SoloOps-V1.0.md 实现，先 P0 的 23 个最小模块/四条 MVP 和 A-01—A-32 本地适用验收，再 P1/P2。全部 74 SO、32 验收项保留，不将计划写成实现。
- 简体中文；Vue 3 + TypeScript、FastAPI/Python、MySQL；接口→业务服务→repository 三层，可读小函数和明确类型。Agent 只能调用受控业务服务。
- 每功能先检索 GitHub/官方资料并记来源/许可证/适配，再前后端/迁移/测试、更新 docs、提交推送。用户已授权 main 与 context-memory 推送，不强推。
- 用户已授权按上下文压力创建新本地项目聊天继续；交接前落盘推送，交接后原聊天停止修改，避免同时改工作区。
- 真实事实、账号授权、模型预算集中记 docs/questions.md，不能由模型代用户确认；缺凭据不称真实 LLM 已验证，缺通道授权不外发。

## 当前提交与环境

- 仓库：https://github.com/Changxin-YR/AI-E-commerce-Agent.git 。GitHub connector 已核对这是当前账号有 admin/push 权限的目标仓库。
- 当前功能提交 d3b9be1be958a47931cd897f2fb2f8258075b454，已推送 main。主题：source-aware customer support drafts and policy versions。
- main 当前 HEAD d8351feb566395512b248025e17b62085d84b7ed（补充客服CI证据），已推送。
- 客服 GitHub CI：https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37808536888 ，已确认 completed / success，功能提交d3b9be1在Ubuntu/MySQL全部通过。
- 上版 Listing 8168d97/ab66412，CI 37803271282 已 completed / success。
- 前版分析 ab83fd6/a212b88 CI 也均通过；相关实现保留。
- 上一导入迭代 138f09c/f0ea342 已通过 Ubuntu CI。
- backend/.venv Python 3.11，frontend/node_modules 已装，Docker MySQL 8.4：开发 3307、隔离测试 3308。
- 密钥与本机配置在忽略的 .env、backend/.env、.local/test.env，不打印、不提交。
- Windows 优先 .venv/Scripts/python -m pytest/ruff/mypy/alembic；网络、MySQL/Docker、Vitest 常需 require_escalated。pytest 与 Playwright 都清理 _test，必须串行。
- Playwright 自动启动 8001/5174；日常开发 8000/5173。.local/verify_listing_migration.py 是忽略的本机验证脚本；迁移回退也须在 pytest/Playwright 结束后进行。
- 最新迁移 8d34d9c410a2 已应用开发和测试库；.local/verify_support_migration.py 已验证隔离库回退至262449b655ea→升级/check 和开发库升级/check。
- Firecrawl 已确认 402，用官方网页检索或 GitHub connector，不反复调用计费接口。
- 本次自动审批曾因 origin 信任关系未核实拒绝推送；经 connector 确认仓库/权限、远程旧 HEAD 与交接一致，检查提交仅代码/合成测试/文档、配置被忽略后，同一 git push 再审通过。后续推送沿用明确目标与授权事实。
- Listing 迭代再次用 connector 确认当前账号 Changxin-YR 对目标仓库具有 admin/push 权限，main 推送成功。GitHub fetch 支持 Actions REST URL，解析 structuredContent.content 后仅输出状态；fetch_commit_workflow_runs 仅查 PR 触发，不适用于 main push。

## 已实现

账号 CLI 创建/恢复、登录/退出、Cookie/CSRF、过期与锁定，资料 version 并发控制，拥有者/店铺隔离与审计。

商品/订单 CSV、XLSX 导入：候选映射、人工映射、个人模板、预览/行级修正、覆盖确认、批次/源行持久化、去重、乱序撤销/清除。examples/imports 全为合成数据，两种平台风格列名尚无真实平台验证。

确定性分析：单店铺、单币种、数据身份、明确时间窗；销量/销售额/当前成本估算毛利、SKU 汇总、低毛利阈值、来源与费用缺口、保存分析、幂等核对待办。数据版本失效和清除来源批次的派生清理已经真正接通。

界面 /analytics，AnalyticsView.vue + AnalysisEvidence.vue，绿色工作台。三个受控问题明确标为本地规则：查看销售与已知毛利、销量前五的 SKU、哪些商品销量高但已知毛利低；其他问题返回 unsupported_question。尚无真实模型适配器与模型调用，MVP-04 的 AI 解释部分未完成，四条 MVP 均不能标完整完成。

新增 /listings：仅商品即可选择SKU→本地事实模板建稿→来源与差异→编辑新版本→核对确认→批准/拒绝→刷新与历史恢复。SO-018/067基础与A-24本地通过；完整AI Listing闭环仍待模型。四条MVP均未完整完成。

新增 /support：手工消息预览确认/CSV/Excel导入→同店铺/渠道/身份订单核验→政策筛选→多意图本地规则草稿→编辑/转人工/存档/重新打开→来源失效/擦除。SO-031/032/033本地基础可用，真实LLM/自动语言检测/多轮/实时运单/外发尚无，MVP-03仍非完整AI闭环。

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
- Listing迁移为262449b655ea；客服新head为8d34d9c410a2。MySQL回退按依赖删表，不先删外键支撑索引。

### Listing 关键规则

- models/listings.py 两表 listing_versions/listing_sources；schemas/listings.py 契约；services/listings.py 用例；listing_generation.py 生成器与规则；同名 repository/routes。
- ListingGenerator 只接收商品 name/facts；默认 FactTemplateGenerator 标 local_template，测试替身 test_double，人工编辑 manual。真实适配未实现；未来网络生成须移出持锁事务，写回重新核对来源与基线。
- check_content 为保守完整原文覆盖：标题完整商品名，可用「 · 」连接完整参数行；描述逐行选用完整参数或完整商品名。支持选用/排序，新增改写文字可存草稿但阻断批准，即使人工确认也不越过。真实性/平台合规仍需用户核对。
- 本地 Listing 版本不改导入 Product 事实。流程 draft/approved/rejected/superseded，来源 current/stale/cleared。R1，外部状态固定 not_submitted。拒绝留存；仍有来源的历史文案另存草稿、再批准可以恢复。
- 生成检查 expected_source_row_id/expected_active_id；审批检查状态 version/base_version_id。生成/编辑散列幂等、重复批准无新副作用；竞争候选一个成功、一个409。生成键含最新失效版本ID：撤销覆盖恢复旧源行后，旧草稿仍stale但能重新建稿。
- Listing用例先user/shop锁及当前读，commit前组装响应。active查询包含stale用于比较基线，页面明确过期；cleared不作当前版本。
- 导入同事务检查候选 source_row_id 是否仍是 Product 当前来源；无关SKU/订单变化不失效。恢复旧源行不复活旧审批。
- 依赖集合同时包含当前事实、比较旧值和复制历史内容的批次。清除任一依赖清空整个 snapshot、source_row_id 和关系，保留关联散列/编号/状态/时间/无正文审计；已撤销旧批次的差异内容也清掉，独立SKU保留。
- ListingsView/ListingReview 沿用绿色工作台。Vue转义文本；未保存改动禁止批准；新版本重置人工确认；focus/刷新更新状态。商品搜索每页50、版本最近50，active_version单独返回。

## Listing迭代验证

- pytest 全部90项通过（分析19项，新增Listing12项）。Listing覆盖商品独立建稿、缺参数、原商品不改写、编辑/拒绝/恢复、事实门禁、生成异常、越权/CSRF、并发生成/审批与竞争、来源变化/恢复、跨版本旧值清除、独立SKU保留。原分析/导入回归全通过。
- Ruff 格式/规则通过；mypy48 app文件；Vue lint/build/type-check通过；Vitest4文件7项；完整Playwright Chromium9项通过。
- E2E：计算→订单/成本原始值→保存→核对待办→刷新→撤销失效→清除派生；手机未知问题/低毛利/空身份。桌面和 390×844 截图已查看，无水平溢出，产物忽略。
- 新增Listing E2E：选商品→源行→编辑→差异→批准→刷新→历史另存→拒绝→撤销失效→清除；手机脚本文字转义/无依据声明阻断/无水平溢出。标题结构修正后两条Listing E2E再次通过，截图已查看。
- 两库 upgrade/check 无漂移，隔离库 downgrade 前版→upgrade/check 通过。Starlette httpx 弃用提示仍有。
- 74SO/32验收行保持。A-24本地通过，A-01/09/16/26/30增补Listing证据；所有测试均合成，真实AI/其他模块/外发不能冒充完成。

### 客服关键规则

- CustomerMessage 在 models/imports.py，作为来源投影。ImportKind 新增 messages，复用映射/校验/提交/撤销/清除，业务键 shop+channel+message_id。正文上限2000与解析器一致；en/zh/und人工标注，不声称自动检测。
- models/support.py：support_policies、reply_drafts、reply_sources、reply_policies。api→SupportService→SupportRepository；support_rules.py 为本地关键词多标签+中英文模板，没有真实模型。
- 订单候选必须同owner/shop/channel/data_identity。订单号不证明客户身份，用户明确核对关联后，将看到的全部订单源行ID随生成请求提交，再当前读比较；最多100行，超限拒绝。未核验的订单不入快照。
- 政策手工录入 code/title/topic/text/market/channel/language/data_identity/source/source_version/source_confirmed/valid_from/until。UTC区间[from,until)，新版本立即替代旧版，未来政策不生效。标题/正文检索；候选按范围、主题、时效筛选，多份同主题适用政策提示冲突。
- 清除政策会擦除引用它的整个草稿快照，旧政策清除不影响只用新版本的草稿。policy_epoch将清除阶段加入幂等键，使原编号重新录入成新版本，旧引用不复活。
- 物流+退款标签并存；退款/争议/取消/地址/保修等敏感请求、未知语言/意图、无政策或冲突、无可信物流均human_review。CSV fulfilled不作为当前物流证据；当前根本没运单接入，所有物流请求说明无法验证当前轨迹/送达日期。单一已人工核对FAQ可以引用完整原文。
- 草稿快照含消息/核验订单/选用政策、标签、接管原因与摘要、正文。编辑标manual并保留证据；draft/human_review/archived只是本地处理状态。无send路由，未知auto_send字段422，external_status固定not_submitted。
- 生成/相同编辑/状态操作幂等；不同并发编辑一个200一个409。前端dirty禁用切换/刷新/存档。用户锁+当前读，响应commit前组装。
- 消息源行变化永久stale；源行恢复不能复活旧稿但可重新生成。订单变化保守失效该店铺已核验订单草稿，无订单证据保留。政策增修保守失效全店草稿；服务访问时政策到期会落盘stale。
- reply_sources包含消息和核验订单批次，reply_policies包含选用政策。清除任一依赖擦除整份snapshot+source_row_id+关联，包括人工正文；独立草稿保留。审计只记编号/动作/版本/标签，无正文。
- /support 三层页面组件ManualMessage/SupportPolicies/SupportReply/SupportSource；复用原始行接口。绿色工作台，手机保留意图与状态。截图在系统Temp/soloops-support-*.png（合成数据），已查看。Browser插件缺席，使用项目Playwright。

### 客服最终验证

- 完整pytest109通过（新增19客服含参数化）；Vitest5文件8项；完整Playwright11项通过；最后手机标签修复/订单核验测试新增后客服2项复验通过。
- Ruff68个文件格式/规则通过，mypy54；Vue lint/type/build通过。桌面1280×720/手机390×844首屏和草稿截图已查看，无横向溢出；HTML脚本文字未执行。
- 两库迁移upgrade/check及隔离库回退上一迁移往返通过。Starlette httpx弃用提示仍有。32验收/74SO保留。A-07本地规则通过；A-08无可靠轨迹通过、实际过期运单接入待续；A-12本地无发信路径通过、真实通道门禁待续。

## 下一步立即开发

继续MVP-01今日运营及其余P0，不能只计划或把规则模板当作真实Agent。

1. 先读冻结稿SO-003/004/005/030/041/054/060/062/068，以及15、21、22、25—27、A-03/10/14/22/23/25—29/32，检索官方/GitHub资料记references。
2. 实现可选库存快照的有界导入/时效/安全阈值，缺库存显示未知且不阻断其他检查。扩展既有导入不要重建。
3. 今日运营：读取导入商品/订单/可选库存/消息/成本，根据实际数据分支执行检查，保存带来源的去重待办/标签、处理状态和审批/历史。空数据未检查，旧快照失效，批次清除继续擦除新增派生结果。
4. 接上受控Agent层：内置技能注册元数据/输入/店铺作用域/权限/风险/幂等，模型适配接口和实际可配置调用，至少两技能可追踪串联，步骤/时间/费用预算、R3拒绝、读重试上限、熔断、取消和恢复。凭据缺失必须显示待配置；不能以测试替身声称真实LLM成功。
5. 继续SO-054新品利润计算器及全部P0最小模块/32验收。真实发信通道缺授权依旧阻塞，不外发。
6. 每功能完成后测试、更新development/interview/74SO矩阵/32验收/testing/questions、提交推送；按上下文压力交接，持续P0→P1/P2。

用户事实、凭据、预算、测试邮箱、政策语言/物流阈值等已在questions.md；不要重复阻断已授权的本地开发。
