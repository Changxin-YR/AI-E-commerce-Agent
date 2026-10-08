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
