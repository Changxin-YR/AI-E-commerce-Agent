# 微信小程序端实现（wave 1）

更新：2026-10-11，分支 `feat/soloops-mobile-m0c`。技术栈：Taro 4.3.0 + Vue 3.5 + TypeScript 5.9 + Vite 4.5（沿用工程既有配置，未新增任何依赖）。

## 本轮交付范围

`apps/soloops_weapp/src/` 由"M0 壳 + 诊断页"扩展为可用的业务端第一波：

| 层 | 文件 |
|---|---|
| core | `config.ts`（API base，构建期 `TARO_APP_API_BASE` 内联）、`api.ts`（Bearer、401、错误归一化、未知结果标记）、`session.ts`、`store.ts`、`format.ts`（金额/时间/时区）、`labels.ts`、`links.ts`、`digest.ts`、`csv.ts` |
| ui | `PageShell.vue`、`FactLine.vue`、`ActionButton.vue`、`forms.ts` |
| pages | `login`、`home`、`tasks`、`imports`、`agent`、`listings`、`support`、`inventory`、`mine`（每页含 `index.config.ts`） |

`app.config.ts` 注册 9 个新页面，tabBar = 首页 / 待办 / AI / 客服 / 我的（与 `contracts/ui-contract.json` 的 5 个 entry 一致）。`config/index.ts` 增加一行 `defineConstants`，使后端地址在构建期内联、运行时不依赖 `process`。

## 页面与接口

均按 `contracts/ui-contract.json` 的 `api_ref` 取值；除注明外带 `/api/shops/{shop_id}` 前缀。

- `login`（r2.login）：`POST /api/mobile/auth/login`（`client_type=weapp`）、`GET /api/shops`。契约中 r2.login 的 api_ref 指向 Web Cookie 会话的 `/api/auth/login`，该路由拒绝 `Authorization` 头，小程序改用后端 `mobile_auth` 的 Bearer 入口，与 Flutter 端保持一致。
- `home`（r2.home）：`GET /api/workbench`、`GET /api/onboarding`；三计数取 `view_counts.attention / ai_completed / update_data`。
- `tasks`（r2.home）：`GET /api/workbench` + `operations/tasks[/{task_id}]`（审批、复检、完成核对）。
- `imports`（r2.imports）：`/api/imports/catalog|mappings`、`/imports`、`/api/imports/{id}/preview|commit|revoke|clear|errors.csv`、`import-groups[/{id}][/revoke]`。
- `agent`（r2.agent + r2.b1）：`agent/skills|model|runs[/{run_id}]`、`business-rules`、`listings/products[/{id}]`、`support/messages/{id}`、`operations/preview`；B1 使用 7 天窗 + `analysis_todo` / `listing_draft` 双节点审批。
- `listings`（r2.listings）：`listings/products[/{product_id}]`、`listings/versions[/{listing_id}]`、`generate`、`versions/{id}/revise`、`decision`、`delivery`。
- `support`（r2.support）：`support/messages[/{id}]`、`messages/{id}/generate`、`policies[/{id}/clear]`、`drafts[/{id}]`、`drafts/{id}/{edit,action,review}`、`delivery`、`drafts/{id}/manual-actions`。
- `inventory`（r2.inventory）：`GET /api/shops/{id}/inventory`（`data_identity`/`channel`/`max_age_hours`/`search`/`offset`）+ `operations/tasks` 取低库存关联待办。
- `mine`（tabBar 第五入口）：`GET /api/mobile/auth/session`、`GET /api/shops`、`POST /api/mobile/auth/logout(-all)`。

## 验证（2026-10-11，本机）

- `npm run type-check`（vue-tsc --noEmit）：exit 0，0 错误。
- `npm run build:weapp`：构建成功（`✓ built in 6.15s`），`dist/app.json` 含 9 个新页面，tabBar 5 项，`dist/app.js` 含全部页面路径。
- 已在构建期确认 `TARO_APP_API_BASE` 内联生效；默认回落 `http://127.0.0.1:18080`。

**尚未验证（不得写成通过）**：未在微信开发者工具/真机联调，未向真实后端发起请求，运行时行为（登录、列表、写操作）未验证；真机需在 MP 后台把服务域名加入合法域名，`http://127.0.0.1:18080` 仅开发者工具可用（并需关闭域名校验）。automator 通道在 M0 阶段即 60s 超时（exit 124），未复测。

## wave 2（同日交付）

新增 11 个页面（各 `index.vue` + `index.config.ts`，共 7,477 行）：`analytics`、`overview`、`profit`、`expenses`、`statements`、`settlements`、`rules`、`outbound`、`schedules`、`product_quality`、`product_edits`。同时：

- `app.config.ts` 注册这 11 页（`pages` 共 22 项，tabBar 仍 5 项）。
- `src/pages/mine/index.vue`（107 → 472 行）在原有内容上**追加**入口分组：开始经营、经营档案、店铺管理（创建店铺 + 回读资料）、经营与财务、规则·自动化与外发、商品维护；原有账号/店铺切换/业务工具/退出逻辑未改。
- `src/core/links.ts` 追加 11 条 `web_route → 页面` 映射，供工作台事项深链。

