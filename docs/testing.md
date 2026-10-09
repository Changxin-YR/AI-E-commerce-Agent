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

## 第四迭代：Listing 草稿与本地审批（2026-10-08）

数据身份为合成商品；仅导入商品即可走通本地流程。默认生成器 `local_template`，可注入 `test_double` 验证业务边界；真实 LLM 和外部平台尚未验证。

| 检查 | 实际结果 |
|---|---|
| pytest / MySQL | 90 项通过，新增 12 项 Listing 测试 |
| Ruff / mypy | 格式与规则通过；48 个 app 源文件通过 |
| Vue lint / 类型 / build | 通过 |
| Vitest | 4 文件、7 项通过；编辑后确认重置、旧版本审批禁用、清除后移除内容 |
| Playwright Chromium | 完整 9 项通过，新增 Listing 桌面与手机两条流程 |
| MySQL 迁移 | 262449b655ea：隔离库 downgrade 到 a32132cebd28→upgrade/check；开发库 upgrade/check 通过 |
| GitHub Actions | [Verify SoloOps](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37803271282)：功能提交 8168d97 在 Ubuntu / MySQL 下 completed / success |

`test_listings.py` 验证：商品独立建稿、缺参数保留空值、编辑产生版本、批准前无生效、商品事实保持原值、拒绝与历史文案恢复、同请求去重、并发生成/审批一次副作用、竞争候选拒绝过期基线、未覆盖声明即使人工确认也阻断、生成器异常没有成功记录或错误正文泄露、店铺/用户隔离、CSRF、额外字段拒绝、来源变化/撤销失效、恢复源行后另建草稿、旧比较值的跨版本清除与独立 SKU 保留。

浏览器验证：选商品→生成→源行→编辑→差异→确认→批准→刷新持久化→历史另存→拒绝→撤销来源→失效→清除。手机将脚本样式原文显示为文字，未执行脚本；新增无依据声明后批准按钮禁用，390×844 无水平溢出。桌面/手机截图保存在忽略的 `frontend/test-results/` 并实际查看。标题区域按现有页面结构排列。Starlette 的 httpx 弃用提示仍存在。

本轮 A-24 本地用例通过；A-01/09/16/26/30 增补相应基础证据。真实模型理解、技能选择、统一运行、预算、熔断与客服仍待实施，四条 MVP 不标完整完成。

## 第五迭代：客服消息、政策与本地回复草稿（2026-10-09）

全部使用合成消息、政策和订单；生成方式为 `local_rules`，人工编辑标 `manual`。

| 检查 | 实际结果 |
|---|---|
| pytest / MySQL | 完整 109 项通过；新增客服 19 项，含六种政策不适用范围 |
| Ruff / mypy | 规则与格式通过；54 个 app 文件 |
| Vue lint / 类型 / build | 通过 |
| Vitest | 5 文件、8 项通过 |
| Playwright Chromium | 完整 11 项通过；手机标签修复、增加核验订单后，客服 2 项再次通过 |
| MySQL 迁移 | 8d34d9c410a2：隔离库回退至 262449b655ea→升级/check，开发库升级/check 均通过 |
| GitHub Actions | [Verify SoloOps](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37808536888)：功能提交 d3b9be1 在 Ubuntu / MySQL 下 completed / success |

`test_support.py` 验证消息去重、公式/非法日期拒绝、注入样式正文保留为数据、物流+退款并存、未知订单/语言拒绝承诺、人工核验全部订单源行、政策范围/版本/过期/冲突/清除/重新录入、编辑与状态幂等、并发建稿/编辑、跨账号/店铺/渠道隔离、来源恢复不复活旧稿、订单清除与独立草稿保留。HTTP 没有发信路由，`auto_send` 等额外字段拒绝。

Browser plugin not available；使用仓库既有 Playwright 工作流，测试 URL 为 `http://127.0.0.1:5174/support`。检查页面 URL/标题、非空内容、无 Vite 错误遮罩及交互状态。首次未登录会话返回 401 是既定鉴权流程；登录后的控制台无应用错误。

桌面 1280×720 和手机 390×844 已截图并实际查看：手工录入→源值预览→保存→订单人工核验→政策选择→原始行→双意图草稿→编辑→存档→刷新→重新打开→撤销失效→清除正文。手机验证脚本样式文本转义、未知语言转人工、全部意图/状态可见、无横向溢出。截图在系统临时目录 `soloops-support-{desktop,mobile}[-page].png`，不提交业务仓库。

