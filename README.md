# SoloOps 重点上下文

更新：2026-10-09。业务代码在 main；本分支只保存重点上下文，不合并到 main。

## 目标与授权

- 持续完成冻结稿 docs/requirements/SoloOps-V1.0.md。保留全部 74 SO、32 验收、7 长期 E2E；23 个 P0 当前仅为四条 MVP 的最小切片，计划不能称实现。
- 简体中文；Vue 3/TypeScript、FastAPI/Python、MySQL；接口→服务→repository，Agent 只能调用受控服务。沿用现有设计。
- 每功能先官方/GitHub 检索并更新 references（借鉴、许可证、适配）；实现前后端并验证，更新 development/interview-guide/testing/questions 与矩阵，正常提交推送 main/context-memory，不强推。
- 用户授权上下文压力时先落盘推送，再创建本地接续聊天；接手后旧聊天停止修改，同工作区独占。未经明确要求不启动子代理。
- 本机百炼凭据已配置；此前鉴权及累计 ¥0.01 合成测试一次性许可已用完。额外真实测试须独立授权，正常页面仍需数据同意与 USD 预算。A-13 真实邮件仍待本人通道、测试收件箱及授权。
- 密钥、真实客户数据、本机配置与日志不提交。已有 backend/.env 无需索取或打印。

## 当前提交、CI 与环境

- main **c652c9175ae026dd86bff2ec51ee319e8c62a43e** 已正常推送：feat: approve source-backed bulk product edits。主工作区干净。
- 本提交 CI https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37920901327 最后观测 in_progress；接续先核对，失败先修。交接基线cb6c585的CI37917649249已verify completed/success。
- GitHub connector github_fetch 读 REST，JSON 在 structuredContent.content；只输出状态摘要。同 URL 可能缓存旧值，可用有效参数 ?exclude_pull_requests=true 或按 head_sha 筛选 workflow runs 核对。
- backend/.venv Python3.11、frontend/node_modules；Docker MySQL8.4 开发3307/测试3308。使用项目容器 soloops-mysql-1 / soloops-mysql-test-1，本轮完整数据库回归和迁移通过。
- 迁移 head **d6f920a41b85**；c5e81a209d74 建 product_edits/product_edit_sources，d6f920a41b85 增 import_batches.origin（历史 file_import，人工 manual_edit）。隔离测试库 down7b92c4d16e80/up/check、开发库 upgrade/check 通过。
- 开发 API8000 已核实原9548/28420的uvicorn身份后隐藏重启：新launcher27088（实际PID后续重核）；前端5173 Node28144，CI=true 防标准输入退出。两者健康200，OpenAPI包含product-edits新路由。API无热重载；后续操作前重核端口与命令行，勿凭旧PID停止。Start-Process 一律 WindowStyle Hidden。
- pytest、Playwright、迁移回退共用 _test 库，严格串行。测试 Settings 显式禁真实模型/邮件/常规调度；本轮验证仅合成替身，专门 worker 测试才显式开启本地扫描。
- Windows 沙箱 socket10013、Vitest缓存rename EPERM须普通允许执行环境。若10061先查项目容器是否运行。长E2E可tty=true，日志重定向.local。使用 python -m mypy，直接mypy.exe曾出现uv trampoline路径问题。
- E2E用 **npm run test:e2e**：pretest:e2e先build-only，再由Playwright管理API8001与vite preview5174，CI=true、生产构建、代理隔离API。不要直接npx playwright test漏构建。
- 本机Vite8.3.4开发转换服务此前退出码3221226505/0xC0000409，具体原生模块未定位；生产预览完整回归通过，不声称根因已修。
- Firecrawl已知402，不重复计费接口；用官方网页/GitHub工具，不临时编写HTTP抓取脚本。

## 最新成果：SO-014 名称/参数本地批量修订

