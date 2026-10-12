# 微信小程序业务页面实现约定（H11–H21 续做基准）

更新：2026-10-12。本文件供并行开发者对齐已落地页面的写法；W01–W09 的实际源码是唯一权威，冲突时以源码为准。

## 文件布局

- 页面：`apps/soloops_weapp/src/pages/<dir>/index.vue` 与 `index.config.ts`（`navigationBarTitleText`）。
- 页面私有纯逻辑：`apps/soloops_weapp/src/services/<feature>-policy.ts`，只放可离线测试的校验/派生/分组逻辑，不放请求。
- 客户端测试：`apps/soloops_weapp/tests/<feature>-policy.test.mjs`，`node --test` + `node:assert/strict`，直接 `import` `.ts` 源文件（Node 24 类型剥离）。
- 可复用组件：`src/components/`（如 `SourceList.vue`、`ReviewedDelivery.vue`）。
- 参考实现：`pages/overview`、`pages/analytics`、`pages/profit` 同级已有页面；先读 `pages/overview/index.vue` 与 `pages/analytics/index.vue` 再动手。

## 数据与状态

- 复用 `services/session.ts` 的 `account` 与 `api`；请求统一走 `scopedRequest(api, () => (alive ? epoch : null))`。
- 页面生命周期：`useUnload` 置 `alive = false` 并 `epoch++`；`watch` 账号/店铺/会话变化时自增 `epoch` 并清空页面数据，取消选中项与确认态。
- `useDidShow` 只做读取与回读；前台不自动执行业务写入。
- `perform()` 统一忙碌态、错误与提示：错误信息取 `Error.message`，网络结果未知保留恢复入口。
- 金额一律 Decimal 字符串，不在客户端做浮点运算；时间持久化 UTC，展示用 `supportTime(value, timezone)` 并显式传业务时区。
- 分页用服务端游标（如 `before`/`next_cursor`），不足时给出“继续读取”的动作，不静默截断。
- 写入后必须按 ID 独立 GET 回读，不能由 HTTP 200 推断成功；`request_id`/`expected_version`/`expected_revision` 按服务端契约传递，结果未知不更换 `request_id` 重试。
- 删除/清除/撤销类动作：先 `Taro.showModal` 确认，再二次核验对象未变化（`id` 未变、会话仍在），才提交；提交后重新回读并刷新列表。
- 未保存的编辑要阻止切换对象并给出提示；已清除/过期状态不提供写入动作。

## 模板与交互

- 只使用 Taro 原生 `view`/`text`/`input`/`picker`/`switch`/`checkbox-group`/`button`，复用现有 `screen`/`card`/`hero`/`row`/`label`/`hint`/`error`/`badge`/`primary`/`danger` 样式类，不新增设计体系。
- 复杂模板表达式移入 `script` 函数；`picker`/`switch`/`checkbox-group` 事件统一用 `(e as { detail: { value: ... } }).detail.value` 取值。
- 所有写入按钮在 `busy` 或前置条件不满足时禁用；空态、加载态、错误态都要有明确文案。

## 离线验证（提交前必须全部通过）

工作目录 `apps/soloops_weapp`，Node 用 `C:\Users\27363\Desktop\AIEcommerceAgent\.local\runtimes\node-v24.16.0-win-x64`（前置到 PATH）：

```
npm run type-check
npm test
npm run build:weapp
```

格式化：`node C:/Users/27363/AppData/Local/npm-cache/_npx/83e71da30ae7cab2/node_modules/prettier/bin/prettier.cjs --write --single-quote --no-semi <files>`；`git diff --check` 必须无输出。

仓库根另跑（后端 venv）：`backend\.venv\Scripts\python.exe scripts\validate_ui_contract.py` 与 `backend\.venv\Scripts\python.exe -m unittest discover -s scripts\mobile\tests`。

## 共享文件与写入边界

- `src/app.config.ts`、`src/services/navigation.ts`、`src/pages/index/index.vue`、`docs/mobile/wechat-implementation-progress.md`、`docs/mobile/wechat-account-handoff.md`、`docs/development.md`、`docs/feature-matrix.md`、`docs/interview-guide.md`、`docs/references.md` 由主协调者统一登记，功能开发者不要写。
- 需要新路由时在 `index.vue` 顶部注释标注 `// route: /<web_route>`，并回报“需注册路由 `/xxx`”。
- 不执行 `git add`/`git commit`/`git push`，由主协调者按包提交。
- 不触碰仓库内其他目录（PC `frontend`、`backend` 业务代码除非确有缺陷并先回报）、其他端工程与本机配置；真实付费模型、邮件和平台写入只用隔离替身。