Starlette 的 httpx 弃用提示仍存在。尚无真实 LLM、真实消息样本、实时运单或测试邮箱外发证据，四条 MVP 不标完整完成。

## 第六迭代：可选库存快照（2026-10-09）

| 检查 | 实际结果 |
|---|---|
| pytest / MySQL | 完整 123 项通过，新增库存 14 项（含参数化） |
| Ruff / mypy | 74 文件格式与规则通过；58 个 app 文件类型检查通过 |
| Vue lint / 类型 / build | 通过 |
| Vitest | 5 文件、8 项通过；沙箱临时缓存重命名 EPERM 后使用本机权限验证 |
| Playwright Chromium | 完整 13 项通过，新增库存桌面/手机两条流程 |
| MySQL 迁移 | 61cb82ef096a：隔离库回退至 8d34d9c410a2→升级/check，开发库升级/check 均通过 |
| GitHub Actions | [Verify SoloOps](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37811072990)：功能提交 53b7d72 在 Ubuntu / MySQL 下 completed / success |

`test_inventory.py` 覆盖无库存、快照原始行、身份/渠道/店铺/拥有者隔离、零阈值、恰好过期和截止前一微秒、调整查询时效、非法/缺失数量和阈值、未来时间、覆盖旧快照警示、重复确认、撤销恢复、乱序撤销、清除、Excel 纠错与时区、文件内重复键、分页与搜索转义。

桌面验证 CSV 映射预览→确认→快照低库存→来源原始值→刷新持久化→撤销/清除→未知；手机验证 30 小时前快照过期，改为 48 小时时效后重新核对。1280×720 与 390×844 截图已实际查看，手机无横向溢出，页面无应用错误与 Vite 遮罩。截图在系统临时目录 `soloops-inventory-{desktop,mobile}.png`，仅含合成数据。

Starlette 的 httpx 弃用提示仍存在。本轮补齐 SO-041 的 P0 快照基础；A-03 的查询页面通过，今日运营中的库存分支待接入。真实库存源与 Agent/模型未验证，四条 MVP 仍未完整完成。

## 复现命令

先完成 README 安装步骤；在项目根运行 `docker compose --profile test up -d --wait`。后端进入 `backend` 后运行上表后端命令，前端进入 `frontend` 后运行上表前端命令。`scripts/setup_local.py` 已生成 `.local/test.env`；CI 通过环境变量提供 `SOLOOPS_TEST_DATABASE_URL`。

Playwright 自动启动隔离 API（8001）和前端（5174），清理测试库并创建合成账号。不要同时手动占用这两个端口。日常开发使用 8000/5173，与测试服务分开。

## 第七迭代：今日运营检查与待办（2026-10-09）

数据身份均为合成数据。新增 15 项 `test_operations.py`，完整 pytest 138 项通过；拆分各检查函数后新增 15 项复验通过。Ruff 82 文件规则/格式、mypy 64 个 app 文件通过；Vue lint/type/build 通过；Vitest 5 文件 8 项通过。完整 Playwright 15 项通过；首页摘要/高级口径和可见优先级/内部标签完善后，新增 2 项运营 E2E 复验通过。

功能提交 `3531ce7` 的 [GitHub Actions](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37815482720) 已核实 `completed / success`：Ubuntu / MySQL 后端、前端与浏览器全部通过。之后的优先级与标签显示补充已完成对应本地 E2E、lint/type/build 验证。

验证重点：空数据未检查、四类候选及原始行、审批前待审批、重复相同操作无新历史、忽略/拒绝/完成/延期重跑保留、无关版本变化去重、库存到期拒绝批准、来源覆盖/撤销/恢复、旧成本清除、备注与历史详情擦除、独立任务保留、输入白名单/CSRF/用户店铺渠道身份隔离、分页与 500 候选上限原子拒绝、预先建立旧快照的并发请求与竞争编辑。

浏览器新增验证：证据→备注→批准→延期→完成→重跑复用→重新打开→刷新保留→清除来源；手机空数据引导→忽略→重跑仍忽略。桌面 1280×720、手机 390×844 的完整截图已实际查看，手机无横向溢出，截图在系统临时目录 `soloops-operations-{desktop,mobile}.png`，不提交。

