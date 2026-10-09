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

- 仓库 https://github.com/Changxin-YR/AI-E-commerce-Agent.git 。main **9ae51bcea5b281839ff74da0f3dccfa3a35ac1e2** 已正常推送，feat: schedule calendar operating reports with persistent evidence；工作区干净。
- 本提交 CI https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37884256378 最后观测 in_progress，接续先核对，失败先修。前提交 fa5cba5 的 CI37882272193 已 completed/success。
- backend/.venv Python3.11、frontend/node_modules；Docker MySQL8.4开发3307/测试3308。迁移 head **54df8f2c09a1**；周期记录新增 task/report_id，开发库已升级，隔离测试库 down/up/check 通过。
- 开发 API8000 隐藏重启，launcher PID **23520** / API PID **13608**；前端5173 Node32612。两者健康200。API无热重载，后续先重核端口、命令行及父进程再停止，不凭旧PID操作。
- .env、backend/.env、.local/test.env、.local回执/日志和.context-memory从main忽略。密钥不打印、不提交、不写聊天文档。backend/.env已有百炼key，无需索取/复制。
- pytest、Playwright、迁移回退共用隔离_test库，必须串行。测试入口 _env_file=None、显式覆盖provider/key/name/rates并关闭真实模型/邮件；开发只用MockTransport/合成替身。
- Windows数据库连接沙箱WinError10013、Vitest缓存rename EPERM在普通允许执行环境通过。长浏览器测试可用 exec_command tty=true 加忽略目录日志。Start-Process 一律 WindowStyle Hidden。
- **E2E入口已改为生产构建预览**：npm run test:e2e 先 pretest:e2e → build-only，再 Playwright；测试前端命令 npm run preview -- --host 127.0.0.1 --port 5174 --strictPort，代理测试API8001、CI=true，Playwright管理启停。完整40项已通过。不要直接用 npx playwright test 而忘记先构建。
- 本机 Vite 8.3.4 开发转换服务完整E2E多次中途断连；子进程观察捕获退出码3221226505(0xC0000409)，具体原生模块未定位。简单stdin实验未复现关闭。生产预览全套通过；开发5173仍为原Vite，不声称原生原因已修复。诊断脚本/日志均在.local忽略。
- Firecrawl已知402，不重复调用计费接口；使用官方网页/GitHub工具，不临时编写网页抓取脚本。
- CI状态用GitHub connector github_fetch读取REST并解析structuredContent.content，只输出状态摘要；同URL有时返回缓存旧状态，可使用有效参数如 ?exclude_pull_requests=true 重新核对。

## 最新成果：SO-006 自然日周月经营报表调度

- development二十六、testing二十一。ScheduleConfig.task=operations/report，report_currencies为空表示所有币种分别统计；原计划默认operations，旧创建请求散列兼容。迁移54df8f2c09a1为ScheduleOccurrence新增task与report_id外键，旧记录补operations，历史类型不随计划修改。
- schedule_reports.report_scope：日报前一自然日；周一取上一完整周；每月1日取上一自然月；比较更前一完整周期。显式IANA、跨年/闰月/DST，含开始不含结束；月对比天数可不同。周报固定weekday0、月报month_day1，报告独立阈值且覆盖所选店铺/身份全部导入渠道。
- 定时窗口锚定原计划时刻，跨日补跑不漂移；复用最近一期24小时内恢复/旧期合并/暂停不补跑。手动按当前时间取最近完整报告期，新UUID允许刷新当前数据，同UUID回放原结果。
- 报告经页面确认按期保存，OverviewService.save_scheduled与人工save共用锁后计算和保存；人工仍验expected_revisions。用户→店铺→计划锁和defer_commits覆盖报告、OverviewSource、周期通知与下次时刻，失败整笔回滚，恢复错误仅固定码并暂停。
- 复用Decimal、分币种、本期/对比期依赖、缺失保持未知。库存/成本/未结待办为生成时投影；报告通知只引用ID，从Overview读stale/clear和源行，清除任何依赖擦正文。巡检保持原Agent daily逐次审批；没有真实模型或外发调用。
- 页面新建/修改类型、周期、币种与确认，修改清同意；epoch丢迟到巡检规则，切回巡检重新绑定。通知显示报表已保存与报告深链，桌面/390px配置→生成→回读→清除通过；普通视口截图已查看，系统Temp soloops-schedule-reports-{desktop,mobile}.png。
- 新后端21项，定向70/23.37s，完整 **448 passed /186.09s**；Ruff159文件、mypy116app。Vue lint/type/build通过，Vitest17文件32/2.83s；最终测试Array.at改slice兼容后相关2/1.39s通过。定向E2E4/15.7s，生产预览完整 **40/1.6min**。
- 首次浏览器测试未展开库存details便检查可见性，已按实际操作展开后通过。隔离迁移down a364d8b4b6bf/up/check、开发upgrade与API重启已完成。22文件提交前路径/敏感模式检查通过，日志/凭据未提交。
- SO-006仍保留业务事件触发、紧急分级、评论/营销监测和授权外部通道，74SO/32验收/7长期E2E完整保留。

