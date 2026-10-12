# 微信包 C：H16 规则授权 / H17 定时运营 / H18 商品质量 / H19 商品本地修订

更新：2026-10-12（Asia/Shanghai）。分支 `feat/soloops-wechat-r2`。
字段、状态与门禁以后端为准：`backend/app/api/routes/{authorizations,business_rules,schedules,product_quality,product_edits}.py`、`backend/app/schemas/*.py`、`backend/app/services/*.py`；Web 参考 `frontend/src/views/{Rules,Schedules,ProductQuality,ProductEdits}View.vue` 与 `frontend/src/api/*.ts`。

## 交付文件

| 文件                                                                        | 作用                                          |
| --------------------------------------------------------------------------- | --------------------------------------------- |
| `apps/soloops_weapp/src/pages/rules/index.vue`、`index.config.ts`           | H16 页面（规则 + 内部授权）                   |
| `apps/soloops_weapp/src/pages/schedules/index.vue`、`index.config.ts`       | H17 页面                                      |
| `apps/soloops_weapp/src/pages/product-quality/index.vue`、`index.config.ts` | H18 页面                                      |
| `apps/soloops_weapp/src/pages/product-edits/index.vue`、`index.config.ts`   | H19 页面                                      |
| `apps/soloops_weapp/src/services/business-rule-policy.ts`                   | 规则值/动作变体校验、授权前置门禁、状态标签   |
| `apps/soloops_weapp/src/services/schedule-policy.ts`                        | 计划配置校验与报表任务归一化、动作/通知门禁   |
| `apps/soloops_weapp/src/services/product-quality-policy.ts`                 | 检查范围校验、保存指纹门禁、覆盖缺口与展示    |
| `apps/soloops_weapp/src/services/product-edit-policy.ts`                    | 商品选择/差异构造、审批与控制门禁、分页与摘要 |
| `apps/soloops_weapp/tests/*-policy.test.mjs`（4 个）                        | 上述纯逻辑的离线测试（33 项）                 |

未修改 `src/app.config.ts`、`src/services/navigation.ts`、`src/pages/index/index.vue` 及共享文档；未执行 git 提交。

## 逐动作覆盖（`contracts/ui-contract.json`，26 项）

### `r2.rules`（9）

| 动作 ID                                          | 页面实现             | 方法/路径                                                      | 门禁与回读                                                                                                                                                                                                   |
| ------------------------------------------------ | -------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `create_api_shops__shop_id__authorizations_post` | `createGrant()`      | `POST /shops/{shop}/authorizations`                            | 先 `GET /agent/runs/{id}` 核对 `template=daily`、`waiting_approval`、`next_node=propose_tasks`、`source_status=current`；`max_uses` 1–20、`valid_hours` 1–168；`confirmed:true`；写后按 ID `GET` 回读        |
| `list_grants_..._authorizations_get`             | `loadGrants()`       | `GET .../authorizations?before_id=`                            | 50 条游标，继续读取按钮                                                                                                                                                                                      |
| `get_..._authorizations__grant_id__get`          | `showGrant()`        | `GET .../authorizations/{id}`                                  | 详情回读；含 uses 与 changes                                                                                                                                                                                 |
| `revoke_..._grant_id__revoke_post`               | `revokeGrant()`      | `POST .../{id}/revoke`                                         | 仅 `status=active` 可点；`showModal` 确认 + 会话/店铺/ID 二次核验；带 `version`；写后 `GET` 回读                                                                                                             |
| `revert_..._uses__use_id__revert_post`           | `revertUse()`        | `POST .../{id}/uses/{useId}/revert`                            | 仅未撤回且 `changes` 非空的 use 可点；`showModal` 说明整批失败语义；写后 `GET` 回读                                                                                                                          |
| `current_..._business_rules_get`                 | `loadRule()`         | `GET .../business-rules?channel&data_identity`                 | 命中页面 + `useDidShow` 只读刷新                                                                                                                                                                             |
| `change_..._business_rules_post`                 | `changeRule(action)` | `POST .../business-rules`                                      | 4 个变体 `save/revoke/reset/restore`；`save` 必带完整 `values`，`restore` 必带 `restore_version`；携带 `expected_version`；撤销/重置/恢复额外 `showModal`；写后按新版本 `GET /business-rules/{version}` 回读 |
| `history_..._business_rules_history_get`         | `loadHistory()`      | `GET .../business-rules/history?channel&data_identity&before=` | 以最后一条 `version` 作 `before` 继续读取                                                                                                                                                                    |
| `get_..._business_rules__version__get`           | `inspect()`          | `GET .../business-rules/{version}`                             | 历史详情 + 从该版本恢复                                                                                                                                                                                      |

### `r2.schedules`（7）

