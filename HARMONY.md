# SoloOps 手机三端 · 跨账号接续记忆

## 最新接续检查点（2026-10-11 23:45，M0-C）

- **当前业务分支：`feat/soloops-mobile-m0c`**，自 m0b 尖端 `40db69e` 分出；首个提交 `029b53b4e91891e71ee821fea89d7bc547b8fda1`（修 m0b 尖端 CI 红灯 I001 + 把 m0c 加入移动 CI 触发分支）。
- **警告：m0b 尖端 `40db69e73a2a37660fbd4b7f90e109f5e195a9e1` 的 CI 是 failure**（run 38151032924，`scripts/mobile/tests/test_business_fixture.py:11` 触发 `I001`）。被它 revert 掉的 `abf1680` 才是 CI success。不要在 m0b 尖端上继续。
- 实际 workdir 不变：`C:/Users/27363/Desktop/AIEcommerceAgent/.local/worktrees/mobile-m0a`（worktree 内分支已切到 m0c）。仓库 `Changxin-YR/AI-E-commerce-Agent`。
- 先读：[完整接续交接](https://github.com/Changxin-YR/AI-E-commerce-Agent/blob/feat/soloops-mobile-m0c/docs/mobile/harmony-handoff.md) 与 `docs/mobile/harmony-implementation-progress.md` 顶部 M0-C 段。

## 本机环境（M0-C 已恢复，可直接复用）

- Docker：容器 `soloops-harmony-r2-mysql`（mysql:8.4，`/var/lib/mysql` 为 tmpfs，宿主 127.0.0.1:3315）。Docker Desktop 不运行会丢库，需重启容器后用 `.local/mobile-business/harmony-account-switch.sql`（424,238 B，SHA256 `e67ce2a4…7f82`）恢复；恢复后应为 67 表、head `b42e83f516c0`、批次 1181–1187 共 7 条。凭据仅在本机忽略文件 `.local/mobile-business/mysql.env`、`test.env`，不得输出或提交。
- 合成 API：`python.exe .local/mobile-business/resume_api_18081.py`（内部 `business_fixture.build_app()`，监听 127.0.0.1:18081，不调用 prepare_samples）。18080 属于其他项目 nx-keycloak，勿占用。设备端仍访问 `http://127.0.0.1:18080`，靠 `hdc rport tcp:18080 tcp:18081` 映射。
- 鸿蒙模拟器：`"C:/Program Files/Huawei/DevEco Studio/tools/emulator/Emulator.exe" -start 22`（HarmonyOS 6.0.2 / API22 / RAM 2048，实例目录 `%LOCALAPPDATA%/Huawei/Emulator/deployed/22`）；HDC `C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe`，target `127.0.0.1:5555`。
- 固定 HAP：`.local/mobile-business/accepted-scope-fix.hap`，103,689,862 B，SHA256 `3148726747764db13eb18de7e71885b69253f3b59274998fe4367bb0ab85ec0e`（SDK24 编译 / API22 运行），覆盖安装通过、无需重建。
- 安卓：adb 只在 `C:/Users/27363/Desktop/max/android-sdk/platform-tools/adb.exe`（`%LOCALAPPDATA%/Android/Sdk/platform-tools` 里没有 adb.exe）；emulator 在 `%LOCALAPPDATA%/Android/Sdk/emulator/emulator.exe`；可用 AVD `KnowFlow_API34`（Android14/API34）。单模拟器约定：跑安卓前先停鸿蒙，反之亦然。
- 微信开发者工具：`D:/微信开发工具/微信web开发者工具/微信开发者工具.exe`（v2.01.2510290），工程 `apps/soloops_weapp`，CLI `cli.bat`；`project.config.json`、`project.private.config.json`、`ohos/build-profile.json5` 为本机配置，不提交、不覆盖。

## 进度与下一步

- 鸿蒙 R2：H01–H21 源码全覆盖；已端测 H01–H08、H11，以及 **H12 的费用修订 v1→v2(2.5678) 与订单行关联 v3（SYN-G1/SYN-CUP·批次1187源行2）**。仍待端测：H12 映射规则、H13 账单、H14 订单核对、H15 回款、H09/H10、H16–H20、H21 边界（横屏/大字体/深浅色/离开恢复/冲突/未知结果）。
- 微信小程序：业务端第一波（core/登录/首页/待办/导入/AI/Listing/客服/库存）在本分支实施中；此前只有 M0 壳（2 页面、7/7 原生 UI 检查）。资质、类目、真实 AppID 后台材料仍 BLOCKED，不注册/不备案/不发布。
- 安卓：M0 技术验收已完成（26 项断言 + 16 项基础运行 PASS，APK `1483dba9…c8b71`）；共享 Dart 业务层已随鸿蒙实现，业务端测未做。
- 端测操作要点：费用页默认"数据身份"是 `user_import`；1138 属 `synthetic`，需切到"合成测试数据"再查询。UI 文本输入后必须回读字段值（曾出现浮点回显尾差）。`scripts/mobile/ohos_ui.py` 的 `dump` 保存布局+截图到 `.local/mobile-business/device/`；中文参数可用 `hdc shell "uitest uiInput click x y"` 直接按坐标操作。

## 保护与约定

- 未提交、禁止覆盖的两项本机配置：`apps/soloops_flutter/ohos/build-profile.json5`、`apps/soloops_weapp/project.config.json`。
- `pytest backend/tests` 会清表，**不得针对保留验收库运行**；端测与清表测试串行。
- 真实模型、真实邮件、真实平台写入均为 0，只使用本地合成/替身。
- 每包完成后提交推送并核对**准确 SHA 的 CI 成功**再继续（m0c 分支触发 `Verify mobile engineering`）。
- 上下文接近上限时：先把进度/证据落盘、提交推送、更新本文件（在该 checkout 只用 `git commit --only HARMONY.md`，因为 README.md 有用户本机改动），再创建接续聊天并给出精确 SHA 与上述入口。
