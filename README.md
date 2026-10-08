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
- main HEAD/当前功能提交：`abb9f798ee156dc40b28f67b34bea2131868e86a`，已推送；主题 independent product profit scenarios。
- 本功能 CI：https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37823550243 ，最后观测 in_progress，接续先核对并修复失败。
- 前版受控 Agent `d1eda91` CI 37820719900 已 completed/success。
- 前版补充提交 `10fa1df` 的 CI `37816007090` 已 completed/success；运营 `3531ce7` 的 CI `37815482720`、库存 `53b7d72` 的 `37811072990`、客服 `d3b9be1` 的 `37808536888` 均已 success。
- backend/.venv Python 3.11、frontend/node_modules、Docker MySQL 8.4 开发3307/测试3308。日常服务8000/5173；Playwright自动启动8001/5174。
- .env、backend/.env、.local/test.env 是忽略的密钥/本机配置，不打印、不提交。Windows 用 .venv/Scripts/python -m；MySQL、Node子进程、Git写常需 require_escalated。
- pytest 与 Playwright 会清理隔离 _test 库，必须串行；迁移回退也等测试结束。测试与 E2E 入口强制 model_enabled=False。
- 当前迁移 `a0188d77d6c6` 已应用两库；`.local/verify_profit_migration.py` 已验证 _test 回退 e84b5e7e8dd1→升级/check；开发库只升级/check，两库无漂移。MySQL回退不要先删FK支撑索引，直接按依赖删除表。
- Firecrawl 已确认402，使用官方网页/GitHub connector，不反复调用计费端点，不临时写抓取脚本。GitHub Actions用 github_fetch REST，解析 structuredContent.content，只输出摘要；fetch_commit_workflow_runs不适用于main push。

## 最新完成：SO-054 独立新品利润计算器

- 详见 development 第十四节，`services/profit.py / profit_rules.py`、`ProfitView.vue`。入口 `/profit`，三层服务与三表 profit_studies/scenarios/fees；金额/费率 Numeric(13,4)，UTC 时间。
- 不需订单，单币种 1—5 方案，候选售价/采购成本及依据；九类费用（头程/尾程/平台/仓储/包装/广告/退款损失/税费/其他分摊）每类固定单件金额或售价比例。空值未知，显式零须依据，最多四位小数/1亿元，单项比例≤100%。不换汇/不自动推税制和退款概率。
- Decimal40位局部精度；采购毛利、已填费用、已知费用后余额分别输出，余额率HALF_UP四位，零售价未知。金额JSON定点字符串，前端不转Number。四组敏感性：售价−10%/原值/+10%、采购成本+10%，不改变未知项。
- 九类齐全且总售价比例<100%才给 `(采购+固定费)/(1−比例)` 保本价，JPY向上取整1，其他支持币种0.01；只是已填假设覆盖价，不保证真实不亏。复杂阶梯费率/换汇待扩展。
- 保存UUID+规范化内容hash绑定拥有者/店铺，数字尾零和费用顺序规范化；并发用户锁与当前读同一记录。存档输入/依据/规则版本，不接收前端计算结果。未知规则版本不静默改算。
- 清除物理删除费用/方案，擦除标题，留无正文tombstone/审计，旧UUID不能复活；独立手填方案不依赖导入批次，清批次不清它。
- 页面编辑立即隐藏旧结果，计算后折叠输入，可复制、对比、展开公式/依据/敏感性、保存/刷新回读/清除；手机可横向滚表，卡片直接给主金额与缺口。新增导航仍保留矮桌面侧栏滚动。
- 完整pytest178通过后新增极小金额/最大边界和Decimal定点序列化，本功能最终18通过（总量179，完整179待CI）；Ruff99文件、mypy77 app文件，Vue lint/type/build，Vitest7文件12项，完整Playwright19项通过。最终截图在系统Temp `soloops-profit-{input-desktop,input-mobile,desktop,mobile}.png`，均已实际查看，合成数据无页面横溢。
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

## 当前验证

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

1. 先核对本功能CI 37823550243；失败则修复。读取AGENTS、此文、development第十三/十四节和冻结稿下一功能相关章节。
2. SO-054 P0最小切片已完成。下一步做 **SO-066 经营规则/偏好及明确生效条件**，随后可撤销预授权；先查官方/GitHub记录references，再完整前后端及测试文档提交推送。不要仅存一些没有实际生效位置的设置并宣称全部完成。
3. 然后继续全部剩余P0（经营偏好/可撤销预授权、跨店总览/日报、统一任务、可配置模型对四MVP的生成/解释、受控测试发信通道与未知结果回查等），依冻结稿逐项推进，再P1/P2。不要停在阶段性计划，不把路由模型当完整AI内容生成。
4. 无真实模型预算/账号授权时完成可配置适配及测试替身证据，真实验收单列待授权；不重复询问questions已有问题，不外发。
5. 每功能验证与文档/矩阵更新、正常提交推送。上下文压力时落盘并按授权创建新聊天接续，禁止两个聊天同时修改工作区。
