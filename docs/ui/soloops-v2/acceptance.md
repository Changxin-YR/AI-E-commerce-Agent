# SoloOps V2.1 UI 重构验收报告

生成时间：2026-10-11T18:30:03+08:00。

本次交付为前端视觉层改动及验收材料。代码保留在独立本地分支 `ui/soloops-v2`，未提交、推送或部署。

## 阶段一：冻结基线与隔离

- 基线 SHA：`0a49a37dcd7f1ccf0acc2c0a225bfdc8d8bee686`。
- 专项目录：`C:/Users/27363/Desktop/AI E-commerce Agent/soloops-ui`。从原 PC 仓库创建独立 Git 副本，原仓库的 `main` 与移动开发分支均未修改。原 PC 仓库仍只有原有 `docs/r2-final-special-acceptance.md`、`docs/uat/` 未跟踪内容。
- 修改前运行附件 `source_ui_contract.py`，保留根目录 `ui-contract-before.json`；补充 Vue SFC/template 与 TypeScript AST 冻结清单。
- 20 个页面、57 个复用组件、20 个实际页面路由、5 组 19 个业务入口。
- 修改前 lint、类型检查、build、39 文件/158 项 unit 与 91 项原 E2E 通过；工作基线检查完成后才添加视觉代码。
- 数据库：`127.0.0.1:3318/soloops_ui_v21_test`；独立 Docker Compose 项目 `soloops-ui-v21-20261011`。采用仓库 `serve_e2e.py`、既有合成样本及模型/邮件测试替身。外部模型、邮件及调度默认关闭。

## 阶段二、三：视觉与功能对应

统一 `soloops.css` 负责配色、间距、标题、卡片、表单、宽表滚动、危险动作和三尺寸布局。19 个业务页面增加纯布局容器，登录页增加 CSS 标记。组件只增加危险按钮 class。`main.ts` 仅追加样式 import。原 Vue 业务脚本 77/77 SHA-256 一致，所有原非视觉属性、条件分支、事件、链接、字段约束、ARIA 与组件传参经 AST 一一核对。

附件契约：前后均为 1,014 个声明节点，含 287 个 button 声明。补充 AST：前后均为 1,051 个控件/事件声明、2,498 个指令。计数口径不同，均不能当作任意业务状态下的实际按钮总数。5 处候选差异均为深链对象缩进，逐项核对见 [contract-difference-review.md](contract-difference-review.md)。

完整旧→新控件、字段、事件、条件、禁用、校验、ARIA、组件调用链与处理函数源码见 [complete-control-matrix.csv](complete-control-matrix.csv)：1,542 行上下文对应，覆盖全部 20 页的复用组件实例；不是抽样清单。全量原始 AST 与脚本源码随本地证据包保存。

