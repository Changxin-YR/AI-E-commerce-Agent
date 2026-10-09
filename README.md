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

- main **cb6c585309ac57f5a4f592ce42b307a5227b7829** 已正常推送：feat: inspect product quality with source-backed reports。主工作区干净。
- 本提交 CI https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37917649249 最后观测 in_progress；接续先核对，失败先修。交接基线9ae51bc的CI37884256378已completed/success。
- GitHub connector github_fetch 读 REST，JSON 在 structuredContent.content；只输出状态摘要。同 URL 可能缓存旧值，可用有效参数 ?exclude_pull_requests=true 或按 head_sha 筛选 workflow runs 核对。
- backend/.venv Python3.11、frontend/node_modules；Docker MySQL8.4 开发3307/测试3308。本轮恢复了已停止的 soloops-mysql-1 / soloops-mysql-test-1，均 healthy。
- 迁移 head **7b92c4d16e80**；隔离测试库 down54df8f2c09a1/up/check 通过，开发库 upgrade/check 通过。新表 product_quality_reports / product_quality_sources。
- 开发 API8000 已隐藏恢复：launcher9548 / 实际API28420；前端5173 Node28144，CI=true 防标准输入退出。两者健康200。API无热重载；后续操作前重核端口与命令行，勿凭旧PID停止。Start-Process 一律 WindowStyle Hidden。
- pytest、Playwright、迁移回退共用 _test 库，严格串行。测试 Settings 显式禁真实模型/邮件/常规调度；开发仅合成替身，专门 worker 测试才显式开启本地扫描。
- Windows 沙箱 socket10013、Vitest缓存rename EPERM须普通允许执行环境。若10061先查项目容器是否运行。长E2E可tty=true，日志重定向.local。使用 python -m mypy，直接mypy.exe曾出现uv trampoline路径问题。
- E2E用 **npm run test:e2e**：pretest:e2e先build-only，再由Playwright管理API8001与vite preview5174，CI=true、生产构建、代理隔离API。不要直接npx playwright test漏构建。
- 本机Vite8.3.4开发转换服务此前退出码3221226505/0xC0000409，具体原生模块未定位；生产预览完整回归通过，不声称根因已修。
- Firecrawl已知402，不重复计费接口；用官方网页/GitHub工具，不临时编写HTTP抓取脚本。

## 最新成果：SO-014 商品信息质量检查与报告

- development二十七、testing二十二。/product-quality当前主档检查→依据→确认保存→历史/固定链接回读→来源stale/clear与手动清除。仅本地确定性规则，无模型/外发/平台变更。
- 范围按用户/店铺/数据身份、可选来源渠道和区分大小写SKU前缀。最多1000商品、正文2MB，超限整体拒绝；所有返回行均保存，不因页面筛选丢依赖。
- product_quality_rules：名称/参数空值及整字段占位、重复参数行、按行属性:值的同名多值、售价/成本及币种缺失、零售价、异币种、NFKC+casefold+空白折叠的相似SKU、六类有限描述关键词。missing/review明确，零成本保留已知零。相似组完整计数、最多20个同行SKU示例，全部商品仍包含在报告。
- 品牌/GTIN/MPN、图片规格、类目属性和平台/跨店一致性明确未检查；空数据全部未检查。不宣称完整质量或平台合规。批量编辑/价格/库存/素材/多店同步仍后续。
- API→ProductQualityService→repository；用户→店铺锁后with_for_update/populate_existing当前读。保存仅接收范围、revision、预览hash、UUID和确认，重新计算；hash覆盖规则/范围/全文证据，排除checked_at。报告/所有来源/审计同事务。同UUID回放当前持久状态，改变输入拒绝；清除后回放不复活。
- 导入提交/撤销/清除保守使本店报告stale（沿用全店data_revision，包括其他类型数据）。撤销恢复不会复活旧current。依赖包含全部已检查商品，包括无问题行；任一批次清除擦snapshot、SKU前缀和所有关联，独立报告保留。主动清除同样幂等。
- ProductQualityView按范围epoch丢迟到响应、变更清同意；刷新/保存/清除先隐藏快照。历史回读同步回填scope；acceptReport用restoringScope抑制内部回填触发reset，清除也同步擦表单SKU前缀。ProductQualityResult缺失/待核筛选、每页20个、原始行复用SupportSource。
- 新后端17/7.38秒，完整pytest **465/168.32秒**；Ruff规则格式167文件、mypy122app。Vue最终lint/type/build通过；完整Vitest18文件37/3.42秒，最终清除前缀修订后相关组件6/1.19秒通过（当前总用例因此多1，未把未跑的全套计为38）。
- 新E2E首轮2/10.5秒；范围回填后完整 **42/1.6分钟**；最终清除前缀修订定向2/8.9秒通过。桌面和390px手机无横溢，截图system Temp soloops-product-quality-{desktop,mobile}.png已看。
- 首轮完整E2E在截图发现范围显示需回填后主动终止于25项，不计完整通过；之后重建全套42通过。Starlette/httpx、NO_COLOR既有提示保留。28个暂存文件路径/敏感token模式检查通过，未提交日志/凭据。

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
- 接续先核对cb6c585的CI37917649249，失败先修。读AGENTS、冻结稿、矩阵、development二十七/testing二十二；当前主工作区由新聊天独占。
- 下一切片继续不依赖外部凭据的 **SO-014 商品本地批量修订**。先官方/GitHub参考并更新references，检查ImportService的投影/版本/撤销与来源清除、Listing审批版本、ProductQuality证据，再设计并完成有草稿→差异预览→明确审批→本地生效→回读/失败明细的首片（可从名称/参数修订切入）。不得直接改Product却沿用旧source_row_id冒充新事实；保留原始导入、人工修订依据及依赖，批量动作限定规模，快照/权限/幂等/事务/撤销和清除需可验。实际平台、价格/库存/素材同步继续遵守外部审批门禁。
- 自行确定合理技术方案并实际完成前后端，不只写计划停工；之后继续独立P1/P2。每功能更新全部跟踪文档、测试/静态检查/桌面手机，再正常推送main/context-memory。上下文压力时先推送再创建接续本地聊天，创建后旧聊天停止修改。
