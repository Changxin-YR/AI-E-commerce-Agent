# 微信 IDE 验收记录（2026-10-12）

本文件记录微信开发者工具（IDE）验收的**实际执行环境与结论**，用于区分「离线验证通过」与「IDE 验收通过」。截至本文件更新时间，H01–H20 仍**没有** IDE 验收结论。

## 环境

- 开发者工具：`D:\微信开发工具\微信web开发者工具`（`cli.bat` / `cli.js` / `wechatdevtools.exe`）。
- 自动化 SDK：`.local/weapp-tools/node_modules/miniprogram-automator@0.12.1`（按仓库根 README 的命令安装，未入库）。
- 被验工程：`apps/soloops_weapp`，`project.config.json` 的 `miniprogramRoot` 为 `dist/`，`appid` 为 `touristappid` 占位。
- 启动命令（已实际执行，IDE 服务与自动化端口均成功监听）：

```powershell
& 'D:\微信开发工具\微信web开发者工具\node.exe' 'D:\微信开发工具\微信web开发者工具\cli.js' `
  auto --project 'C:\Users\27363\Desktop\AI E-commerce Agent\soloops-wechat\apps\soloops_weapp' `
  --auto-port 9420 --trust-project
# 输出：IDE server started successfully, listening on http://127.0.0.1:21740
#       Using AppID: touristappid
```

- 端口状态实测：`9420`（wechatdevtools.exe，自动化）与 `21740`（IDE 服务）均在 `Listen`。
- `miniprogram-automator` 对 `ws://127.0.0.1:9420` 的连接本身**成功**（实测约 8ms）。

## 结论：启动页断言未通过（环境阻断，非代码结论）

```
FAIL: WeChat startup page verification timed out after 55 seconds
```

`scripts/mobile/check_weapp_load.cjs` 在 `automator.connect` 之后卡在 `miniProgram.currentPage()`，55 秒超时退出 1；同一命令在重新完整构建 `dist/`（退出 0、8.15 秒）后复跑结果一致。

## 现场证据与原因判断

工具日志 `%LOCALAPPDATA%\微信开发者工具\User Data\0093999d710c00d7d8055f8e610de85a\WeappLog\logs\` 显示：IDE 以**仓库工作目录**为监听源，反复对源码而非 `dist/` 触发“实时编译”，例如同一分钟内多条：

```
[hybirdLog] compile onFileChange change scripts
[hybirdLog] compile onFileChange change scripts/check-deep-links.mjs
[hybirdLog] compile onFileChange change src/pages/listings/index.vue
```

即 IDE 处于持续重编译状态，小程序实例迟迟没有进入可查询的稳定页面，`currentPage()` 因此不返回。这与仓库 README 已记录的约束一致：Taro 每次 `build:weapp` 会整体重建 `dist/`，IDE 自动热重载可能在目录重建中读到暂时缺文件，必须等 Taro 成功退出后由工具侧完成一次“编译”再断言。本次自动化运行期间本机同时存在编辑器写入与构建，属于该已知竞态。

## 复现与下一步（需要在有界面的工具里操作一次）

1. 停止所有工作区写入与构建，确认 `npm run build:weapp` 已退出 0 且 `dist/app.json`、`dist/app.js`、`dist/pages/index/index.wxml` 存在。
2. 在微信开发者工具中打开 `apps/soloops_weapp`，等待“编译”完成、首页渲染出「经营有据，行动有序。」。
3. 保持工具窗口开启，在仓库根执行 `node scripts/mobile/check_weapp_load.cjs`，应输出 `{"status":"PASS",...}`。
4. 之后再逐页执行读、写、回读与返回流程；本机 AppID 与私有配置不提交。

在完成上述一次 GUI 编译前，不应把任何页面的 IDE 或数据库结论记为通过。数据库持久旅程同样尚未执行：`soloops-wechat` 目录未配置测试库，不得误用其他聊天目录的数据库。
