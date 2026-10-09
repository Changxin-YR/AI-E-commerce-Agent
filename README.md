# SoloOps 重点上下文

更新：2026-10-09。SO-055/SO-056 人工核对结论存档已完成并推送 main；本聊天完成落盘后停止写入，由新聊天独占主工作区继续。不要启动子代理，不要两个聊天并行修改。

## 当前提交与验证

- main **c108006e7926b3a7428e3c4d983780633c59efce** 已正常推送，共32文件；主工作区干净。人工核对结论实现见 development 三十二、testing 第二十七，references/interview-guide/questions/README/两矩阵已更新；全部74 SO/32验收/7长期E2E保留。
- 当前 CI https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37936760400 已在 GitHub Actions 页面核实对应 c108006，最后状态 In progress。接续先核实结果，失败先修。前一 d53cf39 的 CI37932923289 已 Success（verify 6m27s）。
- 完整后端 **604项/245.18秒**在最后原子当前回读调整前通过；补充同事务返回 record+preview 后，最终核对存档 **33项/20.10秒**通过。准确区分两次证据，不称最终修改后又完整运行604。
- 最终完整 Vitest **23文件73项/3.22秒**、完整 Playwright **52项/2.1分钟**通过。Ruff规则/格式201文件、mypy148 app文件、Vue lint/type-check/生产构建通过。
- 新迁移 **9862c543a46b**：隔离_test库 downgrade 2d826d48220b → upgrade head → check通过；开发库正常 upgrade/check通过。pytest、迁移回退与E2E严格串行。
- Chromium 1440×1000、390×844；http://127.0.0.1:5174/statements。URL/标题/非空/overlay/登录后console/pageerror/交互/无横溢通过，四张预览与历史截图实际查看：系统Temp `soloops-statement-reviews-{preview,history}-{desktop,mobile}.png`，不提交。
- 新测试初次stale分支重复创建同店标识，修正fixture后通过；新E2E初次来源定位包含祖先details，限定实际账单结果内后通过。截图复核把勾选框从普通input尺寸改为18px、沿用绿色及文本框样式。

## 最新能力：人工核对结论存档

- `statement_reviews` API → StatementReviewService → StatementReviewRepository；五表主记录、revision、source、expense、rule依赖。`/statements` StatementReviews 提供新建→输入结论/说明→预览→明确保存→详情/固定链接→当前来源费用规则→逐版本历史→修订→撤销/清除。
- 窗口级 conclusion：consistent（本窗口费用一致）、differences_recorded（金额差异已说明，处理待跟进）、pending。说明1—1000字符。非空、全部比较一对一同币种、规则分类一致且无排除费用才允许前两种；金额差异不能确认一致，没有差异不能选择差异说明；未知分类/缺失一侧/重复/异币种/类别冲突/待重核撤销费用/空范围只许pending。
- 状态active/stale/withdrawn/cleared；active不表示业务结论已解决，pending也可active。version记录所有状态变更，content_version指最近人工正文。每份100次保存/单次2MiB/累计10000历史依赖；查询复用366天和两侧各1000行，列表20条仅元数据，详情按version读单个完整依据，历史仅查JSON conclusion摘要。
- 用户→店铺锁，with_for_update/populate_existing；预览复用StatementService与defer_commits。hash绑定契约statement-review-v1、完整draft/目标/version、范围、source_revision、expense_revision、rule_revision及完整比较结果（仅排除calculated_at）。ExpenseRepository新增scope_revision取同范围所有ExpenseRevision最大ID，包含撤销清除；规则已有同样变更号。集合恢复原样仍不能复活旧预览。
- UUID用户内唯一、hash绑定动作/范围/对象/版本/全部输入；重复请求回读当前状态。导入变化保守失效同店active结论；费用/规则变动保守失效同店同身份同渠道结论（即使在窗口之外）。恢复原值不会激活旧确认，须新预览确认。失效递增状态版本，不伪造人工revision。
- 每次保存累加全部当前账单批次、范围内所有费用（含排除项）、全部active规则，并展开费用所有历史来源批次。修订缩短窗口不丢旧依赖。任一历史批次/费用/规则清除，擦相关结论所有revision.snapshot（含说明/范围/账单金额正文）和三类依赖；保留最小状态/hash/无正文审计，与原清除和末尾审计同事务，失败整笔回滚。独立记录保留。
- `GET /statement-reviews/{id}/current` **同一事务**返回ReviewCurrent(record最新存档状态, preview当前依据)；已清除返回preview=null。不能在前端分两次请求读取状态与依据，否则会有跨请求竞态。当前读不保存/激活结论，尚需明确确认。
- 前端范围、focus、规则变化、卸载epoch丢迟到；操作开始隐藏旧正文，失败可见错误；未知请求保留原UUID输入回查，4xx明确拒绝后可重新预览。固定链接回填实际身份/渠道/范围，scope改变清initialReview，避免重建组件又打开旧深链。初始化也有独立epoch。
- StatementResult新增historical标记和useId控件ID，可同页展示历史与当前；历史按保存时规则展示，不冒充当前读取。当前读结果清除时同步隐藏旧正文。源清除保持核对记录最小状态。
- 不生成真实付款或额外费用，不输出实际净利；分类和一致结论仅覆盖导入窗口。Agent尚未新增此写入技能。

