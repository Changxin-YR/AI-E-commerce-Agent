# Android 接续入口

更新：2026-10-11，Asia/Shanghai。

用户已确认 Vue + Capacitor 路线，并选择先在本机使用合成数据验收。下一包 A1：安装/定位 Java 21、Android SDK 36 与模拟器，配置独立 FastAPI/MySQL 测试实例，再验证 APK 登录与会话。原项目需求见 `docs/android-plan.md` 及其中引用的需求基线。

**A0 已完成：** 提交 `84d86a7b213e6bf16d5bcc90aedbbd9a92360159` 的 [CI 38137311083](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38137311083) 全部成功，包含 Android `assembleDebug`。其后的验收文档提交以 `[skip ci]` 标记，代码未改。用户已授权按小任务边界创建新对话自动接续；交接后本对话停止写入，由新对话独占安卓副本。

## 当前状态

独立开发目录 `C:/Users/27363/Desktop/AI E-commerce Agent/soloops-android`，分支 `android/capacitor-m0`。A0 已生成 Android 工程及 API 地址路由。网页 UI 来自同级 `soloops-ui` 的 V2.1 工作区快照。后端业务源码未修改。

`frontend/capacitor.config.ts` 将本地 `dist` 打入安装包，通过 CapacitorHttp 桥接现有 fetch。原生构建的服务地址由 `VITE_SOLOOPS_API_ORIGIN` 注入，必须是 HTTPS origin；保留 `X-SoloOps-Client: web` 与 CSRF 字段契约。Cookie 由原生桥接处理，其持久化、退出清除和二进制上传必须在 A1/A3 设备实测。

`frontend/.env.example` 提供配置格式。`npm run android:sync` 会先执行安卓专用构建，缺少地址时失败。CI 使用保留 `.invalid` 域名测试打包，不能把该包当连通业务的成品。A1 需建立调试专用本机连接路径；如果使用模拟器 `10.0.2.2` HTTP，必须限定 debug 变体和确切测试主机，正式构建继续只允许 HTTPS。

## 环境与未完成验证

- 初始 Java 为 `C:/Program Files/Eclipse Adoptium/jdk-17.0.19.10-hotspot`；不满足 Capacitor Java 21。
- `ANDROID_HOME` / `ANDROID_SDK_ROOT` 指向 `C:/Users/27363/AppData/Local/Android/Sdk`，检查时目录不存在；PATH 无 adb/gradle。
- 独立 Python 虚拟环境已由 `uv sync --frozen --python 3.11` 准备。最终 `npm run test:unit -- --maxWorkers=4`：40 文件、180 项通过；原默认并发曾导致一项 CSV 超时，后续使用四个 worker。
- 类型检查、构建、lint、Android 资源生成与同步、缺服务配置拒绝均通过。UI 快照提交 `af92208`；A0 代码提交以 Git 历史及准确 SHA 的 CI 为准。
- Windows 沙箱曾阻止 Git 辅助进程及 Vite worker realpath，正常权限下可继续。
- npm audit 报告 Capacitor CLI → xcode → uuid 共 3 项 moderate，仅开发依赖；记录 GHSA-w5hq-g745-h8pq，发行前复核上游修复。未使用强制降级。
- 当前尚未启动 Android 模拟器、签名、安装 APK 或验收真实设备；网页构建与单元测试不等同原生验收。

## 下一步

用户已明确授权将安卓代码和文档推送到 `https://github.com/Changxin-YR/AI-E-commerce-Agent` 的 `android/capacitor-m0` 并运行 CI；origin 已设置且分支已推送。此上传授权持续有效。CI 已固定 ubuntu-24.04 并检查预装 SDK 36，准确提交验证通过。下一包优先将本机 Java/SDK 放在安卓副本的忽略目录内，并按进程设置路径，避免影响其他平台聊天的工具链。

先读取本文件、`android-plan.md` 和 `android-a0-acceptance.md`，核对 Git HEAD/status 与准确提交 CI。只写安卓副本。隔离数据库、端口、卷、测试账号及模型/邮件替身；不复用其他聊天正在使用的数据实例。新包补 Android 返回键/网络恢复/上传前，先查看对应官方文档并更新参考记录。
