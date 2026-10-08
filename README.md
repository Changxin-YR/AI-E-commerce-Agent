# SoloOps · AI 跨境电商运营工作台

Vue 3 + TypeScript / Python FastAPI / MySQL 的个人卖家运营项目。后端采用接口层、业务服务层、数据访问层，业务数据与操作记录持久化。

目前已交付**账号与经营工作空间、商品/订单/客服消息/库存快照导入、确定性经营分析、Listing 本地审批、客服草稿与政策证据**基础切片：登录恢复、CSV/XLSX 映射纠错、批次溯源与撤销、销售与已知毛利、保存分析及待办、文案版本与审批、客服多意图本地规则和人工处理存档，以及库存快照时效与安全阈值核对。P0 四条业务闭环正在逐步实现；完整进度以 [74 项功能矩阵](docs/feature-matrix.md) 为准。

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

首次使用：登录 → 经营资料 → 添加店铺 → 数据导入 → 选择文件、报表类型和数据身份 → 核对映射 → 预览纠错 → 确认导入。可以先导入一类数据。界面提供 CSV/Excel 模板；[合成样本与字段说明](examples/imports/README.md) 可用于复现，上传这些样本时请选择“合成测试数据”。

同一店铺以 SKU 或“订单号+行号”识别记录；覆盖更新需核对新旧值并确认。批次可撤销和清除，恢复剩余有效批次的最新数据。导入保留明确来源、币种及时间。

经营分析：选择店铺、数据身份、币种和带时区的起止时间 → 选择受控问题 → 查看订单与成本来源 → 保存分析 → 创建核对待办。当前支持本地规则的销售摘要、购买数量前五和低毛利筛选；真实 LLM 与 AI 巡检仍待实现及验证。导入变化会使历史分析/待办需重算，清除来源批次会清理依赖的快照内容。

历史订单采用当前采购成本估算，缺折扣/退款/成本保留未知，异币种不换算，退款不恢复采购成本或库存。当前未归集平台、广告、物流和税费，因此只能判断已知商品毛利。默认窗口为最近 30 天（UTC 起止），可改为明确的 `2026-10-07T00:00:00+08:00` 至 `2026-10-08T00:00:00+08:00`；区间不含终点。导出时间未知时不能推断数据截至时间。

Listing 审批：只导入商品即可在 `/listings` 选择 SKU → 从事实模板生成草稿 → 查看原始来源、新旧文案与缺失项 → 修改并保存新待审版本 → 核对事实后批准或拒绝。标题可用完整商品名与「 · 」连接的完整参数行，描述可选用、排序完整原文行；新增或改写事实需先补充商品来源。当前生成器为本地模板，模型与平台发布待接入。审批只更新独立本地 Listing 版本；历史文案可另存、重新批准。来源被覆盖或撤销后版本失效，批次清除会移除关联文案和差异内容，保留必要处理记录。

库存快照：在数据导入中选择“通用库存快照文件”，核对 SKU、已知可售数量、快照时间、安全阈值后确认；在 `/inventory` 按店铺/渠道/数据身份查询、展开源行。默认查询时效 24 小时，可调整后刷新；过期或无数据明确显示库存未知。修改阈值通过重新导入并确认差异，撤销/清除沿用导入批次入口。

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
