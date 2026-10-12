# Android A3 验收记录

日期：2026-10-12，Asia/Shanghai。范围：原生文件选择、真实字节上传、CSV 分片与来源回读，以及今日运营、经营问数两条业务 MVP 的设备闭环。74 SO、32 原验收与四条 MVP 继续按安卓计划逐包追踪。

**A3 完成（设备验收 7 项通过）。** 准确提交 `eaed69ce3a517b3a8702bbd236e611597d69d809` 的 [CI 38191429012](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38191429012) 全部成功（3m3s：lint、194 项单元、类型检查、原生资源构建/同步、Gradle `assembleDebug`、release 资源门禁）。本页记录设备端与数据库实际结果。真实模型、邮件与平台写入保持关闭，仅使用合成数据与本地确定性替身。

## 交付与环境

- AVD `emulator-5580`（`SoloOps_A1`，Pixel 6 / Android 14 API 34 / x86_64 / WHPX，无窗口模式）。
- 独立 Compose project `soloops-android-a1`，MySQL 8.4 于 `127.0.0.1:3311`，schema `soloops_android_test`。
- 合成 FastAPI 于 `127.0.0.1:8011`（`scripts/start_android_backend.py`，模型/邮件/调度显式关闭），APK 内 origin 为 `http://10.0.2.2:8011`。
- 本轮重建并安装的 debug APK SHA256：`A1931F93F817DE710CC6CD51925741D4C340D72B3F65B9E58BADAB45B813E91D`。发行与签名仍归 A6。
- 本地检查：`eslint` exit 0；42 文件 **194 项单元**通过；`android:sync:local`（含 `vue-tsc --build` 与 android 模式构建）exit 0；Gradle `assembleDebug` BUILD SUCCESSFUL。

## 设备验收：导入链路（`frontend/scripts/check-android-imports.mjs`）

证据 `.local/android/evidence/device-imports.json`、截图 `a3-*.png`、日志 `a3-imports-run2.log`。

| 检查 | 结果 |
|---|---|
| `shop-unsaved-protection-and-saved-navigation` | **通过**。新增店铺（#6）未保存时切页出现「离开当前编辑？」→「继续编辑」保留输入 →「确认添加」保存 → 进入导入页无离页弹窗 |
| `native-csv-byte-upload-and-source-readback` | **通过**。系统文件选择器选取 UTF-8 中文 CSV（含引号、逗号、换行），真实字节上传 → 批次 **#5** `committed`，库内 `raw.name=安卓合成商品`、`raw.facts` 含逗号与换行原样回读；文件 SHA256 `bbad5bfac0ea476a38e87ea8315bf004a95c1f6c95c3e03e619c7da30f6fee2d` |
| `native-worker-split-and-first-part` | **通过**。111,031 B / 2001 行订单报表经本机 Worker 拆为 2 片并建导入组 **#1**，清单指纹与源文件一致，第 1 片提交成功 |
| `force-stop-resume-fingerprint-dedup-and-sales` | **通过**。强停重启后按原组继续；改文件后选择器提示「原文件与当前组的文件名、指纹或分片清单不一致。」；换回原文件提交第 2 片 → 覆盖「分片全部完成」与「去重后 2000；跨片重叠 1」；再次打开第 1 片不产生新批次；经营分析销售额 **4000.0000**（2000 行 × 1 × 2 USD） |

数据库回读：`import_groups` #1（shop 6，orders，`active`/`complete=1`/version 5）；`import_batches` #6 `part-001.csv`（2000 行，新增 2000）、#7 `part-002.csv`（1 行，新增 0，即跨片重叠行）、#5 `soloops-a3-products.csv`（1 行）。

## 设备验收：两条 MVP（`frontend/scripts/check-android-mvps.mjs`）

证据 `.local/android/evidence/device-mvps.json`、截图 `mvp-*.png`、日志 `a3-mvps-run4.log`。合成店铺 **#10**（code `question-e2e-android-*`，该前缀接入本地确定性模型替身），三个来源批次 #17 商品 / #18 订单 / #19 库存均由设备内真实会话 + CSRF 写入。

