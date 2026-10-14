# SoloOps R2 最终专项验收报告

验收日期：2026-10-10（Asia/Shanghai）。范围：A1—A4、B1—B3、C；只检查、测试和记录，不修改业务实现。

## 1. 验收基线与判断口径

- 本地 `main`、GitHub `main` 均为 `ef3eaa6b8ce2b0086e733270ec2f07f9331d9573`；最后业务代码为 `ed30b872e5a89be096e15c550cb46b9b7240ee44`。开始时工作区干净。
- 本轮重新查询了准确 HEAD 的 [CI 38042981433](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38042981433)：`completed/success`，verify 的后端、前端检查步骤成功。该证据与本机专项结果分别列示。
- 依据 `docs/requirements/SoloOps-R2.md`、三份 foundation 文档、包级计划和当前源码验收。原 74 SO、32 原验收及 47 项长期范围保持。
- 输入全部为明确标记的合成数据和原有模型/邮件替身。**真实样本未验证**：未取得来源可核实的真实脱敏卖家报表；不据此宣称真实 Amazon/Shopify 卖家文件兼容、真实模型输出质量或真实平台执行通过。
- 新建源实例 `soloops-r2-final-20261010`，`127.0.0.1:3311/soloops_test`；新建恢复实例 `soloops-r2-restore-20261010`，端口 `3312`，独立卷。测试没有连接、重置或迁移 3307/3309 业务或历史验收库，也未复用 3308 测试数据。
- 测试按后端→专项→页面→全站 E2E→备份恢复串行使用源库。新的付费模型、真实邮件及平台写入均为 0。业务代码、迁移和原测试未改动。

**最终判断：本地合成范围有条件通过，不作“R2 全部无条件完成”签收。** 原完整回归全部通过；新增专项有 1 项已复现的 P2 首页状态缺陷。真实卖家样本与公开部署证据缺口仍保留。当前 R2 备份恢复已在本轮通过。

## 2. 分级问题与未完成条件

### P0 阻断

目前已执行场景未发现数据丢失、导入重复累计业务金额、越权写入、旧审批绕过或把本地操作标成真实平台执行的 P0 缺陷。结论仅适用于本报告实际覆盖的合成范围。

### P1 重要：验收条件缺口

| 编号 | 条件/影响 | 证据与处理要求 |
|---|---|---|
| P1-01 | **真实样本未验证**。不能对“个人卖家拿真实报表即可独立经营”作最终业务签收。Shopify 商品只验证了官方字段子集的合成输入；Shopify/Amazon 订单预设仍条件延期。 | `docs/r2-a1-3-acceptance.md:9`、`backend/app/services/import_presets.py`、`examples/imports/README.md`。后续需合法脱敏文件、报表类型/日期/原始字段及逐行对账；这不是 47 项长期功能开发的启动许可。 |
| P1-02 | C 的公网/真实客户个人信息上线门禁仍未全部通过。当前只能认定本地合成范围。 | `docs/r2-deployment-gates.md:7`：实际 HTTPS、Secure Cookie、未知账号/IP 入口限流、部署密钥/日志/备份访问控制、留存策略及生产配置尚待验证。`backend/app/services/auth.py:56` 的账号锁定不等同完整入口限流。本轮隔离恢复结果另见第 8 节。 |

上述两项属于明确的条件缺口，不虚构为现有本地业务算法失败；它们阻止无条件宣称“真实卖家/公开运营验收完成”。

### P2 优化：已复现缺陷与操作门槛

**P2-01：B1 的 Listing 基线改变后，首页暂时仍显示来源有效。**

1. 建立合成商品和订单，录历史成本 1；当前本地 Listing 缺 `Capacity: 400ml`。
2. B1 完成 `metrics → margin_evidence`，位于 `ready/product_context`。
3. 另行批准一个包含完整参数的新 Listing。
4. 先读 `/api/workbench`：仍是 `source_status=current`、`view=attention`。
5. 再读 `/api/shops/{shop}/agent/runs/{id}`：变为 `source_status=stale`；再次读首页才进入 `update_data`。