| 页 | route / 源页面 | 保留功能、字段与状态（旧 → 新均相同） | 视觉调整 | 源码声明/组件调用上下文行 | 三尺寸单页 E2E | 原业务 E2E 文件 |
|---|---|---|---|---:|---|---|
| 01 登录 | `/login` / `LoginView.vue` | 登录表单、帮助说明；无额外登录入口 | 双栏登录卡片、抽象背景，小屏纵向排列 | 5/5 | 3/3 通过 | workspace |
| 02 工作台 | `/` / `DashboardView.vue` | 事项筛选、三种视图、运营检查、审批、历史、首次使用、返回深链 | 真实工作计数卡片、事项与审批区分层 | 120/142 | 3/3 通过 | workbench,operations,operations-model,continuity |
| 03 经营资料 | `/settings` / `SettingsView.vue` | 档案七字段、店铺六字段、编辑/取消/确认添加、导入入口 | 经营档案与店铺双列；小屏依次排列 | 45/45 | 3/3 通过 | workspace |
| 04 数据导入 | `/imports` / `ImportsView.vue` | 文件/模板/字段语义/错误/预览/分片/批次撤销清除/状态动作 | 上传与映射分区、模板按钮换行、原始行表格容器滚动 | 94/94 | 3/3 通过 | imports,foundation |
| 05 经营分析 | `/analytics` / `AnalyticsView.vue` | 7/30 天、三种问题、成本、时区/ISO、SKU/来源/历史/待办 | 统计范围表单、指标卡与证据表；保留全部原统计内容 | 70/78 | 3/3 通过 | analytics,analysis-model,continuity,margin-review |
| 06 Listing 审批 | `/listings` / `ListingsView.vue` | 商品/事实/草稿/差异/本地批准拒绝/历史/失效 | 商品选择与当前事实双栏、版本差异对照 | 34/34 | 3/3 通过 | listings,listing-model,foundation |
| 07 客服工作台 | `/support` / `SupportView.vue` | 消息搜索分页、关联核验、政策版本、回复草稿、人工接管、补录 | 消息与证据双栏、回复审阅和政策卡片，小屏单栏 | 126/147 | 3/3 通过 | support,support-model,foundation,continuity |
| 08 库存快照 | `/inventory` / `InventoryView.vue` | 来源时效、SKU/渠道/身份、未知/过期、原始来源、分页、导入 | 查询卡片、库存状态与来源证据层级 | 28/28 | 3/3 通过 | inventory,operations,foundation |
| 09 任务执行台 | `/agent` / `AgentView.vue` | 全部十种流程、模型预算与同意、节点/恢复/暂停取消、内部预授权、日志 | 任务范围、节点审批、预授权与日志分层 | 131/152 | 3/3 通过 | agent,analysis-model,listing-model,support-model,operations-model,margin-review |
| 10 新品利润 | `/profit` / `ProfitView.vue` | 九种费用的金额/方式/依据、多方案、清除、敏感性、历史 | 方案编辑与九类费用分区，保留原重复字段结构 | 42/42 | 3/3 通过 | profit |
| 11 实际费用 | `/expenses` / `ExpensesView.vue` | 凭据号、时间/时区、归属、精确订单行、保存确认、修订/处理/回查 | 费用范围、录入、依据、历史卡片；处理按钮醒目 | 70/84 | 3/3 通过 | expenses,continuity |
| 12 账单核对 | `/statements` / `StatementsView.vue` | 账单金额分类、FeeRules/StatementReviews、历史、二次确认 | 核对范围、收费规则和结论分层；宽表局部滚动 | 97/190 | 3/3 通过 | statements,fee-rules,statement-reviews |
| 13 订单销售与退款核对 | `/order-reconciliation` / `OrderReconciliationView.vue` | 同日同币种一对一条件/差额、缺失/跨期/退款待核 | 核对表单与来源差异卡片，沿用原待核状态 | 45/52 | 3/3 通过 | order-reconciliation |
| 14 结算与回款 | `/settlements` / `SettlementsView.vue` | 原账单周期、50 笔凭据上限、逐笔差额、预览/保存/版本/处理 | 周期范围、人工凭据、预览与登记历史分区 | 72/121 | 3/3 通过 | settlements |
| 15 经营规则 | `/rules` / `RulesView.vue` | 阈值、版本、偏好/预算、恢复/撤销/重置、原读取动作 | 范围与阈值表单、说明和版本历史分层 | 35/35 | 3/3 通过 | business-rules |
| 16 测试外发 | `/outbound` / `OutboundView.vue` | QQ 验证、地址全文、单次批准/预授权、只读回查、收件证据、未知不重发 | 连接状态、摘要准备、审批/证据卡片；危险操作标红 | 54/54 | 3/3 通过 | outbound,foundation |
| 17 经营总览 | `/overview` / `OverviewView.vue` | 平台/市场独立筛选、20 店上限、快捷/自选对比、分币种与来源 | 筛选卡片、实际汇总和来源区域统一主题 | 87/87 | 3/3 通过 | overview |
| 18 定时与通知 | `/schedules` / `SchedulesView.vue` | 日周月差异输入、星期/月日期、规则/时区/免打扰、控制与运行记录 | 计划表单、通知与运行记录卡片 | 62/62 | 3/3 通过 | schedules |
| 19 商品质量 | `/product-quality` / `ProductQualityView.vue` | 口径、SKU 前缀、线索/来源、保存确认、历史/清除 | 检查范围、结果、证据和历史层次 | 41/41 | 3/3 通过 | product-quality |
| 20 商品修订 | `/product-edits` / `ProductEditsView.vue` | 每批50件、选择/逐件字段、理由、差异、审批、撤销清除、历史 | 选择编辑与新旧差异区域统一，移动端表格独立滚动 | 49/49 | 3/3 通过 | product-edits |

## 阶段四：自动化与真实渲染证据

