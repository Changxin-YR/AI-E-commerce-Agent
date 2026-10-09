# 公开实现与借鉴记录

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
