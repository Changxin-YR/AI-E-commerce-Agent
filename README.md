# SoloOps 重点上下文

更新：2026-10-09。SO-055 结算周期与人工回款凭据已完成并推送 main；本聊天落盘后停止写入，由新聊天独占主工作区继续。不要启动子代理或并行写入聊天。

## 当前提交与验证

- main **1763c405e61aa8710a5095167407f8cfee0e02ad** 已正常推送，共31文件，主工作区干净。实现见 development 三十三、testing 第二十八；README/references/interview-guide/questions/两矩阵已更新，全部74 SO/32验收/7长期E2E保留。
- 当前 CI https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37941439350 已在 GitHub Actions 页面核实对应1763c40，最后状态 **In progress**。接续先核实结果，失败先修。基线c108006的CI37936760400已Success（verify 7m41s）。
- 新结算后端 **32项/18.61秒**、最终完整后端 **636项/314.06秒**通过。Ruff规则/格式 **212文件（含scripts）**、mypy **154 app文件**通过。
- 完整Vitest **24文件80项/4.21秒**、Vue lint/type-check/生产构建通过；之后仅文本按钮样式和导航序号调整，最终静态与浏览器流程复验通过。
- 新E2E首次2项/12.5秒通过，样式与截图补充后定向11项/31.7秒通过；最终 **Node24.16.0完整Playwright 54项/2.5分钟，退出码0**。Node24.15前两轮分别52通过/2失败、3通过/51失败，原生退出及连接中断详情见testing。
- 迁移 **7e7851694067**：隔离_test库 downgrade9862c543a46b → upgrade head → check通过；开发库正常upgrade/check通过。pytest、迁移回退与E2E严格串行。
- Chromium1440×1000、390×844，http://127.0.0.1:5174/settlements。URL/标题/非空/overlay/登录后console/pageerror/交互/无横溢通过；六张入口/预览/历史截图实际查看：系统Temp `soloops-settlements-{entry,preview,history}-{desktop,mobile}.png`，未提交。

## 最新能力：周期登记与人工到账凭据

- `settlements` API → SettlementService → SettlementRepository，四表主记录/revision/source/receipt；settlement_calculation专管Decimal。`/settlements`周期/凭据→预览→明确保存→固定链接→当前依据→修订/历史→撤销/清除。Agent尚无此写入技能。
- 当前用户/店铺/身份/渠道内精确原账单号，周期由卖家按文件声明、半开≤366天；按原账单号读取全部当前行≤1000，不用发生日期猜归属。payout/人工到账可在周期外，非payout周期外单独提示。原始settlement_id逐行保留，多结算批号拆合后续。
- ≤50人工凭据：payout_ref/receipt_ref、正数金额、币种、显式偏移/IANA时间、说明。到账偏移须匹配时区，UTC和当地年份2000—2100，未来超过5分钟拒绝。Numeric(18,4)、UTC DATETIME(6)，JSON十进制字符串。bank_status始终unverified，coverage/balance未知。
- evidence_key(NFKC/casefold/空白)匹配平台payout凭据和人工payout_ref。七状态matched/amount_difference/statement_only/receipt_only/ambiguous/currency_mismatch/missing_reference；一对一同币种才算平台减人工。重复不抵销，缺登记不代表未到账；五类金额分别分币种合计，不算余额/净利。
- 用户→店铺锁、with_for_update/populate_existing。hash绑定settlement-v1、shop、完整draft/目标/version、source_revision、完整依据（去calculated_at）和同范围全部登记revision最大ID，含撤销清除，防占用集合恢复复活旧预览。
- 原账单号原字符SHA256键、人工receipt_ref规范化键同范围唯一占用；active/stale保留，修订同事务释放重占，withdraw/clear释放。历史数值保留至clear。UUID用户内唯一/hash绑定完整操作，回放当前状态。
- active/stale/withdrawn/cleared；version含来源失效，content_version指最近正文。导入变化保守失效同店active，恢复原值不激活。100次正文/每版本2MiB/累计10000历史依赖；列表20元数据，history只has_content摘要。
- current同事务返回SettlementCurrent(record最新状态, preview最新来源+最近人工声明)，hash空不能保存确认；cleared时preview=null，读不激活。历史batch依赖累积，换账单也不丢；任一清除擦全部snapshot、Numeric/UTC receipt行、keys/dependencies，与原导入和审计原子化。独立记录保留。
- 输入变化撤预览/确认，focus/范围/卸载epoch丢迟到，读前隐藏正文；未知写原UUID回查、4xx可重预览。范围变化清pending/pendingControl防跨店。固定链接回填原范围，最近正文深拷贝修订，旧历史不能修订；初始化独立epoch。

