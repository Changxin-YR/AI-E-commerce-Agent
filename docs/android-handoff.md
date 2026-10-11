# Android 接续入口

更新：2026-10-11，Asia/Shanghai。独立目录 `C:/Users/27363/Desktop/AI E-commerce Agent/soloops-android`，分支 `android/capacitor-m0`。只写安卓副本；同级 UI、微信、鸿蒙由其他对话维护。

## 当前交付

A0 完成，代码 `84d86a7b213e6bf16d5bcc90aedbbd9a92360159` 的 CI 38137311083 成功。
A1 本机和真实模拟器认证验收完成：Java 21、SDK 36、独立 AVD、FastAPI/MySQL、debug 本机白名单、release 门禁；40文件186单元、APK编译安装、7组设备认证均通过。A1 准确提交 CI 在推送后补充。

先读 `AGENTS.md`、`android-plan.md`、`android-a1-acceptance.md`、`android-local-testing.md`。74 SO、32 原验收和四条 MVP 继承原需求，不把网页结果当设备业务验收。后端业务源码未改。

## 可复用环境

- `. ./scripts/android-env.ps1` 配置当前进程。Java `D:/Javajdk`；SDK `.local/android/sdk`；Gradle `.local/android/tools/gradle-8.14.3`，缓存同级 gradle。
- AVD `.local/android/avd/SoloOps_A1.avd`，设备 `emulator-5580`，API 34 / Pixel 6 / x86_64 / WHPX。模拟器已后台运行；ADB 来自副本 SDK。命令须有正常本机进程访问权限，受限环境的 adb 可能无法访问 5037。
- Docker project `soloops-android-a1`，端口3311、schema `soloops_android_test`、专属卷。配置 `.local/android/mysql.env`，后端配置 `.local/android/backend.env`。模型、邮件、调度明确关闭。
- 后端已后台运行，监听 `127.0.0.1:8011`。启动 `scripts/start_android_backend.py` 前设 `PYTHONPATH` 为副本 backend。停止前按监听端口与父进程命令行核实归属，不使用过期 PID。
- 合成账号 `android_seller` / `Android-Synthetic-2026!`，仅此合成库使用。
- APK：`frontend/android/app/build/outputs/apk/debug/app-debug.apk`；SHA256 `CD676937533F7FA36D64DB12D5D82A57D96302775BE9E01AC28DCD0FC882FDB9`。
- 设备证据 `.local/android/evidence/device-auth.json` 7组通过；同目录截图。当前应用已退出登录。
- 运行 `node frontend/scripts/check-android-device.mjs` 会清除本模拟器中本应用数据；脚本真实操作 APK WebView。冷启动允许120秒，CDP使用 noDefaults。视口截图正常，全页截图在本 WebView 上有重复拼接，应使用 adb 原生截图判断视觉。

## 下一包 A2

1. 核对 Git 状态与 A1 CI，复用现有环境，开始安卓导航/返回键、安全区域、键盘、旋转、前后台恢复和断网恢复。
2. 首先阅读 Capacitor App/Keyboard/Network 官方资料及现有 Vue 路由、未保存任务保护；按项目现有设计系统做移动适配。
3. 登录页和工作台目前沿用网页响应式布局，检查首屏高度、导航可达和键盘遮挡。A1认证可作为回归脚本；设备页面与实际 API 验证配套。
4. File 上传字节、系统文件选择和两条导入/问数MVP留 A3；Listing/客服/审批留 A4。禁止新增真实付费模型、邮件、平台写入。

用户已授权推送本分支到 `https://github.com/Changxin-YR/AI-E-commerce-Agent` 并运行 CI，持续有效。按包落盘、提交、推送并核对准确 SHA；上下文接近上限按已授权创建新对话接续，新对话接手后旧对话停止写入。
