# SoloOps 重点上下文

更新：2026-10-09。业务代码在 main；本分支仅维护稳定约定、进度、验证和接续起点，不合并到 main。

## 目标与授权

- 持续完成冻结稿 docs/requirements/SoloOps-V1.0.md：先 23 个 P0 最小模块、四条 MVP 和 A-01—A-32 本地适用验收，再 P1/P2。保留全部 74 SO、32 验收行和七条长期 E2E；计划不能称实现。
- 简体中文；Vue 3/TypeScript、FastAPI/Python、MySQL。接口→业务服务→repository，明确类型与小函数；Agent 只调用受控服务。沿用现有 Vue 设计。
- 每功能先检索官方/GitHub 资料并更新 references（借鉴、许可证、适配）。完成前后端、测试和静态检查，更新 development/interview-guide/testing/questions/功能与验收矩阵，正常提交并推送 main 和 context-memory；禁止强推。
- 用户授权上下文压力时创建新本地项目聊天接续。先落盘推送，新聊天接手后旧聊天停止修改。未经明确要求不启动子代理。
- 本机百炼凭据已接入。用户先前明确批准官方端点鉴权及累计 ¥0.01 合成测试已执行完毕；额外真实测试不能沿用此一次性授权。正常页面任务仍须数据同意与 USD 预算。
- 真实经营数据、历史成本/费用、自有测试邮件通道/收件箱、项目许可证等集中在 questions；独立开发继续，不重复索取密钥和未新增问题。

## 当前提交与环境

- 仓库 https://github.com/Changxin-YR/AI-E-commerce-Agent.git 。main **8fdd985d470804124f859b356695fa76c8c6823e** 已正常推送，feat: add grounded operations overview and P0 local review；工作区干净。
- 本提交 CI https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37880173315 最后观测 in_progress，接续先核对，失败先修。前提交517d497的CI37878451567已 success。
- backend/.venv Python3.11、frontend/node_modules；Docker MySQL8.4开发3307/测试3308。迁移 head **86df84dc129a**，本轮无新迁移。
- 开发API8000已核实原父子进程后隐藏窗口重启，新 launcher PID **44420**；前端5173原Node32612，两者健康200。API无热重载，改动后重启须重新核实实际端口进程，不能凭旧PID停止。
- .env、backend/.env、.local/test.env、.local回执/日志和.context-memory从main忽略。密钥不打印、不提交、不写聊天文档。backend/.env已有百炼key，无需索取/复制。
- pytest、Playwright、迁移回退共用隔离_test库，必须串行。测试入口 _env_file=None、显式覆盖provider/key/name/rates并关闭真实模型/邮件；开发只用MockTransport/合成替身。
- Windows MySQL/Node/Git写/联网常需允许的普通执行环境；Vitest沙箱缓存rename EPERM在普通环境通过。Start-Process一律WindowStyle Hidden。终端命令保持正确workdir。
- Firecrawl已知402，不重复调用计费接口；使用官方网页/GitHub工具，不临时编写网页抓取脚本。
- CI状态用GitHub connector github_fetch读取REST并解析structuredContent.content，只输出状态摘要；fetch_workflow_run_jobs有时读到旧状态。

## 最新成果：MVP01 运营模型概览

- development二十四、testing十九。daily_model：data_check→explain_operations→propose_tasks（审批）→verify。复用现有十一项技能及OperationsService，无新迁移。
- operation_explanation只允许branch_ids/check_ids；模型排序概览和建议，本地恢复全部九个检查分支、四类候选计数、缺失原因和适用核对建议。模型不能删除候选、修改金额、批准事项或外发；有候选必待审批，无候选保留未知并结束。
- 请求仅目标原文、范围、分支名称/状态/行数、候选类型计数与固定建议。分支详细reason、SKU、订单号、文件名、消息正文、具体业务金额留本地。目标正文须用户核对。
- operations/preview→model_context返回CheckPreview与摘要，目标和聚合数据双同意，expected_operation_hash绑定完整快照。范围/目标/预算/快照变化清同意；组件epoch丢迟到响应，加载/刷新/错误立即清摘要。
- Agent网络前、回包后、审批读取复验当前完整检查；库存时效/规则/投影改变阻断。RunInput.expected_preview_hash在OperationsService.run同锁事务中重验；原有去重、处理状态、依赖、步骤与审计原子性沿用。
- 来源清除擦输入/概览/步骤，在途回包只记已知费；暂停/取消/变更丢解释，未知费保留预留且不重试。原R1预授权仍只适用daily固定流程，daily_model逐次审阅批准。
- OperationModelContext/OperationNarrative/OperationFindingPreview提供聚合发送预览、完整概览、每个候选事实和源行。业务深链带身份/渠道，回到工作台可批准/完成；刷新保持解释。桌面/手机实际验证。
- 完整pytest **398 passed / 140.32s**，新24项 /19.58s；Ruff147文件、mypy108app；Vue type/lint/build，Vitest16文件30项/2.32s；Playwright定向2项12.8s、完整 **36项/1.4min** 通过。
- 完整E2E首轮旧测试因候选增加来源入口出现重复定位，已限定到汇总容器；同轮临时Vite连接中断，重启完整回归36项通过。未归因于业务错误。手机截图已改普通视口，确认非聚焦skiplink不在视口、无横溢。系统Temp soloops-operations-model-{desktop,mobile}.png不提交。
- 暂存30文件检查确认无私密路径/配置值，main已推送。

