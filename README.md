# SoloOps 重点上下文

此分支用于跨聊天连续开发，只保留稳定约束、当前状态和下一步。业务代码在 `main`，不要将本分支合并到 main。

## 用户已明确的要求

- 从 `docs/requirements/SoloOps-V1.0.md` 逐步实现完整功能，先 P0、再 P1/P2；保留 74 个 SO 和 32 个验收项。
- Vue 3 + TypeScript、Python、MySQL；克制使用框架；三层架构；函数与组件封装清楚，代码供人阅读。
- 每个功能先查 GitHub 和公开资料再开发，借鉴结构与方法并记录来源、许可证，不全盘复制。
- 每个功能完成后测试、更新文档、及时推送。开发文档包含整体思路、三层职责、问题解决过程和面试知识点。
- 需要用户意见的问题可积累到 docs/questions.md，次日集中回答；授权、真实账号和预算不能由其他模型替用户决定。
- 用户已授权上下文压力时自动创建新的 Codex 聊天继续。交接前推送并保存重点，避免两个聊天同时改本工作区。

## 当前代码与环境

- 仓库：https://github.com/Changxin-YR/AI-E-commerce-Agent.git
- 工作目录：`C:\Users\27363\Desktop\AI E-commerce Agent`
- main 最新功能提交：`acbceb8`，已推送。
- 后端：FastAPI、Pydantic、SQLAlchemy 2、PyMySQL、Alembic、pwdlib/Argon2；Python 3.11，依赖锁在 backend/uv.lock。
- 前端：官方 create-vue 基础，Vue 3/TypeScript/Router/Vite；ESLint、Vitest、Playwright；锁文件在 frontend/package-lock.json。
- Docker MySQL 8.4 已启动：`soloops-mysql-1`（业务库 localhost:3307）、`soloops-mysql-test-1`（隔离测试库 localhost:3308）。
- 本地随机数据库配置已生成，保存在被 Git 忽略的 `.env`、`backend/.env`、`.local/test.env`。不要输出、复制到文档或提交。
- `context-memory` 工作树位于 `.context-memory`，主仓库已忽略该目录。
- 网络和 MySQL/Docker 调用通常需 exec_command require_escalated；用户已授权常规开发与推送，自动审核目前允许。
- Firecrawl CLI 有认证但搜索返回 402；改用 web 检索和 GitHub 官方资料。不反复尝试计费调用。

## 已完成的第一个纵向切片

账号 CLI 创建/恢复、登录/注销、过期会话、失败锁定；HttpOnly/SameSite Cookie、CSRF Token、来源白名单；数据库会话摘要；恢复密码撤销所有会话。

经营档案持久化与 version 并发保护、拥有者隔离的店铺记录、(owner_id, code) 唯一约束、审计写入；前端登录、首次使用空状态、经营资料、店铺表单和手机布局。

SO-001/066/074 仅基础切片合成测试通过。四条 MVP 尚未完成，不能宣称 P0 已交付。平台状态始终 file_only；目前没有真实用户业务数据、模型凭据或外发授权。

## 代码入口

`backend/app/api/routes/profile.py` → `services/profile.py` → `repositories/identity.py` → `models/identity.py`。共享数据库事务由 UnitOfWork 提交，路由不写 SQL。`schemas` 定义 HTTP 契约。身份依赖在 api/dependencies.py。

`frontend/src/views/SettingsView.vue` → `components/ProfileForm.vue` / ShopForm.vue → `api/identity.ts`。令牌在 HttpOnly Cookie，CSRF 在内存。样式在 styles/tokens.css 和 main.css，沿用绿色克制工作台。

## 已执行检查

- MySQL pytest 19 项通过，包含并发单赢家、跨账号隔离、CSRF、过期/撤销会话和失败锁定。
- Ruff 格式/规则通过，mypy 28 个源码文件通过。
- npm lint/build 通过，Vitest 4 项通过，Playwright Chromium 3 项通过。
- 桌面及 390×844 手机截图已用 view_image 查看；手机无水平溢出。
- Alembic upgrade 与 check 通过，模型和数据库无漂移。
- npm audit 0 已知漏洞；已精简 lint 辅助依赖。
- CI 已配置，使用官方 actions 固定 SHA；远端运行状态需要读取确认。
- Starlette 测试兼容层提示 httpx 将弃用，当前不影响测试，升级时处理。

检查命令见 README 与 docs/testing.md。pytest 和 Playwright 会重置同一个 `_test` 数据库，不要并行运行。

## 下一步立即开发

按冻结稿第 21、25、26 节，先做**商品/订单 CSV 与 Excel 导入、字段映射、预览和批次持久化**，再接确定性已知毛利分析（MVP-04）。每个小功能查资料 → 实现 → 验证 → 更新文档 → 提交推送。

导入应有源行血缘、可调整映射、错误行、不执行公式/宏/脚本、文件大小/类型限制、用户/店铺作用域。商品键店铺+SKU；订单行键店铺+订单+行号；金额 Decimal；时区必须确定；缺费用/币种不一致不得精确净利润排名。批次去重、覆盖/撤销与派生数据处理要先设计清楚，避免在后续统计补救。

P0 推荐顺序：导入/经营問数 MVP-04 → Listing MVP-02 → 客服 MVP-03 → 今日运营 MVP-01。模型客户端可替换，凭据缺失时只能清楚标注模型未验证，不能把固定脚本当真实 LLM Agent。R2 外发与平台写入待实际授权。

## 持续维护的文件

docs/development.md、docs/interview-guide.md、docs/references.md、docs/feature-matrix.md、docs/acceptance-matrix.md、docs/testing.md、docs/questions.md。完整需求文件原样保存，Markdown 行末两空格为原文换行格式。