| 检查 | 结果 | 证据 |
|---|---|---|
| npm ci | 通过，安装 293 个包；package-lock.json 未改动 | 首次冻结基线终端记录 |
| npm run lint | 通过 | `final-lint.log`、`final-lint.result.json` |
| npm run type-check | 通过 | `final-type-check.log`、`final-type-check.result.json` |
| npm run build | 通过 | `final-build.log`、`final-build.result.json` |
| npm run test:unit（39 文件、158 项） | 通过 | `final-unit.log`、`final-unit.result.json` |
| npm run test:e2e（原91 + 新60） | 通过 | `final-e2e.log`、`final-e2e.result.json` |
| 冻结版本三尺寸场景 | 通过 | `baseline-responsive.playwright.json` |
| 冻结版本客服稳定回读补采（3 视口） | 通过 | `baseline-responsive-recapture.playwright.json`；原始加载中截图单独保留 |
| 新版本三尺寸场景 | 通过 | `final-responsive.playwright.json`；完整 E2E 再运行相同 60 项 |
| 运行时控件对照 | PASS；96 场景 | [runtime-parity.json](runtime-parity.json) |

运行时场景为 20 页默认状态 + 12 页指定展开状态，分别覆盖 1440×1000、420×900、390×844，共 96 个状态/视口组合。按钮出现次数合计：旧 608、新 608。比较逐序控件类型和 disabled 状态；数字为场景出现次数之和，不是去重后的功能数。5 组 19 导航入口逐一进行了可见性与试点击检查。页面宽度、表格容器、控件边界和点击命中均有原始 JSON。

高风险业务断言沿用原 E2E：保存前确认、批准后来源变化/失效拒绝、刷新回读、历史恢复、撤销/清除、模型预算与未知结果、邮件未知后只读回查、人工收件证据记录、深链返回、会话与权限边界。详细用例名称和状态见 [e2e-results.json](e2e-results.json)。测试真实调用隔离 API；模型与邮件通过仓库既有测试替身，不产生实际外发，也不把模拟回执描述为真实邮箱送达。

未改后端文件、API 客户端、类型/金额计算、日期/时区、router、鉴权及权限模块。后端独立全量单测未另行运行；本次原有浏览器业务回归直接覆盖隔离后端。

## 截图、双页图与坐标

本地证据目录：`soloops-ui/.local/ui-evidence/`。打开 `review/index.html` 可切换页面、尺寸、长页、展开区、设计参考及冻结版本。

- 20 页 × 3 尺寸：60 张完整长页 + 60 张首屏。
- 12 类展开 × 3 尺寸：36 张完整长页、36 张首屏、36 张关注区域；覆盖登录帮助、工作台审批、导入映射、分析结果、客服草稿、库存来源、内部预授权、费用录入、收费映射规则、订单待核、结算人工凭据、当前阈值。
- 按附件 crop_manifest 01–02 至 19–20：桌面 10 张 2896×1000、手机 10 张 854×900 双页图，原像素不缩放。
- 另附每页设计参考↔运行结果、冻结版本↔运行结果双页对照。
- 坐标清单：`review/crop-manifest.json`；独立完整 PNG 为最终长页依据。联系总览图只用于快速浏览。

## 检查过程中发现与修复

- 冻结阶段首次受限环境 unit 因 Windows EPERM 未执行；改在授权隔离环境运行。Python 环境补齐后，冷启动的 CSV oracle 曾一次超时；完整 158 项复测通过。
- 工作台 scoped 样式覆盖新主题：增加视觉选择器优先级后，计数卡、标题与主题一致。
- 手机结算展开态的嵌套日期网格过窄：日期范围占整行，移动端日期时间独占一行，并增加原生日期输入至少 240px 的可读性断言。所有原 ISO 输入、时区与错误处理均保留。
- 新验收测试的两处定位使用了参考稿标题：改为源码的“订单金额待核清单”“检查阈值”后通过。
- 原生折叠 details 的内部布局矩形不代表可见：采集器按祖先 open 状态过滤。换行链接按各行实际矩形检测命中。相关初次失败日志和 trace 已保留。
- Agent 与客服截图可能捕捉到异步加载中的 disabled 状态：展开态增加等待原按钮恢复可用，再采集稳定状态；不修改业务等待/加载逻辑。

## 范围与证明边界

全部源码控件和条件表达式已做静态等价核对；96 个选定运行状态/视口组合及原业务 E2E 提供动态证据。不存在声称穷举全部数据、权限、网络错误组合的证明；测试覆盖范围以原始用例和状态清单为准。外部真实邮箱送达、线上部署和生产数据操作均不属于本次隔离 UI 验收。

