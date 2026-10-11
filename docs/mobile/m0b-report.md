# SoloOps R2 · M0-B 模拟器验证

2026-10-11。**本轮 M0-B 最小工程模拟器验收 PASS**，按 Android → 鸿蒙 → 微信小程序顺序完成。覆盖启动、导航、生命周期与下表中的合成系统能力；兼容性范围以逐项结果为准。用户明确全部使用模拟器，小程序资质暂缓。真机、生产业务及未集成插件不在本次通过结论内。停止于 M0-B，后续阶段等待新指令。

## 范围、基线与环境

- 工作分支 `feat/soloops-mobile-m0b`，起点 `838d54f14a7cc28d064e2f51937c65df1ee9f2d1`。起点 CI [38113968993](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38113968993) 成功；本轮提交的准确 SHA 与 CI 见交付消息。
- 复用 `.local/worktrees/mobile-m0a` 已导入 IDE 的独立工作区。原 main 为 `0a49a37dcd7f1ccf0acc2c0a225bfdc8d8bee686`；主工作区的未提交资料保持。
- 用户本地 `apps/soloops_weapp/project.config.json` 与 IDE 产生的 `apps/soloops_flutter/ohos/build-profile.json5` 变更保留，不纳入本轮提交。
- Windows 11 x64；Flutter OH tag `3.27.5-ohos-1.0.7` / SHA `6e545c2ce6ec9e303868dece5012d1d928890b57`，宿主 Dart 3.6.2。Android 端实际 `Platform.version` 显示引擎 Dart 3.6.1，两项分别记录。
- Android：Temurin17、SDK35、Gradle8.3、AGP8.1.0；运行于 `KnowFlow_API34` / Android14 / x86_64 / 1080×2400，串号 `emulator-5580`。以 read-only/no-snapshot 模式打开现有 AVD。
- 鸿蒙：DevEco6.1.1.290 / SDK24 6.1.1.125 / Hvigor6.24.3；运行目标为实际 API22 x86_64 模拟器，HDC `127.0.0.1:5555`。本次 HAP 包中实测 `libs/x86_64/libflutter.so`，与 M0-A arm64 包分开。
- 小程序：Taro4.3.0、Vue3.5.43、TypeScript5.9.3、Vite4.5.14、Node24.16.0；已打开开发者工具2.01.2510290、基础库3.17.4。

## 分端结果

| 验证项 | Android | 鸿蒙 | 微信小程序 |
|---|---|---|---|
| 本轮目标构建 | PASS | PASS（未签名 x64 HAP） | PASS |
| 模拟器启动显示 M0-B 页面 | PASS | PASS | PASS |
| 页面导航、返回 | PASS（含系统返回） | PASS（含系统返回） | PASS（页面按钮返回） |
| 前后台切换 | PASS | PASS | PASS（模拟器退出→场景1001恢复） |
| 浅色 / 深色模式 | PASS | NOT_TESTED（仅浅色实测） | NOT_TESTED（仅浅色实测） |
| 横屏与 1.3 倍字体 | PASS | NOT_TESTED | NOT_TESTED |
| 沙箱合成文件写入、读取、删除 | PASS | PASS | PASS |
| 合成剪贴板往返 | PASS | PASS（用户授权后） | PASS |
| 本地非敏感缓存 set/get/remove | NOT_TESTED | NOT_TESTED | PASS |
| HTTPS、证书拒绝、连接失败后恢复 | PASS | PASS | NOT_TESTED |
| 原后端健康接口 200、匿名会话 401 | PASS | PASS | NOT_TESTED |
| 合成 Cookie / Bearer 头传输 | PASS | PASS | NOT_TESTED |
| 官方 automator 脚本通道 | NOT_TESTED | NOT_TESTED | BLOCKED（60秒超时，exit124） |
| 真机、折叠屏、平板、分屏 / 悬浮窗 | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| 真实登录、审批、上传业务状态一致性 | NOT_TESTED | NOT_TESTED | NOT_TESTED |

- Android 共16项运行记录 PASS：`20261011T053605Z-android-runtime`。
- 鸿蒙当前进程10项记录 PASS：`20261011T061237Z-ohos-runtime`，含7项合成诊断及导航、生命周期、未捕获异常检查。原生截图和当前 PID 的 Hilog 同时归档。
- 微信7项原生 UI 观察 PASS，含3项合成诊断；390×753 视口、刘海安全区、按钮可见性实际观察。截图和提取的可访问性文本见 [UI证据](m0b-ui-evidence.json)。DevTools 的 iPhone 外观预设不等于 iPhone 真机运行。
- Flutter analyze PASS；2项 widget 测试 PASS，含小横屏、2倍字体、深色模式宿主布局回归。静态 UI 契约21功能/149 API引用 PASS；工具和契约17项测试 PASS；Python lint/format PASS。静态检查和宿主测试分别记录，不替代设备测试。

