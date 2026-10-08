# SoloOps 重点上下文

更新：2026-10-09。本分支只维护稳定规则、当前提交、测试、下一步及阻塞；业务代码在 main，不合并本分支到 main。

## 用户要求与授权

- 完整实现冻结稿 `docs/requirements/SoloOps-V1.0.md`，先 P0 的 23 个最小模块/四条 MVP 与 A-01—A-32 本地适用验收，再 P1/P2。74 SO、32 验收行全部保留，计划不能算实现。
- 简体中文；Vue 3 + TypeScript、FastAPI/Python、MySQL。接口→业务服务→repository 三层，小函数和明确类型；Agent 只能调用受控业务服务。
- 每功能先查 GitHub/官方资料并记 references/许可证/适配；完成前后端和验证后，更新 development/interview/功能矩阵/验收矩阵/testing/questions，再提交并正常推送。用户已授权 main、context-memory，不强推。
- 用户已授权按上下文压力创建新本地项目聊天连续开发。交接前落盘推送，新聊天接手后旧聊天停止修改共享工作区。
- 真实经营事实、模型供应商/预算、测试发信账号/收件箱集中在 docs/questions.md。缺凭据不称真实模型成功，缺外发授权不外发；这些不阻断独立本地开发。

## 当前提交与环境

- origin：https://github.com/Changxin-YR/AI-E-commerce-Agent.git 。本轮 GitHub connector 核实登录 Changxin-YR，仓库 ID 1410355242，公开，admin/push true；正常 push 已成功。
- main HEAD/当前功能提交：`d43d29bd9a3c6e4d8a2d650a69a9e6d2a4fe7366`，已推送；主题 add controlled R2 test mail delivery。
- 本功能 CI：https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37833883370 ，最后观测 in_progress，接续先核对并修复失败。前版 R1 1edd7db 的 CI37830128990 已 completed/success，规则 c1dac61 CI37826653771、利润 abb9f79 CI37823550243 也 success。
- 前版受控 Agent `d1eda91` CI 37820719900 已 completed/success。
- 前版补充提交 `10fa1df` 的 CI `37816007090` 已 completed/success；运营 `3531ce7` 的 CI `37815482720`、库存 `53b7d72` 的 `37811072990`、客服 `d3b9be1` 的 `37808536888` 均已 success。
- backend/.venv Python 3.11、frontend/node_modules、Docker MySQL 8.4 开发3307/测试3308。日常服务8000/5173；Playwright自动启动8001/5174。
- .env、backend/.env、.local/test.env 是忽略的密钥/本机配置，不打印、不提交。Windows 用 .venv/Scripts/python -m；MySQL、Node子进程、Git写常需 require_escalated。
- pytest 与 Playwright 会清理隔离 _test 库，必须串行；迁移回退也等测试结束。测试与 E2E 入口强制 model_enabled=False。
- 当前迁移 `f219af0a01cf` 已应用两库；`.local/verify_outbound_migration.py` 已验证 _test 回退 3b35be067576→升级/check；开发库只升级/check，两库无漂移。MySQL回退不要先删FK支撑索引，直接按依赖删除表。
- Firecrawl 已确认402，使用官方网页/GitHub connector，不反复调用计费端点，不临时写抓取脚本。GitHub Actions用 github_fetch REST，解析 structuredContent.content，只输出摘要；fetch_commit_workflow_runs不适用于main push。

## 最新完成：R2 测试邮箱与一次性提交

