# SoloOps Flutter OH 最小工程

Android 与 OHOS 共用 `lib/main.dart`，只显示启动页、环境信息、导航和生命周期事件。
`test/widget_test.dart` 是宿主机启动壳测试，不是设备或业务一致性测试。

## 锁定工具链

见 [`toolchain.lock.json`](toolchain.lock.json)。使用 CPF Flutter OH 发布标签
`3.27.5-ohos-1.0.7` / `6e545c2ce6ec9e303868dece5012d1d928890b57`，Dart 3.6.2。
Android 使用 JDK 17、SDK platform/build-tools 35，Gradle 8.3 / AGP 8.1.0。
OHOS 编译和目标 SDK 固定为 `6.0.2(22)`，最低运行 SDK `5.0.0(12)`。
配套 DevEco Studio / Command Line Tools 必须安装完整 API 22 SDK。
维护者发布说明名称为 3.27.4-ohos-1.0.7，实际 tag/version 为 3.27.5-ohos-1.0.7。
本机目前检测到 API 24，API 22 构建实际报 `SDK component missing`，状态 BLOCKED。
`.metadata` 保留首次创建记录；当前 SDK 以锁文件为准。

在仓库根目录用 PowerShell 初始化（SDK 与缓存不提交）：

```powershell
git -c core.longpaths=true clone --depth 1 --branch '3.27.5-ohos-1.0.7' https://atomgit.com/CPF-Flutter/flutter_flutter.git .local/toolchains/flutter-oh-api22
git -C .local/toolchains/flutter-oh-api22 rev-parse HEAD
$flutter = (Resolve-Path .local/toolchains/flutter-oh-api22/bin/flutter.bat).Path
$env:PATH = (Split-Path $flutter) + ';' + $env:PATH
$env:GRADLE_USER_HOME = Join-Path (Get-Location) '.local/gradle'
& $flutter --version
& $flutter doctor -v
Push-Location apps/soloops_flutter
& $flutter pub get
& $flutter analyze --no-pub
& $flutter test --no-pub
& $flutter build apk --debug --no-pub
& $flutter build hap --debug --no-pub
Pop-Location
```

先按本机安装位置设置 `JAVA_HOME`、Android SDK 与 `DEVECO_SDK_HOME`；不要提交
`local.properties`、签名文件或开发者账号资料。Gradle 启动器由 Flutter 工具按模板补齐。
SDK 标签正确仍可能出现 upstream/channel 提示，以固定 Git SHA 和工具输出核对。
下载依赖网络与 Android 许可证；本次 APK 已成功，doctor 仍提示部分组件许可证未接受。

Windows SDK 应放在较短的物理路径，clone 开启 `core.longpaths`；Dart 下载缓存的
路径清理仍可能触及 Windows 长路径限制，盘符映射不保证生效。本次缓存下载完成后
重试已进入 Hvigor，完整原始记录保留。独立 `GRADLE_USER_HOME` 避免复用
其他项目损坏的全局 Gradle cache，不改变用户全局配置。

产物：`build/app/outputs/flutter-apk/app-debug.apk`；OHOS 预期为
`ohos/entry/build/default/outputs/default/*.hap`，本次未生成 HAP。
实际错误及恢复步骤见 M0-A 报告。签名和设备运行待后续授权。