迁移 `c37d9218a640` 在隔离测试库升级→回退 `61cb82ef096a`→升级/check 通过；开发库只升级/check 通过，两库均无漂移。pytest 与 Playwright 串行运行，迁移验证待两者结束。Starlette 的 httpx 兼容层弃用提示仍存在。

交付为可验证的本地运营基础；真实模型、技能注册/预算/熔断/取消恢复、受控外发及剩余 P0 继续实现，不标四条 MVP 全部完成。

## 第八迭代：受控技能与任务执行（2026-10-09）

后端完整 pytest **161 项通过**，新增 `test_agent.py` 23 项（含参数化）。验证真实 MySQL 事务、数据分支、七技能元数据和白名单、审批前零业务写入、同来源去重、版本并发、失效/过期/擦除、跨拥有者/店铺/身份、预算暂停恢复、三次临时读熔断、网络期间取消、来源变化丢弃结果和进程租约恢复。模型协议使用 MockTransport，路由与费用使用标记为 test_double 的替身；未进行真实付费调用。

Vue lint、类型检查、生产构建通过；Vitest **6 文件 10 项通过**。新增两条 Agent E2E 跑通来源原始行→节点审批→预算暂停→提高预算恢复→内部保存→回读核验→刷新→来源擦除，以及手机空数据→模型待配置→取消。完整浏览器回归曾暴露矮桌面侧栏退出按钮溢出，修复后相关 Agent/工作空间 **5 项复验通过**；最终全量结果另记录于本节末尾。

Ruff 规则/格式与 mypy 71 个 app 文件通过。迁移 `e84b5e7e8dd1` 在隔离 `_test` 库回退至 `c37d9218a640` 后升级/check 通过，开发库只升级/check；两库无漂移。测试、E2E、迁移回退串行执行。截图 `soloops-agent-desktop.png` 和 `soloops-agent-mobile.png` 在系统临时目录，合成数据，已实际查看，无横向溢出。Starlette/httpx 兼容层弃用提示仍存在。

前版补充提交 `10fa1df` 的 [GitHub Actions](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37816007090) 已核实 completed/success。74 个 SO 与 32 个验收项完整保留。真实模型生成/解释、业务外发与回查、测试邮箱送达及其余 P0 仍待继续。

最终浏览器全量回归：**17 项全部通过**（Chromium，27.8 秒）；矮桌面侧栏修复后的生产构建与 Vue 类型检查通过。最终桌面/手机截图已再次实际查看。后端 Ruff 覆盖 91 个文件格式/规则通过，mypy 71 个 app 文件通过。

本功能提交 `d1eda91` 的 [GitHub Actions](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37820719900) 已核实 completed/success。

## 第九迭代：独立新品利润计算器（2026-10-09）

合成数据本地验证：新增 `test_profit.py` 最终 **18 项通过**。完整后端回归 **178 项通过**，之后补充极小金额与最大边界测试、十进制定点序列化，针对本功能 18 项复验通过。覆盖无订单、未知/零费用、固定/比例计费、四情景、负余额、零售价、100% 及超额费率、JPY/美分保本向上取整、金额边界与非法输入、数值和来源回读、独立批次清除、店铺/用户隔离、CSRF、请求绑定、并发保存与无正文擦除审计。

完整 Playwright **19 项全部通过**（31.2 秒）；新增桌面无订单→补齐费用→复制第二方案→比较→查看依据和敏感性→存档→刷新→回读→清除，以及手机零售价/未知费用/无页面横向溢出。最终 1280×720、390×844 的输入页和结果页截图位于系统 Temp 的 `soloops-profit-{input-desktop,input-mobile,desktop,mobile}.png`，均为合成数据且已实际查看。

Vitest **7 文件 12 项通过**；金额文本精度与未知/零依据门禁各有组件测试。最终 Vue lint、type-check、生产构建通过；Ruff **99 文件**规则/格式通过，mypy **77 个 app 文件**通过。金额输出保持定点十进制字符串，避免极小费用显示为科学计数。

迁移 `a0188d77d6c6` 已在隔离测试库升级→回退至 `e84b5e7e8dd1`→升级/check；开发库只升级/check，均无漂移。所有数据库测试、E2E、迁移回退按顺序运行。Starlette/httpx 兼容层弃用提示仍存在。该切片不调用模型或外发通道，四条完整 AI MVP 与其余 P0 仍按矩阵继续开发。