- development 第十七节；三层 outbound、outbound_channels 和固定 ResendMailProvider。migration f219af0a01cf 三表 test_mail_channels/outbound_messages/outbound_approvals。UI `/outbound` 的 OutboundView/OutboundMailReview，现有绿系设计。
- 默认关闭。`SOLOOPS_OUTBOUND_` 前缀的 ENABLED/API_KEY/OWNER_ID/SHOP_ID/SENDER/TEST_RECIPIENT/DOMAIN_ID 在本机配置，绑定一个 owner/shop/本人发送地址/本人测试邮箱。浏览器不能覆盖地址或提交密钥；API key 必须支持域读、发送及记录回读。配置/密钥变化旧连接失效。当前没有真实账号或真实调用。
- 用户显式确认固定验证邮件后，GET 域 verified/name/sending，向部署名单邮箱 POST 一封不含业务数据的验证码邮件。8 位随机码只存 SHA256，15 分钟/5 次错误上限，不 API 回显。重复连接读原记录；间隔60秒，每店24h最多10次验证申请。可撤销连接，未知状态可凭实际邮箱验证码激活。
- 从当前已保存 OperationRun（含 Agent 保存结果）生成纯文本检查摘要，标识店铺/检查/身份/渠道/UTC窗口/币种/规则/截至/分支/前50候选，缺数据照标。支持修改主题/正文使审批失效。不是跨店完整日报，也没有给现有 Agent 七技能增加外发权限。
- R2 审批独立绑定邮件版本、完整地址/主题/正文摘要，来源/规则/时间门禁复用 OperationsService。单次审批10分钟；预授权1—24h、固定1次。每份摘要最多提交一次；拒绝保留取消，撤销只阻止未开始动作。R1 ID不适用。
- 用户→店铺锁+当前读→释放锁 GET 域状态→取锁再核对版本/来源/时效/频率→同事务写 dispatch_at/sending/used_at/audit并commit→唯一POST。账号24h最多10份摘要/最少60秒间隔；未知/清除仍计数。审计失败不发，提交后进程中断不返额度，sending超过60s读时转unknown。重复POST API回读，不触发供应商第二次发送。
- HTTP固定 api.resend.com、无代理/重定向，响应300000bytes/超时/耗时限制；UUID幂等键+soloops_dispatch标签。供应商24h键是额外保护，本地dispatch标记长期保留。明确拒绝也占用本次；网络/5xx/429/无回执unknown。
- 只读回查：有回执按ID；无回执查最近100封/最多5候选，或用户提供通道后台UUID。精确匹配地址/全文/标签/无ccbcc后采用回执与事件；未匹配保持状态，10秒回查间隔，不重发。accepted/delivered不能当收件证据；另存明确标注的人工收件声明与证据位置，系统未独立读取真实邮箱。
- 清批次先outbound.purge_batch再Operations删依赖：擦除主题/正文/收件说明，保留ID/摘要/状态。发送中清除，回调只记回执、不恢复正文。真实邮件不能撤回。A11/A28本地替身已过；A13/P0-External仍待本人通道/邮箱/真实提交及收件证据授权。
- 最终完整pytest242通过(69.04s)，本功能28项。Ruff123文件/mypy94app通过；Vitest10文件17项、Vue lint/type/build通过；完整Playwright24通过(42.8s)。迁移往返及两库无漂移。74SO/32验收均保留更新。
- E2E scripts/e2e_mail.py 只由强制_test的serve_e2e注册合成店铺/假provider/合成inbox；生产create_app无测试入口。pytest/E2E默认model_enabled=False，outbound测试只注入替身。不要让测试继承真实发信设置。
- 新页面截图系统Temp `soloops-outbound-{first-desktop,first-mobile,preview-desktop,preview-mobile,desktop,mobile}.png` 已查看，手机无横溢。Vue多语句点击模板改小函数解决生产构建解析错误，收件确认label排除grid解决布局；Vitest沙箱EPERM改require_escalated正常测试环境。Starlette/httpx弃用提示仍在。
- 文档/README/74SO/32验收已随main推送，全部P0尚未完成。缺外部条件继续沿用questions，勿重复询问。

## 前版完成：有界 R1 内部预授权切片