根因位置：`backend/app/repositories/workbench.py:141` 的 `agent_statement` 只派生规则/到期失效，未核对 B1 所依赖的当前 Listing；`backend/app/services/agent.py:130` 的详情读取才调用 `MarginReviewService.require_current`；后者位于 `backend/app/services/margin_review.py:134`。首页分类在 `backend/app/repositories/workbench.py:413`。

实际失败：`test_b1_inbox_reflects_changed_listing_before_opening_task`，`assert 'current' == 'stale'`。完整输入和前后响应在 `.local/r2-final/b1-inbox-stale.json`，失败日志 `.local/r2-final/20261010-182137-pytest-cc5f8e.log`。保留失败测试，未修实现、删测试或降低来源约束。

影响：卖家从首页看到的待办类别与真实可执行性不同，需打开任务后才知道要重新复核。执行门禁仍有效：`agent.py:331` 拒绝旧审批，`:377` 将旧来源继续执行转为 `blocked/source_changed`；未观察到第二项业务写入或虚假完成。建议后续让首页与详情共享来源有效性规则。

**P2-02：大文件入口存在可执行路径，但要求命令行操作。** `frontend/src/components/ImportGroups.vue:154` 引导进入 backend、替换文件路径运行 Python、读取清单并逐片确认。实际 CLI 和桌面/手机分片页面可运行，但没有普通卖家独立操作的可用性测试。对于已完成本地安装且能运行命令的用户，路径可完成；不能仅凭自动化宣称所有个人卖家可独立完成。可改进路径选择、拆分进度和失败恢复引导，不需要扩大导入安全限制。

**P2-03：可导入容量与可分析容量不同。** 拆分支持最多 40000 行，经营分析/运营/总览存在 10000 行读取上限，部分核对页为 1000 行。超限已正确拒绝且未返回截断报告；建议在建组时提前提醒分析容量。对单日超 10000 行，总览仅日期筛选的“缩小范围”并不能覆盖该日完整结果；当前并无自动汇总多个分析窗口的能力。

## 3. R2 对应矩阵

“通过”均限定于本次合成和替身场景；条件延期不计算成真实业务完成。

| 包/要求 | 本轮证据 | 判定及遗漏/部分项 |
|---|---|---|
| A1-1 映射、个人模板、预览、人工纠错、错误导出 | `test_imports.py`、`test_import_review.py`；导入 E2E | 合成通过。复用既有模板和批次；不要求改原表头。 |
| A1-1 金额/状态歧义、缺稳定行标识、币种/时间与安全边界 | 同键跨身份/渠道拒绝；BOM、非 UTF-8 指引、公式/宏/外链、退款/错列用例 | 合成通过。非 UTF-8、多工作表仍需用户转换/选择；未扩成通用解析器。 |
| A1-2 >2000 行、跨订单/跨片去重、失败重试、撤销恢复 | 原 2002 源行场景；新增 10001 行真实 CLI→6 片→API→SQL 对账 | 通过，见第 4 节。普通卖家独立可用性待验证。 |
| A1-2 部分覆盖与超分析上限 | 未完组 409 `partial_coverage`；10001 行三个 API 422；1440/390 页面错误 | 通过。保留容量上限，完整大报表汇总有范围限制。 |
| A1-3 平台预设 | Shopify 当前商品字段子集、补币种/变体名、停用回退 | **部分/条件延期**：Amazon/Shopify 订单预设未完成；S7 真实样本未验证。符合 R2 允许延期条款。 |
| A2 当前成本估算与订单行历史成本两模式 | `test_order_costs.py`；同 SKU 四处对照；旧报告快照 | 合成通过。无凭据保留未知，卖家凭据不是系统独立认证。 |
| A2 多时点、退款、异币种、费用去重、版本/撤销 | 48.97/11/37.97、成本修订、退款不恢复成本、重复费用不二扣、来源撤销清除用例 | 通过。不存在完整净利润/COGS 或隐式费用分摊承诺。 |
| A2 跨页口径 | 经营分析可选两模式；今日运营/总览/AI 自由问数固定当前成本；B1 可选两模式 | 有解释的能力差异，未发现同口径算错。历史成本自由问数和总览切换尚不提供。 |
| A3 六类业务状态、四种异常及复检 | `test_operation_rechecks.py`、`test_workbench_views.py`；四流程里旧完成与新复检并存 | 合成通过。人工核对不自动成为已解决；新来源仍异常、时效不足、撤销/清除/重开均受控。 |
| A4 五组导航、三类收件箱、旧 URL/深链/历史 | `seller-navigation.spec.ts` 19 页、工作台/Agent/基础连续流程 | 主要路径通过；**P2-01 跨包来源展示缺口未关闭**。 |
| B1 现有状态机与真实内部技能组合 | `test_margin_review.py`、新增五边界；混合分支 7 节点、两个独立审批与真实业务 ID | 核心通过。只核对一个选定商品的明确参数行与有效本地基线；缺基线合法停止。 |
| B1 拒绝、幂等、来源变更、权限、预算、熔断和恢复 | 原 Agent/模型/B1 测试；成本更新后第一结果保留、第二写入阻断、新任务可重新复核 | 通过。预算/模型异常以替身验证；本轮未新增付费模型验收。 |
| B2 已批准版本复制/通用导出、来源与公式安全 | `test_listing_delivery.py`、Listing/统一旅程浏览器 | 本地人工交付通过；平台专用格式与真实刊登未实现且没有伪称。 |
| B3 已审草稿、消息/订单/政策、人工自报与隐私 | `test_support_delivery.py`；混合诉求接管、实际剪贴板/CSV、刷新回读 | 合成通过。未发送状态保持，人工证据标明 `seller_reported`。 |
| C/F-08 调度依赖、最近周期、漏跑/合并/实际状态 | `test_schedules.py`、`ScheduleRuntime` 单元、调度浏览器 | 通过合成和生命周期测试；未声称 24 小时在线。 |
| C/F-09 修改处可维护性 | import_groups、margin_review、manual_delivery、support_delivery 独立职责；Ruff/mypy | 分层保持；本轮没有大规模重构。 |
| C/F-10 上线门禁与当前 R2 恢复 | 门禁文档 + 本轮新实例备份恢复 | 条件验收；部署与真实数据门禁见 P1-02。恢复结果见第 8 节。 |