feature → 主要 api_ref（均带 `/api/shops/{shop_id}` 前缀，`r2.overview` 除外）：

- r2.analytics：`/analytics/{calculate,ask,saved,saved/{id},saved/{id}/todo,order-costs/{row_id},sources/{row_id},revision}`
- r2.overview：`/overview/{calculate,reports,reports/{id},reports/{id}/clear}`
- r2.profit：`/profit/{calculate,saved,saved/{id}}`
- r2.expenses：`/expenses{,/summary,/orders,/{id},/{id}/{action}}` + `/fee-rules{/preview,/{id},/{id}/{action}}`
- r2.statements：`/statements/reconcile` + `/statement-reviews{/preview,/{id},/{id}/current,/{id}/{action}}`
- r2.settlements：`/settlements{/preview,/{id},/{id}/current,/{id}/{action}}`
- r2.rules：`/business-rules{,/history,/{version}}` + `/authorizations{,/{id},/{id}/revoke,/{id}/uses/{use_id}/revert}`
- r2.outbound：`/outbound/{channel,connect,channel/{id}/verify,channel/{id}/revoke,messages,messages/{id},{id}/approve,{id}/reject,{id}/send,{id}/reconcile,{id}/receipt}`
- r2.schedules：`/schedules{,/status,/history,/{id},/{id}/check}` + `/history/{item_id}/read`
- r2.product_quality：`/product-quality/{preview,reports,reports/{id},reports/{id}/clear}`
- r2.product_edits：`/product-quality/preview` + `/product-edits{,/{id},/{id}/approve,/{id}/{action}}`

**验证（本机，主代理复核）**：`npm run type-check` exit 0（0 错误）；`npm run build:weapp` 成功（`✓ built in 6.23s`），`dist/app.json` `pages=22`、`tabBar=5`，11 个新页面标题正确；70 处接口路径与 `contracts/ui-contract.json` / 后端路由一致；未新增依赖；金额按十进制字符串处理，未用 `parseFloat/toFixed` 算钱；`r2.outbound` 仅界面与接口，未真实发送。

## wave 3

新增/修改（`apps/soloops_weapp/src/`）：

- `pages/order_reconciliation/{index.vue,index.config.ts}`（r2.order_reconciliation 独立页）：`POST {shopPath}/statements/orders/reconcile`，载荷 `data_identity`/`channel`/`start_at`/`end_at`/`timezone`/`sale_basis`/`basis_note`；展示 `scope`/`coverage`/`comparisons`/`checks` 与订单行、账单行明细；`sale_basis != unknown` 时前端前置校验 `basis_note` 必填（与后端 `Literal` 约束一致）；金额一律十进制字符串透传，未知显示「未知」。
- `pages/fee_rules/{index.vue,index.config.ts}`（r2.expenses 的 `/fee-rules` 独立页）：`GET/POST {shopPath}/fee-rules`、`POST /fee-rules/preview`、`GET /fee-rules/{id}`、`POST /fee-rules/{id}/{action}`；**必须先预览再保存**（改动表单或范围即作废 `preview_hash`）；必填留空不提交；断线/超时提示「结果未知，请回读」。
- `ui/SourceEvidence.vue`：来源证据展开组件，接入 `statements`、`expenses`、`product_quality`、`order_reconciliation` 四页；组件自身不发请求，避免对同一来源重复读取。
- `assets/tabbar/*.png`：10 个 tabBar 图标，**81×81、8 位 RGBA（colortype 6，透明底）、361–710 B**；`app.config.ts` 为 tabBar 5 项补 `iconPath`/`selectedIconPath`。
- `app.config.ts` 注册 2 个新页面；`core/links.ts` 增加 `/order-reconciliation`、`/fee-rules` 映射；`pages/mine/index.vue` 在「经营与财务」分组追加 2 个入口。

**验证（本机，主代理独立复核）**：`npm run type-check`（vue-tsc --noEmit）exit 0；`npm run build:weapp` exit 0（`✓ built in 6.49s`）；`dist/app.json` `pages=24`、`tabBar=5` 且 5 项均带 `iconPath`/`selectedIconPath`，构建产物 `dist/assets/tabbar/` 10 个 PNG 全部落盘；图标尺寸/色深用 PNG 头逐字节校验通过；未新增依赖、未改 `package.json`。

**与 Flutter 端的有意差异（如实记录，不得写成"已对齐"）**：`contracts/ui-contract.json` 的 `r2.order_reconciliation` 只声明 `statements/orders/reconcile` 一个动作，因此小程序订单核对页**只读、不提供"保存审阅"**；Flutter 端另有 `ReviewPanel(orders: true)` 走 `/order-statement-reviews`（后端存在该路由，但不在契约动作内）。同理 `fee-rules/{id}/{action}` 服务端只接受 `withdraw`/`clear`，小程序按此实现，未臆造 `save`/`revoke` 路径。