- 详见 development 第十六节。api/routes/authorizations.py → services/authorizations.py → repositories/authorizations.py，迁移3b35be067576两表 internal_authorizations/authorization_uses，AgentExecution.authorization_id FK。origin_execution_id为经service校验的溯源ID，避免循环FK。UI在/agent下方InternalAuthorizations.vue。
- 仅今日运营固定daily流程的propose_tasks：从当前waiting_approval预览创建，服务端重算一致；绑定owner/shop、渠道/身份、完整OperationScope(日期/币种/阈值/规则版本)、shop.data_revision、预览hash和candidate_count。模板natural/listing/support不能借此授权。严格确认bool、max_uses1—20、valid_hours1—168；来源valid_until更短则提前失效。
- 查看/游标分页/撤销/消耗回读/原预览/按完整授权范围运行；次数期限不可扩大修改，重建须新的当前预览。规则/数据变化即失效，恢复旧值不复活授权。规则页manual_only是默认策略，独立R1记录提供具体例外。
- 当前waiting候选可use_authorization，或StartAgent.authorization_id从绑定范围新建；检查通过→ready→保存→核验。_load/prepare/consume三处核对，撤销/过期/用尽/范围不符转待审，单次approve清除本节点绑定且不扣预授权。暂停恢复仍经下次校验。模型与外发无额外权限。
- 用户→店铺锁+FOR UPDATE当前读；保存候选/消耗/依赖/节点同事务savepoint，后续失败全部回滚，执行途中到期也回滚。两个已建立旧RR快照的执行争抢最后一次额度一成一409。每次成功保存计1次，复用候选也计次；HTTP/UUID回放不重复扣。
- 新可选authorization_id为None时从canonical hash去掉，兼容旧无授权UUID。单次审批与预授权语义独立。AuthorizationUse每execution唯一，记录operation_run、新增task ID/原状态none/新pending_approval/version、reused_count，无业务正文。
- 撤销只停止以后使用。另行revert仅将本次新增且仍为保存时版本的pending候选置rejected，历史留存，不返还额度；任一已编辑/处理/来源导致版本变化则整批拒绝，复用的既有任务不动。清批次沿原Agent/Operations擦除正文，授权保留范围hash和无正文审计且失效。
- 完整pytest214通过，本功能17项；Ruff112文件，mypy87app；Vitest9文件15项，Vue lint/type/build通过；最终完整Playwright23通过40.6s。仅合成数据，无外发/模型调用。
- 截图C:/Users/27363/AppData/Local/Temp/soloops-authorizations-{create-desktop,create-mobile,panel-desktop,panel-mobile,desktop,mobile}.png已实际查看。创建form继承.data-note flex导致挤列，已局部display:block修复并截图复验；手机无横溢。首次全量E2E遇Vite中途退出connection refused，再一次审批网络ERR_NO_BUFFER_SPACE；停止并行构建重启测试后最终23全部通过。不要给安全写入加自动重试以掩盖本机网络问题。
- 文档/README/74SO/32验收矩阵已提交。SO066文本偏好实际模型应用及R2测试外发仍待后续，全部P0尚未完成。

## 前版完成：SO-066 经营规则与版本记忆切片

