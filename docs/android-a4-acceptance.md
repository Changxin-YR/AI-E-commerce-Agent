# Android A4 验收记录

日期：2026-10-12，Asia/Shanghai。范围：Listing 与客服两条业务 MVP 的设备闭环，审批与任务生命周期的拒绝/取消/暂停/恢复/过期，以及客服与任务的未保存保护。74 SO、32 原验收与四条 MVP 继续按安卓计划逐包追踪。

**A4 完成（设备验收 9 项通过）。** 准确提交与 CI 见提交后补记；本页记录设备端与数据库实际结果。真实模型、邮件与平台写入保持关闭，模型仅 `listing-model-e2e-*` 与 `support-model-e2e-*` 前缀店铺使用 `backend/scripts/e2e_analysis.py` 的本地确定性替身。

## 环境

沿用 A3：API 34 AVD `emulator-5580`（Pixel 6，WHPX）、Compose MySQL 3311（schema `soloops_android_test`）、合成 FastAPI 8011（模型/邮件/调度关闭）。脚本复用 `frontend/scripts/android-device.mjs` 的连接、登录、导航、会话内 API 与 CSV 种子函数（A4 起把 `call`/`seedImport`/`createShop` 抽到该共享模块）。

## 设备验收：Listing 与客服 MVP（`frontend/scripts/check-android-listing-support.mjs`）

证据 `.local/android/evidence/device-a4-listing-support.json`，截图 `a4-listing-*.png`、`a4-support-*.png`。

| 检查 | 结果 |
|---|---|
| `listing-model-candidate-and-local-approval` | **通过**。店铺 #16 / 批次 #25；从 Listing 页选 A4-BOTTLE 进入 AI Listing 流程，商品事故事实区含「仅限冷水」，候选预览含「容量 500 ml」；批准节点前 `listings/versions` 为 `[]`，节点批准后到业务页勾选核对并「批准并在本地生效」→ 版本 **#7 `approved`**，页面显示「本地已批准」 |
| `listing-draft-rejection` | **通过**。同一商品再生成一份候选并批准节点成为新草稿，业务页「拒绝此版本」→ 版本 **#8 `rejected`**，页面显示「版本 2 · 已拒绝」，已生效版本 #7 保留 |
| `support-policy-expiry` | **通过（过期路径）**。店铺 #17 建两份政策：**#3 当前有效**（`valid_until` 2099）与 **#4 已过期**（`valid_until` 2026-02-01）；客服工作台政策区显示「安卓合成过期政策 · #2 / v1 · 已过期」与「安卓合成有效政策 · #1 / v1 · 当前有效」 |
| `support-model-draft-save-archive-and-dirty-navigation-blocked` | **通过**。批次 #26 提单条消息 A4-M1，AI 客服候选含「需要人工接管」「物流查询、退款 / 退货」，节点批准后生成草稿 #1；未保存正文时点击导航被客服页自身守卫拦住并提示「正文或人工记录尚未保存，请先保存或放弃修改，再离开当前草稿。」，URL 仍在 `/support` 且正文保留；随后「保存修改」→「人工编辑」→「存档处理记录」→ 草稿 **#2 `archived`** |

## 设备验收：审批与任务生命周期（`frontend/scripts/check-android-agent-lifecycle.mjs`）

证据 `.local/android/evidence/device-a4-agent-lifecycle.json`，截图 `a4-agent-*.png`、`a4-operations-dirty-protection.png`。店铺 #18 / 批次 #27（商品）+ 库存批次（同一脚本内）。

| 检查 | 结果 |
|---|---|
| `agent-approval-rejected` | **通过（拒绝）**。本地 Listing 模板任务停在待审批，点「拒绝当前节点」→ 执行 **#12** `rejected` |
| `agent-task-cancelled` | **通过（取消）**。另一任务在待审批时点「取消任务」→ 执行 **#13** `cancelled`，已完成 3 个步骤与历史保留 |
| `agent-pause-and-resume` | **通过（暂停/恢复）**。执行 **#14** 由设备内真实会话建立并停在 `ready`（页面「启动并运行」会一路执行到审批/结束，因此用会话内 API 留出可暂停状态）→ UI 点「暂停任务」→ `paused` → 出现恢复表单 →「确认预算并恢复」→ 恢复后重新推进到 `waiting_approval` |
| `task-recovery-after-restart` | **通过（恢复）**。强停并重启应用后，从执行记录重新载入 **#14**，步骤与操作记录完整、「批准当前节点」可用；批准后执行 **#14** `succeeded` |
| `operations-dirty-note-protection` | **通过（任务业务保护）**。今日运营检查产生候选，打开待办审批详情填入「未保存的核查记录」后，页面显示「有未保存的处理记录，请先保存后切换或刷新。」且「运行今日运营」被禁用；「批准并创建待办」后提示消失，库内 `operation_tasks` 备注为该文本 |

## 回归与本地检查

- 共享辅助函数重构后重跑 A3 脚本 `check-android-mvps.mjs`：3 项全通过（店铺 #19、批次 #29/30/31、今日运营 run #5、经营问数执行 #15），A3 证据未受影响。
- `eslint` exit 0；42 文件 **194 项单元**通过（`--maxWorkers=2`）。本轮未改应用代码，只新增/重构设备脚本与文档。

## 边界与未覆盖

- **过期**以客服政策有效期验证（页面状态与 AI 客服流程依据）；客服政策 `availability=expired` 为服务端计算，非前端推断。
- 执行记录自身没有“过期”状态：`agent_executions.valid_until` 用于来源有效期提示，不是审批门禁，故未把它当作过期验收。
- 任务侧“请求处理中禁止离页”由 Vue Router 守卫实现，本地替身下请求在毫秒级完成、无法稳定复现；该项由单元测试覆盖，设备侧以运营事项未保存保护与客服未保存正文两条确定性路径验收。
- 客服页对站内导航使用自身守卫文案（不弹壳层确认框）；壳层确认框由经营资料/新增店铺表单路径在 A2 验收。
- 复现：先按 `docs/android-local-testing.md` 启停环境，再在副本根目录依次执行 `node frontend/scripts/check-android-listing-support.mjs` 与 `node frontend/scripts/check-android-agent-lifecycle.mjs`；两脚本只操作专属合成 AVD 与合成库，不与 `check-android-imports.mjs`、`check-android-mvps.mjs` 并发运行。
