# SoloOps 手机三端 · 跨账号接续记忆

## 最新接续检查点（2026-10-11 深夜，M0-C 第二轮）

- **当前业务分支：`feat/soloops-mobile-m0c`**（自 m0b 尖端分出）。本分支已推送的提交：
  - `029b53b4e91891e71ee821fea89d7bc547b8fda1` 修 m0b 尖端 CI 红灯（`scripts/mobile/tests/test_business_fixture.py` 导入顺序 `I001`）+ 把 m0c 加入移动 CI 触发分支。**该 SHA 的 CI 已核实 success**（run 38152019827）。
  - `374a7de` / `e67bf35` / `e385cb3` / `0f12ea9`：鸿蒙进度与验证记录、微信业务端第一波（38 文件）。
  - **警告：不要在 m0b 尖端 `40db69e` 上继续**，其 CI 是 failure。
- 实际 workdir 不变：`C:/Users/27363/Desktop/AIEcommerceAgent/.local/worktrees/mobile-m0a`（worktree 内已切到 m0c）。仓库 `Changxin-YR/AI-E-commerce-Agent`。
- 先读：`docs/mobile/harmony-handoff.md` 顶部 M0-C 段、`docs/mobile/harmony-implementation-progress.md` 顶部 M0-C 段、`docs/mobile/weapp-implementation.md`。
- **未核对项**：GitHub 匿名 API 在本次会话后段返回 403（限流），`374a7de`/`e67bf35`/`e385cb3`/`0f12ea9` 的 CI 结论未逐一确认；限流恢复后用 `https://api.github.com/repos/Changxin-YR/AI-E-commerce-Agent/actions/runs?branch=feat/soloops-mobile-m0c` 复核。

## 本机环境（已恢复，可直接复用）

- Docker：容器 `soloops-harmony-r2-mysql`（mysql:8.4，`/var/lib/mysql` 为 tmpfs，宿主 127.0.0.1:3315）。Docker Desktop 不运行会丢库；重启容器后用 `.local/mobile-business/harmony-account-switch.sql`（424,238 B）恢复，恢复后应为 67 表、head `b42e83f516c0`、批次 1181–1187。凭据只在忽略文件 `.local/mobile-business/mysql.env`、`test.env`，不得输出或提交。恢复命令要点：`docker exec -e MYSQL_PWD=<pwd> -i soloops-harmony-r2-mysql mysql --user=soloops <db> < dump.sql`（用 `cmd /c` 重定向，PowerShell 管道会破坏内容）。
- 合成 API：`backend/.venv/Scripts/python.exe -u .local/mobile-business/resume_api_18081.py`（内部 `business_fixture.build_app()`，监听 127.0.0.1:18081，**不调用 prepare_samples**，保留样本日期）。18080 属其他项目 nx-keycloak，勿占用；设备端仍访问 `http://127.0.0.1:18080`，靠 `hdc rport tcp:18080 tcp:18081` 映射。
- 鸿蒙模拟器：`"C:/Program Files/Huawei/DevEco Studio/tools/emulator/Emulator.exe" -start 22`（HarmonyOS 6.0.2 / API22 / RAM 2048）；HDC `.../sdk/default/openharmony/toolchains/hdc.exe`，target `127.0.0.1:5555`。停止用 `Emulator.exe -stop 22`。
- 固定 HAP：`.local/mobile-business/accepted-scope-fix.hap`，103,689,862 B，SHA256 `3148726747764db13eb18de7e71885b69253f3b59274998fe4367bb0ab85ec0e`；覆盖安装通过，无需重建。
- 安卓：adb 只在 `C:/Users/27363/Desktop/max/android-sdk/platform-tools/adb.exe`（`%LOCALAPPDATA%/Android/Sdk/platform-tools` 无 adb.exe）；emulator 在 `%LOCALAPPDATA%/Android/Sdk/emulator/`；AVD `KnowFlow_API34`（Android14/API34）可用。单模拟器约定：跑安卓先停鸿蒙，反之亦然。
- 微信开发者工具：`D:/微信开发工具/微信web开发者工具/微信开发者工具.exe`（v2.01.2510290），工程 `apps/soloops_weapp`，CLI `cli.bat`；`project.config.json`、`project.private.config.json`、`ohos/build-profile.json5` 为本机配置，不提交、不覆盖。

