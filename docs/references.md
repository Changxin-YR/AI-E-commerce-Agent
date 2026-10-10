# 公开实现与借鉴记录

## R2 B2：人工复制与通用CSV（2026-10-10）

- Mozilla Contributors [Clipboard.writeText](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText)与[内容许可](https://developer.mozilla.org/en-US/docs/MDN/Writing_guidelines/Attrib_copyright_license)：文档CC-BY-SA 2.5或更新版本，示例代码按页面许可说明；本次不复制正文/代码。借鉴安全上下文、异步成功和NotAllowedError处理，失败保留手工复制路径。
- OWASP [CSV Injection](https://community.owasp.org/attacks/CSV_Injection)：CC-BY-SA 4.0，参考分隔符/引号编码、危险公式起始和全角变体、不同电子表格软件重新保存的差异。沿用现有错误CSV的文本字面量思路，补完整转义和恶意内容测试；CSV为人工核对的通用草稿，原始正文可通过纯文本取得。
- 适配：复用本地已批准Listing与来源锁校验，复制/下载前均重新检查当前版本；不引入平台模板或发布连接。无新依赖；Firecrawl负额度，资料通过官方web只读检索核实。

## R2 B1：证据驱动的有限技能组合（2026-10-10）

- Anthropic官方[Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)：借鉴可由确定性分类执行的routing、清楚的技能契约、基于实际工具结果继续和有限停止条件。文章版权归Anthropic，未复制代码；只在现有持久Agent中增加一个低毛利复核模板。
- SQLAlchemy 2.0官方[Transactions and Connection Management](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)：MIT文档参考，沿用原begin_nested与defer_commits，业务写入和步骤在同一外层事务内提交，写失败不制造成功记录。
- 适配：已有metrics/analysis_todo/product_context/listing_draft和verify复用；新的证据判定放在局部服务，以卖家历史成本、原分析缺口与明确商品参数为依据。无新依赖或平台写入。Firecrawl状态认证成功但剩余额度为-318，改用官方web页面，不触发新的收费任务。

## R2 A4 卖家任务入口与分组导航（2026-10-10）

- W3C官方[Disclosure Navigation](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/examples/disclosure-navigation/)：按W3C permissive文档/示例许可参考原生按钮、列表、`aria-expanded`、`aria-controls`及当前页面语义；自行实现五组导航，展开入口和子页均可键盘操作。
- Vue Router官方[Active links](https://router.vuejs.org/guide/essentials/active-links.html)与[Navigation guards](https://router.vuejs.org/guide/advanced/navigation-guards.html)：MIT文档参考；沿用RouterLink、现有登录守卫和对象query，分组只改变入口显示，不更改业务URL或审批权限。
- 适配：复用AppShell/WorkInbox及Workbench只读投影，新增明确业务视图与全范围计数，保留旧筛选、历史和19个业务页面；人工核对、内部任务完成、来源支持解决分别表达。前端遵循项目现有深绿与浅色纸面样式，无新依赖。只读UTC查询验证兼容整秒和微秒时效，实施须再覆盖详情与列表一致性。
- Firecrawl在本轮认证状态下无法fetch，使用官方网页fallback核实；不复制整套组件或引入菜单框架。

## R2 A3 异常复核与处理证据（2026-10-10）

- Shopify官方[订单状态](https://help.shopify.com/en/manual/fulfillment/managing-orders/order-status)及[库存状态](https://help.shopify.com/en/manual/inventory-and-locations/fundamentals/inventory-states)：区分来源履约状态、可售库存与人工核对；平台资料按站点版权条款作语义参考，不复制正文或业务实现。文件中的状态只证明卖家提供的来源，不能充当本系统外部操作回执。
- SQLAlchemy官方[版本计数](https://docs.sqlalchemy.org/en/20/orm/versioning.html)：MIT / 官方文档；借鉴并发旧版本检测，沿用现有用户→店铺锁与显式版本条件，不依赖ORM版本计数自动保护批量更新。
- 适配：复用OperationTask/Event，保存独立人工凭据和复检快照；同对象、新数据时间、原规则、原范围共同限定解决结论，历史来源加入既有隐私清除链。消息通用导入的可选回复字段不声称兼容平台原生CSV，也不增加外发。
- Firecrawl状态检查已认证但fetch失败，改用内置web核实上述官方页面；本包只使用合成数据。

## R2 A1-3 渠道字段预设（2026-10-10）

- Shopify官方[商品CSV说明](https://help.shopify.com/en/manual/products/import-export/using-csv)：当前表头SKU、Title、Price、Cost per item分别作为SKU、名称、销售单价、单位采购成本候选。URL handle仅用于格式识别；币种由卖家另行确认；国际售价、比较价及描述不自动加入商品事实。官方页面同时提示旧版列名不同，故按本次核实日期限定字段签名，允许维护者停用预设。
- Shopify官方[订单CSV说明](https://help.shopify.com/en/manual/fulfillment/managing-orders/exporting-orders)：多行订单部分字段空白，退款为整单金额，公开字段表没有稳定订单行ID；缺完整行级依据时暂不提供订单预设。Amazon官方[Order Reports](https://developer-docs.amazon/sp-api/docs/report-type-values-order)按报告类型列出不同字段，本次核对的Flat File Orders By Order Date Report为制表符分隔；目前未取得能核对单价/行总额及状态转换的实际样本，Amazon订单预设条件延期。
- 资料版权分别归Shopify/Amazon，按官方站点条款参考字段语义，未复制正文、样本或实现。Firecrawl状态检查网络失败，使用内置web读取官方文档。自行制作合成字段子集验证；不将官方文档核实等同真实卖家文件验证。
- 实现选择：派生候选不改变批次映射。用户显式应用后复用预览、逐行修正、语义确认和保存；字段签名不符/预设停用时仍可手工映射。无新解析器、依赖或迁移。

## R2 A1-2 安全分批与原子撤销（2026-10-10）

- Python 官方 [csv](https://docs.python.org/3/library/csv.html)：按 CSV 记录迭代，使用 `newline=""` 保留引号内换行，重写时由 csv.writer 转义。PSF 标准库与文档，仅参考接口自行实现；复用项目现有解析器逐片核验，未新增依赖。
- SQLAlchemy 官方 [Transactions and Connection Management](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)：参考一次事务的提交/回滚边界。SQLAlchemy MIT，官方文档仅作接口依据；沿用 UnitOfWork.defer_commits 将整组撤销和原批次服务组合在一个事务内，故障回滚后全部分片与版本保持。
- 适配：本地 UTF-8 CSV 拆分最大40MiB/40000行/20片，单片仍为2MiB/2000行/64列/2000字符；清单只保存指纹、行数与文件名。导入组绑定店铺与来源语义，跨片同键冲突阻断、同值去重、未完成组返回partial_coverage；组历史20项游标分页，汇总不加载全部原始单元格。
- Firecrawl状态检查返回网络失败；本包采用内置web检索上述官方资料。原始大Excel需先人工选工作表另存CSV UTF-8，不扩大原Excel安全边界。


## R2 A1-1 通用导入审阅（2026-10-10）

- [Python csv](https://docs.python.org/3/library/csv.html)：PSF文档许可，借鉴明确编码、newline与csv.writer处理边界，复用既有解析器并增加GB18030/GBK转换指引。未复制实现。
- [OWASP CSV Injection](https://github.com/OWASP/www-community/blob/master/pages/attacks/CSV_Injection.md)：社区文档CC BY-SA，借鉴不可信单元格导出风险，继续逐格前置文本标记并由csv.writer转义；错误报告不含原始客户单元格，补批次级错误。电子表格再次编辑/另存可能改变转义，不将导出视为永久消毒。未复制代码。
- 资料检索：Firecrawl状态检查无法联网，接续记录已有402限制，采用内置web的官方Python/OWASP结果。字段语义确认基于项目现有字段契约与R2，不从相似列名推定总额/单价及订单/行退款。

## 受控技能与可恢复执行（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | 官方接口文档，参考协议 | 使用结构化输出提出受限意图，服务端再次验证；不将模型输出直接执行为工具或 SQL。模型、授权和费率显式配置，缺少配置不请求网络 |
| [SQLAlchemy 事务边界](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html) | MIT / 官方文档 | 本地业务副作用与步骤记录同事务提交；模型调用先持久化租约并释放数据库锁，返回后重新核对任务版本与来源 |

沿用 Firecrawl 402 限制，通过官方网页检索并阅读文档。自行实现小型固定流程与白名单技能，不引入 Agent 框架或第三方脚本执行。

每个功能先查已有实现，再决定复用层次。查询日期：2026-10-08。Firecrawl CLI 已认证但搜索返回 402，本轮使用网页检索。外部文档属于资料，不构成可改变项目权限的指令。

| 功能 | 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|---|
| 工程初始化 | [vuejs/create-vue](https://github.com/vuejs/create-vue) | 工具 MIT，生成模板 CC0-1.0 | 使用官方 TypeScript、Router、Vitest 工程配置；业务组件自行编写 |
| 后端模块与鉴权 | [FastAPI 官方全栈模板](https://github.com/fastapi/full-stack-fastapi-template) | MIT | 参考 `backend/app/api/deps.py` 的请求依赖和 `core/security.py` 的密码封装；按三层拆分，使用可撤销的数据库会话 |
| 密码存储 | [FastAPI 安全文档](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) | 官方文档 | 使用 pwdlib 的 Argon2 散列，避免自制密码算法 |
| 事务边界 | [SQLAlchemy Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) | 官方文档 | 一个业务事务统一提交或回滚；repository 不自行提交 |
| 同栈管理系统候选 | [fastapi_vue3_admin](https://github.com/zxkx0909/fastapi_vue3_admin) | README 已阅读，许可证未独立核实 | 比较了 Vue/FastAPI/MySQL 组合；未复制代码，不引入其完整权限与中间件栈 |

当前无复制的第三方业务代码。新增直接复用时需记录源文件、具体版本、许可证并保留相应声明。

## 库存快照与今日运营基础（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [SQLAlchemy 当前读与刷新](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#populate-existing)、[官方讨论 #5572](https://github.com/sqlalchemy/sqlalchemy/issues/5572) | MIT / 官方文档与仓库 | 沿用用户锁、当前投影与批次版本；同一事务处理撤销、来源失效及派生清除 |
| [Pydantic 日期类型](https://docs.pydantic.dev/latest/api/standard_library_types/#datetimes)、[官方校验错误说明](https://github.com/pydantic/pydantic/blob/main/docs/errors/validation_errors.md) | MIT / 官方文档与仓库 | 快照时间先按明确时区解析为 UTC，数量和阈值严格校验；时效由查询时的服务端时间与卖家选定窗口判断 |

已检索官方网页与 GitHub 资料。沿用已知 Firecrawl 402 限制使用网页工具；自行编写业务规则，不复制第三方业务代码。库存按店铺、渠道、SKU 分开，不合计可能共享的跨渠道库存，不从订单扣减或推算库存。

## 客服消息、政策证据与人工接管（2026-10-08）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [SQLAlchemy 查询刷新](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#populate-existing)、[官方相关问题](https://github.com/sqlalchemy/sqlalchemy/issues/5572) | MIT / 官方文档与仓库 | 用户锁内当前读核对消息、订单源行和政策版本；撤销、清除与草稿失效在同一事务处理 |
| [Pydantic 校验器](https://docs.pydantic.dev/latest/concepts/validators/) | MIT / 官方文档 | 日期必须带时区；政策生效区间、确认布尔值与状态动作由服务端契约校验，原消息不能改变权限 |

Firecrawl 402 限制仍适用，已检索阅读官方网页。消息复用已有有界文件导入；政策版本和客服流程自行实现。当前生成方式为明确标记的本地规则，后续真实模型沿用受控服务边界。

## Listing 草稿与本地审批（2026-10-08）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [SQLAlchemy 版本计数](https://docs.sqlalchemy.org/en/20/orm/versioning.html) | MIT / 官方文档，已检索阅读 | 借鉴旧版本检测；沿用用户锁和当前读，显式比较候选版本、来源行与本地生效版本，编辑产生独立历史版本 |
| [FastAPI 测试依赖覆盖](https://fastapi.tiangolo.com/advanced/testing-dependencies/) | 官方文档 / 项目 MIT | 生成器采用可注入接口，在测试中注入明确标记的替身，验证不可信输出仍受事实和审批门禁约束；默认使用本地事实摘取模板 |

沿用已确认的 Firecrawl 402 限制，使用官方网页检索。自行实现三层业务与页面，不复制业务源码。只向生成器传商品名称与参数；本切片没有真实模型调用或平台发布。

## 已知毛利与受控问数（2026-10-08）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [Python Decimal](https://docs.python.org/3/library/decimal.html) | PSF / 官方标准库文档 | 十进制字符串进入 Decimal；行金额与合计保持十进制，百分比仅显示时舍入；自行编写统计函数 |
| [SQLAlchemy ORM 查询选项](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html) | MIT / 官方文档 | 在用户锁内使用当前读与 populate_existing，读取来源版本并保存快照；分析与导入使用一致锁顺序 |

沿用 Firecrawl 402 的已知限制，通过官方网页检索确认。只借鉴 API 和事务语义，没有复制业务源码。受控问数先以明确意图和固定问题入口调用业务服务，模型凭据与预算未确认，界面明确标记本地规则。

## 商品与订单导入（2026-10-08）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [django-import-export 工作流](https://django-import-export.readthedocs.io/en/4.3.14/import_workflow.html)、[源码](https://github.com/django-import-export/django-import-export/blob/main/import_export/resources.py) | BSD-2-Clause，已核对仓库 LICENSE | 借鉴预览→确认、逐行结果、重复对比和整批事务；自写 FastAPI 服务，不引入 Django、不复制源码 |
| [openpyxl 官方文档](https://openpyxl.readthedocs.io/en/stable/)、[Excel reader](https://openpyxl.readthedocs.io/en/stable/_modules/openpyxl/reader/excel.html) | MIT/Expat | 使用只读解析、保留公式类型用于拒绝；安装 defusedxml，额外约束 ZIP 大小、行列数并拒绝宏和外部链接 |
| [Python csv](https://docs.python.org/3/library/csv.html)、[zoneinfo](https://docs.python.org/3/library/zoneinfo.html) | Python 官方标准库 / PSF | CSV 只做文本解析；显式解析本地时间并拒绝 DST 重叠/缺口，UTC 入库 |

本次沿用已确认的 Firecrawl 402 限制，使用网页检索官方资料。平台风格别名仅为合成格式候选，不标为真实平台已验证预设。

持续集成参考：[actions/setup-node](https://github.com/actions/setup-node)、[astral-sh/setup-uv](https://github.com/astral-sh/setup-uv)、[Playwright CI](https://playwright.dev/docs/ci-intro)。借鉴官方安装与测试顺序；工作流按本项目的 MySQL、pytest、Vue 测试组合编写。Actions 引用已核对的提交 SHA。
## 有界 R1 内部预授权（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [OWASP Transaction Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html) | OWASP Cheat Sheet Series，CC BY-SA 4.0；仅参考原则 | 服务端绑定可见对象、范围和有效时间，执行时再次核验；预授权仅开放内置保存候选能力，独立实现，不复制源码或正文 |
| [SQLAlchemy SAVEPOINT](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html) | MIT / 官方文档 | 授权消耗、内部候选和步骤使用同一事务，失败一起回滚；延用用户→店铺锁序和当前读，防止并发超用 |

沿用已确认的 Firecrawl 402 限制，通过官方网页检索。授权绑定实际检查预览及规则/来源版本；每次成功保存消耗一次，重放不重复扣减，撤回候选不返还额度。

## 经营规则与版本记忆（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [SQLAlchemy 版本计数](https://docs.sqlalchemy.org/en/20/orm/versioning.html)、[官方维护者讨论](https://github.com/sqlalchemy/sqlalchemy/discussions/6607) | MIT / 官方文档与仓库 | 显式期望版本防止覆盖，独立追加历史版本；沿用用户锁与当前读，自行实现业务逻辑 |
| [MySQL Locking Reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html) | Oracle 官方文档 | 规则修改与业务执行遵守同一用户→店铺锁序，防止检查后改规则的并发窗口 |

沿用已确认 Firecrawl 402 限制检索官方网页。规则按店铺/渠道/数据身份生效；文本偏好只作卖家提供的参考，权限由代码契约控制。无第三方业务源码复制。

## 独立新品利润计算器（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [Python Decimal](https://docs.python.org/3/library/decimal.html)、[CPython 文档源](https://github.com/python/cpython/blob/main/Doc/library/decimal.rst) | PSF / 官方标准库文档 | 字符串进入 Decimal，过程保留精度；余额率展示使用 HALF_UP，保本价按币种最小单位向上取整，独立编写公式与边界测试 |
| [SBA 盈亏平衡说明](https://legacy.sba.gov/business-guide/plan-your-business/calculate-your-startup-costs/break-even-point) | 美国政府官方业务指南，参考公式概念，不复制内容 | 从收入覆盖成本推导单件假设模型：售价 × (1 − 已填售价费率合计) − 采购成本 − 已填固定费用；不将单件保本价冒充企业盈亏平衡销量或真实净利润 |

沿用 Firecrawl 402 的已知限制，通过官方网页检索。P0 使用明确单币种、不换汇；所有费用为手工假设，空值与显式零分开。规则与页面自行实现，无第三方业务代码复制。

## 今日运营与可恢复待办（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [SQLAlchemy Session API](https://docs.sqlalchemy.org/en/20/orm/session_api.html)、[维护者的并发更新说明](https://github.com/sqlalchemy/sqlalchemy/discussions/6607) | MIT / 官方文档与维护者讨论 | 用户锁内当前读，版本冲突返回 409；同一来源与规则的待办用唯一约束去重；自行实现业务状态机 |
| [MySQL Locking Reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html) | Oracle 官方文档，参考事务语义 | 导入与运营统一锁序，同事务失效和擦除派生内容；响应在提交前组装 |

沿用已确认的 Firecrawl 402 限制，使用官方网页检索。复用项目现有 Decimal 利润规则和库存时效判定，分别记录巡检范围、来源有效性、审批与处理状态。

## R2 测试邮件与回查（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [Resend 发送 API](https://resend.com/docs/api-reference/emails/send-email)、[幂等键](https://resend.com/docs/dashboard/emails/idempotency-keys) | 官方 API 文档，服务使用受供应商条款约束；仅参考协议，不复制源码 | 复用现有 httpx 编写默认关闭的纯文本适配器；固定 HTTPS 地址、独立测试名单、业务持久去重。供应商键仅保留 24 小时，本地发送标记长期保留，未知态不重新 POST |
| [读取发送记录](https://resend.com/docs/api-reference/emails/retrieve-email)、[列举已发送邮件](https://resend.com/docs/api-reference/emails/list-emails) | 官方 API 文档 | 只读回查：按回执或有界列表发现候选，再匹配标签、地址及全文摘要；查无记录仍未知。通道 delivered 只表示通道结果，收件证据另记 |
| [读取域验证](https://resend.com/docs/api-reference/domains/get-domain) | 官方 API 文档 | 检查域名、verified 状态、sending 能力；使用卖家显式同意的固定验证码邮件验证部署名单内测试邮箱的持有权；验证码仅哈希保存 |

2026-10-10基础G-06审阅准备再次核对发送API的纯文本正文契约：保留全文绑定审批与原通道；将经营摘要的分支count表述为“检查记录数”，与本地检查统计口径一致。仅修订应用正文标签，不修改供应商协议、权限或发送次数。官方文档仅作协议参考，无源码复制。

沿用已确认的 Firecrawl 402 限制，以官方网页核对协议。部署绑定一个 owner/shop/发送地址/测试收件地址；凭据轮换失效旧连接。经营摘要从当前检查记录生成；R2 独立授权固定全文、目标和关联检查，单份最多提交一次，可在提交前撤销。真实通道与邮箱证据仍沿用 questions 第 4 项。

## 跨店总览与经营摘要（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [SQLAlchemy Session API](https://docs.sqlalchemy.org/en/20/orm/session_api.html)、[官方问题 #5572](https://github.com/sqlalchemy/sqlalchemy/issues/5572) | MIT / 官方文档与维护者讨论 | 沿用用户锁后当前读及 populate_existing，按店铺 ID 顺序锁定多店来源，保存不可变摘要及来源关系；自行实现业务汇总 |
| [Python datetime](https://docs.python.org/3.11/library/datetime.html) | PSF / 标准库官方文档 | 以 IANA 时区的日历日期确定起止点，分别转换 UTC；跨夏令时的日对比保持日历天数，而非假定每天 24 小时 |

沿用 Firecrawl 402 的已知限制，通过官方网页检索。金额复用现有 Decimal 订单计算，分币种聚合，不换汇。摘要为本地确定性结果，缺失、导出时间未知和当前快照的边界逐项展示；无第三方业务源码复制。

## 统一任务、草稿与审批驾驶舱（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [SQLAlchemy SELECT / UNION ALL](https://docs.sqlalchemy.org/en/20/core/selectable.html)、[官方教程](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html) | MIT / 官方文档 | 使用已有业务表的有界联合查询，按创建时间、类型及 ID 稳定翻页；只投影事项元数据，不复制业务正文或建立第二套任务状态 |
| [Vue Router 数据获取](https://router.vuejs.org/guide/advanced/data-fetching.html)、[Composition API](https://router.vuejs.org/guide/advanced/composition-api) | MIT / 官方文档 | 深链携带明确店铺与对象 ID，路由改变重新加载原始业务对象；加载和失败态清晰展示，服务端重新核验权限与来源 |

沿用已确认 Firecrawl 402 限制，以官方网页检索。首页只读取本地已存在记录；所有审批、恢复和外部回查继续调用既有受控业务服务，首页读取不触发模型或发信。

## 经营问数的模型证据解释（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | 官方协议文档，服务受供应商条款约束；不复制业务源码 | Responses 的 text.format/json_schema/strict；拒绝与 incomplete 单独处理。结构合规不等于事实正确，因此服务器另验事实和建议编号，Decimal 指标从受控服务取得 |
| [Responses API](https://developers.openai.com/api/reference/python/resources/responses) | 官方 API 文档 | 固定官方端点、store=false、无工具、限制输入/输出与费用；记录 usage，响应失效仍保存已知费用，无 usage 保留预留且不自动重发 |

沿用 Firecrawl 402 限制，经官方文档检索。模型仅接收卖家同意的问题、明确范围和匿名聚合事实，不接收原始订单号、SKU 文本、文件名或买家消息。模型选择证据顺序和下一步核对建议；事实句由已验证事实渲染，来源与费用缺口强制保留。供应商和预算仍由部署者配置，本地验证使用替身。

## 阿里云百炼模型接入（2026-10-09）

基础G-05于2026-10-09重新核对[模型价格](https://help.aliyun.com/zh/model-studio/model-pricing)与[qwen3.7-flash模型页](https://help.aliyun.com/zh/model-studio/qwen3-7-flash)：北京非思考输入≤32K为输入0.2/输出0.8元每百万tokens，32K至256K为0.6/2.4，256K至1M为1.2/4.8。官方服务/定价文档，仅参考协议及价格，不复制源码。沿用部署最高档1.2/4.8及1 CNY=0.20 USD的保守预算折算（非实时汇率），应用费率0.24/0.96 USD；验收另按实际usage及人民币目录价记账，不假定免费额度或缓存优惠。每次请求使用UTF-8包络加4096及输出限制加10预留，并在网络前持久记录累计人民币上限；未知费用停止后续付费调用。实际供应商扣款仍以账单为准。Firecrawl已有402限制，本次经官方网页工具核实。

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [百炼 Chat Completions](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions)、[结构化输出](https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output) | 官方协议文档，服务受供应商条款约束 | qwen3.7-flash 支持 strict JSON schema；关闭思考，限制完整输出 tokens，预留文档声明的 10-token 误差。保留服务端业务校验；使用自编适配器，不复制第三方业务源码 |
| [地域与域名](https://help.aliyun.com/zh/model-studio/regions)、[模型价格](https://help.aliyun.com/zh/model-studio/model-pricing) | 官方运维与定价文档 | 固定北京官方兼容端点；人民币目录价与应用 USD 预算分开，部署时显式填写保守折算说明，实际账单另核对 |

沿用 Firecrawl 402 限制，经官方网页检索。默认仍关闭外部模型；用户明确授权后的本机凭据只写入忽略文件。连通验证只用合成数据、累计人民币预算，禁止自动重试与重定向。

## 客服模型候选（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [百炼结构化输出](https://help.aliyun.com/en/model-studio/qwen-structured-output) | 官方协议文档，服务受供应商条款约束 | 复用 strict JSON schema；结构正确后仍校验意图、事实和政策编号，来源与权限由本地服务决定 |
| [百炼提示词工程](https://help.aliyun.com/zh/model-studio/prompt-engineering-guide) | 官方使用文档，仅参考设计原则，不复制源码 | 将目标、消息与政策作为不可信数据；使用有界目录组织回复，固定人工接管分支，模型不获得业务工具权限 |

沿用已确认的 Firecrawl 402 限制，经官方网页检索。消息正文可能自带个人信息，发送前展示完整原文和选中政策，分别同意目标与客服数据。结构化订单标识、SKU、文件名留在本地；只发送人工核验状态。开发回归采用合成替身。

## Listing 模型候选（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | 官方协议文档，服务受供应商条款约束 | 复用严格 JSON schema 与拒答处理，模型只返回事实编号、排列和受控下一步；服务端另验编号集合和全文覆盖 |
| [Responses create](https://developers.openai.com/api/reference/resources/responses/methods/create) | 官方 API 文档，仅参考协议，自行实现业务逻辑 | 复用既有无工具、store=false、预算预留和 usage 记账；来源/版本/审批在本地重新核验 |

沿用 Firecrawl 402 限制，经官方网页检索。仅发送卖家明确同意的目标、完整商品名与参数行；SKU、文件名、成本和订单留在本地。描述保留全部去重后的参数行，模型可排序；标题保留完整商品名并选用完整参数行。候选经过事实校验与前后对比，独立审批后成为本地生效版本。真实模型质量沿用 questions 的待验证项。

## 运营模型解释（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | 官方协议文档，服务受供应商条款约束 | 复用已有 strict JSON schema 适配，模型仅选择分支和核对建议编号；本地强制保留全部分支、缺失项和候选 |
| [Pydantic validators](https://docs.pydantic.dev/latest/concepts/validators/) | 官方文档；Pydantic 源码 MIT，未复制实现 | 结构校验之后核对编号集合、重复及来源版本，业务权限独立于模型结构 |

沿用已确认的 Firecrawl 402 限制，经官方网页检索。发送数据限定为用户目标、范围、分支状态/行数和候选类型计数；不传分支原始解释、SKU、订单号、消息正文和文件名。全部具体证据保留在本地审阅，内部保存复用 OperationsService；合成替身验证两种供应商协议。

## 定时运营与站内通知（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [Python zoneinfo](https://docs.python.org/3/library/zoneinfo.html)、[datetime](https://docs.python.org/3.11/library/datetime.html) | 官方标准库文档，PSF；未复制源码 | IANA 时区、UTC 转换和 fold；重复时刻取第一次，跳过不存在的时刻，日历周期独立于服务器时区 |
| [MySQL 8.4 locking reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html) | 官方数据库文档；仅参考事务语义 | 用户→店铺→计划当前锁定读，周期唯一键与原子事务避免多进程重复；本地检查无网络，崩溃回滚后可安全重跑 |

沿用 Firecrawl 已确认的 402 限制，通过官方网页检索。使用已有 SQLAlchemy 与标准库实现有界调度；每周期只启动固定 daily 检查，候选仍逐次审批，站内通知仅保存执行索引与状态。

## 日周月经营报表调度（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [Python datetime](https://docs.python.org/3/library/datetime.html) | 官方标准库文档，PSF；未复制源码 | 先在计划 IANA 时区定位自然日、周一和月首，再计算完整上期与前期；月份按日历移动，不以固定 30 天替代 |
| [SQLAlchemy Session API](https://docs.sqlalchemy.org/en/20/orm/session_api.html) | 官方文档，源码 MIT；未复制实现 | 使用现有 begin_nested / defer_commits 将报告、依赖、周期通知和下次时刻作为同一事务；失败整体回滚 |
| [Vite CI 生命周期修复](https://github.com/vitejs/vite/pull/3659) | Vite 官方仓库，源码 MIT；仅参考设计 | 自动化 Vite 子服务设置 CI=true，由 Playwright 统一管理启停 |
| [Vite 构建预览](https://vite.dev/guide/static-deploy)、[Playwright webServer](https://playwright.dev/docs/test-webserver) | 官方文档；Vite MIT，Playwright Apache-2.0，未复制源码 | E2E 先构建页面再启动本机 preview，API 代理沿用独立测试端口；两个服务由测试运行器启动并回收 |

沿用 Firecrawl 已确认的 402 限制，经官方网页检索。报表保存复用 OverviewService；计划确认授权仅覆盖本地报表保存，通知仅引用报告 ID，来源清除沿用原依赖链。

## 商品信息质量检查（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [Google 商品数据规范](https://support.google.com/google-ads/answer/7052112?hl=en) | 官方产品文档，按网站条款使用；仅参考字段分类，未复制正文或实现 | 名称、描述、价格与标识分别核对；本地规则仅检查当前已导入字段，平台必填与合规规则不能直接当作跨平台结论 |
| [SQLAlchemy Session API](https://docs.sqlalchemy.org/en/20/orm/session_api.html) | 官方文档，源码 MIT；未复制实现 | 用户→店铺锁后当前读，预览摘要复验，报告、来源依赖和审计在同一事务保存；清除来源时同步擦除派生正文 |

沿用已确认的 Firecrawl 402 限制，通过官方检索获得资料。商品主档当前不包含品牌、GTIN/MPN、图片或类目属性模板，明确列为未检查。相似 SKU、参数冲突与描述关键词只提供人工核对线索；本地质量报告不调用模型、不修改商品或外发。

## 商品本地批量修订（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [Shopify productVariantsBulkUpdate](https://shopify.dev/docs/api/admin-graphql/latest/mutations/productVariantsBulkUpdate) | 官方接口文档，受网站条款约束；未复制源码 | 参考整批失败与逐项错误的区分。本地首片最多 50 个商品，任一基线冲突则整批不生效，保存逐项原因；不调用平台接口 |
| [SQLAlchemy Session API](https://docs.sqlalchemy.org/en/20/orm/session_api.html)、[官方 issue 5572](https://github.com/sqlalchemy/sqlalchemy/issues/5572) | SQLAlchemy MIT；官方文档与问题记录 | 锁定读配合 populate_existing 更新 ORM 状态，修订来源行、投影、依赖与审计在同一事务；原始导入保持独立 |

沿用 Firecrawl 已确认的 402 限制，经官方网页与 GitHub 检索。人工修订生成单独来源批次，继承数据身份和渠道，登记全部祖先依赖。来源撤销使派生修订失效，清除沿依赖链擦除正文；后续文件导入仍按当前投影比较。

## 自定义实际费用与本地核对（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [SQLAlchemy Numeric](https://github.com/sqlalchemy/sqlalchemy/blob/main/lib/sqlalchemy/sql/sqltypes.py)、[Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) | 官方文档与仓库，MIT；未复制源码 | Numeric(18,4) 持久 Decimal，用户→店铺锁定读；费用版本、全部历史来源依赖与审计同事务 |
| [Python decimal](https://docs.python.org/3/library/decimal.html)、[datetime](https://docs.python.org/3/library/datetime.html) | 官方标准库文档，PSF；未复制实现 | 有界十进制金额，显式偏移与 IANA 时区一致性校验，UTC 存储，半开查询窗口与分币种汇总 |

沿用已确认的 Firecrawl 402 限制，通过官方网页检索。实际人工费用独立于新品假设；首片支持店铺未分摊和单订单行全额直接归属。凭据编号去重、来源变化待重核、历史依赖清除均由本地服务完成；平台账单/物流/回款尚未核对，费用完整性未知，不据此计算净利润。

## 通用渠道账单与费用差异核对（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [Stripe 回款核对报告](https://docs.stripe.com/reports/payout-reconciliation)、[账务分类](https://docs.stripe.com/reports/reporting-categories) | 官方业务文档，按网站条款使用；未复制正文或源码 | 交易明细与回款分别表示，保留稳定行标识和来源。通用文件明确销售款、退款、费用、平台记载回款；银行到账证据单独待核，不把回款文件等同现金到账 |
| [SQLAlchemy 查询执行选项](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html) | 官方文档，源码 MIT；未复制实现 | 用户→店铺锁之后用当前读与 populate_existing，账单及费用在同一事务快照内计算，Numeric/Decimal 分币种 |

沿用已确认的 Firecrawl 402 限制，经官方网页检索。复用文件解析、预览、版本确认和批次生命周期；每行声明语义及正数绝对金额，费用凭据按统一规范化编号核对。首片只读计算当前范围的差异，不保存“已核对”人工结论，不自动改写账单或费用；平台收费映射、结算周期完整性、银行到账及真实报表验证继续待补。

## 人工收费类别映射规则（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [Amazon Finances API](https://developer-docs.amazon/sp-api/docs/finances-api) | 官方业务文档，按网站条款使用；未复制正文或实现 | 保留平台财务来源语义，分类由卖家按实际收费定义确认；本地规则不预装未经真实报表核验的平台收费表 |
| [SQLAlchemy Populate Existing](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#populate-existing) | 官方文档，源码 MIT；未复制实现 | 用户→店铺锁后的当前读同时刷新 ORM 身份缓存；预览、规则版本、账单来源及费用版本在保存时复验 |

沿用已确认的 Firecrawl 402 限制，经官方网页读取。规则按店铺/身份/渠道、去首尾空白后区分大小写的完整收费名匹配，当前规则适用于全部日期与币种；时间窗口仅限制差异预览。持久化人工规则及调整理由，账单应用结果实时计算，规则保存不等于人工账单核对结论。

## 人工核对结论存档（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [SQLAlchemy Populate Existing](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#populate-existing) | 官方文档，源码 MIT；未复制实现 | 锁后刷新 ORM 实体，保存时重新计算全部依据与版本；历史快照与当前回读分别呈现 |
| [MySQL 8.4 Locking Reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html) | 官方数据库文档；仅参考事务语义 | 用户→店铺锁覆盖结论、全部历史依赖及审计；来源/费用/规则清除与结论正文清除同事务 |

沿用 Firecrawl 已确认的 402 限制，经官方网页读取。窗口级结论限定为一致、差异已说明或待核，未知/重复/异币种/类别冲突不能确认一致。来源版本与费用/规则范围变更号防止恢复原值复活预览；本地结论不产生费用、付款或净利。

## 结算周期与人工回款凭据（2026-10-09）

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [Amazon Settlement Reports](https://developer-docs.amazon/sp-api/docs/report-type-values-settlement) | 官方业务文档，按网站条款使用；未复制源码或正文 | 区分结算标识、周期起止和付款日期；本地按原账单号精确取当前明细，周期为卖家登记的声明，不用交易发生日期猜测结算归属 |
| [Stripe Payout reconciliation](https://docs.stripe.com/reports/payout-reconciliation) | 官方业务文档，按网站条款使用；未复制源码或正文 | 平台预计到账时间、实际银行记账和余额核对各有口径；仅比较平台回款凭据与人工到账登记，一对一同币种才计算差额，未知覆盖和余额保持待核 |

沿用 Firecrawl 已确认的 402 限制，经官方网页检索和读取。每份登记限定一个原账单号、366 天周期、1000 行来源、50 笔人工凭据；回款及到账可在周期之后。来源快照、全部历史批次依赖、UUID 幂等及原子审计沿用现有模式；独立登记不生成费用或发起付款。无银行接口或原始银行文件核验时，人工登记始终标注卖家声明。

### Windows 浏览器验证运行时

| 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|
| [Node Windows TCP 连接崩溃 #63620](https://github.com/nodejs/node/issues/63620) | 官方仓库问题及维护者回复；未复制复现代码 | 24.15.0 在短连接负载下的原生退出与本机现象相近，维护者确认 24.16.0 的相关修复；作为隔离版本对照的依据，不把相似现象当作本机堆栈已确诊 |
| [Node 24.16.0 发布与校验值](https://nodejs.org/en/blog/release/v24.16.0) | 官方发行说明；Node 运行时 MIT 及所附第三方许可证 | 官方 Windows x64 zip 按公开 SHA256 校验，解压到被忽略的 `.local/runtimes`；仅测试命令临时修改 PATH，全局安装及项目依赖锁保持原状态 |

## SO-056 订单金额与账单待核清单（2026-10-09）

- Shopify 官方 [Refund](https://shopify.dev/docs/api/admin-graphql/latest/objects/Refund)：退款包含商品、运费、税费等组成，退款记录存在不代表支付已成功，须另查交易状态。文档版权归 Shopify，本轮只借鉴语义，不复制实现；当前订单只有行退款累计值，缺退款编号、发生时间和组成，故仅展示待核证据，不自动计算退款差额或确证到账。
- Amazon 官方 [Settlement Reports](https://developer-docs.amazon.com/sp-api/docs/report-type-values-settlement)：V2 账单分列 amount-type / amount-description / amount，另有订单及订单项标识。文档版权归 Amazon，本轮只借鉴字段边界；通用账单的 sale 标签不能证明与折后商品款相同，默认金额口径未知。卖家在只读查询中明确两侧金额口径并填写依据后，才对精确一对一、同币种、同当地日期且均在窗内的销售记录计算账单减订单差额。
- 适配决定：保持现有原始导入契约，新增独立 API → service → repository 的有界只读核对；窗口选取候选后回查同范围同订单号全部当前来源，防止窗口截断隐藏多行、多笔与迟到记录。未知文件覆盖、来源缺一侧、跨日和复杂分摊均保留待核。无新增依赖、平台接口调用、模型调用或财务写入。

## 基础版本：跨页流程与备份恢复（2026-10-09）

- Vue Router官方[编程式导航](https://router.vuejs.org/guide/essentials/navigation.html)与[Composition API](https://router.vuejs.org/guide/advanced/composition-api)：借鉴显式query传递及对实际变化字段响应。vuejs/router采用MIT；本轮仅参考公开接口，自行实现有界对象ID、范围与返回事项契约，不复制实现。
- MySQL8.4官方[mysqldump](https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html)与[备份方式](https://dev.mysql.com/doc/refman/8.4/en/backup-methods.html)：参考InnoDB single-transaction、无并发DDL和逻辑恢复约束。官方手册为Oracle版权，不复制内容；工具使用现有MySQL容器中的客户端，凭据不放参数，恢复到新建隔离库并核对代表记录。Firecrawl已知402，使用官方网页检索核实。

## 基础版本：首次启动与进程恢复（2026-10-09）

- Docker官方[独立项目名](https://docs.docker.com/compose/how-tos/project-name/)与[Compose参数](https://docs.docker.com/reference/cli/docker/compose/)：使用独立项目名、配置文件和端口隔离容器、网络与持久卷；只启动验收项目的MySQL。Docker Compose采用Apache-2.0，文档仅作接口参考，不复制实现。
- Pydantic官方[Settings优先级](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/)：环境变量优先于dotenv。pydantic-settings采用MIT，本轮独立验收清除继承的SOLOOPS变量，从新副本backend工作目录读取新配置；真实模型及邮件显式关闭，避免继承开发配置。
- 适配：从已提交源码导出独立副本，执行现有setup_local、迁移及账号CLI，经过真实HTTP与独立API进程验证。初始化补齐对已有.local/test.env的保护，所有配置文件使用独占创建模式；配置与证据均留忽略目录。

## QQ 邮箱测试外发（2026-10-10）

- 腾讯官方[QQ 邮箱连接说明](https://hiflow.tencent.com/document/applications/qq-mail/)及[SMTP 配置示例](https://cloud.tencent.com/document/product/1207/45117/)：开启邮箱 SMTP 服务，以完整 QQ 邮箱地址和客户端授权码登录 `smtp.qq.com:465`，启用 SSL。官方资料版权归腾讯；仅参考协议参数，自行实现，未复制正文或代码。Firecrawl 已确认 402，本次使用官方网页检索。
- Python 官方[smtplib](https://docs.python.org/3/library/smtplib.html)与[email.message](https://docs.python.org/3/library/email.message.html)：PSF 文档与标准库接口，沿用项目 Python 标准库，无新依赖。固定 SSL 主机、证书校验、有限超时；UTF-8 纯文本邮件，稳定 Message-ID；SMTP DATA 最终 250 才记录服务器接受，连接断开保留未知，清理连接失败不覆盖已取得的接受结果。
- 适配：由配置选择 QQ SMTP 通道，账号/店铺与授权码绑定通道；用户指定的单个收件地址与全文绑定审批；通道类型随验证记录持久化，配置变更不能复用旧审批。QQ SMTP 无远端回执查询接口，未知结果仅人工核对原收件箱并记录独立收件声明，不伪造供应商送达或自动重发。Resend 历史通道保留原有语义。

## R2 A2：订单行历史成本依据（2026-10-10）

- Shopify 官方[利润报告](https://help.shopify.com/en/manual/reports-and-analytics/shopify-reports/report-types/default-reports/profit-reports)：商品成本、净销售额和毛利有明确区别，折扣/退款影响利润，成本的记录时点影响覆盖。资料版权归 Shopify；仅参考业务含义，自行实现。SoloOps 保留自身已支付订单/退款归原订单窗规则，历史成本由卖家按订单源行确认，不将当前商品成本或平台报表口径视为独立核实的会计事实。
- SQLAlchemy 2.0 官方[版本计数](https://docs.sqlalchemy.org/en/20/orm/versioning.html)与[Numeric](https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Numeric)：MIT；参考并发版本与 Decimal 存取机制。项目已有用户→店铺锁与显式 expected_version，沿用该协议追加凭据版本；金额列 Numeric(18,4)，不引入依赖或自动浮点转换。
- Firecrawl CLI 状态再次返回 fetch failed，未能取得账户信息；本次通过内置 web 读取上述官方页面。借鉴限于语义/接口说明，没有复制实现。差异计划见 r2-a2-plan.md，开发须以前包目标 CI 成功为前置。

### A2 成本写入与重算时序补充

- Vue官方[组件事件](https://vuejs.org/guide/components/events.html)（MIT）与Playwright官方[操作等待](https://playwright.dev/docs/actionability)（Apache-2.0）：参考显式组件事件传播和按钮enabled检查，不复制实现。成本写入的working状态经证据组件传给分析页，写入及随后来源刷新期间禁止重算/切店；通过受控延迟写入回包验证禁用和完成后的实际重算结果，保持原金额与历史断言。

## R2 B3：审阅绑定与人工证据（2026-10-10）

- OWASP [Transaction Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html)与[Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)：CC BY-SA 4.0。借鉴审阅绑定可见内容、服务端操作前再次校验及敏感数据最小化原则；自行实现版本审阅，审计仅存草稿/证据编号，不记录客户正文或证据内容。
- SQLAlchemy官方[UniqueConstraint](https://docs.sqlalchemy.org/en/20/core/constraints.html#unique-constraint)：MIT。结合既有用户/店铺锁，以唯一UUID请求键和请求指纹处理人工证据重试；相同键不同内容拒绝，来源清除擦除证据payload。
- 文档仅作设计和接口参考，未复制实现。Firecrawl已知额度不足，未发起付费抓取；本次用内置web查阅官方页面。复制/CSV沿用B2的MDN/OWASP依据。


## R2 专项 P2-01：来源一致性（2026-10-10）

- SQLAlchemy 2.0 官方 [EXISTS 子查询](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html#exists-subqueries)及 [JSON 类型](https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.JSON)（MIT）：参考关联子查询、JSON 标量与空值语义。自行实现按任务步骤索引、Listing/商品/来源主键定位的只读谓词，首页列表和分类统计与 B1 执行校验复用，不增加逐任务往返或读取副作用，无新依赖或迁移。
- Firecrawl 状态检查返回 `fetch failed`，本次使用内置 web 查阅上述官方页面；没有复制文档实现。

## R2 修复包2：日期与任务连续性（2026-10-10）

- MDN 官方 [datetime-local](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/datetime-local) 与 [HTML 时间格式](https://developer.mozilla.org/en-US/docs/Web/HTML/Guides/Date_and_time_formats)（文档 CC BY-SA）：原生日期时间值不含时区，而且允许输入夏令时不存在的当地时间。采用原生选择器、显式 IANA 业务时区与 Intl 往返匹配；不采用浏览器系统时区推断。歧义要求用户在原精确 ISO 入口选择明确偏移；原始微秒表达式不因显示切换被改写。
- Vue Router 官方 [Composition API](https://router.vuejs.org/guide/advanced/composition-api.html) 与 [导航守卫](https://router.vuejs.org/guide/advanced/navigation-guards.html)（MIT）：参考查询参数响应和路由离开/更新守卫。仅对 Agent/客服复用当前视图并观察 URL；自身保存 URL 不重挂载编辑器。通过服务端权限查询恢复对象；查询参数不携带授权、客户正文、目标文本或密钥。
- Vue 官方 [生命周期钩子](https://vuejs.org/api/composition-api-lifecycle.html)（MIT）：卸载后停止页面恢复和地址写入。读取数据时允许离开页面，任务启动/推进、草稿保存及未保存编辑仍受保护；延迟读取回包不能把用户带回旧页面。实现由项目自行编写。
- Firecrawl 状态返回 `fetch failed`，使用官方 web 检索作为回退。上述资料作接口与设计依据，自行实现组件和导航处理，不增加第三方依赖。

## R2 C：API内调度与部署边界（2026-10-10）

- FastAPI官方[Lifespan](https://fastapi.tiangolo.com/advanced/events/)与[HTTPS部署](https://fastapi.tiangolo.com/deployment/https/)（MIT项目）：参考API生命周期资源启停、TLS代理和运行进程的职责。既有进程内调度保持，新增摘要只读取已保存自动周期，不当作进程心跳；没有引入任务队列。
- OWASP [Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)（CC BY-SA 4.0）：参考HTTPS、Secure/HttpOnly/SameSite和会话生命周期关系。代码能力与真实部署证据分别记录，公开上线前逐项验证实际环境。
- 文档只作设计依据，自行实现查询与展示，无复制代码或新依赖。Firecrawl已知额度不足，使用内置web查阅官方页面。具体本地/部署门禁见本包交付文档；未取得新的生产操作授权。

## R2 修复包3：浏览器CSV拆分（2026-10-10）

- Python 3.11官方[csv](https://docs.python.org/3.11/library/csv.html)（PSF）：参考strict、newline与默认writer规则，以项目import_split.py作为逐字节对照基准，自行实现有界浏览器子集，不复制源码。
- MDN [digest](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/digest)、[Blob.slice](https://developer.mozilla.org/en-US/docs/Web/API/Blob/slice)、[TextDecoder.decode](https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder/decode)与[Worker.terminate](https://developer.mozilla.org/en-US/docs/Web/API/Worker/terminate)（文档CC BY-SA）：digest必须整块读入，故保留40MiB上限；解析按64KiB严格解码；Worker终止实现取消。只参考API和限制，自行实现，无新依赖。方案见r2-fix-uat-02-plan.md。
- Firecrawl状态再次为fetch failed，本次使用内置web检索并读取上述官方资料。