## 授权、工作方式与环境

- 简体中文；Vue3/TypeScript、FastAPI/Python、MySQL；API→服务→repository，Agent只能调用受控服务。功能基线docs/requirements/SoloOps-V1.0.md；23 P0是四MVP最小切片，不把计划或替身当生产验收。
- 每功能先官方/GitHub检索并更新references（资料/许可证/借鉴/适配），沿用现有UI。前后端、相关测试和静态/桌面手机通过后更新development/interview-guide/testing/questions与矩阵，正常提交推送main和context-memory，禁止强推。
- 用户授权上下文压力时先落盘推送，再创建本地接续聊天。交接后旧聊天停止工作区写入；未经明确要求不启动子代理。context-memory分支仅存重点上下文，不合并main、不保存完整聊天。
- 真实百炼一次性合成测试许可已耗尽（历史累计估算¥0.0001108/¥0.01），不能再用旧许可额外调用。正常测试关闭真实模型、邮件、常规调度；专门worker测试例外仅本地合成。A-13真实邮件仍缺本人通道/测试收件箱/授权。密钥和真实客户数据、本机配置/日志不提交，不输出.env或trace中cookie/CSRF。
- backend/.venv Python3.11，frontend/node_modules；Docker MySQL8.4开发3307、测试3308，soloops-mysql-1 / soloops-mysql-test-1。
- E2E必须 **npm run test:e2e**，pretest先build-only、Playwright管理隔离API8001与preview5174，CI=true；不用直接npx playwright test跳过构建。pytest/迁移回退/E2E共享_test库，严格串行；Vitest可独立。
- Windows沙箱MySQL socket10013与Vitest缓存rename EPERM需要允许执行环境，用户先前已批准检查，本轮执行均获自动允许。若10061先查项目MySQL容器。python -m mypy避免旧mypy.exe trampoline问题。
- **Windows下一轮使用隔离Node24.16.0**：frontend目录中临时 `$env:PATH = (Resolve-Path '../.local/runtimes/node-v24.16.0-win-x64').Path + ';' + $env:PATH`，`$env:CI='true'`，再`node --version`和`npm.cmd run test:e2e`。目录已存在，被gitignore忽略，全局仍24.15.0。
- 官方24.16包SHA256 edaca9bd58ec8e92037dac4e877d52f6b8f430b81c18b57e264b4e2fb111cd56已校验；Node官方#63620维护者确认相关Windows TCP修复。本机24.15捕获3221226505(0xC0000409)及拒连，未取得本机堆栈；隔离24.16完整54项通过是版本对照证据。README建议Windows24.16+。Starlette/httpx、NO_COLOR提示保留，日志/trace忽略，只提取安全请求元数据。
- 开发API8000核对原父54672/子41272命令行后隐藏重启，本次launcher **54736**；前端5173沿用Node28144。OpenAPI结算路由/SettlementCurrent已回读，前端200。后续启停重核端口/CIM身份，不凭历史PID停进程；Start-Process必须WindowStyle Hidden。
- GitHub connector当前github_fetch虽能发现但不可调用，gh未安装。可用cua IAB公开GitHub页面核实CI。本轮Chrome不可用，Edge策略读取失败，IAB可用。Browser插件/browser技能未列出，前端按frontend-testing-debugging用项目Playwright。
- Firecrawl已知402，不重复计费接口，官方web工具fallback，不写HTTP抓取脚本。普通文件定位用rg，语义图才用codegraphcontext且先检查可用。

