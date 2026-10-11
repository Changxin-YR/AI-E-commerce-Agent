# SoloOps 微信小程序最小工程

Taro 4.3.0、Vue 3.5.43、TypeScript 5.9.3，Node 24.16.0 / npm 11.13.0。
采用 Taro Vite runner 4.3.0 的 Vite 4 peer 依赖组合：Vite 4.5.14、
`@vitejs/plugin-vue` 4.6.2、`@vitejs/plugin-vue-jsx` 3.1.0。
`package-lock.json` 锁定解析结果，CI 用 `npm ci`。

```sh
cd apps/soloops_weapp
npm ci
npm run type-check
npm run build:weapp
npm audit --json
```

编译目录为 `dist/`。微信开发者工具导入本目录（`project.config.json` 指向 `dist/`）。
`touristappid` 仅为本地工程占位，真实 AppID 和私有工具配置由开发者本机提供。
合法域名校验保持启用；本页没有网络、登录、上传或 AI 调用。
开发工具加载和模拟器运行必须单独验收，编译成功不代表已在工具内运行。

当前 npm 审计仍失败，详见 [`依赖审查`](../../docs/mobile/dependency-review.md)。
这些问题阻止生产发布放行；本阶段只记录最小编译可行性。不可对审计建议直接使用
`--force` 将 Taro 降级到 1.x/3.x，或把 Vite 升至不满足 peer 约束的版本。

## 开发者工具启动页复核

先编译本工程，在 IDE 导入此目录。以下命令在仓库根目录执行，
`$weappCli` 设置为本机微信开发者工具的 `cli.bat` 绝对路径：

```powershell
npm install --prefix .local/weapp-tools --save-exact miniprogram-automator@0.12.1 --no-audit --no-fund
& $weappCli auto --project (Resolve-Path apps/soloops_weapp).Path --auto-port 9420 --trust-project
node scripts/mobile/check_weapp_load.cjs
```

检查只读取启动页路径、SoloOps 标题和 M0-A 说明，超时55秒，结束时仅断开自动化连接。
它不执行登录、上传或发布。IDE 加载与自动化通道分别记录：界面须实际显示 `pages/index/index`、SoloOps 和 M0-A；
自动化必须完成页面断言才能标记该脚本 PASS。最新结果见 M0-A 报告。

## 开发工具热重载

`npm run build:weapp` 完整重建 `dist/`。IDE 自动热重载可能在目录重建中读取到暂时缺失的
`comp.js`、`babelHelpers.js`、`taro.js`、`app.js`。先等 Taro 命令成功退出、确认这些文件存在，
再点击微信开发者工具“编译”进行完整编译。不要在构建进行中把临时缺文件错误当作最终结果。
持续编辑可使用 `npm run dev:weapp`；完整构建验收仍单独记录命令、退出码与产物。

真实 AppID 由开发者本机提供。提交时显式选择任务文件，保留本机 `project.config.json`
和 `project.private.config.json` 设置，不把账号关联配置包含在工程验收提交中。
