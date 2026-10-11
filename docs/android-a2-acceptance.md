# Android A2 验收记录

日期：2026-10-11。最终应用代码 b70e783 已重新构建安装；本轮修正设备安全区域断言，最终结果见下方接续验证。

## 接续验证（2026-10-11）

- 已 fetch GitHub，接续起点为本地/远端一致的 `9646123d9e65b85906ed2f95868a11282e5257a7`。准确应用代码 `b70e783285a0242f2dafb0f8d714b8fce48bdcde` 的 CI 38141560687 已在 GitHub 页面确认 Success（3m 0s）。
- 本机 lint、vue-tsc、42文件192单元通过；android:sync:local 与 Gradle assembleDebug 成功。真实 HTTP/MySQL Cookie、CSRF、Origin、退出契约通过；最终 APK 认证设备检查7组通过。
- 最终 APK SHA256：`D9DDA3EFFD591CBB8425FC41D09C4AF057ACAE41329588B94CBE1EF03F145A66`。
- 原安全区域断言只接受 CSS padding > 0，在 WebView 113 上误报。Capacitor 8.5.3 的 SystemBars 对旧 WebView 设置原生窗口 padding，再注入零 CSS inset。UIAutomator 证实 WebView 边界 `[0,128][1080,2337]`，屏幕1080×2400；原生顶部128、底部63像素已避让系统栏。测试现在检查原生边界加 CSS 留白，保留正值要求。
- 构建 SDK 不含 API34 镜像；模拟器启动应使用原有 `AppData/Local/Android/Sdk`，AVD仍为安卓副本专属目录。已修正本机指南。
- 下列“第一版”和“换账号前”记录为历史证据；A3新增店铺、A4业务保护以及A5其他设备验证继续按计划执行。

最终完整壳脚本29组全部通过，证据 `.local/android/evidence/device-shell.json`；包含登录首屏、安全区域、19路由、返回保护、键盘、旋转、前后台、真实断网与显式恢复、退出保护。

## 已实现

- 官方插件锁定：App8.1.2、Network8.0.1、Keyboard8.0.6，Capacitor core/android8.5.3。
- 手机登录按钮置于首屏；全部功能收起/展开；19个业务路由共用原设计系统。安卓专用样式保留网页样式路径。
- 返回键先取消离页提示、再收起导航，随后走Vue Router守卫；根页最小化。系统键盘优先消费返回键。
- SystemBars注入的safe-area变量兼容旧WebView，viewport-fit=cover、adjustResize；旋转不重建Activity。
- 经营资料/新增店铺注册未保存保护；保存成功重置基准。客服和任务的现有阻断规则也覆盖退出登录。
- 前台恢复只回读session；断网不清除当前内存输入，恢复后明确提示用户重新读取/核对操作结果；不自动重放写入。会话epoch防止迟到回包恢复已退出会话。

## 已验证

第一版安装APK的 `device-shell.json`：28组全通过，包括登录首屏按钮、导航返回、19路由及412CSS像素下无横向溢出、未保存经营资料返回保护、键盘输入可见/返回收起、横竖屏保留输入、Home/切回保留输入、关闭Wi-Fi和数据后真实API错误、恢复后显式重新读取、退出确认。截图 `a2-login/home/leave-protection/keyboard/landscape/offline-input/recovered.png` 已本机查看。

后续吸顶导航/阻断和会话并发补丁：本机42文件191单元通过，lint和type-check通过，APK构建成功。最后增加一条“退出请求在途时开始的会话回读不得恢复会话”单元；该测试及最新SHA CI结果在后续记录补充。

## 换账号前待办与后续范围

- 已完成：最终应用代码192项单元及准确SHA CI通过。
- 已完成：最终APK重新sync/build/install，认证7组与壳29组全部通过，SHA256见上方。
- 新增店铺的离页确认、保存后无误提示可在A3建店业务中补设备证据；客服/Agent真实业务保护在A4复验。
- 本包仅API34模拟器；其他API/尺寸/实机在A5。未保存输入只承诺旋转及进程存活的前后台保留，不承诺系统杀进程后草稿持久化。完整业务MVP仍待A3/A4。

## 复现

见 `android-handoff.md` 与 `android-local-testing.md`。脚本使用已安装APK WebView CDP并操作真实ADB，不替换后端接口。本机日志/截图/APK/数据库配置在Git忽略目录，源码与步骤已提交。

换账号前最后校验：新增安卓壳/会话恢复两文件6项单元全部通过，lint通过。最新type-check受本机内存不足中断（JavaScript heap out of memory）；此前同包type-check已通过，但最终SHA仍须以CI及重跑结果确认。CI链接/准确SHA在提交后补记。

GitHub代码检查点为 `b70e783285a0242f2dafb0f8d714b8fce48bdcde`；[CI 38141560687](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38141560687) 已触发，写入本记录时仍在运行。最终设备回归依照上方待办执行。