## 授权、工作方式与环境

- 简体中文；Vue3/TypeScript、FastAPI/Python、MySQL；API→服务→repository，Agent只能调用受控服务。功能基线docs/requirements/SoloOps-V1.0.md；23 P0是四MVP最小切片，不把计划或替身当生产验收。
- 每功能先官方/GitHub检索并更新references（资料/许可证/借鉴/适配），沿用现有UI。前后端、相关测试和静态/桌面手机通过后更新development/interview-guide/testing/questions与矩阵，正常提交推送main和context-memory，禁止强推。
- 用户授权上下文压力时先落盘推送，再创建本地接续聊天。交接后旧聊天停止工作区写入；未经明确要求不启动子代理。context-memory分支仅存重点上下文，不合并main、不保存完整聊天。
- 真实百炼一次性合成测试许可已耗尽（历史累计估算¥0.0001108/¥0.01），不能再用旧许可额外调用。正常测试关闭真实模型、邮件、常规调度；专门worker测试例外仅本地合成。A-13真实邮件仍缺本人通道/测试收件箱/授权。密钥和真实客户数据、本机配置/日志不提交，不输出.env或trace中cookie/CSRF。
- backend/.venv Python3.11，frontend/node_modules；Docker MySQL8.4开发3307、测试3308，soloops-mysql-1 / soloops-mysql-test-1。
- E2E必须 **npm run test:e2e**，pretest先build-only、Playwright管理隔离API8001与preview5174，CI=true；不用直接npx playwright test跳过构建。pytest/迁移回退/E2E共享_test库，严格串行；Vitest可独立。
- Windows沙箱MySQL socket10013与Vitest缓存rename EPERM需要允许执行环境，用户先前已批准检查，本轮执行均获自动允许。若10061先查项目MySQL容器。python -m mypy避免旧mypy.exe trampoline问题。
- 本机Node24.15/Vite8.3.4曾偶发退出/请求状态-1，根因未定位；本轮52项全过不代表环境根因修复。Starlette/httpx、NO_COLOR警告仍保留。日志与trace忽略，只提取路径/方法/状态/错误类型。
- 开发API8000旧监听46968/父28892经过CIM核对后隐藏重启，最后launcher **54672**；前端5173既有Node28144沿用。最终OpenAPI核实新路由和ReviewCurrent、前端200。后续重启务必重核端口/CIM身份，不能凭此PID停进程；Start-Process必须WindowStyle Hidden。
- GitHub connector当前github_fetch虽能发现但不可调用，gh未安装。可用cua IAB公开GitHub页面核实CI。本轮Chrome不可用，Edge策略读取失败，IAB可用。Browser插件/browser技能未列出，前端按frontend-testing-debugging用项目Playwright。
- Firecrawl已知402，不重复计费接口，官方web工具fallback，不写HTTP抓取脚本。普通文件定位用rg，语义图才用codegraphcontext且先检查可用。

