# 微信包 B：H13 渠道账单 / H14 订单账单核对 / H15 结算与回款

更新：2026-10-12（Asia/Shanghai）。范围：`task-2`（微信包 B）。写入边界：三个页面目录、
`services/settlement-policy.ts`、`services/statement-policy.ts`、两个客户端测试与本文档；
`app.config.ts`、`navigation.ts`、`pages/index/index.vue` 由主协调者登记。

## 交付文件

| 文件                                                           | 说明                                                  |
| -------------------------------------------------------------- | ----------------------------------------------------- |
| `src/pages/settlements/index.vue` / `index.config.ts`          | H15 原生页面，路由 `/settlements`（`// route:` 标注） |
| `src/pages/statements/index.vue` / `index.config.ts`           | H13 原生页面，路由 `/statements`                      |
| `src/pages/order-reconciliation/index.vue` / `index.config.ts` | H14 独立可注册页面，路由 `/order-reconciliation`      |
| `src/services/settlement-policy.ts`                            | H15 页面私有纯逻辑（校验/派生/标签），不发起请求      |
| `src/services/statement-policy.ts`                             | H13+H14 共用纯逻辑，含两页契约动作 ID 常量            |
| `tests/settlement-policy.test.mjs`                             | 12 项 `node --test` 客户端测试                        |
| `tests/statement-policy.test.mjs`                              | 10 项 `node --test` 客户端测试                        |

## 逐动作覆盖（`contracts/ui-contract.json`）

### r2.settlements（6/6）

| action_id                                                                  | 接口                                               | 页面行为                                                                                                                                                                                                           |
| -------------------------------------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `preview_api_shops__shop_id__settlements_preview_post`                     | `POST /shops/{shop_id}/settlements/preview`        | 「预览周期与回款」：客户端校验范围/账单号/到账凭据后提交，展示 `preview_hash`、来源版本、分币种合计与回款比对；内容变化即清除预览与确认态                                                                          |
| `write_api_shops__shop_id__settlements_post`                               | `POST /shops/{shop_id}/settlements`                | 勾选确认后保存；固定 `request_id`+`preview_hash`+`confirm:true`；写后按 ID 独立 GET 回读；4xx 才允许修正后新建请求，结果未知保留同次恢复按钮且不更换 `request_id`                                                  |
| `page_api_shops__shop_id__settlements_get`                                 | `GET /shops/{shop_id}/settlements`                 | 「读取结算登记」：带 `data_identity`/`channel`，`before` 游标继续读取，不静默截断                                                                                                                                  |
| `get_api_shops__shop_id__settlements__settlement_id__get`                  | `GET /shops/{shop_id}/settlements/{settlement_id}` | 列表点击回读详情；历史条目按 `?version=` 回读历史正文；展示状态/版本/正文版本/历史                                                                                                                                 |
| `read_current_api_shops__shop_id__settlements__settlement_id__current_get` | `GET .../current`                                  | 「回读当前账单与凭据（不更新历史）」：同一事务返回状态与当前依据，页面标注"尚未重新确认"                                                                                                                           |
| `control_api_shops__shop_id__settlements__settlement_id___action__post`    | `POST .../{settlement_id}/{action}`                | 处理动作仅 `withdraw`/`clear`（服务端 `Literal`）；`showModal` 确认 + 二次核验 `id` 未变 + `version`+`confirm`；`active/stale` 可撤销或清除、`withdrawn` 仅清除、`cleared` 不提供动作；写后独立 GET 回读并刷新列表 |

语义覆盖：结算核对（`statements` 明细 + `checks` 口径）、回款记录（`receipts` 人工到账凭据，
最多 50 笔、凭据规范化去重）、币种/期间（`scope` 半开区间、币种不换汇、`totals` 分币种分类型）、
差异与证据（`comparisons` 7 种状态、`outside_cycle_ids` 周期外非回款行、逐行 `source`）。

### r2.statements（7/7）

| action_id                                                                    | 接口                                              | 页面行为                                                                                                                                        |
| ---------------------------------------------------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `reconcile_api_shops__shop_id__statements_reconcile_post`                    | `POST /shops/{shop_id}/statements/reconcile`      | 「读取并核对账单与费用」：范围（身份/渠道/显式偏移起止/IANA 时区）校验后提交，展示合计、比对、收费分类映射、待重核/撤销计数与 8 条口径          |
| `preview_api_shops__shop_id__statement_reviews_preview_post`                 | `POST /shops/{shop_id}/statement-reviews/preview` | 「预览结论与依据」：结论（`consistent`/`differences_recorded`/`pending`）+ 说明；按 `blockers` 只保留允许的结论项；展示预览哈希与三个来源版本号 |
| `write_api_shops__shop_id__statement_reviews_post`                           | `POST /shops/{shop_id}/statement-reviews`         | 勾选确认后保存；`request_id`/`preview_hash`/`confirm` 同 H15；写后按 ID 独立 GET 回读；未知结果保留同次恢复                                     |
| `page_api_shops__shop_id__statement_reviews_get`                             | `GET /shops/{shop_id}/statement-reviews`          | 「读取核对存档」：`data_identity`/`channel`+`before` 游标分页                                                                                   |
| `get_api_shops__shop_id__statement_reviews__review_id__get`                  | `GET .../statement-reviews/{review_id}`           | 列表点击、历史版本（`?version=`）回读                                                                                                           |
| `read_current_api_shops__shop_id__statement_reviews__review_id__current_get` | `GET .../{review_id}/current`                     | 「回读当前来源、费用与规则（不更新历史）」                                                                                                      |
| `control_api_shops__shop_id__statement_reviews__review_id___action__post`    | `POST .../{review_id}/{action}`                   | 与 H15 相同的 `withdraw`/`clear` 确认与回读语义                                                                                                 |