## 已实现的修正与诊断边界

共享 Dart 增加系统深色主题、可滚动环境页和显式触发的合成诊断。Android/OHOS 共用相同 `lib/`，OHOS 仅增加前台剪贴板权限声明及原因说明。小程序增设独立诊断页用于缓存、沙箱文件、剪贴板和页面生命周期检查。

`runtime_fixture.py` 是本机测试夹具，仅监听127.0.0.1:18443；复用原 FastAPI 健康和匿名会话处理器。禁止所有数据库连接、所有写方法和其他业务路由，拒绝把 Cookie/Bearer 送入原身份接口，禁用调度、模型及外发。`/_m0b/echo` 仅返回合成头匹配的两个布尔值，不实现 Bearer 身份认证。私钥与原始日志留在 Git 忽略的 `.local/mobile-m0b`。测试包只在 debug 下信任本次 loopback 证书，同时实际验证默认信任链会拒绝此证书。

### 实际问题与处理

1. OHOS 剪贴板：固定 HAR 读取接口要求 READ_PASTEBOARD。已按[官方声明要求](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/declare-permissions)补齐权限、reason 与 usedScene。用户在系统框选择本次允许后重跑，7项诊断全部 PASS。等待授权的12秒超时记录保留；后续重启出现权限框时仍需用户处理。
2. OHOS 启动：重启后出现 `ReferenceError: cannot find record ... @ohos/flutter_ohos/index`。当时磁盘 HAP 为135697882字节，与此前验收包不同。执行 `hvigorw.bat clean --no-daemon` 后按固定 x64 参数完整构建、安装，最终包95335396字节，启动和后台恢复均 PASS。证据支持构建缓存/产物状态相关性，未把单一内部原因认定为已证实。另保留早期安装后窗口异常日志。复现时避免 IDE 与命令行同时构建同一输出目录。
3. 微信热重载：Taro 生成 dist 期间出现短暂缺少 app.json/JS 文件错误；完整构建结束后点击“编译”，M0-B 页面加载，最后控制台 Errors:0。官方 automator 通道仍60秒超时，因此脚本通道 BLOCKED，界面验收独立记录 PASS。
4. 微信工具警告：灰度基础库3.17.4、SharedArrayBuffer 弃用提示、windowInfoChanged 监听器计数、worker reportRealtimeAction 不支持。已保留观察；内存泄漏与长期稳定性 NOT_TESTED，后续用稳定基础库和长时测试判断。

5. CI 导入排序：首次远端检查因工作目录不同，将本地 `app` 模块分类不同而报 I001。新增 mobile 专用 Ruff 配置继承后端规则，显式声明 `app` 为 first-party，并统一本地与 CI 命令；原后端配置保持。

## 复现命令

以下在 worktree 根执行。先将锁定 Flutter OH、JDK17、Android SDK35、DevEco 的 Node/OHPM/Hvigor 加入本机环境；具体版本见 `apps/soloops_flutter/toolchain.lock.json`。Python 使用现有 backend 虚拟环境（cryptography 来自锁定的 pymysql[rsa] 依赖）。

```powershell
python scripts/mobile/runtime_fixture.py prepare
python scripts/mobile/runtime_fixture.py serve
# 在第二个终端构建；测试服务仅在本地提供合成诊断。
cd apps/soloops_flutter
flutter analyze --no-pub
flutter test --no-pub
flutter build apk --debug --no-pub --dart-define-from-file=../../.local/mobile-m0b/tls/dart-defines.json
cd ../..
adb -s emulator-5580 install -r apps/soloops_flutter/build/app/outputs/flutter-apk/app-debug.apk
python scripts/mobile/check_android_emulator.py --adb $ADB --serial emulator-5580
```

鸿蒙实际使用下列 Hvigor 命令（`$encoded` 为 dart-defines.json 每个 `KEY=VALUE` 的 UTF-8 Base64，以逗号连接）：

```powershell
$defines = Get-Content .local/mobile-m0b/tls/dart-defines.json -Raw | ConvertFrom-Json
$encoded = ($defines.PSObject.Properties | ForEach-Object {
  [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($_.Name+'='+$_.Value))
}) -join ','
$packageConfig = (Resolve-Path apps/soloops_flutter/.dart_tool/package_config.json).Path
cd apps/soloops_flutter/ohos
hvigorw.bat clean --no-daemon
hvigorw.bat assembleHap -p product=default -p buildMode=debug --no-daemon -p FLUTTER_TARGET=lib/main.dart -p TARGET_PLATFORM=ohos-x64 -p DART_OBFUSCATION=false -p TRACK_WIDGET_CREATION=true -p TREE_SHAKE_ICONS=false -p "DART_DEFINES=$encoded" -p "PACKAGE_CONFIG=$packageConfig"
cd ../../..
hdc -t 127.0.0.1:5555 install -r apps/soloops_flutter/ohos/entry/build/default/outputs/default/entry-default-unsigned.hap
hdc -t 127.0.0.1:5555 rport tcp:18443 tcp:18443
hdc -t 127.0.0.1:5555 shell aa start -a EntryAbility -b dev.soloops.soloops_flutter
# 完成按钮、系统返回及前后台操作后读取当前进程的真实事件：
python scripts/mobile/check_ohos_emulator.py --hdc $HDC --target 127.0.0.1:5555 --require-navigation --require-lifecycle
```

