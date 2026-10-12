# 微信 H11 利润测算 + H12 费用/映射（W11）

更新：2026-10-12。范围：`docs/requirements/SoloOps-Mobile-V1.3.md` H11/H12、`contracts/ui-contract.json` 的 `r2.profit`（5 个动作）与 `r2.expenses`（12 个动作）、SO-054/SO-056。

## 页面与动作

原生 `pages/profit`（`/profit`）与 `pages/expenses`（`/expenses`）两个页面逐动作覆盖全部 17 个动作，与后端路由一一对应。

### H11 `/profit`（5/5）

| 动作 | 实现要点 |
|---|---|
| `POST /shops/{id}/profit/calculate` | 试算名称、结算币种、假设来源与 1–5 个方案（售价/采购成本/九类费用）经 `checkedStudyInput` 校验后提交；结果按返回的 `rule_version`、`calculated_at`、`formula`、`scope_note`、`input` 回显，不落库也不由 HTTP 200 推断存档成功 |
| `POST /shops/{id}/profit/saved` | 冻结 `request_key` + 校验后的输入体；成功后按 ID 独立 `GET` 回读再刷新历史；网络/409/5xx 结果未知时保留“回查原保存请求”，不更换 `request_key` 重试；确定性 4xx 视为拒绝并释放恢复入口 |
| `GET /shops/{id}/profit/saved?offset=` | 服务端每页 50 条；`hasMoreStudies` 判定是否给出“继续读取更早方案”，不静默截断 |
| `GET /shops/{id}/profit/saved/{study_id}` | 历史点选后以服务端记录覆盖页面表单与结果；`result.input` 作为输入唯一来源 |
| `DELETE /shops/{id}/profit/saved/{study_id}` | 勾选确认 + `Taro.showModal` 二次确认 + 提交前重新 `GET` 核对 `created_at`/`title` 未变化；清除后再次 `GET` 期望 404 才算清除成立，并刷新历史；已清除记录不再提供写入动作 |

九类费用（`inbound`/`outbound`/`platform`/`storage`/`packaging`/`advertising`/`refund`/`tax`/`other`）各出现一次，留空即“未计入”，已填金额必须填依据，百分比模式不超过 100%——与服务端 `ScenarioInput`/`FeeInput` 校验一致。金额全程为 Decimal 字符串，页面不做浮点运算；费用金额超过 1 亿或超过四位小数在本地即拒绝。

### H12 `/expenses`（12/12）

| 分组 | 动作 | 实现要点 |
|---|---|---|
| 费用记录 | `POST /shops/{id}/expenses`、`POST /shops/{id}/expenses/{expense_id}` | 冻结 `request_id`/`confirm`/`version`/`content`；新增 `version=0`，修订用回读到的当前 `version`；凭据编号去重与订单行来源冲突由服务端判定并原样展示；写后按 ID 独立 `GET` 回读 |
| 分页 | `GET /shops/{id}/expenses` | `data_identity`+`channel` 必填，`before` 服务端游标；“继续读取更早费用”按 `next_cursor` 追加 |
| 订单行 | `GET /shops/{id}/expenses/orders` | 按订单号精确查找当前订单行，选中即绑定 `order_line_id`/`expected_source_row_id`/`expected_source_revision`；任何归属或订单号变更都会解绑并要求重新查找 |
| 合计 | `POST /shops/{id}/expenses/summary` | 1–366 天窗口 + 显示时区；展示分币种/类别/归属合计、有效/待重核/已撤销计数与服务端 checks（不换汇、费用完整性未知） |
| 详情 | `GET /shops/{id}/expenses/{expense_id}` | 正文、金额、发生时间（按记录自身时区显示）、归属、订单行、来源逐行证据与版本历史 |
| 处理 | `POST /shops/{id}/expenses/{expense_id}/{withdraw\|clear}` | 状态门禁 `expenseActions`（active/stale→撤销/清除，withdrawn→清除，cleared→无动作）；`Taro.showModal` + 版本二次核验后提交 `{request_id, version, confirm}`，回读刷新 |
| 规则预览 | `POST /shops/{id}/fee-rules/preview` | 冻结“范围窗口 + 规则内容 + 版本”后预览；展示原规则/拟保存、`statement_count`、`source_revision`、`preview_hash` 与逐行 before→after 分类变化（每 20 条可展开） |
| 规则写入 | `POST /shops/{id}/fee-rules` | 复用预览时的同一 draft 与 `preview_hash`，`request_id` 固定；写后按 ID 独立 `GET` 回读 |
| 规则分页/详情 | `GET /shops/{id}/fee-rules`、`GET /shops/{id}/fee-rules/{rule_id}` | `before` 游标分页、规则正文与版本历史 |
| 规则处理 | `POST /shops/{id}/fee-rules/{rule_id}/{withdraw\|clear}` | 门禁 `ruleActions`（active→撤销/清除，withdrawn→清除，cleared→无动作），确认弹窗 + 版本二次核验后提交并回读 |

## 状态、证据与未知结果

- 页面上下文：`useUnload` 置 `alive=false` 并自增 `epoch`；切店/换会话清空数据与待核对态；`scopedRequest(api, () => alive ? epoch : null)` 拦下过期响应。
- 写入结果未知（网络错误、5xx、409）保留冻结请求与恢复入口；同次恢复沿用原 `request_id`/`request_key`，服务端按请求标识幂等；确定性 4xx 释放恢复入口，允许修正后新建。
- 从身份/渠道/记录切换、未保存编辑、待核对写入三类状态启用 `Taro.enableAlertBeforeUnload`；费用编辑打开时禁止切换范围与记录。
- 时间一律带明确偏移并使用 `supportTime(value, timezone)` 显式展示；发生时间偏移与 IANA 时区不一致在本地即拒绝（与服务端 `valid_evidence` 同规则）。
- 金额、费用、税费与汇率假设均按服务端语义展示，不生成示例业务数字；空态只给范围调整与文件导入入口。

## 共享文件与边界

- 未修改 `src/app.config.ts`、`src/services/navigation.ts`、`src/pages/index/index.vue` 及共享文档；页面顶部以 `// route: /profit`、`// route: /expenses` 标注。
- 需主协调者注册：`app.config.ts` 增加 `pages/profit/index`、`pages/expenses/index`；`navigation.ts` 与卖家首页入口按需登记 `/profit`、`/expenses`。注册前 `taro build` 不会把这两个页面打进产物。
- 规则预览中的账单行来源沿用既有 `SourceList`（跳转 `/imports`），费用来源批次同样复用该组件；规则空态提供“打开文件导入”入口。

## 离线验证（2026-10-12）

工作目录 `apps/soloops_weapp`，Node 24.16.0：

| 命令 | 结果 |
|---|---|
| `npm run type-check` | 退出 0（全量，含本包 2 页面 + 2 策略） |
| `npm test` | 退出 0，123/123 通过；其中本包新增 18 项（profit-policy 8、expense-policy 10） |
| `npm run build:weapp` | 退出 0（5.61s）；`/profit`、`/expenses` 未注册路由前不在产物内 |
| `@vue/compiler-sfc` 编译检查 | 两页 script setup + template 编译通过（脚本：临时目录 `weapp-sfc-check.cjs`，不入库） |
| `git diff --check` | 无输出；新文件未跟踪，另做行尾空白/制表符扫描 0 问题 |
| `scripts/validate_ui_contract.py` | PASS：21 features / 149 API references |
| `python -m unittest discover -s scripts/mobile/tests` | 24 tests OK |

未执行微信开发者工具交互、真实后端数据库旅程与真实外部调用；编译与单测通过不等于 IDE/数据库验收。