| 动作 ID                                        | 页面实现           | 方法/路径                                   | 门禁与回读                                                                                                                                                     |
| ---------------------------------------------- | ------------------ | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `status_..._schedules_status_get`              | `load()`           | `GET .../schedules/status`                  | 展示 `worker_enabled` 与 `latest_timer`（不受未读筛选影响）                                                                                                    |
| `schedules_..._schedules_get`                  | `load()`           | `GET .../schedules`                         | 计划卡片 + 动作门禁                                                                                                                                            |
| `create_..._schedules_post`                    | `save()`           | `POST .../schedules`                        | `request_id` 固定到成功；`confirmed:true`；写后 `GET /schedules` 列表按 ID 回读；结果未知保留同 `request_id` 回查                                              |
| `history_..._schedules_history_get`            | `load()`           | `GET .../schedules/history?unread=&before=` | 未读开关 + 50 条游标                                                                                                                                           |
| `read_..._history__item_id__read_post`         | `markRead()`       | `POST .../schedules/history/{id}/read`      | 前置门禁：仅 `read_at=null` 且 `notify_at<=now` 可点；`showModal` 确认；写后刷新列表                                                                           |
| `act_..._schedules__schedule_id__post`         | `act()` / `save()` | `POST .../schedules/{id}`                   | 变体 `pause/resume/revoke/edit`；`resume`/`edit` 带 `confirmed:true`；`edit` 带完整 `config`；`pause` 后不再显示“立即检查”；撤销不提供任何写动作；写后回读列表 |
| `check_..._schedules__schedule_id__check_post` | `check()`          | `POST .../schedules/{id}/check`             | 仅 `status=active` 且 `version` 最新可点；`request_id` 固定到成功，未知结果可同 ID 回查；`showModal` 确认；写后回读列表                                        |

### `r2.product_quality`（5）

| 动作 ID                                           | 页面实现                 | 方法/路径                                 | 门禁与回读                                                                                                                                                                          |
| ------------------------------------------------- | ------------------------ | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `preview_..._product_quality_preview_post`        | `preview()`              | `POST .../product-quality/preview`        | 身份/渠道（可空=全部）/SKU 前缀；返回覆盖项、限制、逐项问题与来源                                                                                                                   |
| `save_..._product_quality_reports_post`           | `save()` / `retrySave()` | `POST .../product-quality/reports`        | 必须勾选确认；携带 `scope`、`expected_revision`、`expected_preview_hash`（64 位十六进制）、`request_id`、`confirm:true`；保存中隐藏旧预览；写后按 ID `GET` 回读；未知结果同 ID 回查 |
| `page_..._product_quality_reports_get`            | `loadHistory()`          | `GET .../product-quality/reports?before=` | 20 条游标 + 继续读取                                                                                                                                                                |
| `get_..._product_quality_reports__report_id__get` | `show()`                 | `GET .../reports/{id}`                    | 详情回读；`cleared` 时只显示范围、状态与审计                                                                                                                                        |
| `clear_..._reports__report_id__clear_post`        | `clear()`                | `POST .../reports/{id}/clear`             | `showModal` 确认 + ID/会话二次核验 + `confirm:true`；`cleared` 后不再提供清除；写后按 ID 回读                                                                                       |

### `r2.product_edits`（5）

| 动作 ID                               | 页面实现        | 方法/路径                       | 门禁与回读                                                                                                                                                                          |
| ------------------------------------- | --------------- | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `create_..._product_edits_post`       | `create()`      | `POST .../product-edits`        | 每批 1–50 个不重复商品、仅名称/参数有变化者；`reason` 必填；`channel` 必须具体；`request_id` 固定到成功；写后按 ID `GET` 回读；未知结果同 ID 回查                                   |
| `page_..._product_edits_get`          | `loadHistory()` | `GET .../product-edits?before=` | 20 条游标 + 继续读取                                                                                                                                                                |
| `get_..._product_edits__edit_id__get` | `show()`        | `GET .../product-edits/{id}`    | 详情回读（差异明细、结果、来源、输出批次、当前项数）                                                                                                                                |
| `approve_..._edit_id__approve_post`   | `approve()`     | `POST .../{id}/approve`         | 勾选确认 + 仅 `draft`/有差异明细/指纹有效；`showModal` 确认后再次核验 ID 与版本；携带 `version`、`expected_preview_hash`、`confirm:true`；写后按 ID 回读并区分 `applied` / `failed` |
| `control_..._edit_id___action__post`  | `control()`     | `POST .../{id}/{action}`        | 变体 `reject/withdraw/clear`；`reject` 仅草稿、`withdraw` 仅已有输出批次、`clear` 仅未清除；勾选确认 + `showModal` + ID/版本二次核验 + `confirm:true`；写后按 ID 回读               |

