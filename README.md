# SoloOps 重点上下文

更新：2026-10-09。业务代码在 main；本分支只保存重点上下文，不合并到 main。

## 目标与授权

- 持续完成冻结稿 docs/requirements/SoloOps-V1.0.md。保留全部 74 SO、32 验收、7 长期 E2E；23 个 P0 当前仅为四条 MVP 的最小切片，计划不能称实现。
- 简体中文；Vue 3/TypeScript、FastAPI/Python、MySQL；接口→服务→repository，Agent 只能调用受控服务。沿用现有设计。
- 每功能先官方/GitHub 检索并更新 references（借鉴、许可证、适配）；实际实现前后端并验证，更新 development/interview-guide/testing/questions 与矩阵，正常提交推送 main/context-memory，不强推。
- 用户授权上下文压力时先落盘推送，再创建本地接续聊天；接手后旧聊天停止修改，同工作区独占。未经明确要求不启动子代理。
- 百炼凭据在本机忽略配置中；此前鉴权及累计 ¥0.01 合成测试一次性许可已用完。额外真实测试须独立授权，正常页面仍需数据同意与 USD 预算。A-13 真实邮件仍待本人通道、测试收件箱及授权。
- 密钥、真实客户数据、本机配置与日志不提交。已有 backend/.env 无需索取或打印。仅本地合成测试可直接继续。

## 当前提交、CI 与环境

- main **a085232547788db34968b56e19a15b3ea087a6e7** 已正常推送：feat: record and verify evidence-backed actual expenses。主工作区干净。
- 当前 CI https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37924316380 最后观测 in_progress，接续先核对，失败先修。交接基线 c652c91 的 CI37920901327 已核实 completed/success。
- GitHub connector github_fetch 读 REST，JSON 常在 structuredContent.content，有时再套一层；只打印状态摘要。同 URL 可能缓存旧值，可用有效参数或 workflow runs 集合按 head_sha 核对。当前 actions/runs?per_page=5 可读。
- backend/.venv Python3.11、frontend/node_modules；Docker MySQL8.4 开发3307/测试3308，项目容器 soloops-mysql-1 / soloops-mysql-test-1。迁移 head **a269fe553f96**，新增费用台账三表。隔离库 down d6f920a41b85 / up head / check 与开发库 upgrade/check 已通过。
- 开发 API8000 已核实原27088/39712命令行后隐藏重启，本次 launcher39496（实际PID后续重核）；前端5173 Node28144沿用，CI=true。两端正常，新 expenses OpenAPI 路由可读。API无热重载；启停必须重核端口和CIM命令行，不凭旧PID停进程；Start-Process一律WindowStyle Hidden。
- pytest、Playwright、迁移回退共用 _test 库，严格串行。测试 Settings 显式关闭真实模型/邮件/常规调度，专门worker测试才开启本地扫描。日志在忽略的 .local，不提交。
- Windows 沙箱 socket10013 / Vitest临时缓存rename EPERM须允许执行环境。若10061先查两个项目MySQL容器。使用 python -m mypy，直接mypy.exe历史有uv trampoline路径问题。
- E2E必须 **npm run test:e2e**：pretest:e2e先build-only，Playwright管理隔离API8001与vite preview5174，CI=true，生产预览代理隔离API。不要直接npx playwright test漏构建。
- 本机 Vite8.3.4开发转换服务历史捕获0xC0000409，根因未定位。本轮首次完整预览回归在第3项发生ECONNRESET，后续5174连接拒绝（2通过/44失败）；没查到可定位的近期Node应用错误事件。随后普通exec、无tty/无重定向的 npm run test:e2e **46项全部通过**，不把复验通过当退出根因已修。真实失败日志勿直接输出：含测试会话cookie/CSRF；仅提取错误类型，日志不提交。
- Firecrawl已知402，不重复计费接口；用官方网页/GitHub工具，不临时编写HTTP抓取脚本。

## 最新成果：SO-056 自定义实际费用与本地核对