## 4. 大报表专项

原 `test_large_group_reconcile_retry_correct_revoke_and_restore` 随 870 项回归通过：2002 源行拆成 2000+2，跨片订单、1 重叠行，2001 唯一业务行；1 取消行排除销售，0 数量错误阻断整片，修正后销售 4000。成功片重传复用原批次；单片撤销导致部分覆盖，原片恢复；组外更新销售 3 在整组撤销后仍保留。原子撤销故障、同键异值、来源/映射不符、过期/清除与并发保护也在原套件内通过。

新增实际 CLI 命令（在 backend 下，由验收脚本调用）：

```powershell
.venv\Scripts\python.exe -m scripts.split_import "C:\Users\27363\Desktop\AI E-commerce Agent\.local\r2-final\large-6a324d86.csv" "C:\Users\27363\Desktop\AI E-commerce Agent\.local\r2-final\large-6a324d86"
```

实际输出：`已核对 10001 个源记录、6 个分片。` 分片行数为 `2000/2000/2000/2000/2000/1`。所有片上传→预览→提交，并各重传一次；最终 `complete=true`、`unique_rows=committed_rows=10001`，SQL `COUNT(*)=10001`、`SUM(quantity*unit_price)=20002.0000`。无截断、无重复累加。第一片完成时汇总返回 409 部分覆盖。

全量导入后，经营分析、今日运营、总览均返回 422 `range_too_large`，提示包含 10000 行及缩小范围。实际 Chromium 1440/390 两种宽度在经营分析页显示“时间窗超过 10000 行，请缩小范围”，没有旧/虚假分析结果，横向溢出为 false。截图 `.local/r2-final/analysis-limit-1440.png`、`analysis-limit-390.png`，已目视检查手机截图。

证据：`.local/r2-final/large-cli.json`、`large-10001.json`、`browser-limit.json`。代码：`import_split.py:29`、`import_groups.py:13`、`analytics.py:61`、`operations.py:308`、`overview.py:150`。

卖家独立操作判断：技术路径可完成，但需要本地安装、CSV 编码转换、命令行拆分和逐片审阅能力；**普通个人卖家独立完成尚未获得真实可用性证据**。

## 5. 同 SKU 成本与利润对照

