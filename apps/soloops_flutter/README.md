# SoloOps Flutter OH 最小工程

Android 与 OHOS 共用 `lib/main.dart`，只显示启动页、环境信息、导航和生命周期事件。
`test/widget_test.dart` 是宿主机启动壳测试。

## 锁定工具链

[`toolchain.lock.json`](toolchain.lock.json) 固定 CPF Flutter OH
`3.27.5-ohos-1.0.7` / `6e545c2ce6ec9e303868dece5012d1d928890b57`，Dart 3.6.2。
维护者发布说明名称为 3.27.4-ohos-1.0.7；实际 tag/version 为 3.27.5-ohos-1.0.7。
该版本引擎最低构建 API22，本工程 compile/target 固定 `6.1.1(24)`，最低运行声明为
`5.0.0(12)`。本机 SDK 包 6.1.1.125、DevEco6.1.1.290、Hvigor6.24.3。
SDK24 未签名 HAP 编译 PASS；声明的最低运行版本尚未经过设备验证。
`.metadata` 保留首次创建记录，当前 SDK 以锁文件为准。

Android 使用 JDK17、SDK platform/build-tools35，Gradle8.3 / AGP8.1.0。
本机 SDK 路径、`local.properties`、证书及账号资料不提交。

## Windows 复现

SDK 和 OHOS 工具都需要无空格物理路径。示例从仓库根目录执行，PowerShell7：

```powershell
$env:SOLOOPS_FLUTTER_SDK = Join-Path $env:TEMP 'soloops-flutter-6e545c2'
# 目录不存在时初始化；已存在时先核对 SHA 与 git status。
git -c core.longpaths=true clone --depth 1 --branch '3.27.5-ohos-1.0.7' https://atomgit.com/CPF-Flutter/flutter_flutter.git $env:SOLOOPS_FLUTTER_SDK
git -C $env:SOLOOPS_FLUTTER_SDK rev-parse HEAD
$flutter = Join-Path $env:SOLOOPS_FLUTTER_SDK 'bin/flutter.bat'
$env:GRADLE_USER_HOME = Join-Path (Get-Location) '.local/gradle'
Push-Location apps/soloops_flutter
& $flutter pub get
& $flutter analyze --no-pub
& $flutter test --no-pub
& $flutter build apk --debug --no-pub
Pop-Location
pwsh -NoProfile -File scripts/mobile/build_hap_windows.ps1 -Unsigned
```

先按本机安装位置配置 Android SDK、JAVA_HOME、DEVECO_SDK_HOME 和 hvigorw.bat 的 PATH。
`build_hap_windows.ps1` 校验 SDK 提交及干净状态，将仓库内已跟踪的 Flutter 文件复制到
独立临时目录，逐文件核对 SHA256，并确认 pub get 没有改动依赖锁。
该临时目录是构建快照，源码仍在本仓库；新文件应先 git add 才能进入快照。
默认创建新目录，不清理已有目录。SDK/构建目录保留用于本机复核。

脚本先运行 `flutter build hap --debug --no-pub`，再在 `-Unsigned` 模式单独运行相同的
Hvigor assembleHap 命令，保留两个退出码。当前 Flutter 包装命令在编译后要求签名，退出1；
Hvigor 未签名构建退出0。该编译 PASS 不能用于声明签名、安装或设备运行成功。
SDK24 仍有上游 ArkTS 弃用/异常处理告警，设备兼容性留待后续阶段。

产物：`build/app/outputs/flutter-apk/app-debug.apk`、
`build/ohos/hap/entry-default-unsigned.hap`。
构建快照清单与分步退出码在 `.local/mobile-m0a/hap-source-manifest.json`、
`hap-build-results.json`；完整结果见 [`M0-A报告`](../../docs/mobile/m0a-report.md)。

## IDE 导入与完整路径

仓库和 Flutter SDK 的物理路径均应无空格。Android Studio 打开 `android/`，
DevEco Studio 打开 `ohos/`，两端页面仍来自同一 `lib/main.dart`。

Android Studio 提示 Gradle 8.3 与 JVM21 不兼容时，选择 **Use JVM 17**。
也可在 Settings > Build, Execution, Deployment > Build Tools > Gradle 中选择 JDK17。
本机 `.gradle/config.properties` 的 `java.home` 和 `local.properties` 均保持忽略，
使用者按安装位置设置；仅改 Java 编译目标不能替代 Gradle 运行时 JVM 配置。
若全局 Gradle 缓存报缺失 `metadata.bin`，可把 IDE 的 Gradle 用户主目录设置为本仓库
`.local/gradle` 的绝对路径，与命令行 `GRADLE_USER_HOME` 对齐，然后重新同步。
这是本机 IDE 设置，不提交到 Git，也无需删除其他工程的缓存。

Flutter OH 1.0.7 会把 `buildinfo.json5` 和 `framesconfig.json` 从
`entry/src/main/resources/base/profile/` 迁到 `entry/src/main/resources/rawfile/`。
工程现已采用 SDK 使用的目标位置，配置语义不变；`flutter_assets/` 仍是被忽略的构建产物。

无空格仓库可直接在 `ohos/` 执行未签名构建（需先 `flutter pub get`，并按上述说明配置工具）：

```powershell
$packageConfig = (Resolve-Path ../.dart_tool/package_config.json).Path
hvigorw.bat assembleHap -p product=default -p buildMode=debug --no-daemon -p FLUTTER_TARGET=lib/main.dart -p TARGET_PLATFORM=ohos-arm64 -p DART_OBFUSCATION=false -p TRACK_WIDGET_CREATION=true -p TREE_SHAKE_ICONS=false -p "PACKAGE_CONFIG=$packageConfig"
```

原生输出位于 `ohos/entry/build/default/outputs/default/entry-default-unsigned.hap`。
实际签名和安装仍需单独验收。