## 交付边界（2026-10-12 由用户确认收尾）

- **已完成**：微信端 wave 3 代码（`r2.order_reconciliation` 独立页与「我的」入口、`/fee-rules` 独立页、tabBar 图标、「来源证据展开」组件）通过 `vue-tsc` 与 `taro build`；**微信开发者工具模拟器可正常渲染该小程序**（登录页显示服务地址 `http://127.0.0.1:18081`），并定位到可复现的启动失败修复（见下）。
- **已知限制（收尾，不再反复重试）**：**登录/列表/写操作的"真实链路驱动"未取得结果**。原因已穷尽：`miniprogram-automator@0.12.1` 是 npm 最新版且与本机 IDE `v2.01.2510290` 不兼容；`SendKeys`/剪贴板注入不到小程序输入框；盲点坐标打不开调试器控制台。**补齐方式**：请人工在开发者工具里登录一次（账号 `harmony_r2` / 密码 `Synthetic-R2-2026!`）并回传截图；或改走真机调试（需在 MP 后台把服务域名加入合法域名）。运行时脚本已备 `scripts/mobile/check_weapp_runtime.cjs`。

## 微信开发者工具运行时联调（进展、可复现修复与仍阻塞的部分）

**已确认：构建产物能在微信开发者工具里正常加载与渲染。**

- 模拟器稳定渲染出**业务登录页**：标题"登录"、`SoloOps`、副标题"把每天的经营事务，整理成下一步行动。"、**服务地址 `http://127.0.0.1:18081`**（本轮 `TARO_APP_API_BASE` 构建的结果）、账号/密码输入框与"登录"主按钮。截图：`.local/mobile-business/device/weapp-after-swc.png`。
- **可复现修复（重要）**：模拟器报 **"模拟器启动失败 / TypeError: Cannot read property 'subPackages' of undefined"**（更早还出现过 `TypeError: Failed to fetch`）时，**删除 `apps/soloops_weapp/.swc/`（该目录在 `apps/soloops_weapp/.gitignore` 中，属工具编译缓存，删了不影响仓库）后重启 IDE 即恢复正常渲染**。此前把成因归到系统代理是错的——代理仍开启时同样能渲染。
- **更正上一轮判断**：之前"系统代理 `127.0.0.1:7897` 下 `servicewechat.com` TLS 失败导致模拟器起不来"的结论**不成立**；真实原因是 IDE 的编译缓存/进程状态损坏。代理现象本身属实，但不需要为此改动系统网络设置。

**仍然阻塞：无法自动化驱动登录/列表/写操作。**

- `cli auto --project … --auto-port 9420` **可以成功**（端口监听、解析出 AppID `wx7f42829bf7c13898`），但 `miniprogram-automator@0.12.1` **已是 npm 上的最新版本**，与本机 IDE `Stable v2.01.2510290` **不兼容**：报 `EMFILE: too many open files … core.wxvpkg` → `The "fd" argument must be of type number. Received undefined`（错误来自 IDE 侧，依赖里并无 `wxvpkg` 字样）。
- 退路"窗口点击 + `SendKeys`/剪贴板"也不行：点击能命中模拟器、按键能到 DevTools 外壳（`Ctrl+B` 可触发编译），但**注入不到小程序渲染出的输入框**——多次尝试账号框始终为空。
- 连"打开调试器控制台"这一步也无法用盲点坐标稳定命中（菜单栏点击无响应）。
- 因此 **登录、列表、写操作的真实链路仍未取得结果**，不得写成已验证。**下一步建议**：(a) 请用户在该开发者工具里手工登录一次（账号 `harmony_r2` / 密码 `Synthetic-R2-2026!`，服务地址已构建为 `http://127.0.0.1:18081`）并把结果截图交回；(b) 或改走真机调试（需在 MP 后台把服务域名加入合法域名）。
- 已备好运行时脚本 `scripts/mobile/check_weapp_runtime.cjs`（登录→待办列表→商品质量检查保存），一旦自动化通道可用即可直接跑；本机已用只读 API 探针确认 `client_type=weapp` 登录可用且 `GET /api/shops` 返回 `918 HarmonyR2Main`。

## 其他仍待验证

- 真机需在 MP 后台把服务域名加入合法域名；`http://127.0.0.1:18081` 仅供开发者工具使用（`project.config.json` 的 `urlCheck` 为 `true`，**该文件受保护不得修改**）。
- 本轮构建产物的 `TARO_APP_API_BASE` 为 **`http://127.0.0.1:18081`**（本机 18080 是其他项目的 nx-keycloak），内联已确认；`DEFAULT_API_BASE` 仍为 `18080`（仅回落用）。该构建产物属本机验证，不影响已提交源码。

## 保护

`apps/soloops_weapp/project.config.json`（真实 AppID）与 `project.private.config.json` 为本机配置，不提交、不覆盖（本轮已核 mtime 仍为 2026-10-11 12:20，未被改动）；`dist/` 为构建产物，已在 `.gitignore` 中。
