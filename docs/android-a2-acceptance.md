# Android A2 进度检查点

日期：2026-10-11。用户切换账号前保存，A2状态为实现已落盘、最终设备回归待完成。

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

## 待完成

- 最终提交全套单元应为192项；核对准确SHA CI。
- 最终提交重新sync/build/install，运行认证7组和shell设备脚本（新增安全区域数值断言，预计29组），记录最终APK SHA256。
- 新增店铺的离页确认、保存后无误提示可在A3建店业务中补设备证据；客服/Agent真实业务保护在A4复验。
- 本包仅API34模拟器；其他API/尺寸/实机在A5。未保存输入只承诺旋转及进程存活的前后台保留，不承诺系统杀进程后草稿持久化。完整业务MVP仍待A3/A4。

## 复现

见 `android-handoff.md` 与 `android-local-testing.md`。脚本使用已安装APK WebView CDP并操作真实ADB，不替换后端接口。本机日志/截图/APK/数据库配置在Git忽略目录，源码与步骤已提交。

换账号前最后校验：新增安卓壳/会话恢复两文件6项单元全部通过，lint通过。最新type-check受本机内存不足中断（JavaScript heap out of memory）；此前同包type-check已通过，但最终SHA仍须以CI及重跑结果确认。CI链接/准确SHA在提交后补记。

GitHub代码检查点为 `b70e783285a0242f2dafb0f8d714b8fce48bdcde`；[CI 38141560687](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38141560687) 已触发，写入本记录时仍在运行。最终设备回归依照上方待办执行。
