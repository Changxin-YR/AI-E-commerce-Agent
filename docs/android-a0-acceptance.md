# Android A0 工程验收

日期：2026-10-11。本包交付独立安卓工程与连接基础，后续 A1 完成本机 APK 与模拟器联调。

## 实现

1. 基于既有业务提交 `0a49a37` 创建独立副本，并导入同级 Vue V2.1 视觉快照；20 页及原业务入口保留。
2. 锁定 Capacitor core/android/cli 8.5.3，生成 Android Gradle 工程，开发标识 `com.soloops.android`。关闭备份与正式明文网络，忽略签名密钥。
3. 原生 API 读取构建时 HTTPS origin。缺少配置、非法协议、账号、路径、参数、回环地址及越界接口路径均拒绝；网页模式保持同源。
4. 使用 CapacitorHttp fetch 桥接；保留 CSRF、HttpOnly 会话、原 client header、冲突和会话失效反馈，以及上传 File 对象。
5. `android:sync` 包含类型检查、安卓专用构建和资源同步。新增分支 CI，分别验证前端、原生资源同步和 Gradle debug 编译。

## 验证记录

本地业务提交 `f857d87`，远端推送因自动审批要求确认具体 GitHub 目的地而待用户确认；CI 尚未运行。本包为工程与本地检查完成，原生编译/设备联调仍待验证。

- `npm run build`：通过（类型检查与生产资源构建）。
- `npx cap add android`：通过。
- `npm run lint`：通过。
- 初次 `npm run test:unit`：176 通过、4 失败；四项失败均因独立副本缺 Python oracle 环境。
- `uv sync --frozen --python 3.11`：通过，已建立独立 Python 环境。首次复验在默认并发下有一项 CSV 超过 5 秒；限制并发后 `npm run test:unit -- --maxWorkers=4` 全部通过：40 文件、180 项，14.22 秒。
- `npm run build:android` 缺 origin 时按预期退出 1；设置保留测试地址后 `npm run android:sync` 通过类型检查、安卓资源构建与同步，未发出业务网络请求。
- 新增 22 项用例：18 项 origin/路径校验；4 项原生请求、缺配置禁止发出、二进制对象保持、401 UI 会话失效。桥接行为在本包以替身验证。
- 本机 Java 17、SDK 路径不存在，因此尚未执行本机 Gradle/APK 安装；设备层 Cookie、文件字节、断网/恢复、返回键留待 A1/A2/A3。

没有数据库迁移或后端业务变更。回退在安卓分支上恢复 A0 前提交即可；已运行服务与其他平台副本不受本包影响。

## 参考与依赖

Capacitor 官方 HTTP 文档：https://capacitorjs.com/docs/apis/http 。采用 fetch bridge 以兼容现有 JSON 与二进制上传。环境要求：https://capacitorjs.com/docs/getting-started/environment-setup 。Cookie 文档：https://capacitorjs.com/docs/apis/cookies 。代码来源 `ionic-team/capacitor`，许可证 MIT；安装包模板及 API 适配分别维护。

`npm audit` 检出开发工具链 CLI/xcode/uuid 的 3 项 moderate（GHSA-w5hq-g745-h8pq），未修改依赖主版本以隐藏告警。首包未使用 iOS 工具；正式发行前复核上游修复。
