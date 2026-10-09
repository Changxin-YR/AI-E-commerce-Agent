# SoloOps 重点上下文

更新：2026-10-09。SO-056人工收费映射规则与调整历史已完成最终检查并推送main。用户“可以，批准检查”后的后端、前端单元和桌面/手机回归均通过；当前无执行许可阻塞。

## 最新成果：人工收费类别规则

- `fee_rules` API→服务→repository，FeeRule/FeeRuleRevision，迁移`2d826d48220b`，`fee_mapping`纯分类；账单页FeeRules提供新建/修订→原行差异预览→明确保存→当前分类回读→历史→撤销/清除。development三十一/testing二十六，references/questions/interview-guide/README/矩阵已更新；全部74 SO/32验收保留。
- 同用户店铺/身份/渠道，收费名strip后区分大小写/全半角/内部空白完整匹配；SHA256 UTF8有效匹配键唯一。七个费用类别、全部日期币种生效，窗口仅限预览；200有效规则/100次创建修订/20条列表，仍可撤销清除；预览复用每侧1000行/366天。
- 用户→店铺锁，with_for_update/populate_existing当前读；preview复用reconcile与defer_commits同事务。摘要绑定完整输入/窗口、来源版本、费用版本、完整active规则ID/version/content、匹配契约fee-name-exact-v1。`scope_revision`读取同范围全部revision最新ID（含撤销清除），返回rule_revision，防新建后撤销把规则集恢复原样而复活旧预览。
- UUID按用户唯一，hash绑定动作/范围/目标/version/预览；服务端锁后重算hash，旧预览409；UUID回放返回当前记录，清除不会重建正文。withdraw释放match_key保留历史；clear同事务擦current与所有revision正文/key，保留无正文状态/hash/审计；审计失败回滚。
- 规则为独立人工字典，不保存来源账单/费用正文或批次依赖。原来源清除下一次读自然无分类行，规则仍保留；来源恢复重新分类，不恢复“已核对”结论。当前只读分类未保存核对结论；不改原账单/人工费用，不生成费用或净利。
- 五状态unmapped/ambiguous/currency_mismatch/category_conflict/mapped；重复凭据或规则整组待核，异币种不分类，类别冲突显示拟分类并待核，mapped也标业务待核。旧金额比较六状态独立展示。
- 前端范围变化重建组件，输入改变撤preview/consent；focus/unmount/epoch丢迟到，刷新/保存先隐藏旧正文，未知请求保留原UUID原输入回查。最后修正refresh在action前invalidate，确保请求失败错误可见；scope表单在ruleBusy锁定。
- 本地完整后端 **570项/216.66秒**、完整E2E **50项/2.0分钟**在最后补充前通过；补充规则变更号/刷新错误后，最终规则与账单 **56项/29.84秒**、完整Vitest **22文件65项/3.78秒**、桌面/手机规则与账单E2E **4项/17.1秒**通过，当前571个后端用例均有本轮覆盖，不称一次完整571运行。
- 最终Ruff规则/format197文件、mypy143app、Vue lint/type-check/build通过。隔离库迁移回退/升级/check及开发库升级/check通过；downgrade按依赖直接drop新增表，避免删除FK必需索引失败。最后30路径敏感文件/凭据模式与git diff --check通过。
- Chromium URL http://127.0.0.1:5174/statements，1440×1000/390×844；URL/标题/内容/框架错误层/登录后console/pageerror/交互/手机无横溢均检查。Browser插件/browser技能未提供，依frontend-testing-debugging使用项目Playwright。截图已查看：系统Temp `soloops-fee-rules-{preview,history}-{desktop,mobile}.png`，不提交。

## 目标与授权

- 持续完成冻结稿 docs/requirements/SoloOps-V1.0.md。保留全部 74 SO、32 验收、7 长期 E2E；23 个 P0 当前仅为四条 MVP 的最小切片，计划不能称实现。
- 简体中文；Vue 3/TypeScript、FastAPI/Python、MySQL；接口→服务→repository，Agent 只能调用受控服务。沿用现有设计。
- 每功能先官方/GitHub 检索并更新 references（借鉴、许可证、适配）；实际实现前后端并验证，更新 development/interview-guide/testing/questions 与矩阵，正常提交推送 main/context-memory，不强推。
- 用户授权上下文压力时先落盘推送，再创建本地接续聊天；接手后旧聊天停止修改，同工作区独占。未经明确要求不启动子代理。
- 百炼凭据在本机忽略配置中；此前鉴权及累计 ¥0.01 合成测试一次性许可已用完。额外真实测试须独立授权，正常页面仍需数据同意与 USD 预算。A-13 真实邮件仍待本人通道、测试收件箱及授权。
- 密钥、真实客户数据、本机配置与日志不提交。已有 backend/.env 无需索取或打印。仅本地合成测试可直接继续。

## 当前提交、CI 与环境

