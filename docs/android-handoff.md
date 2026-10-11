# Android 开发接续入口

更新时间：2026-10-11，Asia/Shanghai。GitHub 仓库 `Changxin-YR/AI-E-commerce-Agent`，分支 `android/capacitor-m0`。
本地独立目录：`C:/Users/27363/Desktop/AI E-commerce Agent/soloops-android`。只写本副本；同级 UI、微信、鸿蒙由其他聊天维护。

## 当前进度与下一步

- A0/A1已完成；A2最终应用补丁已验收：lint、type-check、42文件192单元、原生构建、7组认证与29组壳设备检查全部通过。
- 应用代码 `b70e783285a0242f2dafb0f8d714b8fce48bdcde` 的 CI 38141560687 已在GitHub页面核对 Success。
- 本轮修正旧WebView安全区域测试误报，原生顶部128/底部63像素已避让系统栏，CSS为0是预期；应用代码未改。修正模拟器启动使用原有SDK镜像的说明。
- 最终APK SHA256 `D9DDA3EFFD591CBB8425FC41D09C4AF057ACAE41329588B94CBE1EF03F145A66`；详细证据见android-a2-acceptance.md。
- 首个动作：确认本轮接续提交的准确SHA CI结果，然后进入A3：原生文件选择、真实字节上传、CSV分片及来源回读、今日运营/经营问数两条MVP安卓闭环。A4 Listing/客服/审批恢复；A5其他模块及设备适配；A6安装升级与交付。74 SO、32验收和47长期模块范围保持。
- A3应复用现有Vue/后端业务和frontend/e2e流程，补已安装APK的设备证据；页面可达不等于业务完成。新增店铺的离页确认/保存解除在A3补验，客服/任务业务保护在A4补验。
- 当前仅专属API34模拟器；真机与其他尺寸归A5，正式签名/服务地址归A6。

## 本轮执行注意

- Windows沙箱导致Vitest临时文件rename EPERM，正常本机权限重跑192项通过。必须加载scripts/android-env.ps1后构建，否则缺少VITE_SOLOOPS_API_ORIGIN。
- 模拟器启动另将ANDROID_HOME和ANDROID_SDK_ROOT指向原有AppData/Local/Android/Sdk，构建则重新加载android-env.ps1使用副本SDK。
- gh未在PATH，GitHub匿名REST受到限流；内置浏览器成功读取CI页面。git fetch正常权限成功，远端接续起点9646123与本地一致。
- 单元maxWorkers=2。模拟器设备脚本依次执行，避免共享ADB9223端口冲突。检查命令各自退出码，PowerShell最后的Get-FileHash会掩盖前面失败。

## 可复用本机环境

- Java `D:/Javajdk`；SDK `.local/android/sdk`；Gradle `.local/android/tools/gradle-8.14.3`；环境脚本只设置当前进程，并设置 `VITE_SOLOOPS_API_ORIGIN=http://10.0.2.2:8011`。
- AVD `.local/android/avd/SoloOps_A1.avd`，API34 / Pixel6 / x86_64 / WHPX；模拟器和镜像复用原SDK。当前后台运行，ADB5037需正常本机访问权限。
- 独立 Docker project `soloops-android-a1`，MySQL8.4，端口3311，schema `soloops_android_test`，专属卷。配置 `.local/android/mysql.env`、`.local/android/backend.env`。
- FastAPI后台监听 `127.0.0.1:8011`，启动入口 `scripts/start_android_backend.py`，模型/邮件/调度明确关闭。停止前按端口和父进程命令行核对归属，勿使用旧PID。
- 合成账号 `android_seller` / `Android-Synthetic-2026!`。最后设备测试已退出登录。
- 证据 `.local/android/evidence/device-shell.json`（29组）与 `a2-*.png`，单元 `.local/android/unit-a2.log`，构建 `.local/android/build-a2.log`。这些本机文件被Git忽略；可用已提交脚本复现。
- 最终APK已安装并通过认证/壳验证，设备最后退出登录。数据库与8011后端已恢复运行。

## 授权和协作约定

用户已授权持续开发、推送本安卓分支并运行CI；无需重复确认。仅合成数据/替身，新的真实付费模型、邮件、平台写入须另获明确授权。只允许一个开发聊天写本安卓副本。
用户授权上下文接近上限时先落盘/推送，再新建聊天接续；旧聊天从新聊天接手起停止写入。此次因切换账号提前保存检查点，新账号可从本文直接恢复。

## 本次GitHub检查点

本轮接续提交由 `git log -1` 确定；推送后核对该SHA的 Android foundation CI。应用代码b70e783的CI已确认成功。本轮只修改测试及文档。