- development二十九/testing第二十四。`/expenses`：店铺/身份/渠道→名称类别、金额币种、发生时间/IANA、凭据行编号、事实依据、理由→明确确认保存→详情/历史/固定链接→修订→撤销/清除→按发生时间核对合计。金额Decimal/Numeric(18,4)，大于0，时间UTC DATETIME(6)，偏移须匹配IANA，未来最多5分钟时钟误差，年份2000—2100。
- API→ExpenseService→ExpenseRepository。Expense维护状态/版本/当前内容版本，ExpenseRevision保存每次人工操作的强类型amount/occurred_at及有界snapshot，ExpenseSource登记全部历史批次。名称100/凭据120/依据1000/理由500字符；每笔最多100次录入/修订，仍可撤销/清除；列表20条游标，订单精确查找最多100行，核对最多366天/1000笔整体拒绝超限。
- 两种归属：shop未分摊、order_line单行全额。订单关联验证当前源行、shop.data_revision、同店/身份/渠道/币种；费用总额只计一次，不乘订单数量。订单状态始终展示，取消/退款后费用是否适用仍需人工依据。无多行分摊/换汇。
- 用户→店铺→费用锁 + populate_existing当前读。UUID按用户唯一，hash绑定目标/动作/版本/范围/全部输入，同请求返回当前状态；不同内容拒绝。凭据编号NFKC/casefold/空白折叠后在同店/身份/渠道去重，active与stale都阻断，撤销/清除释放；旧UUID不会重建清除内容。所有版本/来源/无正文审计同事务。
- 任意店铺导入变更保守地将有效order_line费用stale并递增版本，恢复旧投影不复活旧确认；shop独立费用保留。重新核对关联并保存才active。状态版本与内容版本可能间隔。
- ImportService清除任一历史来源时，擦该笔全部revision snapshot/金额/发生时间/凭据键/全部依赖，即使已改成shop费用也擦历史。独立记录保留；源清除和费用清除同事务，审计故障整笔回滚。
- 核对按当前版本occurred_at半开窗口、身份/渠道、币种/类别/归属，active Decimal合计，stale/withdrawn计排除笔数，cleared无法计入时间窗。费用完整性未知，平台/物流账单及回款待核对；空范围不代表实际零费用；既有毛利与新品假设独立，不能据此输出净利润。
- ExpensesView/ExpenseEditor/ExpenseEvidence使用现有设计。更改字段清确认；编辑订单行必须重新查来源；epoch丢迟到范围/订单回包；保存/刷新/处理先隐藏旧正文及列表，失败不残留。未知请求保存原UUID/输入用于回查。读合计时禁用而不卸载编辑表单，保留未保存输入；固定链接回填身份渠道。导入页提示费用依赖影响。
- 新后端 **29项/12.06秒**，完整pytest **515项/206.83秒**。Ruff规则/格式182文件、mypy132app。最终Vue lint/type/build通过。新组件 **7项/1.15秒**，完整Vitest **20文件52项/3.54秒**。定向E2E **2项/11.3秒**，最终完整 **46项/1.7分钟**，桌面1440×1000和390×844，无横溢/页面脚本错误。
- 页面/标题/内容/overlay/登录后console/交互均检查，最新桌面手机入口及费用详情截图已看：系统Temp soloops-expenses-{entry-}{desktop,mobile}.png。Browser插件/browser技能未提供，按frontend-testing-debugging用项目Playwright。28提交文件路径及敏感token检查通过，凭据/日志未提交。
- 首轮新测试用错SourceReference.kind与purge/withdraw路由，已按现有data_identity与clear/revoke契约改正；真实时间回读精度问题已改DATETIME(6)并重做迁移。首轮E2E撤销后未展开新处理区超时，正确展开后通过。最终新增读合计保留编辑输入用例通过。

## 既有主要能力与不变量