## 第十迭代：经营规则与版本记忆（2026-10-09）

完整 pytest **197 项通过**（52.45 秒）；本功能 `test_business_rules.py` **18 项**，覆盖阈值实际改变低库存/低毛利结果、历史查看/撤销/重置/恢复、店铺/渠道/身份与跨账号隔离、CSRF、输入边界/权限扩张拒绝、旧版本冲突、当前读并发一成一冲突、旧审批失效、幂等回放、模型在途改规则后丢弃结果并记已知费用。真实模型调用仍为 test_double，无外发调用。

Vitest **8 文件 13 项通过**，新增慢请求跨店铺返回和加载失败阻断测试。Vue lint、type-check、生产构建通过；后端 Ruff **106 文件**格式/规则通过，mypy **82 个 app 文件**通过。全量 Playwright **21 项通过**（34.3 秒），覆盖规则保存→刷新→原值回看→今日运营/Agent 实际应用→恢复→重置→渠道隔离，以及手机保存→撤销→历史依据；既有 19 项回归同时通过。

Browser plugin not available，使用仓库 Playwright（Chromium，http://127.0.0.1:5174）。最终桌面 1280×720、手机 390×844 的首屏及完整截图保存在系统 Temp `soloops-rules-{desktop,mobile,first-desktop,first-mobile}.png`，实际查看，手机无页面横向溢出。检查了有效页面、主要控件、无框架错误层、登录后的控制台错误和脚本文字转义。首次会话探测的登录前 401 为预期；一次回归测试服务中途停止导致 connection refused，重启后全量通过。复选框尺寸问题由截图发现并修正。

迁移 `944381607c1c` 在隔离 `_test` 库升级→回退 `a0188d77d6c6`→升级/check 通过；开发库只升级/check，两库无漂移。pytest、Playwright、迁移回退串行执行。Starlette/httpx 兼容层弃用提示仍存在。

上一功能提交 `abb9f79` 的 [GitHub Actions](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37823550243) 已核实 completed/success。74 SO、32 验收行完整保留；SO-066 的可撤销自动执行授权、剩余 P0 和真实外部验证继续实施。

## 第十一迭代：有界 R1 内部预授权（2026-10-09）

最终完整后端 pytest **214 项通过**，本功能 `test_authorizations.py` **17 项**。覆盖真实 MySQL 中的授权创建/回放、严格次数与时效字段、白名单、拥有者/店铺/身份/渠道隔离、CSRF、两个执行争用最后一次额度、来源清除与规则变化、执行中到期、业务与消耗一起回滚、旧 UUID 兼容、复用、撤回冲突和撤销后的单次审批。Ruff **112 文件**规则/格式检查通过，mypy **87 个 app 文件**通过。

Vue 类型、lint、生产构建通过，Vitest **9 文件 15 项通过**。最终完整 Playwright **23 项通过（40.6 秒）**；新增桌面/手机真实页面操作覆盖创建授权→自动保存→复用消耗→撤回新增候选→撤销授权→刷新回读，页面与控制台无错误，手机无横向溢出。截图 `soloops-authorizations-{create-desktop,create-mobile,panel-desktop,panel-mobile,desktop,mobile}.png` 位于系统临时目录，仅含合成数据并已实际查看，不提交。

截图发现通用 `.data-note` 的 flex 横排使授权表单挤成窄列，改为表单局部纵向排版并复验。全量浏览器测试曾遇本机服务中途退出 `ERR_CONNECTION_REFUSED`，另一次审批请求的 trace 为 `ERR_NO_BUFFER_SPACE`；停止并行构建、重启测试服务后最终 23 项全部通过。后端 Starlette/httpx 弃用提示仍存在。

迁移 `3b35be067576` 在隔离 `_test` 库回退 `944381607c1c` 后升级/check，通过；开发库只升级/check，两库无漂移。迁移、pytest、E2E 按顺序执行。74 SO、32 验收行完整保留。前版 `c1dac61` 的 [GitHub Actions](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37826653771) 已核实 completed/success。

本功能没有模型调用或外发；R2 测试发送、真实通道回执与收件证据及剩余 P0 继续实现。

## 第十二迭代：R2 测试邮件与回查（2026-10-09）