## 既有财务与来源不变量

- StatementReview窗口结论consistent/differences_recorded/pending；未知/重复/异币种/类别冲突/缺一侧/排除费用/空范围仅pending。来源/费用/规则变更号及完整结果绑定hash，同事务current返回record+preview。全部历史batch/expense/rule依赖累积，任一清除擦所有正文/依赖，与原清除和审计原子化。详见development三十二/testing第二十七。

- 通用账单kind statements：四类sale/refund/fee/payout正绝对金额；fee要求evidence_ref和fee_name，其他禁止fee_name。2MiB文件/2000行/64列；无偏移按批次IANA，拒DST歧义缺失，UTC2000—2100未来5分钟。Numeric(18,4)、DATETIME(6)，大小写敏感键shop+identity+channel+statement_id+line_id。
- StatementService只读reconcile：同范围半开窗366天/各1000，用户→店铺锁与当前读；共同evidence_key为NFKC/casefold/空白折叠。六状态matched/amount_difference/statement_only/expense_only/ambiguous/currency_mismatch；差额账单减人工，仅一对一同币种，重复整组待核不抵销。双方各按自身发生时间筛选，stale/withdrawn排除。
- FeeRule独立人工字典，完整收费名strip后区分大小写/全半角/内部空白，SHA256匹配键唯一；七类别/全部日期币种，预览窗口不是生效期。200active/100revision。规则变化号包含撤销清除；withdraw释放key，clear擦全部正文。五分类mapped/unmapped/ambiguous/currency_mismatch/category_conflict均不自动生成人工已核对结论。
- Expense人工台账：shop未分摊或order_line单行全额，不乘数量。金额Decimal/UTC/IANA、凭据同范围去重active/stale阻断，UUID回放当前状态。来源变化保守失效order_line，shop费用保留；ExpenseSource保存所有历史批次，改成shop也不删除历史依赖。来源清除擦所有版本、金额、时间、凭据键与依赖。
- ImportService撤销恢复剩余有效投影；清除擦原行和同业务键previous副本。产品人工修订为独立manual_edit批次并登记全部祖先，后代优先撤销清除、整链同事务。SupportSource按shop/源行getter watch，真实切换epoch防A→B→A迟到。

## 其他长期不变量与接续起点

- 今日运营四类本地候选、逐次审批；问数固定统计/匿名事实、当前成本估历史毛利，未知费用不能算净利。Listing模型只编排事实、客服规则和模型并集敏感转人工；模型网络前后及保存复验来源、预算/授权，未知响应不重发。
- R1范围/规则/次数/时效预授权，R2 Resend默认关闭、本人验证邮箱单次全文摘要、未知只读回查。定时本地日周月/DST/唯一周期、24小时最近一期恢复、站内通知只引用ID，日历报表按完整上期自然区间。商品质量与本地名称参数批修、跨店总览、驾驶舱原权限深链均已合成通过，完整边界见对应docs。
- 接续先读AGENTS、冻结需求、两矩阵、development三十三/testing第二十八及本文；先核实 **1763c40 CI37941439350**，失败先修。
- 下一独立切片建议 **SO-056 账单销售/退款与订单金额差异核对**。先官方/GitHub检索并更新references，检查现有订单/账单字段语义与关联键，设计有界、只读、有来源证据的待核清单。精确关联、一对一同币种才计算可比差额，跨日期/订单多行/多笔退款/缺字段保留未知，不把窗口外或未导入当业务缺失，不推断物流费用或改写原始记录。必要语义缺失写questions并推进独立部分，不臆测分摊。
- 合成本地功能可继续，不重复请求已有开发授权；不得连接真实银行/触发付款/复用耗尽的真实模型许可。真实平台适配、银行确证、完整余额、复杂分摊/物流差异、换汇税费继续如实区分未验部分。
