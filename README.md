# SoloOps · AI 跨境电商运营工作台

Vue 3 + TypeScript / Python FastAPI / MySQL 的个人卖家运营项目。后端采用接口层、业务服务层、数据访问层，业务数据与操作记录持久化。

目前已完成**账号与经营工作空间**这一基础迭代：登录、注销、本机账号恢复、经营资料、店铺记录、首次使用引导和自动化测试。P0 四条业务闭环正在逐步实现；完整进度以 [74 项功能矩阵](docs/feature-matrix.md) 为准。

## 文档入口

- [需求冻结稿](docs/requirements/SoloOps-V1.0.md)：74 项长期需求与 32 项 P0 验收基线。
- [开发文档](docs/development.md)：整体思路、三层职责、技术选择、问题与解决记录、代码阅读路线。
- [面试知识点](docs/interview-guide.md)：关联实际代码的设计依据与常见追问。
- [测试记录](docs/testing.md) / [验收矩阵](docs/acceptance-matrix.md)：已运行证据与待验证范围。
- [公开实现借鉴](docs/references.md) / [待集中确认](docs/questions.md)。
- `context-memory` 分支：重点上下文、当前进度与下一次开发起点。

## 本地启动

需要 Python 3.11+、uv、Node.js 24.12+ 和 Docker。以下命令在项目根目录开始执行；MySQL 仅绑定本机 3307，测试库绑定 3308。

```powershell
python scripts/setup_local.py
docker compose --profile test up -d --wait
cd backend
uv sync --frozen --python 3.11
uv run alembic upgrade head
uv run python -m app.cli create-user owner
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

账号创建时交互输入至少 12 位密码。配置脚本生成随机数据库口令，保存在被忽略的本机 `.env` 中；已有配置时拒绝覆盖。也可以按根目录和 backend 的 `.env.example` 手动配置。

另开一个终端，从项目根目录执行：

```powershell
cd frontend
npm ci
npm run dev
```

打开 [本地工作台](http://127.0.0.1:5173)，用自己创建的账号登录。API 文档在 [OpenAPI 页面](http://127.0.0.1:8000/docs)。前端通过同源 `/api` 代理访问后端。

首次使用：登录 → 经营资料 → 保存档案 → 添加店铺。店铺目前为文件模式；尚未录入业务数据时不会出现销售额、AI 巡检或平台已连接的虚构结果。

## 账号管理

在 `backend` 目录使用以下命令，密码由终端交互读取，不放进命令参数：

```powershell
uv run python -m app.cli create-user owner
uv run python -m app.cli reset-password owner
```

恢复密码会撤销该账号的全部现有会话。本地拥有数据库访问权限的管理员才应执行恢复命令。当前设计用于本机开发；公开部署前需要 HTTPS、Secure Cookie、入口限流和备份配置。

## 运行检查

先启动隔离测试库：`docker compose --profile test up -d --wait`。测试会清理指定的 `_test` 数据库，勿配置为真实业务库，后端测试和浏览器测试请顺序执行。

```powershell
cd backend
uv run ruff check app tests migrations scripts
uv run ruff format --check app tests migrations scripts
uv run mypy app
uv run pytest -q
cd ../frontend
npm run lint
npm run build
npm run test:unit
npx playwright install chromium
npm run test:e2e
```

`npm run test:e2e` 自动启动 8001/5174 测试服务并创建合成账号。GitHub Actions 对 main 的推送和 PR 执行相同检查。测试报告见 [testing.md](docs/testing.md)。

## 目录与阅读顺序

```text
backend/app/api/           HTTP 输入、响应、鉴权依赖
backend/app/services/      业务规则、用例组织、事务边界
backend/app/repositories/  参数化查询、持久化、数据库会话
backend/app/models/       SQLAlchemy 数据模型
backend/app/schemas/      Pydantic 输入输出契约
backend/migrations/       Alembic 版本迁移
backend/tests/            真实 MySQL 集成与规则测试
frontend/src/views/       页面组织
frontend/src/components/  可复用表单和展示组件
frontend/src/api/         类型化 API 调用与统一错误
frontend/src/composables/ 会话等组合逻辑
docs/                     需求、设计、进度、测试、面试资料
```

从 `profile.py` 路由进入服务，再看 repository 和数据库约束；前端从 `SettingsView.vue` 进入 `ProfileForm.vue` 和 `api/identity.ts`。

## 数据与能力状态

目前验证使用合成数据。真实文件、模型调用、平台读写与测试邮箱送达将分别记录证据。账号密钥和客户资料不进入 Git；参考代码与依赖来源在开发文档中说明。项目自身开源许可证待仓库所有者决定。