最终完整 pytest **242 项通过（69.04 秒）**，本功能 `test_outbound.py` **28 项**。覆盖验证码不回显/哈希存储/重复连接/错误上限/过期/域门禁；严格确认、固定测试名单、店铺隔离和 CSRF；全文修改失效、R1 字段拒绝、独立授权撤销/过期/配置轮换；来源与规则变化；旧 RR 快照并发只 POST 一次；发送前审计失败全回滚；发送中清批次保留回执不恢复正文；超时、进程中断、限频、只读回查和错误回执/标签/地址/全文拒绝。HTTP MockTransport 验证固定域、幂等键、一次发送和有界发现。所有邮件均为测试替身，无真实调用。

Ruff **123 文件**规则和格式检查、mypy **94 个 app 文件**通过。Vue lint、type-check、生产构建通过，Vitest **10 文件 17 项通过**。初次 Vitest 在沙箱缓存重命名时报 EPERM，正常本机环境复验通过；生产构建发现 Vue 多语句事件表达式问题，改为显式函数后通过。Starlette/httpx 弃用提示仍存在。

完整 Playwright **24 项通过（42.8 秒）**。新流程：测试连接确认→从合成收件箱取得验证码→选择检查与全文预览→限一次预授权→撤销→单次审批提交→未知→只读回查→人工收件声明→刷新持久回读；收件箱仅一封验证码与一封摘要。既有业务和新增导航全部回归通过。

Browser plugin not available，使用仓库 Playwright，地址 `http://127.0.0.1:5174/outbound`，1280×720 与 390×844。页面身份/有效内容、无 Vite 错误层、登录后控制台、主要交互均通过；手机无页面横溢。首屏、预览和结果截图在系统 Temp `soloops-outbound-{first-desktop,first-mobile,preview-desktop,preview-mobile,desktop,mobile}.png`，均已实际查看，只含合成数据。收件确认框布局已由截图发现并修复。

迁移 `f219af0a01cf` 在隔离 `_test` 库回退 `3b35be067576` 后升级/check 通过，开发库仅 upgrade/check，两库无漂移。pytest、Playwright、迁移回退串行。74 SO、32 验收行完整保留。上一提交 `1edd7db` 的 [GitHub Actions](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37830128990) 已核实 completed/success。

A-11/A-28 的本地状态机已验证；A-13/P0-External 仍待本人通道/邮箱授权、实际供应商提交回执及收件证据。模型生成解释、跨店总览/日报、统一任务等剩余 P0 继续实施。


## 第十三迭代：跨店总览与经营摘要（2026-10-09）

完整后端 pytest **260 项通过（76.95 秒）**，随后补充跨夏令时超长 UTC 窗口的 422 边界和已批准任务的 open 状态回顾，本功能最终 **20 项通过（6.15 秒）**，当前测试总数 262。覆盖两店相同订单号去重、分币种 Decimal/退款/对比、状态排除、未知折扣/退款/成本/库存/回复状态、23 小时日历日、日期下界回读、拥有者/店铺/身份与 CSRF、UUID 内容绑定、旧 RR 快照并发同一保存、审计失败回滚、来源版本冲突、库存微秒到期、来源清除与独立摘要隔离、读取上限及游标历史。

Ruff **131 文件**格式/规则通过，mypy **100 个 app 文件**通过。Vitest **11 文件 19 项通过**，新增旧报告迟到来源/错误丢弃与未知覆盖显示；Vue lint、type-check、生产构建通过。当前 TypeScript 标准库不支持 Array.at，来源截止范围改用常规索引并完成构建复验。后端 Starlette/httpx 兼容弃用提示仍存在。

最终全量 Playwright **26 项通过（45.3 秒）**。新增桌面两店不同市场、两币种汇总与本期/对比、订单原始行、保存/刷新、来源撤销后 stale、清除正文；手机日报空数据、市场筛选、主动清除及页面无横溢通过。首次全量新增用例在异步店铺列表完成前枚举了控件，补充等待目标控件可用后再取消其他选择，最终全部通过。

使用仓库 Chromium Playwright，地址 `http://127.0.0.1:5174/overview`，桌面 1280×720、手机 390×844。首屏、表单及完整结果截图位于系统 Temp `soloops-overview-{form-desktop,first-desktop,first-mobile,desktop,mobile}.png`，均为合成数据，已实际查看；有效内容、主要交互、页面脚本错误检查和手机宽度检查通过。截图不提交。

