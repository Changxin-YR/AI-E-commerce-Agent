# SoloOps 开发文档

本项目面向个人跨境卖家，使用 CSV/Excel 作为首版业务入口。完整需求见 [冻结稿](requirements/SoloOps-V1.0.md)，验收状态见 [功能矩阵](feature-matrix.md)。这是持续更新的工程说明，代码、测试与运行证据决定完成状态。

## 一、整体思路与迭代顺序

先建立可运行、可验证的最小纵向功能：账号与经营资料 → 文件导入与映射 → 确定性利润分析 → 受控问数 → Listing 草稿与审批 → 客服草稿 → 今日运营。每次交付均包含前后端、持久化、错误处理、测试与说明。

P0 的 23 个模块围绕四条 MVP 实现最小切片；P1/P2 保留完整清单，按实际授权逐步启用。界面只展示真实记录，初次使用显示空状态与下一步操作。

## 二、三层架构如何落地

```text
Vue 页面 → api 客户端 → FastAPI routes（接口层）
                         ↓
                      services（业务层）
                         ↓
                      repositories（数据访问层）→ MySQL
```

- 接口层：校验 HTTP 输入，读取当前身份，调用服务，返回稳定的响应模型；不计算业务金额、不拼 SQL。
- 业务层：执行权限、业务约束与事务决策。独立函数承载可重复的计算；服务组织一个用例涉及的持久化动作。
- 数据访问层：封装 SQLAlchemy 查询与写入，所有业务资源按拥有者过滤；数据库约束负责并发情况下的最终一致性保护。
- `schemas` 定义输入输出契约；`models` 描述持久化结构；`core` 放配置、时间、密码等共用能力。这些是三层的辅助模块。

选择模块化单体，进程内调用服务即可。先使用同步数据库访问配合 FastAPI 的同步路由线程池，让调用顺序、事务与调试容易理解。

## 三、依赖与选择理由

| 依赖 | 用途 | 选择理由与代价 |
|---|---|---|
| Vue 3、TypeScript、Vite | 组件、类型检查、构建 | 沿用官方脚手架；按页面与组合函数拆分 |
| FastAPI、Pydantic | HTTP、输入验证、OpenAPI | 一套 Web 框架即可；不手写验证和文档生成 |
| SQLAlchemy、PyMySQL | 参数化查询、事务、MySQL 驱动 | 显式 repository；业务函数不绑定 SQL 字符串 |
| Alembic | 数据库版本迁移 | 每次结构调整有可审查的升级/回退步骤 |
| pwdlib / Argon2 | 密码存储 | 使用经过维护的密码散列实现 |
| pytest、Ruff、mypy | 后端验证 | 业务、接口、真实 MySQL 约束同时可测 |
| Vitest、Playwright | 前端与 E2E | 单一单测工具与单一浏览器测试工具 |

版本由 `backend/uv.lock`、`frontend/package-lock.json` 锁定。运行数据落在 MySQL；测试使用独立 MySQL 数据库。

## 四、问题与解决记录

| 日期 | 问题 | 原因与处理 | 验证 |
|---|---|---|---|
| 2026-10-08 | 工作目录为空 | 拉取用户指定仓库，保留初始提交 | Git 历史可追溯 |
| 2026-10-08 | Firecrawl 检索返回 402 | 当前额度不可用，改用网页检索官方仓库与文档 | 参考资料记录在 references.md |
| 2026-10-08 | 沙箱无法连接 GitHub / Docker | 使用授权的网络与本机 Docker 执行权限 | 仓库拉取成功，Docker 服务可读 |

## 五、当前实现与运行证据

本阶段已实现 SO-074 的登录/注销/本地恢复及 SO-001/066 的经营资料与店铺记录。MySQL 19 项集成、前端 4 项单元、3 项浏览器测试通过；完整证据与边界见 [测试记录](testing.md)。完整导入、业务规则和隐私清理在后续切片补齐。

### 身份与请求处理

本机 CLI 创建账号和恢复密码，不提供开放注册。密码至少 12 位，使用 Argon2；登录成功生成随机会话，数据库只存会话摘要。HttpOnly + SameSite Cookie 承载身份，CSRF Token 与来源白名单保护写入。密码恢复清除该账号全部会话。账号连续失败 5 次锁定 15 分钟，锁定状态落库；公开部署前还需入口级请求限流与 HTTPS。

浏览器通过 Vite 同源 `/api` 代理访问后端，CSRF Token 只存前端内存。HTTP 错误统一为 `error.code/message/request_id`；错误不返回原始密码、SQL 参数或堆栈。日志记录请求编号和异常类型，便于定位且减少泄露。

### 资料修改与并发

每份资料带 `version`。服务先锁当前用户及资料行，再比较客户端版本；版本过期返回 409，前端保留输入并提示刷新。创建店铺使用 `(owner_id, code)` 唯一约束，跨账号同名可以共存。同一次修改及其审计记录在一个事务中提交。

### 进一步的问题与处理

| 问题 | 解决 | 证据 |
|---|---|---|
| 新脚手架 lint 辅助依赖带入已知 `braces` 风险 | 用 ESLint/TypeScript ESLint 基础配置完成同样检查，精简工具依赖 | npm audit 0 漏洞，lint/build 通过 |
| 前端只见成功提示，难以证明落库 | E2E 保存后刷新页面，再读取数据库返回值 | 3 项 E2E 通过 |
| 先查询再更新不足以阻止并发覆盖 | 数据库行锁结合版本比较，唯一约束兜底 | 双线程测试一个成功、一个冲突 |
| 测试可能误清真实数据 | 独立 MySQL 服务与 `_test` 数据库名防护 | 测试启动前校验，日常业务库独立 |

## 六、代码阅读路线

1. `backend/app/api/routes/profile.py`：看一次 HTTP 请求如何进入服务。
2. `backend/app/services/profile.py`：看业务规则、版本判断和事务提交。
3. `backend/app/repositories/identity.py`：看带拥有者条件的查询与唯一冲突转换。
4. `backend/app/models/identity.py` 与 `backend/migrations/versions/`：看对象如何持久化。
5. `frontend/src/views/SettingsView.vue` → `components/ProfileForm.vue` → `api/identity.ts`：看页面、表单与接口职责。
6. `backend/tests/test_identity.py` 与 `frontend/e2e/workspace.spec.ts`：看需求如何被证明。