固定同店、USD、2026-10-07（Asia/Shanghai）、SKU `001`，2 件×10、折扣/退款均 0；当前单位成本 9.5，卖家确认历史单位成本 1。只含同一来源渠道，排除跨渠道/日期差异。

| 页面/流程 | 采用成本 | 成本合计 | 商品毛利 | 说明 |
|---|---|---:|---:|---|
| 经营分析—当前估算 | 9.5×2 | 19 | 1 | 当前成本回推，非订单时点实际成本 |
| 今日运营低毛利事项 | 9.5×2 | 19 | 1 | 事项 impact 与 facts 明示当前采购成本/估算毛利 |
| 总览 | 9.5×2 | 19 | 1 | 详情 cost_basis 和汇总 warnings 明示当前成本估算 |
| AI 经营问数（模型替身规划/解释，真实业务服务计算） | 9.5×2 | 19 | 1 | AnalysisEvidence/Narrative 展示当前估算依据 |
| 经营分析—历史成本及本页受控问题 | 1×2 | 2 | 18 | 卖家提供确认，未经系统独立核验 |

结论：本次未发现缺少口径解释的数值冲突。录历史成本后旧保存分析被标为 `stale`，原快照仍与保存时完全一致。历史模式下，经营分析页明确写出 AI 经营问数/今日运营仍用当前估算，并取消该模式的直接 AI 跳转，见 `frontend/src/views/AnalyticsView.vue:202`。总览没有历史成本切换；B1 的默认历史模式需与其他页面区分。

所有上述毛利均未完整扣除平台、物流、广告和税费，不能改称已核实净利润。详见 `.local/r2-final/cost-comparison.json`；核心公式和说明在 `backend/app/services/profit_calculation.py:20`。

## 6. B1 边界与闭环

| 输入/变化 | 实际行为 | 判定 |
|---|---|---|
| 没有历史成本 | 毛利 null、完整排行不可用；批准后创建核对分析和 open 待办，4 步完成内部保存 | 可推进；不会补造历史成本或把待办当异常已解决 |
| 没有有效 Listing 基线，历史成本充分且无低毛利 | `succeeded/margin_no_action`，说明先核对本地基线，0 新分析/Listing 写入 | 合法停止；完成的是本次复核，未声称已改善商品 |
| 商品参数完整且本地已批准版本完整 | `succeeded/margin_no_action`，提示没有可执行遗漏，0 新写入 | 不制造无意义的 Listing 任务 |
| 缺历史成本与参数遗漏并存 | 成本核对和内容建议分列，两个 R1 审批，7 步，analysis/listing 两个 verify ID | 两种以上技能实际调用，写入可回查，无因果夸大 |
| 第一项分析保存后补历史成本 | 旧分析 stale；原任务 advance 返回 HTTP 200 但业务态 `blocked/source_changed`，步数不增加，没有 listing_draft；重新发起得到新依据 | 旧任务不能继续写；已有批准结果保留，正常新建恢复路径 |
| Listing 基线变化 | 详情/审批能拒绝旧来源；首页要打开详情后才同步 | 执行保护通过；展示缺陷 P2-01 |

原套件还验证无订单等待补录、拒绝第二节点保留第一结果、同 UUID 重放/同范围去重、跨用户店铺身份渠道拒绝、R3 篡改阻断、只读失败 3 次熔断、步骤/时间/模型费用预算及独立 Python 进程回读。本轮通过不表示模型有自由扩权或外部执行能力。

## 7. 四条 MVP 与执行语义

以 `frontend/e2e/foundation.spec.ts:101` 的同组合成资料逐步走四流程，覆盖 1440px 桌面、390px 手机。脚本执行真实页面和后端 HTTP，模型解释使用替身；状态落地 MySQL 后另做 API/数据库回读。