- 详见 development 第十五节。`services/business_rules.py` 三层、`RulesView.vue`，入口 `/rules`；migration944381607c1c 单表 business_rule_revisions。按拥有者/店铺/渠道/数据身份严格隔离。
- 库存有效小时1—720、最低销量1—1000000、低毛利率上限−1000%—100%（两位）实际应用今日运营与 Agent 检查；低毛利为未舍入值不高于阈值。库存安全数量仍来自每条快照。独立库存/问数/利润试算页面保持各自显式口径，页面说明生效范围。
- 站点、仓库、物流、品牌语言、客服话术为有界手填参考；广告每日计划Decimal/Numeric(13,4)，空值未知，保存币种和依据。尚未用于模型生成/物流/广告执行，不发送给模型；不冒称全部记忆自动应用。automation仅manual_only，未知工具/自动发送值schema拒绝。
- 查看/保存/修改/撤销/重置/恢复；每次追加版本，previous_id/restored_from_id留血缘。expected_version+用户锁→店铺锁→当前读，并发一成一409。恢复创建新版本，不能复活旧审批。撤销/重置当前值清空回24小时/1件/20%，停止约束，历史留存明确告知。历史50条游标分页，单版读取。
- OperationScope.rule_revision_id随检查与Agent输入保存，无规则旧记录0。新执行必须当前版本且启用规则时阈值一致，拒绝旧预览和改参数绕过。重复运行UUID先回读既有记录，不因规则变化重写。Finding存rule_revision_id；task_key按规则版本区分新候选，旧处理记录保留标stale。
- task动作除reject/ignore均核对当前规则；Agent _load在读取/推进/审批/恢复/网络回写核对，标stale且version+1和步骤business_rules_changed。模型在途修改规则可成功，返回意图丢弃，已知费用照记；不创建待办。历史结果不重算。
- AppliedRules.vue用于工作台/Agent，加载当前版本并锁定生效阈值，加载失败禁止启动，切店/渠道/身份用请求序号丢弃迟到结果。历史规则有链接。页面沿用设计系统，确认框check-label、手机无横溢。
- 完整pytest197通过（本功能18项）；Ruff106文件、mypy82app文件；Vitest8文件13项；Vue lint/type/build通过；完整Playwright21通过(34.3s)。测试为合成数据，模型test_double，未外发/未付费调用。
- 最终首屏/全页截图C:/Users/27363/AppData/Local/Temp/soloops-rules-{desktop,mobile,first-desktop,first-mobile}.png均已实际查看，不提交。Browser plugin absent，使用repo Playwright。一次全量测试服务中途退出，重启后21全部通过；登录前session401为预期，控制台检查在登录后。Starlette/httpx弃用提示仍在。
- 文档、README、74SO/32验收矩阵已提交推送。SO066仍待可撤销预授权和后续业务对文本偏好的明确应用；不要标全部P0完成。

## 前版完成：SO-054 独立新品利润计算器

- 详见 development 第十四节，`services/profit.py / profit_rules.py`、`ProfitView.vue`。入口 `/profit`，三层服务与三表 profit_studies/scenarios/fees；金额/费率 Numeric(13,4)，UTC 时间。
- 不需订单，单币种 1—5 方案，候选售价/采购成本及依据；九类费用（头程/尾程/平台/仓储/包装/广告/退款损失/税费/其他分摊）每类固定单件金额或售价比例。空值未知，显式零须依据，最多四位小数/1亿元，单项比例≤100%。不换汇/不自动推税制和退款概率。
- Decimal40位局部精度；采购毛利、已填费用、已知费用后余额分别输出，余额率HALF_UP四位，零售价未知。金额JSON定点字符串，前端不转Number。四组敏感性：售价−10%/原值/+10%、采购成本+10%，不改变未知项。
- 九类齐全且总售价比例<100%才给 `(采购+固定费)/(1−比例)` 保本价，JPY向上取整1，其他支持币种0.01；只是已填假设覆盖价，不保证真实不亏。复杂阶梯费率/换汇待扩展。
- 保存UUID+规范化内容hash绑定拥有者/店铺，数字尾零和费用顺序规范化；并发用户锁与当前读同一记录。存档输入/依据/规则版本，不接收前端计算结果。未知规则版本不静默改算。
- 清除物理删除费用/方案，擦除标题，留无正文tombstone/审计，旧UUID不能复活；独立手填方案不依赖导入批次，清批次不清它。
- 页面编辑立即隐藏旧结果，计算后折叠输入，可复制、对比、展开公式/依据/敏感性、保存/刷新回读/清除；手机可横向滚表，卡片直接给主金额与缺口。新增导航仍保留矮桌面侧栏滚动。
- 完整pytest178通过后新增极小金额/最大边界和Decimal定点序列化，本功能最终18通过（总量179，CI已通过）；Ruff99文件、mypy77 app文件，Vue lint/type/build，Vitest7文件12项，完整Playwright19项通过。最终截图在系统Temp `soloops-profit-{input-desktop,input-mobile,desktop,mobile}.png`，均已实际查看，合成数据无页面横溢。
- 文档、README、74SO/32验收行已更新并推送。无真实模型/外发调用。

## 前版完成：受控执行层