商品目录来源：H19 使用 H18 的 `POST /product-quality/preview` 读取当前主档（含 `product_id`、`source.row_id`、名称与参数），与 Web `ProductEditsView.vue` 一致；H19 契约本身不提供目录读取接口。

## 关键语义

- 金额与百分比始终是 Decimal 字符串（`max_margin_percent`、`advertising_daily_budget`、价格/成本仅展示，不做客户端浮点运算）。
- 时间展示统一 `supportTime(value, timezone)`：规则/计划用计划自身 `timezone`，授权/质量/修订回退当前店铺时区；持久化仍为 UTC。
- 写后一律按 ID 独立 `GET` 回读；`request_id` 在结果未知时保持不变（授权、计划创建、手动检查、质量保存、修订创建），确定性 4xx 允许修正后新建。
- 删除/清除/撤销/启停/审批/已读：`Taro.showModal` 确认 + 对象未变化（ID、版本、会话）二次核验后才提交。
- 页面生命周期：`useUnload` 置 `alive=false` 并 `epoch++`；切店/换账号清空数据、选中项与确认态；`useDidShow` 只读刷新；未保存草稿/待核对写入启用 `Taro.enableAlertBeforeUnload`。
- 状态未知一律失败关闭：未知状态不提供写入动作；网络未知保留恢复入口并阻断重复提交，直到刷新核对。

## 验证证据（2026-10-12，Node v24.16.0）

| 命令（工作目录 `apps/soloops_weapp`）                                           | 结果                                                                                                                                                                            |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run type-check`                                                            | 退出 0，全包通过（其间曾因他人 `pages/outbound`、`pages/profit` 半写入报错，对方修复后复跑通过）                                                                                |
| `npm test`                                                                      | 退出 0，124/124 通过（本包 33 项；并发开发中其他包测试数持续变动，某次运行曾因他人文件半写入失败，最终运行全绿）                                                                |
| `npm run build:weapp`                                                           | 退出 1：他人在写的 `pages/settlements/index.vue:45`（早前为 `pages/statements/index.vue:53`）报 “Element is missing end tag”，与本包无关；主协调者已注册本包四页                |
| 隔离验证：临时副本仅保留已提交页面 + 本包四页后 `npm run build:weapp`           | 退出 0，5.39s，产出 `dist/pages/rules/index.js` 28.89 kB、`schedules` 39.85 kB、`product-quality` 18.57 kB、`product-edits` 30.06 kB（临时副本位于 `%TEMP%`，不改仓库共享文件） |
| `git diff --check`（仓库根）                                                    | 无输出，退出 0                                                                                                                                                                  |
| `backend\.venv\Scripts\python.exe scripts\validate_ui_contract.py`              | 退出 0：PASS，21 features / 149 API references                                                                                                                                  |
| `backend\.venv\Scripts\python.exe -m unittest discover -s scripts\mobile\tests` | 退出 0，24 项 OK                                                                                                                                                                |

格式化：prettier 3.6.2 `--write --single-quote --no-semi`（本包 16 个源码/测试文件与 1 个文档；另检查无行尾空白、无 CRLF）。

## 未完成项与不确定点

- 需主协调者确认路由注册（已于本次验证时看到 `src/services/navigation.ts` + `src/app.config.ts` 已加入 `/rules`、`/schedules`、`/product-quality`、`/product-edits`）；仓库整体 `npm run build:weapp` 目前被他人在写的 `pages/settlements/index.vue` 模板解析错误阻塞，修好后需重建确认四页产物。
- 未执行微信开发者工具交互、数据库持久旅程与真实后端端到端；编译与单测通过不等于 IDE 或数据库验收。
- `npm run type-check` 曾被他人在写文件阻塞（`pages/outbound` 的 `PATCH`/`string | undefined`、`pages/profit` 的 `formEpoch`），对方修复后复跑退出 0；`npm run build:weapp` 仍被他人在写的 `pages/settlements/index.vue` 模板解析错误阻塞，本包四页以隔离副本构建（退出 0）作为编译证据。
- 周期记录没有按 ID 的 `GET`：`POST /schedules/history/{id}/read` 的响应即回读依据，已读后再以列表刷新复核；这是契约限制，不是遗漏。
- 规则写入（`POST /business-rules`）无 `request_id`，网络未知时无法用同标识回查，只能重新读取当前版本核对后再操作；页面已阻断重复提交并给出提示。
- 授权创建依赖已存在的 `daily` 待审批任务：页面通过 `GET /agent/runs/{id}` 做前置门禁，若任务在方案外被推进则以服务端 409 为准。
- `product-edits` 控制动作 `withdraw/clear` 依赖 `output_batch_id`；草稿阶段仅 `reject`/`clear` 可用，与服务端 `ConflictError` 一致，未做端到端验证。
