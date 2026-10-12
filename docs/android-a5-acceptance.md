# Android A5 验收记录

日期：2026-10-12，Asia/Shanghai。范围：其余已有业务模块在设备上的逐项真实结果，以及多尺寸、方向与系统字号的适配回归。74 SO、32 原验收与四条 MVP 继续按安卓计划逐包追踪。

**A5 完成（设备验收 20 个模块项 + 41 项适配检查通过）。** 准确提交与 CI 见提交后补记。真实模型、邮件与平台写入保持关闭；本轮未改应用代码，全部为设备脚本与文档。

## 环境

沿用 A3/A4：API 34 AVD `emulator-5580`（Pixel 6，WHPX）、Compose MySQL 3311（schema `soloops_android_test`）、合成 FastAPI 8011。适配回归通过 `wm size` / `wm density` / `settings put system font_scale` 与 `user_rotation` 临时改变显示与字号，结束后恢复原值。

## 模块逐项结果（`frontend/scripts/check-android-modules.mjs`）

证据 `.local/android/evidence/device-a5-modules.json`，截图 `a5-*.png`，日志 `a5-modules-run11.log`。加载合成店铺 #30（批次 72 商品 / 73 订单 / 74 库存 / 75 消息），每个入口选店并切到合成身份后记录真实页面结果；每项同时断言无横向溢出（412 CSS px 视口下 `scrollWidth == innerWidth`）。

| 模块 | 路径 | 设备结果 |
|---|---|---|
| 工作台 | `/` | 今日运营收件箱与经营事项渲染 |
| 数据导入 | `/imports` | 批次列表显示 `a5-products.csv` |
| 任务执行台 | `/agent` | 「启动任务」区与执行记录渲染 |
| Listing 审批 | `/listings` | 商品列表显示 `A5-SKU` |
| Listing 本地模板 | `/listings` | 点「从商品事实生成草稿」生成版本，`listings/versions` 由 0 → 1 |
| 库存快照 | `/inventory` | 快照列表显示 `A5-SKU`（合成身份 + 24 小时时效） |
| 新品利润 | `/profit` | 填试算名称/售价 20/采购 18/依据后计算并比较 → 利润情景结果区出现 |
| 商品质量 | `/product-quality` | 点「检查商品信息」→ 商品质量检查结果区出现 |
| 商品修订 | `/product-edits` | 「此店暂无修订记录。」空状态正确 |
| 客服工作台 | `/support` | 消息列表显示 `A5-M1` |
| 订单销售与退款核对 | `/order-reconciliation` | 点「读取销售与退款待核清单」→ 订单金额待核清单区出现 |
| 经营分析 | `/analytics` | 点「计算并查看证据」→ 分析结果区给出净销售额 `60.0000`（3 × 20 USD） |
| 经营总览 | `/overview` | 点「生成经营总览」→ 结果含「净销售额」与覆盖说明 |
| 实际费用 | `/expenses` | 「暂无已加载记录。」（无费用来源时不补零） |
| 账单核对 | `/statements` | 「读取并核对」入口可用（本店未导入账单，保持待核对状态） |
| 结算与回款 | `/settlements` | 结算登记区渲染 |
| 经营资料 | `/settings` | 店铺列表包含本轮合成店铺 |
| 经营规则 | `/rules` | 规则范围区渲染（默认 24 小时 / 1 件 / 20%） |
| 测试外发 | `/outbound` | 「尚未配置此店铺的外发通道」（真实外发关闭） |
| 定时与通知 | `/schedules` | 「还没有定时计划。」空状态正确 |

模块脚本额外记录：`module-scope-summary`（店铺数 30、模块 20）与每项视口几何。

## 适配回归（`frontend/scripts/check-android-adaptation.mjs`）

证据 `.local/android/evidence/device-a5-adaptation.json`，截图 `a5-small-phone.png`、`a5-tablet.png`、`a5-landscape.png`、`a5-large-font.png`、`a5-default-dashboard.png`。对 8 个代表入口（工作台、数据导入、任务执行台、Listing、客服、经营分析、经营资料、定时与通知）在 5 种配置下逐一断言标题可见、工具栏可见且无横向溢出：

| 配置 | 视口（CSS px） | 结果 |
|---|---|---|
| 默认 1080×2400 @420 | 412 × 842 | 8/8 通过 |
| 小屏 720×1280 @320 | 360 × 582 | 8/8 通过 |
| 平板 1600×2560 @240 | 1067 × 1556 | 8/8 通过 |
| 横屏（默认尺寸，rotation=1） | 866 × 364 | 8/8 通过；路由与滚动位置保持 |
| 系统字号 1.3 倍 | 412 × 842 | 8/8 通过；标题字号 23px → **29.9px**，证明 WebView 跟随系统字号且布局无溢出 |

`adapt:font-scale-effect` 记录 `webview_follows_system_font_scale: true`。测试结束后 `wm size`、`wm density`、`font_scale`、`user_rotation` 恢复原值（脚本 finally 分支执行，原有保存值已回写）。

## 边界与未覆盖

- **真机未覆盖**：本机没有可用 Android 真机，以上均为 API 34 模拟器（可改逻辑尺寸/密度/字号/旋转）。真机的厂商 ROM、刘海/挖孔、手势导航与真实网络仍需在拿到设备后补齐。
- 适配回归只覆盖 8 个代表入口（A2 的 29 组壳检查与 A5 模块脚本已在其默认配置下覆盖全部 19 个入口）；其他 API 级别（33/35）未测。
- 账单、结算、费用、商品修订等模块在本轮合成店铺下没有对应来源数据，验收记录的是「页面可用 + 空状态/入口正确」，不声称这些模块的业务闭环已完成；其网页/服务端验收保留在既有 R2 记录中。
- 复现：先按 `docs/android-local-testing.md` 启停环境，再依次执行 `node frontend/scripts/check-android-modules.mjs` 与 `node frontend/scripts/check-android-adaptation.mjs`；两脚本依次运行，不与其它设备脚本并发。
