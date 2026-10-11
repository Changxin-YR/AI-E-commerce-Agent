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

## 下一波（wave 3）

`r2.order_reconciliation` 独立页面与「我的」入口、`/fee-rules` 独立页（现并入实际费用页）、tabBar 图标、"来源证据展开"组件；**微信开发者工具运行时联调**（登录、列表、写操作真实链路）并把结果写入文档；真机需在 MP 后台配置合法域名（`http://127.0.0.1:18080` 仅开发者工具可用）。

## 保护

`apps/soloops_weapp/project.config.json`（真实 AppID）与 `project.private.config.json` 为本机配置，不提交、不覆盖；`dist/` 为构建产物，已在 `.gitignore` 中。