迁移 `728544d1186c` 在隔离 `_test` 库回退 f219af0a01cf→升级/check，开发库仅升级/check，两库无漂移。时间精度边界验证发现默认 DATETIME 的小数秒舍入，有效期改为 DATETIME(6) 后通过；回退按依赖直接删表，避免删 FK 支撑索引。pytest、Playwright 和迁移回退均串行执行。

上一提交 d43d29b 的 [GitHub Actions](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37833883370) 已确认 completed/success。本轮没有真实模型或外发调用；74 SO 与 32 验收行完整保留。统一驾驶舱、四 MVP 模型内容生成及真实外部验证继续实施。

## 第十四迭代：统一任务、草稿与审批驾驶舱（2026-10-09）

最终完整后端 pytest **274 项通过（83.45 秒）**；新增 `test_workbench.py` **12 项**，覆盖十类实际业务记录、拥有者/店铺/身份/渠道隔离、相同时间戳的游标分页、全范围计数、规则/政策/库存时效失效、未知优先、只读请求无执行或审计副作用、清除后无正文、R1 状态与原服务一致、分析待办完成/重开/旧版本/CSRF和审计失败回滚。Ruff **137 文件**格式/规则、mypy **104 个 app 文件**通过；Starlette/httpx 兼容层弃用提示仍存在。

Vitest **12 文件 21 项通过**，新增组件测试覆盖切范围后的迟到响应和错误、窗口聚焦刷新失败后清空旧卡片、原草稿状态与确切链接、导入文字转义。Vue lint、type-check 和生产构建通过。

完整 Playwright **28 项通过（54.3 秒）**。新用例覆盖桌面首页到 Listing/客服/分析待办/跨店报告/Agent/R1/运营待办/检查的确切对象、原 Listing 审批、分析完成→刷新→重开、R2 未知邮件入口→原只读回查；手机覆盖筛选、链接刷新回读、无权店铺与无横向溢出。随后收紧运营链接 ID 校验顺序，补充无效 ID 不显示检查详情；工作台两项定向复验通过（11.2 秒）。

新增分析详情使旧测试的“待办 #”匹配到两处，已将断言限定在对应详情区域。两次全量测试还分别遇到本机前端连接中断（ECONNRESET/ERR_CONNECTION_REFUSED），停止位置不同；捕获 webServer 启停日志后重新运行，28 项全部通过且服务在测试结束后正常停止。未定位中断根因；没有为业务写入添加自动重试。手机链接测试等待目标 URL 后再 reload，保证测到目标记录回读。

使用仓库 Chromium Playwright，首页 `http://127.0.0.1:5174/`，桌面 1280×720、手机 390×844。最终首屏与收件箱截图在系统 Temp `soloops-workbench-{first-desktop,first-mobile,desktop,mobile}.png`，实际查看了桌面首屏与手机收件箱；合成数据、有效内容、主要交互、登录后页面错误及手机宽度检查通过，截图和诊断日志不提交。

迁移 `86df84dc129a` 在隔离 `_test` 库升级→回退 `728544d1186c`→升级/check 通过；开发库只升级/check，两库无漂移。数据库测试、浏览器测试与迁移回退串行执行。上一提交 b98dad3 的 [GitHub Actions](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37837382644) 已核实 completed/success。74 SO、32 验收行完整保留；本轮未调用真实模型或邮件通道，四条完整 AI MVP 及剩余 P0 继续开发。

## 第十五迭代：模型经营问数与受控证据解释（2026-10-09）

完整后端 pytest **302 项通过（91.74 秒）**；新增 `test_analysis_model.py` **28 项**，覆盖三类意图/拒答、空数据与缺成本、事实与建议 ID/额外字段阻断、重复问数的 Decimal 数值与来源一致、授权/两次费用预算、暂停与恢复、在途取消/撤销/清除、审计回滚、保存去重、租约失效及供应商响应分类。HTTP MockTransport 覆盖合法响应、拒答、incomplete、非法 JSON、无 usage、布尔 usage、超时、重定向、过大及非对象响应；没有真实模型调用。首轮定向测试的两条断言原先误取最后的暂停/取消操作记录，改为定位模型丢弃状态后全量通过。