| 流程 | 页面步骤与 API | 业务状态/历史核对 |
|---|---|---|
| F-01 今日运营 | 五文件导入→模型替身检查→批准 5 候选→SKU 库存入口→返回原事项→备注完成/重开→重复检查→更新数据复检 | 原 complete 不自动等于 resolved；重检仍异常为 `still_anomalous`，原备注和完成历史保留；5 当前/6 历史不重建重复有效任务 |
| F-02 经营问数 | 同范围分析→订单/退款来源→AI 解释→审批保存分析/待办→完成/重开→来源变化→重算 | 原净销售/成本/毛利 75/62/13；成本修订后当前毛利 10，旧快照保持且标 stale；分析与 todo 均有真实 ID |
| F-03 Listing | 同 SKU 模型替身候选→人工另存→事实审阅→本地批准→复制/CSV→刷新→源变更→旧导出禁用→新版本批准/导出 | 已批准、已替代、来源失效及新版本历史保留；输出含店铺/SKU/版本/来源；旧新下载文件名不同 |
| F-04 客服 | 原混合消息→订单与两份政策核验→人工接管→编辑存档→目标语言/全文审阅→复制/CSV→人工自报→刷新/重新登录 | 原诉求同时含物流和退款；不宣称退款完成，审阅版本及人工证据保留；外部始终 `not_submitted` |

同一连续旅程还覆盖深链店铺/身份/渠道/时间窗、返回原事项、退出重登和总览 USD 87（跨渠道且成本不全）的说明。浏览器成功数与恢复后的业务 ID/历史计数见第 8、9 节。

执行语义审查：

- Listing schema 和 Agent/客服结果的 `external_status` 为 `not_submitted`；`listings.py:109` 只交付当前已批准且来源有效的版本，生成文案明确“本地已批准 · 外部未提交”。
- 客服复制/下载要求当前版本显式审阅；`support_delivery.py:71` 附消息索引、订单关联、政策有效期、语言和接管原因；不复制未核实订单/原始消息个人信息。
- `support_delivery.py:134` 独立登记人工操作；`schemas/support_delivery.py:44` 固定 `provenance=seller_reported` 和 `external_status=not_submitted`。自报不是平台回执。
- CSV 数据格统一文字转义，BOM 与中文/英文内容实际读取验证；缺 GTIN/认证保留待核对。来源变更后的旧版本不能以最新结果继续导出。
- 邮件 accepted/SMTP 接受、unknown、独立收件声明由原邮件测试验证；其替身或历史本人 QQ 证据不能充当真实买家客服或平台刊登证明。本轮没有真实外部执行可签收。

## 8. 当前 R2 备份恢复

**通过。** 源与恢复目标分别在两个本轮新建的 MySQL 8.4 容器、两个新卷内。使用仓库原维护工具 `scripts/database_backup.py`；源写入结束后备份到 `.local/backups/r2-final-20261010/`，目标为新库 `soloops_restore_r2_final_test`。

实际命令：

```powershell
& backend/.venv/Scripts/python.exe .local/r2-final/run.py python ../.local/r2-final/readback.py source
& backend/.venv/Scripts/python.exe .local/r2-final/run.py python ../scripts/database_backup.py backup --service mysql-test --name r2-final-20261010
$env:R2_AUDIT_RESTORE='1'
& backend/.venv/Scripts/python.exe .local/r2-final/run.py docker up -d --wait
& backend/.venv/Scripts/python.exe .local/r2-final/run.py python ../scripts/database_backup.py restore --name r2-final-20261010 --target soloops_restore_r2_final_test
& backend/.venv/Scripts/python.exe .local/r2-final/run.py python ../.local/r2-final/restore_verify.py
& backend/.venv/Scripts/python.exe .local/r2-final/run.py python ../.local/r2-final/readback.py restored
Remove-Item Env:R2_AUDIT_RESTORE
```

源/恢复数据库均为迁移 `d93f6b210ac4`，**67 张表的 COUNT 与 CHECKSUM EXTENDED 全部一致**，SQL 文件 SHA256 由工具校验。重复向同一目标恢复被拒绝，前后 67 表校验未改变；临时 `restore_` 数据库账号数量为 0。验证脚本随后仅为隔离恢复库授予合成应用账号权限，用于 API 回读。

另在独立 Python 进程创建应用、登录合成账号，经真实 FastAPI 路由回读两个基础旅程店铺（764 桌面/766 手机）的 **38 份业务 API 快照**，与源库逐字段完全一致（包括状态、金额、版本、来源、人工记录、步骤和历史）。没有用仅能启动或表数量相同代替数据完整性验证。