- development二十八、testing二十三。/product-edits：加载当前商品→最多50个选择编辑/共同前缀追加参数→保存草稿→全量差异及原行→明确审批→本地生效→历史/固定链接/当前数量→拒绝/撤销/清除。同用户/店铺/身份/渠道；目录沿用1000商品/2MB，修订正文1MB、祖先依赖1000批次。
- API→ProductEditService→repository。名称1—240字符、参数≤2000、理由1—500、重复/无改动/额外字段拒绝。保存原before/after、SourceReference、理由与shop.data_revision。批准仅收版本/hash/confirm，锁后逐项重读并验整店revision；任一冲突整批不执行，conflict/blocked逐项持久failed。无关导入也保守阻断；来源覆盖再恢复不能让旧批准有效。
- 审批后建立独立ImportBatch origin=manual_edit/人工修订标签及新ImportRow，raw保留依据批次/行、理由和旧名称/参数，corrections新字段、normalized完整新资料，金额原样继承。原文件独立。复用ImportService.commit更新Product.source_row_id和所有派生失效；新增SourceReference.origin，SupportSource显示人工依据。商品金额/SKU/库存/素材/外部平台未在本片修改范围。
- 创建UUID按用户唯一、摘要绑定；原创建请求回读当前状态。批准重放原版本/hash只返回已有结果；清除后不复活。defer_commits将来源/投影/审批/依赖/审计同事务，末尾审计错误整体回滚。
- ProductEditSource登记直接来源及全部人工祖先。ImportService.withdraw新增外层协调：读所有affected（含本记录输出批次），后代优先用_withdraw_single处理输出，再处理原批次；完整祖先使其无需递归。撤销pending→stale，applied→revoked；清除snapshot/依赖/新源行及下游全文。独立文件与修订保留，撤销按仍committed来源重建，已撤祖先不复活。导入页确认文案提示依赖影响。
- 详情同时展示曾执行数量/current_count（锁定当前读）；后续独立导入可覆盖人工版本，导入差异与人工当前源行比较。前端epoch丢迟到回包，变更重置审批；保存/刷新/批准/清除先隐藏正文，失败不残留；未知保存用同UUID回查，历史回填身份/渠道。批量拼接字段过长在发送前指出SKU并保留编辑。
- 新后端最终21/10.55秒；完整pytest **486/206.81秒**。Ruff规则/格式175文件、mypy127app。最终Vue type-check/lint/build通过；新组件7/1.64秒，完整Vitest **19文件45/3.16秒**。
- 新E2E2/12.2秒，完整 **44/1.7分钟**；最后增加批量共同填入和超长前端检查后定向2/13.6秒。desktop1440x1000/mobile390x844页面身份/非空/无overlay/登录后console/交互/无横溢通过。系统Temp soloops-product-edits-{entry-}{desktop,mobile}.png已看。
- 首轮E2E业务完成但console断言将正常未登录401计为错误；调整为登录后检查并复验。Browser插件/browser skill缺席，按frontend-testing-debugging用项目Playwright。全套测试、迁移回退严格串行，真实模型/邮件均未调用。36暂存文件路径/敏感token模式检查通过，未提交日志/凭据。

## 既有 SO-014 质量检查

- /product-quality 首片见development二十七/testing二十二。当前主档按身份/渠道/大小写SKU前缀检查，1000商品/2MB整体拒绝；名称/参数占位、重复/冲突、售价/成本/币种、零售价、相似SKU、六类描述关键词。missing/review明确；品牌/编码/素材/类目/平台未检查。
- 保存范围/revision/hash/UUID/确认，锁内重算，报告/全部已检查商品来源/审计同事务。来源变化stale，清任何依赖擦snapshot/SKU前缀/所有关联，独立报告保留，旧UUID不复活。前端epoch、历史范围回填和隐藏失效正文已有验证。

## 既有主要能力与不变量