先读 `docs/development.md` 第十三节及 `services/agent.py / agent_skills.py / agent_model.py`。原始业务服务保持可用。

- 新增 `/agent` 执行台、AgentRunReview.vue、API/schema/model/repository三层；四表 agent_executions/agent_steps/agent_sources/agent_policy_sources。
- 七项白名单技能：data_check、metrics、propose_tasks、product_context、listing_draft、message_context、support_draft，覆盖五类P0基础能力。每项有名称/版本、typed输入输出schema、来源/权限/工具/读写范围/风险/前提/副作用/幂等/重试/失败/核验元数据；与可信代码契约不符即阻断。只调用现有受控服务，无任意脚本入口。
- daily：只读检查→实际有异常才等待审批→保存异常候选→回读核验；空/缺数据记录各分支后结束。候选最终处理仍到工作台逐项批准/忽略/完成。listing缺参数等待输入，完整则审批保存本地模板草稿；support保存未核验订单/未选政策的人工接管草稿。生效审批/政策核验复用业务页。
- metrics口径是全店所选身份与窗口（复用 AnalyticsService），不按渠道；界面明确。daily按所选渠道。商品上下文核对身份，消息核对身份+渠道。
- `UnitOfWork.defer_commits()` 将既有服务提交改为内层flush，业务写入+依赖+步骤原子提交，失败节点savepoint回滚。请求UUID+内容散列幂等；版本并发一成一409。用户→店铺锁串行化与原服务一致。
- 每次advance仅一个节点；前端启动/恢复推进至等待或终态，刷新不执行。pause/cancel在节点边界生效。默认12步/累计执行120秒/模型0USD，上限100步/3600秒/10USD；恢复可增加总预算，累计量不清零。审批/暂停等待不计时。
- 临时SQL读错误1205/1213/2006/2013至多3次尝试，之后circuit_open；写入不自动重试。R3/未知技能/硬规则阻断立即停止，不换工具。blocked/circuit_open/unknown终态核对后新建任务；缺商品事实须补源后新建。
- 执行input/result及所有步骤输出登记批次/政策依赖；Listing旧值继承原版本全部来源。导入保守stale、库存UTC到期；清除依赖批次/政策擦除input/result/全部步骤正文/关系，保留无正文状态和审计。旧来源不能批准或恢复。
- 实际OpenAI Responses HTTP适配只做意图路由 daily/analysis/listing/support/blocked。部署设置 MODEL_ENABLED、MODEL_API_KEY、MODEL_NAME、MODEL_INPUT_USD_PER_MILLION、MODEL_OUTPUT_USD_PER_MILLION，用户任务allow_model和美元预算双门禁；缺项not_configured，不调用网络。
- 仅发送最多500字目标及固定分类指令，不发送导入业务数据/数据库凭据；固定官方HTTPS端点、无重定向、不继承环境代理、store=false、256输出tokens、200000bytes响应。UTF8输入包络+协议余量保守预留、usage Decimal核算；费率与真实账单要核对。
- `_claim_model → decide → _complete_plan`：先提交租约/预算、释放锁再联网，回写重新核对租约/版本/来源。暂停/取消/导入变化丢弃后续动作，但已知费用照记；超时/无usage/无效结构/租约中断标model_result_unknown、保留预留、不自动重发。这不是业务外发通道的未知态验收。
- 当前真实LLM解释、Listing创作、多语言客服仍待接入；模型验证仅test_double/MockTransport，无真实供应商调用证据。四条完整AI MVP及全部P0未完成。
- 新导航导致矮桌面侧栏退出按钮越界，已增加纵向滚动及短窗口间距，完整E2E通过。不要移除该修复。

## 前版 Agent 验证