Ruff **140 文件**规则/格式、mypy **105 个 app 文件**通过。Vitest **13 文件 23 项通过**，新增解释组件的原始文本转义、缺口和未完成模型状态。Vue lint、type-check、生产构建通过；Starlette/httpx 弃用提示仍在。

完整 Playwright **30 项通过（59.4 秒）**；新增桌面/手机合成模型路径：确认问题/事实授权和预算 → 显示确定性毛利与模型证据组合 → 审批保存 → 刷新回读 → 确切分析深链 → 完成核对待办 → 清除来源擦除解释。原有 28 项回归一并通过，手机无横向溢出、页面无脚本错误。浏览器替身只在隔离 launcher 和特定合成店铺生效，普通店铺仍显示模型未配置。

使用仓库 Chromium，`http://127.0.0.1:5174/agent`，桌面 1280×800、手机 390×844。解释及清除截图在系统 Temp `soloops-question-{explanation,cleared}-{desktop,mobile}.png`，已实际查看解释卡片；均合成数据，截图不提交。数据库测试与 E2E 串行，本切片无数据库结构变化。

上一提交 5be1ff9 的 [GitHub Actions](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37841674665) 已核实 completed/success。74 SO 与 32 验收行保持完整。MVP-04 的模型协议与本地记录闭环已用替身验证；真实模型供应商调用、真实外发以及其他 P0 模型业务切片仍按矩阵记录。

提交前将分析保存与待办创建收拢为 `AnalyticsService.save_and_create_todo`，模型步骤同时持久化本次供应商、模型名和配置费率；对应问数/Agent/分析定向复验 **70 项通过（21.01 秒）**。最终页面补充暂停后已知回包丢弃、恢复可能重新计费的说明，lint/type/build/格式通过。

## 第十六迭代：模型 Listing 候选与审批（2026-10-09）

完整后端 pytest **323 项通过（114.87 秒）**。新增 `test_listing_model.py` **21 项**：只导入商品的候选/差异/两道审批与真实回读；目标和原文双授权及来源版本绑定；未知/重复/遗漏事实和额外字段阻断；缺参数与 needs_review 分支；预算、未知费用与重放；在途暂停/取消/撤销/清除/生效基线变化；暂停后显式恢复重新计费；保存基线冲突、去重及审计失败原子回滚；跨店/身份范围与 Responses HTTP MockTransport。无真实模型费用或外发。

Ruff **142 文件**规则/格式、mypy **106 个 app 文件**通过。Vitest **14 文件 24 项通过**；新增候选的完整限制、基线及文本转义组件测试。Vue lint、type-check、生产构建通过。前版 CI [37844263020](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37844263020) 的后端通过、前端组件失败，原因是模型解释显示时隐藏了本地 answer；本轮恢复常显本地结论，相关组件及完整前端回归均通过。Starlette/httpx 弃用提示仍在。

新增 Listing 桌面/手机 Playwright 定向 **2 项通过（12.3 秒）**，随后完整 **32 项通过（1.2 分钟）**。验证从具体商品进入 AI 流程、展示发送事实、修改目标清空同意、审批前零草稿、候选刷新持久、保存后精确深链、事实确认后本地生效、再次刷新及来源清除擦除；无页面脚本错误，手机无横向溢出。使用现有 Chromium，桌面 1280×800、手机 390×844；系统 Temp `soloops-listing-{candidate,approved}-{desktop,mobile}.png` 仅合成数据，已实际查看桌面候选及手机审批结果，截图不提交。

模型浏览器替身沿用 `scripts/e2e_analysis.py`，新增 `listing-model-e2e-` 合成店铺范围；仅由强制 `_test` 库的 launcher 注册，普通店铺默认模型关闭。完整 pytest 与 Playwright 串行，无新增迁移，head 仍为 `86df84dc129a`。

初轮定向测试有两处合成店铺标识冲突，修正测试准备后进入全量。期间项目 Docker MySQL 容器退出，3308 连接被拒绝；重启原有开发/测试容器并确认 healthy 后重新执行，全量通过。开发数据未清理，本地配置和日志未提交。74 SO、32 验收行完整保留；MVP-02 的模型协议与本地版本流程用替身验证，真实模型质量仍待配置/授权，MVP-03 和 MVP-01 模型切片继续。