- main **d53cf39ba92d0a17dd3a39fe888d1577e2e836c3** 已正常推送，人工收费映射规则实现及文档共30文件；主工作区干净。本分支仅维护重点上下文，不合并到main。
- 新CI https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37932923289 已从GitHub页面核实对应d53cf39，当前In progress；接续先确认结果。上一9530848的CI37928125060已核实Success。
- 当前GitHub connector的github_fetch虽可发现但不可调用，gh未安装；通过可用浏览器读取GitHub CI。Firecrawl已知402，不重复计费接口；官方网页工具作为公开资料fallback，不临时编写HTTP抓取脚本。
- backend/.venv Python3.11、frontend/node_modules；Docker MySQL8.4 开发3307/测试3308，项目容器soloops-mysql-1 / soloops-mysql-test-1。迁移head **2d826d48220b**；隔离_test库 down d32312391696 / up head / check 和开发库upgrade/check通过。
- 开发API8000核实父44580/子40380命令行后隐藏重启，最后launcher28892；前端5173 Node28144沿用。最终OpenAPI含fee-rules及StatementReconciliation.rule_revision，账单页200。API无热重载；启停必须重核端口和CIM命令行，不凭旧PID停进程；Start-Process一律WindowStyle Hidden。
- pytest、Playwright、迁移回退共用_test库，严格串行。Settings显式关闭真实模型/邮件/常规调度，专门worker测试才开启本地扫描；Vitest可独立运行。日志在忽略的.local，不提交。
- Windows沙箱MySQL socket10013/Vitest缓存rename EPERM需允许执行环境；用户本轮明确批准最终检查，已成功运行。若10061先查项目MySQL容器；使用python -m mypy，直接mypy.exe历史有uv trampoline路径问题。
- E2E必须 **npm run test:e2e**：pretest先build-only，Playwright管理隔离API8001与vite preview5174，CI=true。不要直接npx playwright test漏构建。
- 本机Node24.15.0 / Vite8.3.4历史偶发预览退出/请求状态-1，根因未定位。本轮首次定向4项3过1单次清除连接中断，随后完整50项与最终定向4项通过。不得把复验通过当作环境根因修复；日志/trace含合成cookie/CSRF，只提取方法/路径/状态/错误类型，不原样输出，保持忽略。

## 既有账单与费用差异能力

- development三十/testing第二十五。`/statements`：范围→CSV/Excel模板与上传→映射纠错预览→明确确认导入→当前费用核对→状态筛选→原始行/批次/人工费用深链→撤销/清除→重新核对。AppShell第17项导航；导入页支持statements类型和范围/批次深链，进入批次先隐藏旧正文。
- 新ImportKind statements复用2MiB/2000行/64列上限和既有导入版本/幂等/更新确认/撤销恢复。字段statement_id、line_id、entry_type、amount、currency、occurred_at、evidence_ref、fee_name、settlement_id、order_id、note。四类sale/refund/fee/payout使用正绝对值Decimal/Numeric(18,4)，分别合计；payout是平台记载回款、到账待核。fee要求凭据费用行编号和原始收费项名各120字符；非fee禁止fee_name，note500，稳定ID120。
- 无明确语义的调整/余额/返还/符号净额拒绝。无偏移时间使用批次IANA，拒绝DST歧义/缺失，UTC年2000—2100，未来最多5分钟；StatementLine发生时间和批次created_at/expires_at/committed_at为DATETIME(6)。唯一键shop+identity+channel+statement_id+line_id，ID保留大小写utf8mb4_bin，ImportRow业务键包含kind/identity/channel/两个ID，避免跨范围覆盖。
- `api/routes/statements.py → StatementService → StatementRepository`；POST `/shops/{shop_id}/statements/reconcile`只读，复用ExpenseScope。含偏移半开时间窗最多366天，两侧各1000行，任一超限整体拒绝。用户→店铺锁，两侧with_for_update/populate_existing当前读，防RR旧快照及ORM缓存。双方各按自身发生时间过滤，不跨期找编号。
- 比较窗口内当前fee账单和active人工费用，NFKC/casefold/空白折叠的共同evidence_key在services/evidence.py。六类matched/amount_difference/statement_only/expense_only/ambiguous/currency_mismatch；一对一同币种差额=账单-人工费用；重复整组歧义不加总，异币种不算差额。stale/withdrawn计排除笔数；cleared无时间正文不计。
- 返回读取时刻、店铺source_revision、每笔expense.version及账单source，只读不保存人工已核对结论，不改原记录。来源变化保守失效订单行费用，恢复不复活确认，独立shop费用保留。撤销恢复剩余有效账单版本；清除擦原行及其它同业务键行的previous副本，下一次当前读自然不含清除行。整店运营报告继续失效，四类运营候选不消费账单。
- StatementsView/StatementResult/StatementEvidence沿用现有设计；每页20条、六状态筛选、原始收费名/人工类别归属/币种符号/窗口/完整性未知明确。范围变化、刷新、focus隐藏旧结果，epoch丢迟到返回。共享SupportSource按店铺/源行getter监听，父页面新对象但同源时保留正文；再次读取先清旧值，真正切换/unmount递增epoch，A→B→A旧请求不能回填。
- 新后端最终 **35项/20.00秒**；完整pytest先 **548项/263.56秒**通过，其后新增2个数据库边界用例包含在最终35项定向中。当前550测试均有本轮通过覆盖，不称一次完整550运行。Ruff规则/格式189文件、mypy137app、Vue lint/type/build通过，完整Vitest **21文件60项/4.71秒**。迁移隔离库回退/升级/check和开发库升级/check均通过。
- 最终完整E2E **47/48项/2.1分钟**，失败和环境限制见上；最终定时+账单定向 **6项/20.3秒**全通过。Chromium 1440×1000和390×844，URL http://127.0.0.1:5174/statements；URL/标题/内容/overlay/登录后console/pageerror/交互/横溢均检查。Browser插件/browser技能未提供，按frontend-testing-debugging用项目Playwright。最新入口及详情截图已查看：系统Temp soloops-statements-{entry-}{desktop,mobile}.png。38文件路径/敏感token检查及git diff --check通过。
- SO-055/SO-056当前为通用文件和本地费用差异切片；真实平台收费映射、订单/物流差异、人工核对结论存档、结算周期/银行到账和复杂分摊待继续。账单费用不自动重复加入人工费用，完整性未知，不输出实际净利润。