- owner/shop约束；用户→店铺→来源→派生锁序；Decimal/Numeric，UTC持久化、IANA显示。锁后当前读防MySQL RR旧快照及ORM缓存。商品键shop+SKU、订单shop+order+line、消息shop+channel+message_id、库存shop+channel+SKU。
- SO-014 `/product-quality` 当前主档检查，1000商品/2MB；名称/参数/售价成本币种、相似SKU、有限关键词规则，missing/review及未检查项明确。保存范围/revision/hash/UUID，全部商品依赖，来源变化stale，清任何依赖擦正文和SKU前缀。
- SO-014 `/product-edits` 本地名称/参数批修，最多50商品、1MB正文、1000祖先批次。草稿差异→逐次审批→整批生效/逐项失败→当前来源计数→拒绝/撤销/清除。审批绑定草稿version/hash、全部原行、整店revision，来源恢复不复活审批。
- 人工商品修订独立manual_edit ImportBatch+ImportRow，raw保留理由和before，normalized after，金额继承原来源；复用ImportService.commit更新Product和派生失效。全部祖先依赖，ImportService.withdraw外层事务后代优先处理输出再原批次，无递归提交；源清除擦祖先派生/下游正文，独立分支保留，审计故障整链回滚。共享SourceReference.origin/SupportSource区分人工依据。
- SO-006定时巡检/自然周期报表：日周月、DST、唯一周期、最近一期24小时恢复，更旧合并、暂停不补跑；每店100计划、每轮20。daily Agent本地候选仍逐次审批。报表锚原计划时刻取前自然日/周/月，分币种前后期，OverviewService+依赖+通知+下期同事务，通知只引用ID。外部通知、事件、紧急分级后续。
- 今日运营四类：来源待核履约、有效低库存、客服回复核对、已知成本低毛利。单项10000行/最多500候选、超限整体拒绝；重跑保留人工状态。MVP01 daily_model仅发送目标/范围/聚合分支和候选数，本地恢复9分支/4类候选；双同意与完整hash，调用前后/审批/保存复验。
- 问数：半开窗口最多366天/10000行，同身份同币种当前成本估历史毛利，费用缺失不算净利；question_plan→metrics→explain_analysis→analysis_todo→verify，数值本地渲染，最多20匿名SKU。
- Listing模型只选标题参数/排序全部参数，描述不得漏事实；来源/当前基线网络前后/保存复验，候选保存和本地生效独立审批，依赖包括比较旧版，去重保留人工状态。
- 客服规则与模型意图并集，固定事实/政策ID、本地中英模板和完整FAQ；敏感/冲突/未知语言转人工，消息/政策双同意绑定原行/版本/全部订单行人工核验；全部已发送政策登记依赖。语义检索、自动语言检测、多轮后续。
- 模型openai_responses/dashscope_chat固定官方端点，无工具/重试/代理/重定向，有界JSON。预算预留/持久租约网络前提交，返回复验；已知usage拒答或无效仍计费，未知保留预留不重发。Agent默认12步/120秒/0USD，恢复提高总预算不归零，临时白名单读最多3次，写不重试，defer_commits/savepoint保持原子。
- R1预授权绑定范围/规则/来源/次数/时效；R2 Resend默认关闭，仅本人验证邮箱/全文摘要一次，未知只读回查不重发。跨店Overview按币种/显式时区/完整依赖，驾驶舱10类元数据UNION ALL稳定keyset，读不执行、深链回原权限服务。

## P0边界与接续起点

- p0-local-review.md保留4 MVP、23 P0最小模块、32验收边界；A01—12与A14—32共31项本地适用证据通过。A13真实邮件、真实模型全面质量、七条长期E2E未完整验收。
- 接续先核对a085232的CI37924316380，失败先修。读AGENTS、冻结稿、矩阵、development二十九/testing第二十四；新聊天独占主工作区，旧聊天停止修改。
- 下一切片建议 **SO-055 通用渠道账单文件导入与 SO-056 费用差异核对首片**，不依赖外部账号。先官方/GitHub检索更新references；读SO-053/055/056/057及新expenses、imports分层。自行确定有界账单行契约和明确来源元数据，提供文件预览/确认导入→原行/历史回读→按明确凭据行编号、范围和币种匹配实际费用→一致/金额差异/单边缺失/重复或歧义待核清单→撤销/清除及依赖失效。必须实际前后端闭环，不只写计划。
- 账单账面收入、退款、手续费和回款的业务含义需明确，未提供到账凭据不能当作已收现金；未覆盖/跨币种/未知保持明确。匹配不得自动改原始记录或人工费用，不声称真实平台对账或精确净利通过。原四类导入和新台账都须保持权限、身份、金额/UTC、幂等、审计原子、来源恢复阻断与全依赖清除。
- 每功能更新全部跟踪文档、测试/静态/桌面手机后正常推送main/context-memory；继续独立P1/P2。上下文压力时依既有授权先推送再创建本地接续，创建后旧聊天停止修改，不启动子代理。
