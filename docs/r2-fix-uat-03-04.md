# R2 修复包2：日期输入与任务连续性

日期：2026-10-10。包1准确 SHA CI 成功后开始。本包本地验证通过，等待独立提交的准确 SHA CI。测试使用新隔离库 `127.0.0.1:3313/soloops_r2_fixes_test`，全部资料为合成数据。

## 修改与理由

- `BusinessDateTime.vue`、`BusinessDateRange.vue`、`businessTime.ts`：原生日期与时间选择、IANA 时区和最终范围回显，适用分析窗口提供最近7/30天（明确每天24小时）快捷选择，B1保持固定7天。高级 ISO 入口保留 Z、明确偏移和微秒原文；显示转换不改写保存值。选择器不依赖电脑所在时区，夏令时缺口和重叠通过候选 UTC 时间往返匹配拒绝；重叠须使用高级偏移。无效选值阻止提交，不能沿用旧有效时间或静默变成未填写。
- 分析、Agent、今日运营、导入导出时间、历史成本、客服消息/政策/人工记录、待办截止/证据，以及现有费用/账单/订单核对/结算时间入口复用组件。自然日期总览和调度原有日期/时间控件继续使用。UTC持久化和 `[start,end)` 后端规则不变。
- `AgentView.vue`、`AgentRunReview.vue`：店铺/查询范围/任务对象有可验证链接，已保存任务通过其记录恢复表单和独立只读范围回显。支持既有 execution 与 run 链接，刷新只读；节点推进仍由显式操作触发。历史授权/模型数据许可不复选，继续原任务用原预算/审批，新任务重新核对。来源清除后同时丢弃表单副本；切店重置旧目标和对象。
- `SupportView.vue`、`useRecordLink.ts`、`AppShell.vue`：生成或选择草稿、消息和店铺后写入地址；刷新及浏览器历史定位保存对象。自身 URL 更新保留编辑器；未保存正文/人工记录阻止路由切换，浏览器刷新触发离开提示，提供显式放弃。无权/失效/撤销/清除沿当前服务权限和来源回读，恢复不发送消息。
- 相关浏览器测试更新高级入口的真实操作和预期带店铺地址，全部金额、审批、版本、权限与来源断言保留；新增1440/390日期及连续性场景。运营数据预览修复恢复表单后手机横向溢出。

## 验证记录

启动器为 `backend/.venv/Scripts/python.exe .local/r2-fixes/run.py`，下表命令接其后。后端和浏览器串行，模型/外发/调度关闭；浏览器模型流程使用测试替身。

| 检查 | 命令 / 结果 | 忽略目录中的原始证据 |
|---|---|---|
| 后端门禁 | `pytest tests/test_agent.py tests/test_support.py tests/test_support_model.py tests/test_support_delivery.py tests/test_margin_review.py tests/test_order_costs.py tests/test_analytics.py -q`：144 passed / 77.67秒 | `20261010-193705-pytest-1e9fb2.log` |
| 前端单元 | `npm run test:unit`：137 passed；末次新增无效显示断言后，businessTime/AgentRunReview/OperationModelContext三文件16 passed，合计138个不同用例有通过覆盖 | `20261010-193018-npm-a5e409.log`、`20261010-194008-npm-857395.log` |
| 最终Agent与连续性 | `npm run test:e2e -- continuity.spec.ts agent.spec.ts margin-review.spec.ts support-model.spec.ts listing-model.spec.ts operations-model.spec.ts analysis-model.spec.ts`：18 passed / 1.1分钟 | `20261010-193957-npm-f40fe7.log` |
| 日期相关业务 | continuity/expenses/fee-rules/order-reconciliation/statements/statement-reviews/settlements/operations：20 passed / 1.1分钟 | `20261010-193519-npm-2a9927.log` |
| 原四MVP | foundation两尺寸和analytics四场景6项通过；support四场景随后通过，最终CI再完整覆盖 | `20261010-192640-npm-34038a.log`、`20261010-192954-npm-cc15d0.log` |
| 静态与构建 | Ruff check及258文件format；mypy176；最终ESLint、TypeScript和E2E前置生产build均通过 | `20261010-193605-python-*`、`20261010-194008-python-826900.log`、`20261010-194008-npm-155095.log`、`20261010-194008-npm-833c9e.log`及最终E2E日志 |

浏览器新增4项覆盖1440/390：纽约DST缺口/重叠拒绝、显式偏移选择、7/30天精确跨度；暂停任务刷新前后版本/步骤完全一致且未新增任务；恢复后审批落盘；切店/前进后退；草稿编辑保存、离开保护、刷新和历史回读；跨店无权、撤销失效、清除快照。原模型流程额外断言历史恢复后新任务许可未勾选、启动按钮关闭，原任务当前节点审批仍可继续。原B1两次内部写入及全部数值断言通过。桌面和手机截图保存在任务tmp，已目视核对。

独立进程只读回查 `uat34-readback.json`：店铺543/546、任务406/407，各3个实际执行节点，最后清除后 blocked/cleared/input NULL；对应草稿66/67和68/69均cleared、snapshot NULL，保留human_review状态及版本。业务测试在清除前已断言任务succeeded、正文保存回读和外部未提交。迁移仍d93f6b210ac4。

初轮发现旧测试定位ID已被公共日期组件替换、旧URL断言未包含新增shop参数、B1旧run参数兼容、当前店铺重复选择及手机恢复表单溢出，均按真实输入/导航行为修正，保留业务断言。历史导航须等待当前读取完成，忙碌时守卫给出提示；未保存编辑须保存或明确放弃。原137全量前端之外最后只复验受影响模块；失败运行不计作整轮通过。

## 数据与回退

无新依赖、数据库迁移或批量数据更新；head仍 `d93f6b210ac4`。后端接口和权限/审批/预算/幂等服务不变。回退本包前端代码即可，已保存任务和草稿由原表保存，精确时间仍由原接口接受；URL旧execution/run链接可继续使用。没有新增模型付费、真实邮件或平台写入。