语义覆盖：账单范围/明细（`scope`、`statements` 分页、逐行 `source`）、核对结果（`totals`+
`comparisons`+`mappings`，`stale_expenses`/`withdrawn_expenses` 明确排除）、费用缺失
（`statement_only`/`expense_only`/`ambiguous`/`currency_mismatch` 逐条列出人工费用详情）、
审阅与依据（`ReviewSnapshot.conclusion`+`blockers`+`expense_revision`+`rule_revision`，人工结论
不修改原账单/费用/规则）。

### r2.order_reconciliation（1/1）

| action_id                                                               | 接口                                                | 页面行为                                                                                                                                                                                                              |
| ----------------------------------------------------------------------- | --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `reconcile_orders_api_shops__shop_id__statements_orders_reconcile_post` | `POST /shops/{shop_id}/statements/orders/reconcile` | H14 独立页面读取窗口与同订单号关联来源；展示 `coverage`、销售口径 `sale_basis`+`basis_note`、`comparisons`（销售/退款筛选）、窗口内外计数、订单行与销售/退款账单行分页、逐行来源与 7 条口径。只读结果，不保存人工结论 |

H14 另在 H13 页面内提供同一动作的入口（共用结果语义，按钮分别调用同一接口并在独立页面注册
后跳转 `/order-reconciliation`），满足"从 H13 进入 + 独立可注册路由"的双重要求。

## 关键约定落实

- 金额：只传输/显示 Decimal 字符串，客户端不做浮点运算；`trimmedAmount` 仅去掉显示用尾随零。
- 时间：`start_at`/`end_at`/`received_at` 必须是带明确偏移的 ISO 文本；显式偏移须与所选 IANA 时区
  一致（`Z` 视作同一时刻不做换算）；`localIso` 依据 IANA 时区写出偏移，默认窗口 30 天。
- 写入门禁：`busy` 禁用、`showModal` 二次确认 + `id` 复核、`preview_hash`/`version`/`confirm` 按契约、
  写后按 ID 独立 GET 回读；结果未知保留恢复按钮且不更换 `request_id`。
- 状态门禁：`availableActions` 与服务端 `Literal["withdraw","clear"]` 对齐；`cleared` 记录不提供
  修订或处理动作；已撤销/已清除/无正文不提供修订。
- 页面生命周期：`useUnload` 置 `alive=false` 并自增 `epoch`；账号/店铺变化清空页面数据与确认态；
  `useDidShow` 只做读取与回读，不自动执行业务写入；所有请求走 `scopedRequest`。
- 深链：读取 `shop`/`settlement`/`review`/`data_identity`/`channel`，链接店铺与当前店铺不一致时报错，
  不静默切换。
- 模板只用 `view`/`text`/`input`/`textarea`/`picker`/`checkbox-group`/`button` 与既有
  `screen`/`card`/`hero`/`row`/`label`/`hint`/`error`/`badge`/`primary`/`danger` 样式。

## 验证记录（2026-10-12，Node 24.16.0）

工作目录 `apps/soloops_weapp`：

- `npm run type-check` → 退出 0（首次发现三页缺少 `<script setup lang="ts">`，补齐后为 0）。
- `npm test` → 退出 0，124/124 通过（其中本包新增 22 项：settlement 12 + statement 10）。
- `npm run build:weapp` → 退出 0，`dist/pages/settlements/index.js`（42.05 kB）、
  `dist/pages/statements/index.js`（42.62 kB）、`dist/pages/order-reconciliation/index.js`（19.16 kB）
  与对应 `index.json` 均生成；`dist/app.json` 含三条页面路径。
- `node scripts/check-registration.mjs` → PASS（22 页面 / 22 注册 / 19 业务路由）。
- prettier `--write --single-quote --no-semi`：三个页面、三个 `index.config.ts`、两个策略与两个测试
  均无改动残留；`git diff --check` 无输出。

仓库根：`backend\.venv\Scripts\python.exe scripts\validate_ui_contract.py` → 退出 0
（`PASS: static UI contract; 21 features, 149 API references`）。

## 未完成项与不确定点

- 未执行微信开发者工具交互、真实后端数据库旅程与真实凭据核验；编译/单测通过不等于 IDE 或数据库验收。
- 契约 `data_fields` 未声明 `StatementReviewed`/`OrderReconciliation`/`StatementReconciliation` 输出模型；
  `SettlementSaved` 声明含 `content_version`（实现中存在），H15/H13 返回体还包含 `data_identity`/
  `channel`/`history`，均按后端 schema 展示。若需写入契约请由主协调者决定。
- H14 单独页面未提供人工结论存档（契约中该特性只有 1 个 read 动作），如需结论请回 H13 页面。
- 分页一律服务端游标（H15/H13 存档）或 20 行窗口（账单/订单明细），未在客户端合并跨页求和。
- 三个页面的"导入或查看账单批次"入口按约定跳 `/imports`（带 `shop` 与 `kind=statements`）；当前
  `pages/imports` 只解析 `batch` 参数，`kind` 暂被忽略（该页属包 A 写入范围，未改动）。
