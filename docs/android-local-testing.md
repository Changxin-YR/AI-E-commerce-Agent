# Android 本机合成验收

在安卓副本根目录执行。构建、数据库、AVD 与证据保存在本副本；Java 21 使用只读现有安装。测试账号仅限合成数据库。

## 环境

- Java 21：`D:/Javajdk`（Temurin 21.0.10）；`scripts/android-env.ps1` 可传 `-JavaHome`。
- SDK：`.local/android/sdk`，包含 platform 36、build-tools 35.0.0/36.0.0、platform-tools 37.0.1。
- Gradle 8.14.3：`.local/android/tools/gradle-8.14.3`；官方 binary SHA256 为 `bd71102213493060956ec229d946beee57158dbd89d0e62b91bca0fa2c5f3531`。
- AVD：`.local/android/avd/SoloOps_A1.avd`，Android 14 / API 34 / Google APIs x86_64 / Pixel 6，WHPX；使用现有 SDK 的 emulator 和 system image。
- MySQL：Compose project `soloops-android-a1`，宿主 `127.0.0.1:3311`，专属命名卷；schema `soloops_android_test`，用户 `soloops_android`。
- API：`127.0.0.1:8011`；APK 内 `http://10.0.2.2:8011`。固定禁用模型、邮件与调度。

## 初始化和启动

```powershell
# 首次生成随机数据库密码，已有配置会拒绝覆盖。
backend/.venv/Scripts/python.exe scripts/setup_android_test.py
docker compose -f compose.android-test.yaml --env-file .local/android/mysql.env up -d --wait

# 只在当前进程加载隔离数据库，执行迁移和账号创建。
Get-Content .local/android/backend.env | ForEach-Object {
  $parts = $_.Split('=', 2)
  [Environment]::SetEnvironmentVariable($parts[0], $parts[1], 'Process')
}
Push-Location backend
.venv/Scripts/python.exe -m alembic upgrade head
'Android-Synthetic-2026!' | .venv/Scripts/python.exe -m app.cli create-user android_seller --password-stdin
Pop-Location
$env:PYTHONPATH = (Resolve-Path backend).Path
backend/.venv/Scripts/python.exe scripts/start_android_backend.py
```

独立终端启动模拟器（`ANDROID_AVD_HOME` 由环境脚本设置）：

```powershell
. ./scripts/android-env.ps1
$env:ANDROID_SDK_ROOT = 'C:/Users/27363/AppData/Local/Android/Sdk'
$env:ANDROID_HOME = $env:ANDROID_SDK_ROOT
& 'C:/Users/27363/AppData/Local/Android/Sdk/emulator/emulator.exe' -avd SoloOps_A1 -port 5580 -no-window -no-audio -no-snapshot -gpu swiftshader_indirect
```

## 构建与验收

```powershell
. ./scripts/android-env.ps1
Push-Location frontend
npm run android:sync:local
Pop-Location
.local/android/tools/gradle-8.14.3/bin/gradle.bat -p frontend/android assembleDebug
adb -s emulator-5580 install -r frontend/android/app/build/outputs/apk/debug/app-debug.apk
backend/.venv/Scripts/python.exe scripts/check_android_service.py
node frontend/scripts/check-android-device.mjs
node frontend/scripts/check-android-imports.mjs
node frontend/scripts/check-android-mvps.mjs
node frontend/scripts/check-android-listing-support.mjs
node frontend/scripts/check-android-agent-lifecycle.mjs
node frontend/scripts/check-android-modules.mjs
node frontend/scripts/check-android-adaptation.mjs
```

设备脚本通过 WebView 调试连接操作已安装 APK，写 `.local/android/evidence`。`check-android-device.mjs` 会清除 **本 AVD 中 `com.soloops.android` 的应用数据**；其余脚本只强制停止并重启应用，沿用现有会话。仅用于专属合成 AVD。HTTP/MySQL 契约脚本与真实设备脚本分别记录；不得用前者替代后者。七个设备脚本依次执行，共用 ADB 9223 端口，不可并发。`check-android-adaptation.mjs` 会临时修改 `wm size`/`wm density`/`font_scale`/`user_rotation`，结束时恢复。

打包与升级验证：`node frontend/scripts/check-android-package.mjs`（`SOLOOPS_PACKAGE_PHASE=upgrade` 验证同签名升级保留会话；`=release` 会先卸载再安装签名发行包并断言落在登录页）。签名材料由 `scripts/make-release-key.ps1` 生成到忽略目录 `.local/android/keystore/`，并在 `frontend/android/keystore.properties`（已忽略）写入 Gradle 配置。

模拟器网络校验：Android 在本机模拟器上把 Wi-Fi/移动网络标为 `PARTIAL_CONNECTIVITY`（门户校验不可达）时，`@capacitor/network` 要求 `NET_CAPABILITY_VALIDATED`，壳层会显示「网络已断开」而 API 实际可用。需要干净提示时先执行 `adb -s emulator-5580 shell settings put global captive_portal_mode 0` 与 `captive_portal_detection_enabled 0`，再重启 Wi-Fi（`svc wifi disable/enable`）等待网络变为 `VALIDATED`。这是模拟器环境设置，不改变应用语义。

原生文件选择器的 CSV 可用性：`accept` 只写单个 `.csv` 时，WebView 以 `typ=text/csv` 请求选择器，而 MediaProvider 把 `.csv` 记为 `text/comma-separated-values`，文件会被置灰；入口应使用 `.csv,text/csv,text/comma-separated-values`。排查手法见 `docs/android-a3-acceptance.md`。

正式资源使用 HTTPS origin 和 `npm run android:sync`。`preReleaseBuild` 要求构建元数据 mode 为 `android`；本机模式打 release 会失败。debug Network Security Config 只为 `10.0.2.2` 开放明文，前端进一步限定端口 8011。

停止本包数据库：`docker compose -f compose.android-test.yaml --env-file .local/android/mysql.env stop`。停止本 AVD：`adb -s emulator-5580 emu kill`。后端在启动终端按 Ctrl+C；后台运行时先核对 8011 监听进程和安卓副本父进程再停止。