| 恢复后的 R2/业务记录 | 行数（与源一致） |
|---|---:|
| 订单行成本版本 `order_cost_revisions` | 8 |
| 导入组 `import_groups` | 2 |
| 运营事项 / 事项历史 | 25 / 70 |
| 保存分析 / 分析待办 | 12 / 10 |
| Listing 版本 | 24 |
| 客服草稿 / 人工操作自报 | 11 / 4 |
| Agent 执行 / 步骤 | 31 / 168 |

代表业务回读（以下 ID 均为本轮隔离合成数据）：

- 桌面事项 #203、手机 #209：`completed + stale + still_anomalous`，各 4 条历史；没有把已完成核对伪装成异常解除。
- 分析 #31/#32：旧依据 `stale`、关联待办 `completed`，原金额快照保留。
- Listing #72/#73 与 #75/#76 已替代且旧来源失效；#74/#77 为 `approved/current`。
- 客服 #43/#44 为 `archived/current`、当前版本已审阅；各人工操作记录仍为 `seller_reported/not_submitted`。
- 8 个基础旅程 Agent 执行保留 `succeeded` 历史，同时准确标记来源 `stale`；没有因新来源改写过去执行结果。

证据文件：`.local/r2-final/readback-source.json`、`readback-restored.json`、对应 summary 与 `restore-verification.json`；备份 manifest 含完整 67 表校验。

日志：`20261010-182939-python-393c3b.log`（源回读）、`20261010-182952-python-5a27ac.log`（备份）、`20261010-183004-python-811055.log`（恢复）、`20261010-183020-python-05d807.log`（拒绝覆盖/账号清理）、`20261010-183024-python-de0dc8.log`（38 快照相同）。

此结果补齐此前 `r2-deployment-gates.md` 中“当前新结构恢复待验”的证据，不代替真实部署备份加密、存取控制、恢复时限和灾备策略验证。验收完成后停止两个专用容器，保留卷和备份供复核。

## 9. 实际命令、结果和失败日志

命令均从仓库根目录发起；封装器 `.local/r2-final/run.py` 清理继承的 SOLOOPS/COMPOSE 环境，固定到上述新实例、关闭真实模型/邮件/调度，输出实际子命令、目录、日志和退出码。运行时为后端现有 Python 3.11.16 虚拟环境、隔离 Node 24.16.0、MySQL 8.4、Chromium。

```powershell
& backend/.venv/Scripts/python.exe .local/r2-final/run.py docker up -d --wait
& backend/.venv/Scripts/python.exe .local/r2-final/run.py pytest -q --tb=short --basetemp=../.local/r2-final/pytest-temp
& backend/.venv/Scripts/python.exe .local/r2-final/run.py npm run test:unit
& backend/.venv/Scripts/python.exe .local/r2-final/run.py npm run lint
& backend/.venv/Scripts/python.exe .local/r2-final/run.py npm run build
& backend/.venv/Scripts/python.exe .local/r2-final/run.py python -m ruff check app tests migrations scripts ../scripts
& backend/.venv/Scripts/python.exe .local/r2-final/run.py python -m ruff format --check app tests migrations scripts ../scripts
& backend/.venv/Scripts/python.exe .local/r2-final/run.py python -m mypy app
& backend/.venv/Scripts/python.exe .local/r2-final/run.py pytest ../.local/r2-final/test_audit.py -vv --tb=short --basetemp=../.local/r2-final/probe-temp
& backend/.venv/Scripts/python.exe .local/r2-final/run.py pytest ../.local/r2-final/test_audit.py -vv --tb=short -k 'changed_after_first_write or actual_10001' --basetemp=../.local/r2-final/probe-rerun
& backend/.venv/Scripts/python.exe .local/r2-final/run.py ui
& backend/.venv/Scripts/python.exe .local/r2-final/run.py e2e
```