## 本轮已验证（设备 + 数据库回读）

| 项 | 结果 |
|---|---|
| 环境恢复 | 库 67 表/head `b42e83f516c0`/批次 1181–1187；固定 HAP 覆盖安装；会话与店铺 918 恢复 |
| H12 费用修订 | 费用 1138 v1(2.3456) → v2(2.5678)，发生时间保持 12:00+08:00→04:00 UTC，v1 历史保留 |
| H12 订单关联 | v3 `allocation=order_line`，订单行 `SYN-G1/1·SYN-CUP`，来源批次 #1187 源行 2 |
| H12 映射规则 | 规则 **#310**（`SyntheticShipping → 物流`）预览影响账单行 #8280 后保存 v1 |
| H12 费用新建 | 人工费用 **#1139**（user_import/generic，2.3456 USD，凭据 `SYN-EXP-20261011-01`，类别物流） |
| H13 账单 | 批次 **#1188** 导入 5 行（sale/fee/fee/payout/refund）；按类型合计正确；**凭据一致、差额 0.0000**；未匹配项保持"仅账单有记录·无法确定"；跨身份按作用域隔离 |
| H15 回款 | 原账单 `SYN-ST-001` + `BANK-SYN-001/PAY-SYN-001` 100.0000 USD → **逐笔一致、差额 0.0000**，保存后 `settlements/settlement_receipts/settlement_revisions` 各 1 |
| H14 订单核对 | 匹配可运行；当前 user_import/generic 作用域订单行为 0，结果保持"待核实·差异未知"（**未完成**） |

证据目录 `.local/mobile-business/device/`：`expense-revision-linkage-v3.json`、`statements-and-mapping-rule.json`、`statement-review-and-match.json`、`settlement-receipt-verification.json`。

## 仍待端测

H12 映射规则撤销/清除 → H13 审阅结论预览/保存/版本/清除 → H14 结论保存与"有差异"路径（需先在 user_import 作用域导入订单行）→ H15 撤销/清除 → **H09 分析、H10 总览、H16 规则授权、H17 定时通知、H18 商品质量、H19 本地修订、H20 测试外发** → **H21 边界**（横屏/大字体/深浅色/离开恢复/冲突/未知结果）→ 完整卖家旅程与用户联调。

微信端：第一波 9 页已提交（type-check/build 通过，**未做运行时联调**）；第二波 12 个页面正在实施（`analytics/overview/profit/expenses/statements/settlements/rules/outbound/schedules/product_quality/product_edits` + mine 扩展）。真机需配置合法域名；automator 通道 M0 阶段即 60s 超时（exit 124）。

安卓端：M0 技术验收已完成（26 断言 + 16 基础运行，APK `1483dba9…c8b71`）；共享 Dart 业务层已随鸿蒙实现，业务端测未做。

## 端上操作要点（避免重复踩坑）

- 费用页默认"数据身份"是 `user_import`；费用 1138 属 `synthetic`，必须切换后才可见。
- `uitest uiInput text` **只接受单个无空格参数**；多词请用连字符。中文参数可用（`ohos_ui.py` 的 `dump` 标签用 ASCII）。
- 表单必填项（如"映射依据""结算说明"）留空时，预览按钮不会提交且界面看似无反应。
- 键盘开合会改变布局坐标；每次输入后先 `hide-ime` 再重新 `dump` 取坐标。`ohos_ui.py` 的 `@input:N` 可稳定定位第 N 个 TextInput。
- `pytest backend/tests` 会清表，**禁止对保留验收库运行**；端测与清表测试串行。
- 真实模型、真实邮件、真实平台写入保持 0，只使用本地合成/替身。

## 交接约定

上下文接近上限时：先把进度/证据落盘、提交推送、更新本文件（在该 checkout 只用 `git commit --only HARMONY.md`，README.md 有用户本机改动），再创建接续聊天并给出精确 SHA 与上述入口。子代理成果必须由主代理独立验证（type-check/构建/数据库回读）后再提交。
