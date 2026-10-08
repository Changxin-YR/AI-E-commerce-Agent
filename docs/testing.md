# 测试与验收记录

## 第一迭代：账号与经营工作空间（2026-10-08）

数据身份：全部为合成测试数据。数据库：Docker MySQL 8.4，业务库 `soloops`，测试库 `soloops_test`。测试只清理名称以 `_test` 结尾的隔离库；禁止把测试 URL 指向真实业务库。后端与浏览器测试串行运行，避免重置同一个测试库时相互影响。

| 检查 | 命令 | 实际结果 |
|---|---|---|
| 后端规范 | `uv run ruff check app tests migrations scripts` | 通过 |
| 后端类型 | `uv run mypy app` | 28 个源文件通过 |
| MySQL 集成 | `uv run pytest -q` | 19 项通过 |
| 前端规范 | `npm run lint` | 通过 |
| 前端构建与类型 | `npm run build` | 通过 |
| 前端单元 | `npm run test:unit` | 2 文件、4 项通过 |
| 浏览器 E2E | `npm run test:e2e` | Chromium 3 项通过 |
| npm 依赖审计 | `npm audit` | 0 个已知漏洞（本次检查时） |
| GitHub Actions | [Verify SoloOps #1](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37788563158) | 功能提交 acbceb8：Ubuntu / MySQL 下全部通过 |

MySQL 集成验证了：匿名阻断、Cookie 属性、退出后重放旧令牌失败、CSRF/来源阻断、密码不进入错误响应、失败登录锁定、会话到期、密码恢复撤销会话、资料持久化、无效字段、版本冲突、店铺唯一性、跨账号隔离、两个并发更新仅一个成功、未提交事务回滚。

浏览器验证了：错误登录反馈 → 正确登录 → 保存经营资料 → 添加店铺 → 刷新后数据仍在 → 注销后不能访问资料；390×844 手机视口没有水平溢出。桌面与手机截图已实际查看，截图为本地临时 QA 产物，不作为业务数据提交。

一次手机测试因测试定位器忽略链接文字间空格而失败，改为在“主导航”内按语义匹配链接；修复后完整 3 项通过。后端测试工具提示 Starlette 的 httpx 兼容层后续弃用，当前所有测试通过，后续依赖升级时处理。

Windows 沙箱内首次 Vitest 执行遇到临时文件重命名 EPERM；使用已授权的本机执行权限后 4 项通过，GitHub Actions 的 Linux 环境也通过。

## 覆盖范围

本迭代仅验证 SO-001/066/074 的基础切片。四条 MVP、32 项完整 P0 验收、模型选择技能、导入、审批和外部操作均需后续功能与证据，不能因基础工程通过而标记 P0 完成。

## 第二迭代：商品与订单 CSV / Excel 导入（2026-10-08）

数据身份：合成数据，含项目编写的两种平台风格列名样本。没有真实用户报表或平台验证。检查命令同上，Windows 环境使用 `.venv/Scripts/python -m` 调用 Python 工具。

| 检查 | 实际结果 |
|---|---|
| pytest / MySQL | 59 项通过（原 19 项 + 本轮 40 项）；覆盖解析规则和 MySQL 持久化 |
| Ruff 规则/格式、mypy | 通过；36 个 app 源文件 |
| Vue lint / 类型 / build | 通过 |
| Vitest | 3 个文件、5 项通过，含源文本转义和修正事件 |
| Playwright Chromium | 5 项通过，含完整映射纠错导入→刷新→撤销→清除、手机重复行预览 |
| MySQL 迁移 | 新迁移在隔离库 upgrade→downgrade 至前一版本→upgrade→check 通过；开发库 upgrade/check 通过 |
| GitHub Actions | [Verify SoloOps #3](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37794268422)：功能提交 f0ea342 在 Ubuntu / MySQL 环境全部通过 |

`tests/test_imports.py` 验证：上传不提前写业务投影、Decimal/UTC 微秒保存、源行引用、未映射隐私字段清理、CSV 多行起始行号、两种模板下载、两种合成格式自动映射、文件内重复整批拒绝、跨文件相同记录不增量、重复/并发提交仅一次生效、金额修正、新旧值确认、旧预览拒绝、异常中途回滚、店铺和拥有者隔离、大小写敏感业务键、乱序撤销、最新值恢复、清除后其他批次不受影响、草稿到期、CSRF、未知成本与混合币种警示。

安全测试覆盖：伪装宏、外部关系、ZIP 解压膨胀、越界单元格、XML 实体、非 UTF-8、过大文件、超行数、公式、非法数值、未知状态、无法确认的日期与 DST 缺口/重叠。资料中的注入文本保留为普通文本，不执行工具。模型端权限验收尚待 Agent 切片。

桌面与 390×844 手机截图已实际查看，手机无横向溢出；错误行逐项展开，可横向查看字段明细。截图与浏览器 trace 是被忽略的本地 QA 产物。Starlette 的 httpx 弃用提示仍存在，不影响结果。

本轮交付 SO-001/008/027/074 的导入基础切片；A-02/17/18 达到合成数据本地验证，A-04/09/19/20/30 仅导入相关部分通过。毛利统计、派生任务失效和完整四条 MVP 尚未完成。

## 第三迭代：确定性经营分析与核对待办（2026-10-08）

本轮使用合成商品与订单，实际跑过本机 MySQL 和 Chromium。模型入口明确为本地规则，真实用户文件与真实 LLM 均未验证。

| 检查 | 实际结果 |
|---|---|
| pytest / MySQL | 最终完整回归 78 项通过；其中新增 19 项分析测试 |
| Ruff / mypy | 格式与规则通过；42 个 app 源文件通过 |
| Vue lint / build / 类型 | 通过 |
| Vitest | 原 3 个文件、5 项通过 |
| Playwright Chromium | 完整 7 项通过，含新增两条分析流程 |
| MySQL 迁移 | a32132cebd28：隔离库 upgrade→downgrade 到 0776318e56e3→upgrade/check；开发库 upgrade/check 通过 |
| GitHub Actions | [Verify SoloOps](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37798933063)：功能提交 ab83fd6 在 Ubuntu / MySQL 下 completed / success |

`test_analytics.py` 覆盖精确十进制、同单两 SKU、六类状态、退款不恢复成本、成本缺失/异币种/不同数据身份、缺折扣/退款、时间窗边界、相同口径重复计算及来源、未舍入阈值比较、保存与待办并发去重、版本失效、旧成本源撤销后清除、活动订单批次清除、独立快照保留、权限隔离、任意指令拒答、无时区/过大范围拒绝及空数据。

浏览器验证：选择范围→计算 38.9800 销售额 / 14.2500 成本 / 24.7300 已知毛利→展开订单和采购成本源行→保存→创建核对待办→刷新读取→撤销来源后标记失效→清除后移除派生快照。手机验证未知问题拒答、明确阈值筛选、空身份范围提示；390×844 无水平溢出。桌面/手机截图已实际查看，保存在忽略的 `frontend/test-results/`。

并发测试发现的事务锁顺序问题已修正：提交前组装响应，避免提交后先获取待办锁再获取用户锁。完整 E2E 的导入场景改为显式选择目标测试店铺并等待历史加载，不依赖共享账号只有一个店铺。Starlette 的 httpx 弃用提示仍存在。

## 复现命令

先完成 README 安装步骤；在项目根运行 `docker compose --profile test up -d --wait`。后端进入 `backend` 后运行上表后端命令，前端进入 `frontend` 后运行上表前端命令。`scripts/setup_local.py` 已生成 `.local/test.env`；CI 通过环境变量提供 `SOLOOPS_TEST_DATABASE_URL`。

Playwright 自动启动隔离 API（8001）和前端（5174），清理测试库并创建合成账号。不要同时手动占用这两个端口。日常开发使用 8000/5173，与测试服务分开。