| 检查 | 实际结果 | 本机日志（均在 `.local/r2-final/`） |
|---|---|---|
| 原完整后端 | **870 passed**，439.12 秒；1 条 Starlette/httpx 弃用 warning | `20261010-181359-pytest.log` |
| 前端单元 | **128 passed / 36 文件**，8.74 秒 | `20261010-181401-npm.log` |
| 前端 lint、type-check、build | 全部退出 0 | `20261010-181411-npm.log`、`20261010-181425-npm.log` |
| Ruff 规则/格式、mypy | 通过；256 文件格式、175 app 源文件类型检查 | `20261010-181739-python-f56842.log`、`20261010-181739-python-845df2.log`、`20261010-181630-python.log` |
| 新增 8 个专项首轮 | **5 passed / 3 failed**，9.58 秒 | `20261010-182137-pytest-cc5f8e.log` |
| 两个验收脚本契约误用修正后定向复验 | **2 passed**，28.80 秒；原 8 项累计 7 通过/1 产品缺陷失败 | `20261010-182216-pytest-ee813e.log` |
| 10001 行超限页面 | 桌面/手机 **2 场景通过**，9.17 秒（含服务生命周期） | `20261010-182430-ui-262054.log` |
| 全站 Playwright | **78 passed**，4.3 分钟（封装进程 259.25 秒）；0 重试 | `20261010-182448-e2e-a26a40.log` |
| 新环境备份恢复 | **67 表校验相同、38 份 API 快照完全一致**；拒绝覆盖、账号清理通过 | 见第 8 节五份日志 |

失败日志保留及解释：

1. 产品缺陷 `P2-01` 未修复，专项失败断言保留。复现只跑 `-k inbox_reflects`；需使用专用隔离库，因为 pytest fixture 会清空测试表。
2. 新脚本最初把 `advance` 的来源阻断假定为 HTTP 409。现有契约中 `approve` 返回 409，`advance` 返回 200 + `blocked/source_changed`。复验改为核对实际契约，并增加步数不增长、没有 Listing 写入的断言；业务约束没有放宽。
3. CLI 新生成文件名与测试辅助函数的固定 `synthetic.csv` 不同，建组输入被 422 正确拒绝；脚本改成清单的真实源文件名后成功。原约束保留。响应中的空泛“请检查输入字段：”是当前批次级校验反馈的易用性限制。
4. 原生浏览器探针首次未等待登录完成就跳转，30 秒定位超时；日志 `20261010-182323-ui-e490e0.log` 保留。增加登录成功标题等待后两个宽度通过，未改页面或金额/状态断言。
5. 初次默认沙箱读取 Docker 被本机管道权限拒绝；经工具权限升级后仅创建专用容器。没有自动审批拒绝，也没有绕过业务权限。
6. Windows 页面测试助手结束后遗留了 8011/5176 子进程；收尾通过端口和完整命令行核实其属于本轮探针后停止。8001/5174 全站 E2E 服务正常退出，两个专用数据库容器已停止，卷和证据保留。

本机日志、SQL 备份、截图和合成运行数据位于忽略目录，不提交到仓库；验收报告记录可核对路径。没有把测试脚本错误计成产品 P0，也没有把实际状态缺陷改成通过。

## 10. 最终签收判断

1. **P0：未发现。P1：2 项条件缺口（真实样本、部署门禁）。P2：1 项已复现状态缺陷，2 项操作/容量优化。**
2. A1-1/A1-2、A2/A3、B1 核心执行、B2/B3 和 C 的本地调度/恢复部分在实际覆盖范围内通过；A4/B1 首页来源状态存在 P2-01，不能标成专项全绿。A1-3 订单预设、S7 与公网门禁保持条件延期。
3. 四条 MVP 的桌面/手机连续业务流程、API/数据库业务状态、版本与历史回读成立。当前 R2 恢复能力不再只沿用旧版 64 表证据，本轮已取得当前 67 表的独立恢复证据。
4. 个人卖家可沿文档在本地使用合成场景完成业务，但命令行拆分、范围上限和字段语义审阅有操作门槛；**真实样本未验证**，无法签收真实卖家独立使用与真实经营兼容性。
5. 建议保留本轮报告与失败复现，后续仅在另获修复授权时处理 P2-01，并按真实样本/部署条件补验。本轮没有启动剩余 47 项长期开发，没有修改业务代码或已有测试。

报告之外的完整证据索引为 `.local/r2-final/evidence-manifest.json`（文件路径、大小、SHA256）；测试脚本、失败日志、JSON 和截图均可据此核对。本报告为本轮唯一新增的仓库交付文档。