## 受影响文件及原因

| 文件 | 原因 |
|---|---|
| `docs/ui/soloops-v2/acceptance.md` | 冻结契约、逐项功能对应或验收证据 |
| `docs/ui/soloops-v2/changed-file-hashes.json` | 冻结契约、逐项功能对应或验收证据 |
| `docs/ui/soloops-v2/complete-control-matrix.csv` | 冻结契约、逐项功能对应或验收证据 |
| `docs/ui/soloops-v2/contract-difference-review.md` | 冻结契约、逐项功能对应或验收证据 |
| `docs/ui/soloops-v2/e2e-results.json` | 冻结契约、逐项功能对应或验收证据 |
| `docs/ui/soloops-v2/page-acceptance-matrix.json` | 冻结契约、逐项功能对应或验收证据 |
| `docs/ui/soloops-v2/route-control-index.json` | 冻结契约、逐项功能对应或验收证据 |
| `docs/ui/soloops-v2/runtime-parity.json` | 冻结契约、逐项功能对应或验收证据 |
| `docs/ui/soloops-v2/source-equivalence-summary.json` | 冻结契约、逐项功能对应或验收证据 |
| `frontend/e2e/soloops-responsive.spec.ts` | 20 页三尺寸、12 类展开、导航、溢出、遮挡与截图验收 |
| `frontend/src/components/AgentRunReview.vue` | 现有危险动作增加视觉 class；原确认流程保留 |
| `frontend/src/components/FeeRules.vue` | 现有危险动作增加视觉 class；原确认流程保留 |
| `frontend/src/components/ImportGroups.vue` | 现有危险动作增加视觉 class；原确认流程保留 |
| `frontend/src/components/InternalAuthorizations.vue` | 现有危险动作增加视觉 class；原确认流程保留 |
| `frontend/src/components/ListingReview.vue` | 现有危险动作增加视觉 class；原确认流程保留 |
| `frontend/src/components/OperationTaskReview.vue` | 现有危险动作增加视觉 class；原确认流程保留 |
| `frontend/src/components/OrderCostEditor.vue` | 现有危险动作增加视觉 class；原确认流程保留 |
| `frontend/src/components/OutboundMailReview.vue` | 现有危险动作增加视觉 class；原确认流程保留 |
| `frontend/src/components/SettlementRecords.vue` | 现有危险动作增加视觉 class；原确认流程保留 |
| `frontend/src/components/StatementReviews.vue` | 现有危险动作增加视觉 class；原确认流程保留 |
| `frontend/src/components/SupportPolicies.vue` | 现有危险动作增加视觉 class；原确认流程保留 |
| `frontend/src/main.ts` | 加载新视觉样式，仅一条 import |
| `frontend/src/styles/soloops.css` | 统一视觉系统、逐页布局及响应式规则 |
| `frontend/src/views/AgentView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/AnalyticsView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/DashboardView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/ExpensesView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/ImportsView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/InventoryView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/ListingsView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/LoginView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/OrderReconciliationView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/OutboundView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/OverviewView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/ProductEditsView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/ProductQualityView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/ProfitView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/RulesView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/SchedulesView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/SettingsView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/SettlementsView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/StatementsView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `frontend/src/views/SupportView.vue` | 纯布局容器/CSS 标记；原脚本及所有业务绑定保留 |
| `ui-contract-after.json` | 冻结契约、逐项功能对应或验收证据 |
| `ui-contract-after.json.diff.json` | 冻结契约、逐项功能对应或验收证据 |
| `ui-contract-before.json` | 冻结契约、逐项功能对应或验收证据 |

大体积截图、日志、原始 AST 存于本地证据目录及打包附件，避免将合成运行产物混入应用源码。

## 复现

使用 README/CI 的隔离数据库要求（数据库名以 `_test` 结尾），先安装前后端锁定依赖。不要使用线上数据库。

```powershell
cd frontend
npm ci
npm run lint
npm run type-check
npm run build
npm run test:unit
npm run test:e2e
```

新增响应式验收单独运行：`npm run test:e2e -- soloops-responsive.spec.ts`。默认输出 `soloops-ui/.local/ui-evidence`；可用 `UI_EVIDENCE_DIR` 指定独立证据目录。

源码核对工具及附件 Python 契约脚本另随证据包 `tools/` 提供。本机审计工具目录：`C:/Users/27363/Desktop/AI E-commerce Agent/.local/soloops-ui-audit`。