## 第十七迭代：百炼接入与真实合成验证（2026-10-09）

新增 `test_dashscope_model.py` **19 项**，覆盖严格结构化协议、固定端点/禁重定向和代理、正常/拒答/截断/坏 JSON/无或非法 usage/多候选/非法消息/工具调用/超时/HTTP 错误/超大响应、费用已知与未知分类、输出 10-token 余量、未知模型拒绝、路由，以及百炼候选经真实服务审批保存回读。模型相关定向 **91 项通过（30.66 秒）**，完整后端 **342 项通过（110.58 秒）**。Ruff **143 文件**规则/格式、mypy **106 app 文件**通过，Starlette/httpx 弃用提示仍在。

Vue lint/type-check/生产构建通过，Vitest **14 文件 24 项通过（2.98 秒）**；第一次沙箱缓存 rename 的 EPERM 使测试未执行，正常权限环境复验通过。完整 Playwright **32 项通过（1.2 分钟）**，与 pytest 串行使用隔离 `_test` 库。两个测试入口显式排除本机 .env 和真实模型配置；本轮无数据库迁移。

用户明确批准官方北京端点和总额 ¥0.01 后，只读鉴权返回 200，实际应用适配器的两次合成请求成功：路由输入/输出 **103/11 tokens**，Listing **203/51 tokens**；后者经 `compose_listing` 完整事实覆盖校验。按官网 <=32K 档位输入 ¥0.2/输出 ¥0.8 每百万 tokens，目录估算分别 **¥0.0000294 / ¥0.0000814**，合计 **¥0.0001108**。实际账单另核对。测试预留总额 ¥0.0030100，脚本以本机回执拒绝重跑，无自动重试和真实业务数据发送。此证据只覆盖两类合成输入，不代替问数/客服/运营全链路模型质量验收。

上一提交 cb6f119 的 [GitHub Actions](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37874275146) 已核实 completed/success。74 SO 与 32 验收行完整保留；密钥、私密配置及原始回执未进入 Git。

## 第十八迭代：客服模型候选与人工接管（2026-10-09）

完整后端 pytest **374 项通过（125.41 秒）**，新增 `test_support_model.py` **32 项**。覆盖 FAQ 候选、审批前零草稿、持久审批回读、重复候选保留人工编辑；混合意图不可降级、模型补充语义意图；消息/政策/订单源行授权、跨店/身份/渠道隔离；重复/未知/遗漏编号及额外字段阻断；调用前/审批前/批准后政策到期；订单来源清除、政策冲突、在途暂停/取消/清除/政策更新；预算恢复、未知费用禁止重发；审计失败回滚；中文与未识别语言；OpenAI Responses 和百炼 Chat HTTP MockTransport 协议。开发测试使用合成数据，不调用真实模型或邮件通道。

Ruff **145 文件**规则和格式、mypy **107 app 文件**通过。Vue lint/type-check/生产构建通过，Vitest **15 文件 27 项通过（2.74 秒）**，新增客服资料迟到回包隔离、源行绑定、文本转义和接管候选展示。现有技能注册表断言更新为十一项。首轮未识别语言测试改用导入契约的 `und`；Windows 沙箱 MySQL 套接字 WinError 10013 和 Vitest 临时缓存 EPERM 在允许的普通执行环境中复验通过。Starlette/httpx 弃用提示仍在。

新增桌面/手机客服模型 Playwright **2 项通过（13.3 秒）**，随后完整 **34 项通过（1.5 分钟）**。从确切消息进入模型流程，显示发送正文/政策，修改政策清空双授权，候选显示物流与退款双意图和人工接管，刷新回读，审批保存后跳转准确草稿，编辑/存档/刷新，再清除来源验证正文擦除。无页面脚本错误，手机无横向溢出。已实际查看桌面候选与手机存档截图；系统 Temp `soloops-support-{candidate,archived}-{desktop,mobile}.png` 为合成数据，不提交截图。

pytest 与 Playwright 串行使用隔离 `_test` 库；浏览器替身只在测试 launcher 中向 `support-model-e2e-` 合成店铺开放。无需新迁移，head 仍为 `86df84dc129a`。上一提交 51c8701 的 [GitHub Actions](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37875677800) 已核实成功。74 SO、32 验收行完整保留，客服真实模型理解质量、运营模型流程及真实外发按矩阵继续验收。
