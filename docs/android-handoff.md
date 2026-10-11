# Android 换账号接续入口

更新时间：2026-10-11，Asia/Shanghai。GitHub 仓库 `Changxin-YR/AI-E-commerce-Agent`，分支 `android/capacitor-m0`。
本地独立目录：`C:/Users/27363/Desktop/AI E-commerce Agent/soloops-android`。只写本副本；同级 UI、微信、鸿蒙由其他聊天维护。

## 当前进度

- A0、A1 已完成。A1准确代码 `d6c54bed66081dcee7a9b6c10549087e2a4d94b7` 的 CI 38139535722 全成功。
- A2 已实现安卓收拢导航、返回键、安全区域、键盘/旋转适配、前后台会话回读、断网提示/恢复，以及经营资料和新增店铺离页保护。客服草稿和执行中任务沿用原保护，并补到退出入口。
- A2第一版 APK 在 API34 上通过28组设备检查，包括19个页面入口、无横向溢出、返回键保护、键盘、旋转、后台恢复、真实断网和显式重试。
- 后续增加导航条吸顶、保存中离页阻断、会话回读与退出并发保护。42文件191项单元已通过；最后补充的并发用例及最终提交CI以 `android-a2-acceptance.md` 为准。
- **A2 尚需用最终提交重新编译安装并重跑两个设备脚本，再记录最终APK校验值。** 第一版设备证据不能替代最后补丁的验收。用户要求现在先推送进度，供切换账号恢复。

## 新账号首先执行

1. 切到安卓分支，先读 `AGENTS.md`、本文、`docs/android-plan.md`、`docs/android-a2-acceptance.md`、`docs/android-local-testing.md`。
2. 核对工作区与远端 SHA；检查对应提交的 Android foundation CI。先完成下面命令与设备验收，再将 A2 标为完成。
3. A2完成后进入A3：原生文件选择/字节上传/分片与导入来源回读、今日运营和经营问数两条MVP；A4为Listing/客服/审批。74 SO、32原验收、四MVP及47长期模块继续按原需求/矩阵区分，不把页面可达计为业务完成。

```powershell
. ./scripts/android-env.ps1
Push-Location frontend
npm run lint
npm run type-check
npm run test:unit -- --maxWorkers=2
npm run android:sync:local
Pop-Location
.local/android/tools/gradle-8.14.3/bin/gradle.bat -p frontend/android assembleDebug
adb -s emulator-5580 install -r frontend/android/app/build/outputs/apk/debug/app-debug.apk
node frontend/scripts/check-android-device.mjs
node frontend/scripts/check-android-shell.mjs
```

每步确认成功再继续。`check-android-device.mjs` 会清空专属模拟器内本应用数据；shell脚本暂时关闭网络、旋转和显示键盘，finally恢复设置；仅对 `SoloOps_A1/emulator-5580` 执行。
Windows沙箱曾令 Vite worker realpath 报EPERM；使用正常本机执行权限。单元默认并行在本机耗尽内存，`--maxWorkers=2` 已通过。不要将这些环境限制误判成业务失败。

## 可复用本机环境

- Java `D:/Javajdk`；SDK `.local/android/sdk`；Gradle `.local/android/tools/gradle-8.14.3`；环境脚本只设置当前进程，并设置 `VITE_SOLOOPS_API_ORIGIN=http://10.0.2.2:8011`。
- AVD `.local/android/avd/SoloOps_A1.avd`，API34 / Pixel6 / x86_64 / WHPX；模拟器和镜像复用原SDK。当前后台运行，ADB5037需正常本机访问权限。
- 独立 Docker project `soloops-android-a1`，MySQL8.4，端口3311，schema `soloops_android_test`，专属卷。配置 `.local/android/mysql.env`、`.local/android/backend.env`。
- FastAPI后台监听 `127.0.0.1:8011`，启动入口 `scripts/start_android_backend.py`，模型/邮件/调度明确关闭。停止前按端口和父进程命令行核对归属，勿使用旧PID。
- 合成账号 `android_seller` / `Android-Synthetic-2026!`。最后设备测试已退出登录。
- 证据 `.local/android/evidence/device-shell.json`（28组）与 `a2-*.png`，单元 `.local/android/unit-a2.log`，构建 `.local/android/build-a2.log`。这些本机文件被Git忽略；可用已提交脚本复现。
- 第一版 APK 已安装；构建输出后来又生成过版本，最终提交仍须重建安装。不要把当前输出/旧设备证据混记为同一二进制验收。

## 授权和协作约定

用户已授权持续开发、推送本安卓分支并运行CI；无需重复确认。仅合成数据/替身，新的真实付费模型、邮件、平台写入须另获明确授权。只允许一个开发聊天写本安卓副本。
用户授权上下文接近上限时先落盘/推送，再新建聊天接续；旧聊天从新聊天接手起停止写入。此次因切换账号提前保存检查点，新账号可从本文直接恢复。
