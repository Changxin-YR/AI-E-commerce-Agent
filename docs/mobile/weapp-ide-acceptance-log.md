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

2026-10-12 20:25 的第二次尝试（重启 `cli auto`，工具报“IDE may already started at port 21740”，随后 IDE 服务监听 61383）在同一位置超时，日志给出了更底层的原因：

```
[INFO] restart appservice compile
[ERROR] https://servicewechat.com/wxa-dev-logic/checkaccountcardaccess?... 系统错误
[ERROR] fetchDevelopLibInfo Error: 系统错误，错误码：41002,appid missing
[ERROR] [fetchAppExptInfo] fail with error: 系统错误，错误码：41002,appid missing
[ERROR] start cli server error: [object Object]
```

即模拟器**没有拿到基础库**：工具要在线拉取开发版基础库（`gettestpublib` / `getexptinfosync`），请求被服务端以 `41002 appid missing` 拒绝，`appservice` 的 `restart appservice compile` 因此没有完成，小程序实例一直不可查询，`currentPage()` 超时。`%LOCALAPPDATA%\微信开发者工具\User Data\<id>\` 下也没有可离线使用的基础库缓存（`WeappSimulator` 只有 WeappFileSystem/WeappStorage/WeappBackgroudData，模拟器未初始化）。

因此这是**环境问题，不是页面代码问题**；第一次尝试记录的“持续实时编译”现象同样源于 `appservice` 未就绪，日志里的 `compile onFileChange` 只是文件监听事件，不能当作编译成功。

## 复现与下一步（需要在有界面的工具里操作一次）

前提：先让开发者工具能正常启动模拟器（用可用的网络与已登录账号打开一次任意项目，或配置可用的基础库版本），确认首页能渲染出「经营有据，行动有序。」。

1. 停止所有工作区写入与构建，确认 `npm run build:weapp` 已退出 0 且 `dist/app.json`、`dist/app.js`、`dist/pages/index/index.wxml` 存在。
2. 在微信开发者工具中打开 `apps/soloops_weapp`，等待“编译”完成、首页渲染出「经营有据，行动有序。」。
3. 保持工具窗口开启，在仓库根执行 `node scripts/mobile/check_weapp_load.cjs`，应输出 `{"status":"PASS",...}`。
4. 之后再逐页执行读、写、回读与返回流程；本机 AppID 与私有配置不提交。
5. 若要让无界面自动化复现，需先准备本地基础库（工具离线包）并在 `project.config.json` 指定该 `libVersion`；仓库保留 `touristappid` 占位，不提交本机账号配置。

在完成上述一次 GUI 编译前，不应把任何页面的 IDE 结论记为通过。

## 数据库旅程（2026-10-12，已完成）

IDE 不可用的同一时段，用隔离 MySQL 跑通了后端全量持久旅程：

- 容器：`soloops-wechat-r2-20261012`（`mysql:8.4`，镜像 sha256:0744ee5…，标签 `soloops.worktree=soloops-wechat`），仅 `127.0.0.1:3313`，库 `soloops_wechat_r2_test`，独立卷 `soloops-wechat-r2-20261012-data`；与 PC 开发库 3307、`mysql-test` 3308 及安卓/其他聊天库完全隔离。
- 连接配置只写在忽略目录 `.local/test.env` 的 `SOLOOPS_TEST_DATABASE_URL`（`conftest.py` 要求库名以 `_test` 结尾，否则拒绝运行）。
- 迁移：pytest 会话夹具执行 `alembic upgrade head`，MySQL 8.4.11 下建成 67 张表。
- 结果：在 `backend/` 执行 `python -m pytest -x -q` → **895 passed，0 failed，7 分 50 秒**；覆盖 `test_overview.py`（20 项）以及 profit、expenses、fee_rules、statements、statement_reviews、order_statement_reviews、settlements、business_rules、authorizations、schedules、product_quality、product_edits、outbound 等微信页面对应的全部业务接口。
- 真实外部通道仍未触碰：夹具强制 `model_enabled=False`、`scheduler_enabled=False`、`outbound_enabled=False`，模型与邮件均为替身。
- 复现命令：

```powershell
docker run -d --name soloops-wechat-r2-<date> -e MYSQL_DATABASE=soloops_wechat_r2_test -e MYSQL_USER=soloops `
  -e MYSQL_PASSWORD=<local> -e MYSQL_ROOT_PASSWORD=<local> -p 127.0.0.1:3313:3306 `
  -v soloops-wechat-r2-<date>-data:/var/lib/mysql mysql:8.4 --character-set-server=utf8mb4 --collation-server=utf8mb4_0900_as_cs
# 写 .local/test.env 后，在 backend/ 运行：
python -m pytest -x -q
```

结论边界：这证明**服务端接口 + 真实 MySQL 持久化**在微信页面所依赖的读/写/回读语义下全部通过；它**不能**替代微信 IDE 内的页面交互与渲染验收，后者仍卡在基础库下载。
