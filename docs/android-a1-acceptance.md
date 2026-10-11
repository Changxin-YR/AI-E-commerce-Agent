# Android A1 本机环境与认证验收

日期：2026-10-11，Asia/Shanghai。范围：本机工具链、隔离合成服务、APK 安装及认证。74 SO、32 原验收与四条 MVP 继续按 Android 计划逐包追踪。

## 交付与环境

- Java 21.0.10、compile/target SDK 36；独立 SDK、Gradle 缓存和 AVD 位于 `.local/android`。Java 使用已有 `D:/Javajdk`，模拟器及 API 34 镜像复用本机 SDK。
- 模拟器 `emulator-5580` / `SoloOps_A1` / Pixel 6 / Android 14 API 34 / x86_64 / WHPX。
- MySQL 8.4 独立 Compose project、卷、schema 和账号，端口 3311；真实 FastAPI 监听 `127.0.0.1:8011`。模型、邮件、调度由启动脚本明确关闭。
- `android-local` 仅允许明文 origin `http://10.0.2.2:8011`。debug 专用 Network Security Config 按主机放行，release 继续禁用明文，并拒绝非 `android` 模式的前端包。
- 可复现步骤见 [本机验收手册](android-local-testing.md)。配置密码、日志、AVD、APK、截图位于 Git 忽略目录。

## 实际验证

| 检查 | 结果与证据 |
|---|---|
| 前端 | lint、类型检查通过；40 文件 186 项通过，含本机地址白名单与正式拒绝 |
| 本机编译 | Gradle 8.14.3 `assembleDebug` 成功，93 tasks；APK 安装返回 Success |
| 正式构建门禁 | 本机资源执行 `:app:preReleaseBuild` 按预期失败：`Release requires npm run android:sync with an HTTPS API origin.` |
| 首次启动 | 清空本合成应用数据后显示登录页 |
| 错误反馈 | 实际填写错误密码，界面显示“账号或密码错误” |
| 登录 | UI 提交合成账号，工作台显示 `android_seller` |
| 设备 Cookie | 原生 fetch 回读 session 为 200；JS document.cookie 为空。真实 HTTP 响应核实 HttpOnly、SameSite=Strict、Path=/api |
| 设备 CSRF | 已登录 APK 发起缺失/错误 token 的 logout，均为 403 csrf_rejected |
| 会话恢复 | am force-stop 后重启 APK，工作台自动恢复合成账号 |
| 退出 | 点击“退出”，回登录页；设备请求 session 为 401 |
| 退出后重启 | 再次停止并启动 APK，仍为登录页 |
| 来源校验 | 真实 HTTP/MySQL 检查中，非法 Origin 返回 origin_rejected；正确 CSRF 退出成功 |

`frontend/scripts/check-android-device.mjs` 连接本模拟器 APK 的 WebView 执行，未替换网络或业务服务。结果 `.local/android/evidence/device-auth.json` 共 7 组通过；截图同目录，另有原生 `device-screen.png`。构建日志 `.local/android/build.log`，门禁日志 `.local/android/release-gate.log`。

APK：`frontend/android/app/build/outputs/apk/debug/app-debug.apk`。
SHA256：`CD676937533F7FA36D64DB12D5D82A57D96302775BE9E01AC28DCD0FC882FDB9`。
该 APK 面向本机模拟器测试服务；发行与签名在 A6 验收。

## 限制与下一包

- 仅 API 34 模拟器实测，其他 API/尺寸/实机待 A5；编译目标为 36。
- 返回键、安全区域、键盘、横竖屏、前后台与断网恢复属于 A2。登录页、工作台沿用网页响应式布局，A2 检查窄屏入口与首屏高度。
- File 字节上传、原生文件选择、分片与四条业务 MVP 在 A3/A4 验收。
- WebView 冷启动曾超过 30 秒，等待扩为 120 次一秒重试；Playwright 使用 noDefaults 适配 WebView 上下文管理。全页截图会重复拼接，改用视口及 adb 原生截图。
- 本机 SDK 已定位，缺失的 adb 单独安装到副本；Gradle 镜像下载已核实官方 SHA256。
- 准确提交及 CI 由交接入口记录，推送后核对。