## 既有成果：SO-006 持久本地定时巡检与站内通知

- development二十五、testing二十。新增 schedules三层、schedule_clock日历、scheduler worker；迁移a364d8b4b6bf有operation_schedules / schedule_occurrences。
- 卖家确认创建日/周/月计划（每月1—28日），IANA时区/UTC持久化，DST不存在时刻跳过，重复取fold=0。订单窗口[计划时刻-N×24h,计划时刻)，N<=365；库存/商品/消息取执行时投影，时效按真实当前时间。
- FastAPI lifespan每30秒扫描至多20到期计划，API运行时有效；SOLOOPS_SCHEDULER_ENABLED默认true。pytest和E2E显式false；专门lifespan测试开启真实worker，已验证自动运行与正常停止。
- 用户→店铺→计划当前读，计划+UTC周期唯一键。只处理最近一期，24小时内补跑，更旧周期合并起点；超窗记missed。创建/编辑/恢复从未来一期开始；暂停/撤销不补跑，撤销终态。
- 只用AgentService daily→data_check，有候选停waiting_approval，无候选保存缺口结束。LocalOnlyModel无网络，0费用、不绑定旧R1授权；原Agent再审批保存与工作台逐项处理。规则变化阻断并暂停，修改确认后恢复。
- defer_commits将执行/来源/通知/下次时刻同事务提交；Agent组合模式的OperationalError向外抛由调用方回滚。普通异常回滚后新事务比较版本/到期值，相符才记录无正文失败并暂停；数据库完全不可用待恢复扫描。
- 通知仅执行索引/周期结束状态，原Agent当前来源/审批另读，来源清除沿用原依赖擦正文。免打扰按计划时区延后未读列表，完整历史始终可看；已读幂等，50条游标历史，每店100计划上限。
- SchedulesView / ScheduleEditor沿用既有设计，桌面/手机配置修改、确认变更重置、暂停/恢复/撤销、立即检查、原审批深链、通知已读/刷新/清除已验。正常视口截图system Temp soloops-schedules-{desktop,mobile}.png已查看，390px无横溢。
- 完整pytest **427 passed / 146.96s**（新增29）；调度+Agent定向51/15.16s后补lifespan纳入全套。Ruff156文件、mypy115app；Vue lint/type/build、Vitest16文件30/2.96s；定向E2E2/11.2s、完整 **38/1.6min**。
- 完整E2E前两次Vite连接断开，第一次后续全部拒连，第二次5项通过后ECONNRESET，持久tty重新启动后38通过；不冒充前两次通过。首次新downgrade先删FK支撑索引被MySQL1553拒绝，改为按从表→主表drop_table后隔离down/up/check通过；开发库已upgrade。
- 32文件提交前路径/敏感token模式检查通过，.env与日志未提交。SO-006仍是首片；专用日周月经营报表、业务事件/紧急分级、评论/营销监测和外部通知继续保留。

## 既有成果：MVP01 运营模型概览

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

1. 先核对9ae51bc的CI37884256378，失败先修。读AGENTS、冻结稿、矩阵、development二十六/testing二十一；保持当前权限、数据与隐私不变量。
2. 继续不依赖外部凭据的P1 **SO-014 商品信息质量与批量运营**。先官方/GitHub资料和references，再检视商品导入投影、Listing/运营质量分支、来源依赖及审批层，自行确定可验收的本地首片并实际完成前后端闭环。建议先做商品质量检查、缺失/待核原因与可回读依据，必要的内部修订或批量动作仍需预览和审批；真实平台同步另守授权门禁。不能只写计划停工，不把当前无品牌/编码/图片字段的范围称完整检查。之后继续独立P1/P2。
3. 每功能完成相关测试/静态检查、桌面手机、development/interview/testing/questions及74SO/32验收，正常提交推送main/context-memory。pytest、Playwright、迁移回退严格串行；npm run test:e2e 自动先构建生产页面。每次启停服务重核端口和命令行。
4. 用户授权上下文压力下先落盘推送，再建本地接续聊天；新聊天接手后旧聊天停止修改，同工作区独占。未经用户明确要求不启动子代理。