## 既有费用台账的不变量

- development二十九/testing第二十四。`/expenses`：店铺/身份/渠道→名称类别、金额币种、发生时间/IANA、凭据行编号、事实依据、理由→明确确认保存→详情/历史/固定链接→修订→撤销/清除→按发生时间核对合计。金额Decimal/Numeric(18,4)，大于0，时间UTC DATETIME(6)，偏移须匹配IANA，未来最多5分钟时钟误差，年份2000—2100。
- API→ExpenseService→ExpenseRepository。Expense维护状态/版本/当前内容版本，ExpenseRevision保存每次人工操作的强类型amount/occurred_at及有界snapshot，ExpenseSource登记全部历史批次。名称100/凭据120/依据1000/理由500字符；每笔最多100次录入/修订，仍可撤销/清除；列表20条游标，订单精确查找最多100行，核对最多366天/1000笔整体拒绝超限。
- 两种归属：shop未分摊、order_line单行全额。订单关联验证当前源行、shop.data_revision、同店/身份/渠道/币种；费用总额只计一次，不乘订单数量。订单状态始终展示，取消/退款后费用是否适用仍需人工依据。无多行分摊/换汇。
- 用户→店铺→费用锁 + populate_existing当前读。UUID按用户唯一，hash绑定目标/动作/版本/范围/全部输入，同请求返回当前状态；不同内容拒绝。凭据编号NFKC/casefold/空白折叠后在同店/身份/渠道去重，active与stale都阻断，撤销/清除释放；旧UUID不会重建清除内容。所有版本/来源/无正文审计同事务。
- 任意店铺导入变更保守地将有效order_line费用stale并递增版本，恢复旧投影不复活旧确认；shop独立费用保留。重新核对关联并保存才active。状态版本与内容版本可能间隔。
- ImportService清除任一历史来源时，擦该笔全部revision snapshot/金额/发生时间/凭据键/全部依赖，即使已改成shop费用也擦历史。独立记录保留；源清除和费用清除同事务，审计故障整笔回滚。
- 核对按当前版本occurred_at半开窗口、身份/渠道、币种/类别/归属，active Decimal合计，stale/withdrawn计排除笔数，cleared无法计入时间窗。费用完整性未知，平台/物流账单及回款待核对；空范围不代表实际零费用；既有毛利与新品假设独立，不能据此输出净利润。
- ExpensesView/ExpenseEditor/ExpenseEvidence使用现有设计。更改字段清确认；编辑订单行必须重新查来源；epoch丢迟到范围/订单回包；保存/刷新/处理先隐藏旧正文及列表，失败不残留。未知请求保存原UUID/输入用于回查。读合计时禁用而不卸载编辑表单，保留未保存输入；固定链接回填身份渠道。导入页提示费用依赖影响。

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
- 接续先核对d53cf39的CI37932923289，失败先修。读AGENTS、冻结稿、矩阵、development三十一/testing第二十六及本文件；新聊天独占主工作区，旧聊天停止修改。
- 下一独立切片建议 **SO-055/SO-056 人工核对结论存档**：先官方/GitHub检索更新references，阅读SO-053/055/056/057及statements/expenses/fee_rules/imports分层，确定有界人工结论及差异说明契约，实现预览→明确保存→当前来源/费用/规则回读→历史→撤销/清除前后端闭环。
- 保存结论绑定当前账单来源、人工费用版本、完整范围与规则变更号，以及全部历史来源依赖。来源/费用/规则变化使旧结论失效；恢复原值不复活旧确认；来源清除擦所有历史依赖正文，与源清除及末尾审计同事务。未知/重复/币种与类别冲突仍明确待核，不自动生成费用或真实付款，不输出实际净利润。
- 真实平台收费定义、多条件/生效日期规则、复杂分摊、物流/订单金额差异、结算周期和银行到账继续保留待实现。每功能更新全部跟踪文档、测试/静态/桌面手机后正常推送main/context-memory；继续独立P1/P2。
- 上下文压力时依既有授权先落盘推送再创建本地接续聊天；创建后旧聊天停止修改，不启动子代理。