| 检查 | 结果 |
|---|---|
| `seed-scoped-sources` | **通过**。批次 #17/#18/#19 落库；店铺列表在页内刷新后可见 |
| `today-operations-candidate-and-task` | **通过**。设备内点「运行今日运营」得检查 **#3**（来源有效，来源版本 3）：商品事实已检查 1 个、订单履约部分可核对 1 行、库存阈值已检查 1 个快照、已知毛利命中 1 个 SKU；**新增候选 2**（`low_inventory` 与 `low_margin`）。核对库存候选 → 填处理备注「安卓合成核对记录」→「批准并创建待办」→ 页内「事项 #5 · 待处理」；库内 `operation_tasks` #5 `low_inventory` `open` v2（`note` 已保存），低毛利候选 #6 仍 `pending_approval` 未被误改 |
| `business-question-evidence-and-approval` | **通过**。`/agent` 选「AI 经营问数」后页面显示「模型已配置：synthetic-evidence-model」；填受控问题、时间窗 2026-10-07→10-08 UTC、预算 0.03 USD、勾选两项数据许可 →「启动并运行」→ 执行 **#1** 进入「等待审批」；解释区给出可核对依据：净销售额 **60.0000 USD**、估算采购成本 **54.0000 USD**、已知商品毛利 **6.0000 USD**、毛利率 **10.00%**、命中 1 个 SKU，并明确「费用尚未完整归集」「未知截至时间不能推断」；批准当前节点后出现「到业务页面复查」链接。库内 `agent_executions` #1：`template=question`、`status=succeeded`、`next_node=end`、`source_status=current`、`source_revision=3`、`steps_used=5`、`spent_usd=0.002000`、`reserved_usd=0`、**`model_status=test_double`**（本地替身，非供应商调用） |

## 本轮发现并修复的安卓缺陷：原生选择器置灰 CSV

- **现象**：A3 首轮与原交接记录中，「选择原始大报表 CSV（本机拆分／恢复）」在系统文件选择器中点选无反应，等待「本机文件已就绪：2001个源记录」超时（复现两次）。小文件入口（`accept=".csv,.xlsx"`）同轮可用。
- **根因**：该输入为 `accept=".csv"`，WebView 将单扩展名映射为宿主意图 `typ=text/csv`；而 Android MediaProvider 为 `.csv` 记录的类型是 `text/comma-separated-values`，DocumentsUI 因此把文件节点标记为不可选。`adb shell dumpsys activity activities` 显示 `Intent { act=GET_CONTENT ... typ=text/csv }`；`uiautomator dump` 显示两张文件卡均 `enabled="false"`；`content query --uri content://media/external/file` 显示 `mime_type=text/comma-separated-values`。小文件入口因多类型回落为 `typ=*/*` 才恰好可用。
- **修复**：`frontend/src/components/BrowserImportSource.vue`（大报表入口）与 `frontend/src/components/ImportGroups.vue`（原分片入口）改为 `accept=".csv,text/csv,text/comma-separated-values"`；新增 2 项单元断言该属性（`BrowserImportSource.spec.ts`、`ImportGroups.spec.ts`），单元总数 192 → 194。
- **设备复验**：重跑导入脚本，四项检查全部通过；复验探针显示应用侧意图变为 `typ=*/*` + `EXTRA_MIME_TYPES`，两张 CSV 卡 `enabled=true,true`，2001 行文件成功进入本机拆分。

## 环境观察（非本包功能改动）

模拟器两张网络（Wi-Fi/移动）在选择关闭门户探测前均为 `PARTIAL_CONNECTIVITY`，`@capacitor/network` 要求 `NET_CAPABILITY_VALIDATED`，因此壳层显示「网络已断开」而同一时刻 8011 的真实请求全部成功（后端访问日志可对照）。本轮以模拟器设置 `settings put global captive_portal_mode 0`、`captive_portal_detection_enabled 0` 关闭门户探测使网络通过校验，应用代码未改。该语义（无法校验的网络是否应显示为离线）建议在 A5 与其他设备适配一并复核。

## 未覆盖与下一包

- `ImportGroups` 的「选择原分片 CSV」入口本轮仅单元验证属性，未在设备上单独走选择器；A4 的客服/任务业务保护、A5 的其他 API/尺寸/真机、A6 的签名与发行构建继续按计划。
- 浏览器模型 E2E 本轮仍未启动（终端未加载 `_test` 数据库环境）；设备证据是本包的验收依据。
- 复现：先 `docs/android-local-testing.md` 启停环境，再在副本根目录执行 `node frontend/scripts/check-android-imports.mjs` 与 `node frontend/scripts/check-android-mvps.mjs`；两脚本只对专属合成 AVD 与合成库操作。