小程序实际构建命令：`npm run type-check`、`npm run build:weapp`（目录 `apps/soloops_weapp`）。Taro 重建 dist 期间 IDE 热重载可能读到暂时缺失的文件，应待完整构建结束后执行 IDE 完整编译。随后使用原生工具点击启动页→环境信息→运行合成诊断→返回，并从右上角退出后选择模拟场景1001恢复。截图和事件逐项核对。`node scripts/mobile/check_weapp_load.cjs` 本轮实际运行60秒超时（exit124），未标记脚本通过。

公共检查：`python scripts/validate_ui_contract.py`、`python -m unittest discover -s scripts/mobile/tests -v`，以及按 `scripts/mobile/ruff.toml`（继承后端规则，固定本地 app 导入分类）配置运行 Ruff。CI 增加对 M0-B 分支的触发，仍只代表契约与小程序构建检查，不代表远端 APK/HAP 或模拟器验收。

## 产物与证据

- APK：`apps/soloops_flutter/build/app/outputs/flutter-apk/app-debug.apk`，100032674 bytes，SHA256 `7ef69788ffa5e41d35e081e04b8ddef12ad47b4ca0f3f2e838308cd1bdc25004`。
- HAP：`apps/soloops_flutter/ohos/entry/build/default/outputs/default/entry-default-unsigned.hap`，95335396 bytes，SHA256 `8af25aa37190dae68c36908aede045c354e5d3197085c17d713b775a5e8d1283`。
- 小程序：`apps/soloops_weapp/dist/`；本地执行记录 `20261011T061334Z-weapp-types`、`20261011T061345Z-weapp-build`。
- 命令、真实退出码、日志哈希、产物哈希：[`m0b-evidence.json`](m0b-evidence.json)，导出时重新校验原文件 SHA256。
- 原始证据：`.local/mobile-m0b/*.{log,json}`；Android XML、截图、进程日志在 `.local/mobile-m0b/emulator-5580/`；鸿蒙截图和 Hilog 在 `.local/mobile-m0b/ohos-emulator/`；微信截图和观察文本在 `.local/mobile-m0b/weapp-emulator/`。
- M0-A 原包另保留在 `.local/mobile-m0b/baseline-artifacts/`。

## 变更与依赖核对

本轮改动集中于两个客户端的诊断页面、OHOS 权限声明、运行验证脚本、证据工具、CI 和文档。后端和原 Web 的差异为空，依赖锁文件与候选插件未变，无数据库迁移。许可证延续 M0-A 核对结果；TLS 夹具使用现有 `pymysql[rsa]` 依赖带入的 cryptography。用户 AppID、IDE 本地配置、私钥、构建包与原始日志保持本地，不提交。

## 阶段准入

- **本轮最小工程模拟器基线：Android PASS / OHOS PASS / 微信 PASS。** 可作为后续移动开发的工程起点；三端业务行为一致性仍需后续实现并验收。
- M0-B 的真机项按用户要求 NOT_TESTED；鸿蒙深色/旋转/字体、多设备形态、文件选择/上传/分享、安全存储插件及微信生产网络均 NOT_TESTED，进入相关功能前应补验证。
- 自动化脚本通道：微信 BLOCKED，可先用已验证的原生 UI 方法复验；后续解决工具协议兼容，不能把本次 GUI 观察描述为自动化业务 E2E。
- **生产发布 BLOCKED**：M0-A 已记录的 npm 安全审计 FAIL、鸿蒙发布签名、真实平台/账号流、域名与微信资质仍未闭合。个人主体及尚未设置服务类目的现状保留，本轮按用户要求暂缓资质工作。
- 本次仅交付 M0-B；分支提交推送后停止，等待下一条指令。


## M0 技术缺口补齐进度（2026-10-11）

本报告正文记录此前基础诊断子集。当前新增 Android 安全存储、缓存、系统文件选择与合成传输实测见 [Android 技术验收](m0-android-closure.md)；鸿蒙和微信补齐工作继续按顺序执行，不能把上述基础诊断结论解释为全部 M0 技术门禁通过。