## P0 本地复核结果

- docs/p0-local-review.md记录四条可重复操作、全部23个P0最小能力、32验收边界。A01—12和A14—32共31项本地适用行为有已通过证据；A13真实测试邮件仍缺账号/收件箱/授权，准确阻塞。模型协议与本地持久闭环用替身通过，真实模型全面质量不能据此宣称通过。
- 四条MVP均有数据库记录、审批/状态/来源与回读。百炼真实路由及Listing合成编排有独立证据，其余真实问数/客服/运营质量仍待独立授权验证。七条长期E2E未完整验收。
- 23个P0仅实现支持四MVP的最小能力；完整工作流编辑/语义检索/自动语言检测/多轮/复杂库存等后续范围仍保留。P0本地逻辑已形成稳定回归基线，可继续不依赖外部授权的P1工作；不能声称全部长期模块完成。

## 已有业务不变量

- owner/shop约束；用户→店铺→来源→派生锁序，锁后当前读和populate_existing避免RR旧快照；Decimal/Numeric，UTC持久化和IANA显式显示。
- 导入键商品shop+SKU、订单shop+order+line、消息shop+channel+message_id、库存shop+channel+SKU；source_row_id与批次版本决定投影。撤销不复活已撤祖先，来源恢复不自动复活审批。清除擦所有派生全文和依赖，保留必要无正文审计。
- 今日运营四类：来源待核履约、有效低库存、消息回复核对、完整已知成本低毛利。单项10000行/最多500候选，超限整体拒绝；未授权物流/广告/平台和未比较销售变化为未检查。候选重跑保留完成/忽略/延期状态。
- 分析时间窗[start,end)最多366天、10000行；同身份同币种当前成本估历史毛利，费用缺失不算净利，不跨币种排名。模型question_plan→metrics→explain_analysis→analysis_todo→verify，数值由本地渲染，coverage/fees强制保留，匿名SKU最多20。
- Listing模型只能选标题参数、排序全部完整参数；描述不能漏事实。来源/当前生效基线网络前/后/保存复验；候选保存与最终本地生效各自审批；依赖包含比较旧版。去重保留人工状态。
- 客服模型支持意图补充并与规则取并集，固定事实和政策ID，本地中英模板与唯一完整已核对FAQ組装；敏感/冲突/未知语言转人工。政策本地主题筛选，语义检索和多轮未做。双同意绑定消息源行/政策版本/人工核验全部订单行。消息原文可能含个人信息，页面明确展示；结构化订单号等留本地。全部已发送政策（包括未被选中者）登记清除依赖。
- 模型工厂openai_responses/dashscope_chat，固定官方端点、无工具/重试/代理/重定向，有界JSON协议。生成768输出tokens、60KB请求/200KB响应；百炼输出预留额外10token。网络前费用预留和租约提交释放锁，回包后校验版本/来源。已知usage拒答或无效仍计费，未知保留预留不自动重发。
- 百炼本机qwen3.7-flash北京已配置；费率0.24/0.96 USD每百万token按保守预算换算而非实时汇率/账单。先前鉴权200、真实合成路由103/11和Listing203/51tokens，目录估算合计¥0.0001108/¥0.01；原回执.local。额外真实测试须新授权。
- Agent默认12步/120秒/模型0USD，恢复提升总预算不归零；只读已知临时DB故障最多3次，写不重试；步骤和业务savepoint/defer_commits原子提交。
- R1预授权绑定预览范围/规则/来源/次数/时效，不能授权未来任意新快照。R2 Resend默认关闭，限本人验证测试邮箱/全文摘要一次；未知只读回查不重发，实际送达未验。
- 跨店按币种汇总、显式时区对比、保存全依赖。统一驾驶舱十类业务元数据UNION ALL，稳定keyset，读取不执行；深链回原服务，原服务决定权限。

## 接续起点

1. 先核对8fdd985的CI37880173315；失败先修。读取AGENTS、冻结稿、p0-local-review和矩阵；必要时读development运营/Agent/规则与授权章节。
2. 按冻结稿继续 **P1 SO-006 定时运营与经营通知**，先官方资料及references，然后实际实现。优先持久化本地定时检查、站内通知、暂停/恢复/撤销和可回读执行状态，显式时区/UTC、唯一周期去重、进程重启与错过周期的有界恢复。沿用受控Operations/Agent服务与权限规则；不能把旧R1快照授权泛化为未来新来源自动批准，也不能后台默认调用付费模型或邮件。外部通知继续等待原授权条件。设计时先读现有服务与需求，具体方案由接手聊天自行判断并完成验证。
3. 新切片完成相关测试/静态检查、桌面手机与文档后提交推送main/context-memory；用户目标是持续开发，不能只写计划停工。遇上下文压力按原授权先交接落盘再开新聊天，独占工作区。