- 完整 pytest 161 项通过（新增23）；Ruff91文件规则/格式通过，mypy71个app文件通过。
- Vue lint/type/production build通过；Vitest6文件10项；最终完整Playwright17项通过。Agent桌面/手机来源→审批→预算暂停→提高预算恢复→核验→刷新→清除，以及手机空数据→模型待配置→取消实际通过。
- 最终1280x720/390x844截图已查看，无横向溢出，系统Temp/soloops-agent-{desktop,mobile}.png只含合成数据、不提交。Starlette/httpx弃用提示仍存在。
- 两库迁移/check及测试库回退往返通过。功能/验收矩阵维持74/32行。A14/25/26/27/29增补本地证据；A28业务外发仍待实现/授权。

## 前版业务不变量（详细见 development 各节）

- 导入 CSV/XLSX支持字段映射/模板/逐行纠错/覆盖确认/预览/提交/撤销/清除。商品键shop+SKU；订单shop+order+line；消息shop+channel+message_id；库存shop+channel+SKU。ImportBatch/Row版本加当前投影source_row_id，applied_revision决定有效顺序。撤销不复活已撤销祖先。
- 所有资源owner+shop约束，认证可能先建立RR快照，业务锁后必须当前读+populate_existing。用户→店铺→来源→派生锁序；响应commit前组装。金额Decimal/Numeric，UTC时间，业务显示显式时区。
- 分析订单窗[start,end)最长366天，最多10000行。paid/partially_refunded/refunded有效；qty×price−discount−refund，历史毛利用当前同身份/币种采购成本。未知不补零，成本/退款/费用缺失不宣称净利润，不跨币种排名。analysis_todos仍是独立基础记录，跨模块统一待办待继续。
- Listing事实门禁：标题完整商品名（可拼完整参数行），描述只选完整原文行；新增事实可存draft但不能approve。来源变化永久stale、恢复源行不恢复旧审批；多版本比较/复制血缘必须完整清除。生成器默认local_template。
- 客服订单号不能证明客户身份，订单关联须人工核验当前全部源行。同店/渠道/身份政策按主题/语言/市场/UTC有效区间筛选，冲突/退款混合意图/无可信物流/未知语言转人工。草稿存档不代表发送。来源/政策清除擦除整稿含人工文字；policy_epoch防清除后复活。
- 库存只据有时效快照与显式阈值，缺库存为unknown；不同渠道不合计共享库存，不由订单推算库存。
- 今日运营四类候选：订单来源未履约/部分履约、有效低库存、消息是否需回复核对、完整已知费用下低毛利。物流/平台/广告/跨期变化未检查，导出时间未知不以导入时间替代。单项10000行/最多500候选，超限整体拒绝。
- 运营task去重shop+channel+identity+kind+规则版本+相关口径+排序来源集合，不含无关revision；重跑保留ignored/rejected/completed/deferred。source_status和处理status独立，恢复旧源需实际重跑才current，库存过期不能批准。清批次擦除snapshot/note/due/event.details及来源，独立内容保留。

## 下一步立即开发

1. 核对 CI37833883370，失败修复；当前 main d43d29bd9a3c6e4d8a2d650a69a9e6d2a4fe7366。读取 AGENTS、本文、development 十三—十七节与冻结需求/矩阵。
2. 立即开发 SO-002 跨店铺经营总览与运营日报 P0 切片：按店铺/平台/市场/时间与币种分组；前日/近7/近30/自选对比；库存/客服/营销等缺口明确未知；金额Decimal，不把多个币种合计，不冒称全渠道实时。总览/日报事实可下钻已有来源行与批次，持久摘要须处理来源变化/清除。
3. 随后统一任务/草稿/审批驾驶舱，四条MVP可配置模型生成与解释等剩余P0，再P1/P2。OpenAIResponses目前仅意图路由，不是四条MVP完整AI能力；无模型预算/外发账号时完成适配和替身，真实验收单列待授权。R2此轮已经有本地受控发送/未知回查路径，别重复从零实现。
4. 每功能先查官方/GitHub并更新references/许可证/适配，完成前后端/迁移/测试/development/interview/74SO/32验收/testing/questions，再正常提交推送main和context-memory，不强推。不重复询问questions已有外部条件。
5. 上下文压力时落盘推送后按授权创建新聊天独占接续；原聊天停止修改，不让两个聊天同时改工作区。
