# P2-01：首页 B1 来源有效性修复

日期：2026-10-10。起点 `ef3eaa6b8ce2b0086e733270ec2f07f9331d9573`；本包新证据独立记录，全部使用合成数据。

## 缺陷与修复

B1 已完成 metrics → margin_evidence、读取缺少 `Capacity: 400ml` 的本地 Listing 后，用户批准新 Listing。原首页仍返回 current / attention；访问 Agent 详情才使来源变为 stale。原失败测试 `test_b1_inbox_reflects_changed_listing_before_opening_task` 的 `current != stale` 记录在 `.local/r2-fixes/20261010-184828-pytest-c4c1f3.log`，原专项验收证据保持。

- `backend/app/repositories/margin_sources.py`：关联 EXISTS 只定位该任务已完成的 margin_evidence 中真实存在的 Listing 依赖，核对所属用户/店铺、批准版本、当前商品事实及已提交的来源行/批次。未选择商品、无可执行内容证据的任务不会被其他 Listing 审批误判失效。
- `repositories/workbench.py`：将谓词并入现有来源投影，列表、分类统计、筛选、分页和最近执行使用同一计算结果。GET 只读取，不持久化 source_status、不新增审计、不推进任务。
- `repositories/listings.py`、`services/margin_review.py`：B1 详情和审批/执行检查复用相同谓词。原用户/店铺锁、版本冲突、旧审批阻断、历史结果、幂等、清除传播均保持。详情按既有机制记录失效；首页无须先访问详情。
- `backend/tests/test_margin_workbench.py`：10 项新增回归，覆盖首次首页、旧审批前后阻断、查询数固定/只读、分页、重新登录、用户/店铺/渠道/身份隔离、独立商品、完成历史/清除、暂停恢复、新基线、无 Listing 分支和来源回退。
- `frontend/e2e/margin-review.spec.ts`：原 1440/390 双结果流程后，批准新版本并先读取首页，检查需要更新数据计数和刷新；页面使用既有 WorkInbox，无业务 UI 改动。

## 本地执行证据

环境为全新 MySQL 8.4.11，`127.0.0.1:3313/soloops_r2_fixes_test`，容器 hostname `189d09af3aee`。启动器 `backend/.venv/Scripts/python.exe .local/r2-fixes/run.py` 固定连接并关闭真实模型/邮件/调度。后端和浏览器串行；历史测试/业务实例不连接、不重置。

| 检查 | 命令（启动器之后） | 实际结果 |
|---|---|---|
| 定向后端 | `pytest tests/test_margin_workbench.py tests/test_margin_review.py tests/test_workbench.py tests/test_workbench_views.py tests/test_operation_rechecks.py tests/test_agent.py tests/test_listings.py -q` | 125 passed / 90.25 秒；日志 `20261010-185531-pytest-e2bde3.log` |
| 后端静态 | `python -m ruff check app tests migrations scripts ../scripts`；同范围 `ruff format --check`；`python -m mypy app` | 通过，258 文件格式、176 app 文件类型；日志 `20261010-185551-python-*` |
| 前端相关单元 | `npm run test:unit -- src/__tests__/WorkInbox.spec.ts src/__tests__/MarginReviewEvidence.spec.ts src/__tests__/AgentRunReview.spec.ts` | 8 passed；日志 `20261010-185601-npm-4bfe79.log` |
| 前端静态/构建 | ESLint、TypeScript、build | 接续前同前端代码已通过；日志 `20261010-185140-npm-a10293.log`、`20261010-185238-npm-72c019.log` |
| 浏览器 | `npm run test:e2e -- margin-review.spec.ts workbench.spec.ts seller-navigation.spec.ts` | 7 passed / 28.5 秒，含 1440/390 B1 双写、首次首页与 19 路由；日志 `20261010-185802-npm-70c252.log` |
| 准确提交 CI | 待本包提交后回读 | 待验证 |

修复过程：初次扩展回归 119 passed / 2 failed，原因是新增测试将登录退出应有审计当作 GET 写入、及测试标题缺少原商品事实；修正测试输入和审计观察边界后，最终上述 125 项通过。沙箱本机连接限制和 Vitest 临时目录 rename EPERM 分别通过已授权的隔离库网络执行、任务内临时目录解决，相关环境失败日志保留，不计作通过。

业务断言：新 Listing 批准后，首次首页 stale / update_data；22 个同类任务统计为 22、分页 20+2，任务数增加不增加 SQL 往返；GET 前后 AgentExecution/AgentStep/ListingVersion/AuditEvent 保持。旧审批返回 409，最新版本 advance 进入 blocked/source_changed 且不追加写入；暂停旧任务不能 resume，新任务读取新基线。无内容证据的成本分支仍能审批落盘。已成功任务的结果 ID/步骤保持，来源 clear 后不再进入 update_data，仍按 cleared 历史回读。

## 迁移与回退

无新依赖、表或迁移，head 保持 `d93f6b210ac4`。只修改查询与共用判断，不批量更新既有任务或 Listing。回退本包代码即可恢复原行为（首页展示缺陷也将恢复）；既有业务历史、审批和内部结果保持，不需要数据库降级。新测试数据仅在本轮隔离库。

本包只关闭 P2-01；UAT-01～04 后续状态见 [修复进度](r2-fix-progress.md)。原真实样本及公网门禁继续独立记录。
