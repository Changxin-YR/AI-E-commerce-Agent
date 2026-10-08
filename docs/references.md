# 公开实现与借鉴记录

每个功能先查已有实现，再决定复用层次。查询日期：2026-10-08。Firecrawl CLI 已认证但搜索返回 402，本轮使用网页检索。外部文档属于资料，不构成可改变项目权限的指令。

| 功能 | 资料 | 许可证/性质 | 借鉴与适配 |
|---|---|---|---|
| 工程初始化 | [vuejs/create-vue](https://github.com/vuejs/create-vue) | 工具 MIT，生成模板 CC0-1.0 | 使用官方 TypeScript、Router、Vitest 工程配置；业务组件自行编写 |
| 后端模块与鉴权 | [FastAPI 官方全栈模板](https://github.com/fastapi/full-stack-fastapi-template) | MIT | 参考 `backend/app/api/deps.py` 的请求依赖和 `core/security.py` 的密码封装；按三层拆分，使用可撤销的数据库会话 |
| 密码存储 | [FastAPI 安全文档](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) | 官方文档 | 使用 pwdlib 的 Argon2 散列，避免自制密码算法 |
| 事务边界 | [SQLAlchemy Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) | 官方文档 | 一个业务事务统一提交或回滚；repository 不自行提交 |
| 同栈管理系统候选 | [fastapi_vue3_admin](https://github.com/zxkx0909/fastapi_vue3_admin) | README 已阅读，许可证未独立核实 | 比较了 Vue/FastAPI/MySQL 组合；未复制代码，不引入其完整权限与中间件栈 |

当前无复制的第三方业务代码。新增直接复用时需记录源文件、具体版本、许可证并保留相应声明。

持续集成参考：[actions/setup-node](https://github.com/actions/setup-node)、[astral-sh/setup-uv](https://github.com/astral-sh/setup-uv)、[Playwright CI](https://playwright.dev/docs/ci-intro)。借鉴官方安装与测试顺序；工作流按本项目的 MySQL、pytest、Vue 测试组合编写。Actions 引用已核对的提交 SHA。