## 既有财务与来源不变量

- 通用账单kind statements：四类sale/refund/fee/payout正绝对金额；fee要求evidence_ref和fee_name，其他禁止fee_name。2MiB文件/2000行/64列；无偏移按批次IANA，拒DST歧义缺失，UTC2000—2100未来5分钟。Numeric(18,4)、DATETIME(6)，大小写敏感键shop+identity+channel+statement_id+line_id。
- StatementService只读reconcile：同范围半开窗366天/各1000，用户→店铺锁与当前读；共同evidence_key为NFKC/casefold/空白折叠。六状态matched/amount_difference/statement_only/expense_only/ambiguous/currency_mismatch；差额账单减人工，仅一对一同币种，重复整组待核不抵销。双方各按自身发生时间筛选，stale/withdrawn排除。
- FeeRule独立人工字典，完整收费名strip后区分大小写/全半角/内部空白，SHA256匹配键唯一；七类别/全部日期币种，预览窗口不是生效期。200active/100revision。规则变化号包含撤销清除；withdraw释放key，clear擦全部正文。五分类mapped/unmapped/ambiguous/currency_mismatch/category_conflict均不自动生成人工已核对结论。
- Expense人工台账：shop未分摊或order_line单行全额，不乘数量。金额Decimal/UTC/IANA、凭据同范围去重active/stale阻断，UUID回放当前状态。来源变化保守失效order_line，shop费用保留；ExpenseSource保存所有历史批次，改成shop也不删除历史依赖。来源清除擦所有版本、金额、时间、凭据键与依赖。
- ImportService撤销恢复剩余有效投影；清除擦原行和同业务键previous副本。产品人工修订为独立manual_edit批次并登记全部祖先，后代优先撤销清除、整链同事务。SupportSource按shop/源行getter watch，真实切换epoch防A→B→A迟到。

## 其他长期不变量与接续起点

- 今日运营四类本地候选、逐次审批；问数固定统计/匿名事实、当前成本估历史毛利，未知费用不能算净利。Listing模型只编排事实、客服规则和模型并集敏感转人工；模型网络前后及保存复验来源、预算/授权，未知响应不重发。
- R1范围/规则/次数/时效预授权，R2 Resend默认关闭、本人验证邮箱单次全文摘要、未知只读回查。定时本地日周月/DST/唯一周期、24小时最近一期恢复、站内通知只引用ID，日历报表按完整上期自然区间。商品质量与本地名称参数批修、跨店总览、驾驶舱原权限深链均已合成通过，完整边界见对应docs。
- 接续先读AGENTS、冻结稿、矩阵、development三十二/testing第二十七及本文；先核实 c108006 的CI37936760400，失败先修。
- 下一独立切片建议 **SO-055 结算周期与人工回款凭据核对**。先检索官方/GitHub资料并更新references，阅读SO-053/055/056/057/059与现有statements/expenses/reviews/imports。定义有界、可溯源的周期及平台记载回款/卖家人工登记到账依据契约，区分平台记载、人工声称及真实银行证据；未知覆盖/余额/跨币种不自动确认。实现本地预览→明确保存→当前来源回读→差异/历史→撤销/清除闭环，保持全部历史依赖及原子审计。
- 本地合成数据可独立推进；不得申请真实银行连接、触发付款、自动生成重复费用或把人工登记当银行API确证。真实平台报表、结算余额、银行到账、复杂分摊/物流订单差异继续如实区分未验部分。若设计发现必要业务语义缺失，写questions并推进独立部分。