- owner/shop约束；用户→店铺→来源→派生锁序；Decimal/Numeric，UTC持久化和IANA显示。锁后当前读防RR旧快照与ORM缓存。
- 商品键shop+SKU、订单shop+order+line、消息shop+channel+message_id、库存shop+channel+SKU；source_row_id及批次决定当前投影。撤销不复活已撤祖先，来源恢复不自动复活旧审批；清除全依赖正文，仅留必要无正文审计。
- SO-006持久本地巡检：计划日/周/月、日历DST、用户→店铺→计划锁、唯一周期、最近一期24小时恢复、更旧期合并、暂停不补跑；Agent daily→data_check无网络，有候选仍逐次审批。免打扰、已读、50条游标，每店100计划。
- SO-006专用报表：上一自然日、周一上一完整周、每月1日上一自然月，对比更前完整周期；锚定原计划时刻，分币种。手动新UUID当下投影、同UUID回读原报告。OverviewService同事务保存OverviewSource/报告/通知/下期，通知只引用ID，来源清除复用Overview。业务事件、紧急分级、评论营销、外部通道仍后续。
- 今日运营四类：来源待核履约、有效低库存、消息回复核对、已知成本低毛利。单项10000行/最多500候选、超限整体拒绝，重跑保留人工状态。无物流/广告/平台及未比较销售为未检查。
- MVP01 daily_model：data_check→explain_operations→propose_tasks审批→verify。仅发目标、范围、聚合分支和候选数；本地恢复全部9分支/4类候选、缺口与建议，不能删候选、改金额、审批或外发。双同意与expected_operation_hash绑定完整快照；调用前后/审批/保存复验。
- 问数：窗口[start,end)最多366天/10000行；同身份同币种当前成本估历史毛利，费用缺失不算净利。question_plan→metrics→explain_analysis→analysis_todo→verify，数值本地渲染、coverage/fees强制保留、最多20匿名SKU。
- Listing模型只选标题参数并排序全部完整参数，描述不可漏事实；来源/当前基线网络前后/保存复验；候选保存与本地生效独立审批，依赖含比较旧版。去重保留人工状态。
- 客服规则与模型意图取并集、固定事实/政策ID、本地中英模板和完整FAQ组装；敏感/冲突/未知语言转人工。消息/政策双同意绑定源行、政策版本、全部订单行人工核验；原文可能有个人信息，明确预览。全部已发送政策登记清除依赖；语义检索、自动语言检测、多轮后续。
- 模型openai_responses/dashscope_chat固定官方端点，无工具/重试/代理/重定向，有界JSON。预算预留/持久租约网络前提交，返回复验；已知usage拒答或无效仍计费，未知保留预留不重发。Agent默认12步/120秒/0USD，恢复提高总预算不归零；白名单临时只读最多3次，写不重试；defer_commits/savepoint保证业务与步骤/审计原子。
- R1预授权绑定范围/规则/来源/次数/时效，不授权未来任意快照。R2 Resend默认关闭，仅本人验证测试邮箱/全文摘要一次；未知只读回查不重发，实际送达待验。
- 跨店Overview按币种、显式时区对比与全依赖；统一工作台10类元数据UNION ALL、稳定keyset，读取不执行，深链回原服务权限。

## P0边界与接续起点

- p0-local-review.md记录4 MVP、23 P0最小模块、32验收边界。A01—12与A14—32共31项本地适用证据通过；A13真实测试邮件仍待本人通道/收件证据。真实模型全面质量与七条长期E2E未完整验收。
- 接续先核对c652c91的CI37920901327，失败先修。读AGENTS、冻结稿、矩阵、development二十八/testing二十三；新聊天独占主工作区，旧聊天停止修改。
- 下一切片选择不依赖外部凭据的 **SO-056 自定义实际费用记录与费用核对首片**。先检索官方/GitHub更新references，读SO-053/055/056/057及现有analytics/profit分层，设计并实际完成前后端有界录入→明确归属/币种/发生时间/事实依据→确认保存→当前/历史回读→修改版本/撤销清除的最小业务闭环。金额Decimal/Numeric、UTC/IANA、用户/店铺/身份隔离、幂等、审计同事务、重复/失效来源和依赖清除可验。实际费用与SO-054新品假设费用分开；未有平台账单不伪称对账通过，缺完整费用/归属不输出精确净利。自行确定最小合理分摊/订单关联边界，避免擅加真实费用或静默改变既有毛利。
- 自行确定技术方案并完成实现，不只写计划停工；持续推进独立P1/P2。每功能更新全部跟踪文档、测试/静态检查/桌面手机后正常推送main/context-memory。上下文压力时先推送再创建接续本地聊天，创建后旧聊天停止修改；未经用户明确要求不启动子代理。
