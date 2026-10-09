# 项目理解与面试知识点

本文件将问题对应到实际实现，随功能扩展更新。简历只描述已验证的能力，不把计划或测试替身写成生产成果。

## 为什么采用三层架构？

接口处理 HTTP；服务处理一个业务用例的权限、规则与事务；repository 处理数据库查询。修改 API 展示格式不会改变 SQL，改用其他模型供应商不会改变金额计算。阅读顺序是路由 → 同名 service → repository → model → 对应测试。

面试追问：与 MVC 有什么区别？MVC 更关注展示与交互组织；这里按职责和依赖方向划分后端。三层不是三个进程，也不需要微服务。

## 为什么没有把所有东西封成通用基类？

封装重复且稳定的规则，如密码处理、当前用户、数据库会话和错误响应。商品导入、审批等业务动作应有表达用途的函数名。只有重复出现且语义相同时才提取通用逻辑，避免读代码时不断跳转抽象层。

## 为什么使用数据库会话而不是把令牌留在 localStorage？

随机会话令牌放 HttpOnly Cookie，数据库只保存令牌摘要，支持注销与密码恢复时立即撤销。Cookie 自动携带，因此还需要 SameSite、来源检查和 CSRF 令牌。HTTPS 部署使用 Secure Cookie。会话有过期时间，不在日志里记录令牌。

## 事务、唯一约束和并发分别解决什么？

事务保证一次业务操作要么整体提交，要么整体回滚；唯一约束保证并发请求最终也无法写出重复业务键。应用层先查能给友好错误，数据库约束才是最后防线。后续订单行、审批和幂等任务都要遵循这一点。

## 如何证明功能是真的完成？

单元测试证明确定性规则，MySQL 集成测试证明约束与持久化，浏览器 E2E 证明用户可以完成流程。外部动作还需要授权、通道回执与结果回查。合成数据测试、用户真实文件验证和真实平台验证是不同证据等级。

## 为什么导入需要预览版本与数据库当前读？

`ImportService.preview` 保存映射、逐行结果与店铺数据版本；`commit` 在行锁后比较版本。用户检查预览期间可能有人导入另一批数据，旧预览不能直接覆盖新记录。MySQL 默认 REPEATABLE READ 的普通 SELECT 可能继续读取认证时建立的快照，所以受锁保护的业务判断使用 `SELECT ... FOR UPDATE` 当前读。`test_concurrent_commits_have_one_effect_even_after_auth_snapshot` 特意预先建立快照，证明重放只有一次副作用。

## 如何撤销乱序导入且不丢失后续数据？

`import_rows` 留存每批的规范化版本，当前 `products/order_lines` 只保留有效投影。撤销时按业务键查找仍有效批次的最新提交版本，而不是机械恢复“上一条旧值”。否则先撤销 A，再撤销覆盖 A 的 B，会错误复活 A。相关测试覆盖最新批次恢复、旧批次清除及独立 SKU 保留。

## 为什么金额不用浮点数，历史 JSON 又保存字符串？

`Decimal` 和 `Numeric(18,4)` 保持十进制精度。历史规范化 JSON 采用四位小数字符串，避免 JSON 数字经过浮点解析后改变数值；比较时统一格式，所以 20、20.0 是相同记录。前端只展示这些字符串，后续聚合继续在确定性业务服务计算。未知费用用空值，不能用零掩盖缺失。

## 文件安全为什么不只看扩展名？

`import_parser.py` 同时限制输入字节、ZIP 解压大小、实际单元格坐标、行列与字段长度，并拒绝宏、外链和公式。defusedxml 防止实体扩展；只读解析避免执行 Office 内容。报表中的指令仍是文本。源值与修正值分开留存，批次清除则移除源内容，安全和可追溯性各有明确边界。

## 缺数据时为什么不能把已知收入减已知成本当成毛利？

两组金额可能来自不同订单行。`profit_calculation.aggregate` 同时保存已知行数与部分合计，毛利只从收入和成本都已知的配对行求和。只要完整范围存在缺口，完整毛利即为 null。测试 `test_two_skus_partial_coverage_no_mismatched_subtraction` 证明缺成本 SKU 不会污染另一个 SKU 的可验证毛利。

## 确定性问数如何与模型职责分开？

受控问题经过白名单映射进入 `AnalyticsService.run`，用有类型的店铺、时间、币种、身份和阈值调用 repository。金额来自 Decimal 计算，模型未来只能解释已验证结果。当前返回 `local_rules`，未接入真实模型。`test_decimal_refunds_and_repeatable_question_with_evidence` 比较不同入口的数值与原始引用；不要求文案逐字相同。

## 缓存失效和隐私清理为什么都需要？

`shops.data_revision` 判断旧分析是否能作为现值；`analysis_sources` 决定删除某批数据应清掉哪些持久快照。仅增加版本号不会删除源内容，仅删源行又可能留下派生信息。`AnalyticsRepository.invalidate/purge_batch` 与导入在同一事务里执行，独立结果保留。查看保存分析时可区分 current、stale 和 cleared。

## 为什么提交后读取响应也会影响并发？

提交会释放锁，后续读取可能重新开启事务并持有新的锁。若先拿待办锁，再调用用例拿用户锁，就可能与另一个先拿用户锁的请求形成环。当前保存服务在提交前组装响应，遵循统一锁顺序。测试真实 MySQL 并发并预先建立旧快照，覆盖常规顺序测试无法暴露的问题。

## Listing 为什么同时需要候选版本和比较基线？

`ListingService.decide` 检查用户看到的状态版本和候选生成时的本地生效版本。只检查候选本身不能发现另一候选已先批准。`test_competing_candidates_do_not_overwrite_newly_approved_baseline` 同时批准两个候选，证明一个成功、另一个返回 409。编辑新增历史版本，批准前不改商品事实或原生效文本。

## 可注入生成器是否等于真实 AI 已接入？

`ListingGenerator` 只定义传入名称/参数、返回有类型内容的边界。默认实现是 `local_template`，测试替身标记 `test_double`。依赖覆盖证明虚构声明会被业务检查挡住，但不是模型推理或平台调用的证据。真实适配器、调用预算与实际回执需要独立实现和验证。

## 为什么完整原文覆盖检查后还要人工确认？

`check_content` 只能证明候选选用了完整来源行，不能证明来源真实、合法或适合发布。页面显式显示这一范围，用户要核对事实、差异和影响。任意新增断言先阻断批准；生成器输出与人工修改经过相同规则，不由生成器决定自己的权限。

## 为什么清除来源还要处理修改前的值？

一份版本快照可能用新批次写候选，同时复制旧批准版本作对比。若只关联新来源，删除旧批次后仍会在差异中泄露旧正文。`ListingService._save` 合并当前来源、基线与复制版本的批次集合；`ListingRepository.purge_batch` 清掉整份依赖快照，其他 SKU 独立结果保留。来源失效也不会因撤销覆盖批次而自动恢复审批。

## 客服为什么保留多个意图？

`support_rules.classify` 独立匹配每类诉求，物流和退款可以同时存在。`prepare_reply` 根据全部意图汇总接管原因；固定物流模板不能覆盖退款请求。当前关键词实现明确标为本地规则，未知意图交人工，未来模型替换需继续遵守同一业务门禁。

## 订单号匹配为什么不等于客户身份验证？

`SupportService.generate` 先按拥有者、店铺、渠道和数据身份取证，再校验人工确认及客户端所见全部订单源行。一个匹配的订单号不能证明发件人拥有该订单；只保存最小订单证据，也不允许模型声称已核验身份。`test_channels_separate_message_ids_and_order_evidence` 和跨拥有者测试证明作用域隔离。

## 政策有效期为什么还需要版本依赖表？

`SupportPolicy` 保存不可变版本和 UTC 有效区间；`ReplyPolicy` 追踪每份草稿实际引用的版本。时间到期使结果失效，删除版本则清除内容，两种动作目的不同。`policy_epoch` 使清除后重新录入成为新版本而非返回已擦除的幂等结果；旧草稿不会复活。

## 人工编辑为什么仍要继承来源清除边界？

回复可以混合来自客户消息、订单和政策的文字。人工改写后无法仅靠词匹配证明哪些信息仍来自某条源记录。`SupportRepository._purge` 因而擦除整份依赖快照和关联，保留无正文审计；其他独立草稿不受影响。

## 库存快照为何需要独立的业务时间与查询时效？

文件导入时间不等于库存盘点时间。`InventorySnapshot.snapshot_at` 保存事实发生时刻；`assess_snapshot` 使用 UTC 判断左闭右开的有效区间，到期即返回 `unknown`。`test_freshness_boundary_threshold_and_zero` 检查截止前一微秒和恰好截止时的差别，也验证零阈值不会把零库存误判成“严格低于阈值”。

## 为什么渠道库存不直接合计？

两个渠道可能引用同一实体仓库；缺少共享库存关系时相加会高估可售。当前以店铺+渠道+SKU 保存投影，按数据身份和渠道分开查询。`test_revoke_out_of_order_and_channel_isolation` 证明撤销通用渠道的版本不会删除另一个渠道同 SKU 的记录；完整仓库分配由后续业务模块承担。
## 今日运营：幂等、审批与来源生命周期

- **为什么待办键不含店铺 revision？** `services/operations.py::task_key` 根据来源集合和规则口径识别同一异常。无关商品导入可以改变店铺 revision，但不应让卖家已忽略的同一消息再次变成待处理；`test_repeated_checks_preserve_disposition_and_unrelated_revision` 验证四种处理状态。
- **业务状态和证据状态如何分开？** `models/operations.py` 同时保存 `status` 与 `source_status`。完成是卖家动作，来源失效是事实变化；撤销导入不会抹掉曾经完成的记录，也不会据此批准过期候选。库存截止用半开区间与服务端时钟判定。
- **如何在 REPEATABLE READ 下保证幂等？** API 认证可能已建立旧快照，因此在统一用户锁之后使用 `FOR UPDATE` 当前读；唯一约束为请求 UUID 和异常键兜底。并发回放只产生一个运行/候选，并发不同编辑一个成功、一个版本冲突。
- **删除如何覆盖自由文本？** `repositories/operations.py::purge_batch` 沿显式依赖同时擦除快照、备注和事件详情。只清原始行会留下人工备注或旧成本的派生内容；测试验证被覆盖批次及独立事项隔离。
- **确定性规则与模型如何衔接？** `operation_checks.py` 只用受控计算与证据，`OperationRun` 保存本次真实输出。当前 `local_rules` 不冒充模型运行；后续技能/模型层应调用业务服务并保留同样的权限、审批、幂等和擦除边界。

## 受控执行：事务、租约与预算怎样协作？

- `agent_skills.py` 的声明为什么不直接执行？声明必须与代码内置契约逐项一致，实际调用由明确的业务服务分派完成。模型只能选择受限意图，不能增加工具、改变权限或取得数据库对象。
- `UnitOfWork.defer_commits()` 为什么重要？复用服务原本会独立提交。执行器把业务写入、依赖和步骤完成放进同一事务，失败回滚；`test_atomic_step_failure_rolls_back_business_write` 验证步骤记录失败时没有残留待办。
- 网络调用为何分三段？`_claim_model → decide → _complete_plan` 先持久化租约和预算，再释放锁调用，最后取锁重新验证。取消、来源变化和旧版本都能阻止结果继续执行；费用仍需记账。
- 超时为什么保留费用预留？供应商可能已处理请求，未收到响应无法证明零消耗。保留未知态并禁止自动重发，可避免恢复任务时重复付费；`test_crashed_model_lease_stops_replay` 覆盖进程中断。
- 安全读取能重试，写入为什么不能照搬？执行器只允许白名单临时数据库错误的只读节点最多三次；写入依靠事务与业务幂等，硬规则拒绝立即结束。`test_transient_reads_stop_after_three_attempts` 验证熔断。
- 如何处理历史派生隐私？`AgentSource/AgentPolicySource` 跟踪批次与政策依赖，清除同时擦除整个相关执行输入、结果和步骤正文。Listing 比较旧值需继承原版本全部依赖，避免只清最新商品事实。

## 新品试算：精度、未知值与可重现假设

- 为什么前后端都保留金额字符串？`schemas/profit.py` 校验后使用 Decimal，`models/profit.py` 使用 Numeric，Vue 输入保持文本而不用 number 自动转换；前端 `decimalText` 仅移除尾零。高精度单价不会在浏览器先损失精度。
- 为什么保本价向上取整？`profit_rules.py` 先从线性费用模型推导精确覆盖价，再用 ROUND_CEILING 到币种最小单位。`test_break_even_rounds_up_and_covers_cost` 同时证明建议价可覆盖、再少一最小单位则亏损。
- 空值和零有何差别？空值仍列在费用缺口中并阻断确定保本价，零需要依据后才从缺口移除。没有费用不能由模型或默认值补成零；零售价的余额率也不能除零或显示 0%。
- 如何使历史可重现？每次存档固定输入、依据与规则版本，服务端按规则重新计算；未来升级公式须继续支持旧规则或显式迁移。`ProfitService._output` 拒绝用新规则悄悄替换未知版本。
- 为什么清除保留请求键？无正文 tombstone 阻止旧网络请求把已擦除内容重新创建；新的独立试算必须使用新请求键。用户锁、当前读与唯一约束共同保证旧 RR 快照中的并发保存也幂等。

## 经营规则：怎样证明记忆真正生效？

- **持久化设置为何还不够？** `BusinessRulesService.validate_scope` 在实际 Operations 检查和 Agent 启动时比较当前规则版本及阈值，旧版本或改参数立即冲突；`test_inventory_age_rule_changes_real_findings` 证明同一份 36 小时前快照在 24/48 小时规则下产生不同结论。
- **恢复旧值为何创建新版本？** `previous_id/restored_from_id` 记录血缘；恢复只是重新采用历史数值，旧审批所依据的版本仍失效。否则撤销后恢复可能使等待中的旧动作悄悄复活。
- **怎样避免保存覆盖？** 客户端携带 `expected_version`，服务端先取拥有者/店铺锁并当前读；`test_concurrent_rule_changes_use_current_read` 验证即使认证已建立 RR 快照，并发也只有一份新规则。
- **模型调用途中改规则如何处理？** `_load` 在模型回写前重新核对引用版本，旧意图丢弃而实际已知成本记账。`test_rule_changes_during_model_call_discard_result` 验证锁已释放、规则可修改、业务动作不会继续。
- **自由文本记忆为什么不能表示授权？** `RuleNotes` 只有限定描述字段，`automation` 仅接受 `manual_only`，执行仍由业务服务和技能白名单决定。经营建议、预算计划和可执行授权必须具有各自可验证的生效位置。
- **前端怎样避免跨范围串值？** `AppliedRules.vue` 在店铺/渠道/身份变更时增加请求序号；较早请求即使最后返回也不再发出 loaded 事件。组件测试覆盖慢请求和加载失败，服务端版本核对继续作为最终保障。

## R1 预授权：权限如何经受等待、并发与重放？

- `AuthorizationsService.create/prepare` 重新检查预览，绑定完整范围、规则与来源版本及内容摘要。店铺 ID 并不足以代表用户同意所有未来写入；对象变化要重新审阅。
- `AgentService._local` 在同一锁和 savepoint 内完成业务写入、消耗与步骤登记。`test_two_executions_compete_for_last_use` 先建立旧 RR 快照再并发，证明最后一次额度只有一个执行成功。
- 时钟在检查和写入期间仍前进。`consume` 在提交前重新验证时效；`test_expiry_during_business_save_rolls_back_all` 证明执行中到期不会留下候选或消耗。
- 撤销授权停止未来使用；`revert` 检查新增候选的保存版本，把未处理候选设为已拒绝。全量校验后同事务修改，避免覆盖人工后续处理；审计保留、额度不返还。
- 输入新增 `authorization_id: null` 会改变序列化摘要。`AgentService.start` 对空值不纳入摘要，`test_previous_unbound_request_hash_remains_replayable` 覆盖升级前 UUID 回放兼容性。

## R2 外发：数据库事务为何不能保证邮件恰好送达一次？

- `OutboundService.send` 在网络前提交发送占用、审批消耗和审计。数据库与邮件服务没有共同事务，本系统保证同一记录至多发起一次 POST；进程中断会保留未知，用只读回查恢复证据。没有响应不表示没有发送。
- `test_two_old_snapshots_only_one_external_post` 先建立两个 RR 快照，验证用户锁与当前读使后一个请求看到已占用状态。`test_dispatch_audit_failure_rolls_back_consent_before_network` 证明数据库提交前失败不会调用邮件供应商。
- 域核验期间用户可撤销、来源可变化、时间可推进。`_grant` 在发送占用前重新核对；到期和撤销测试证明释放锁联网不会放行旧授权。
- Resend 幂等键只保留 24 小时，本地 dispatch_at 长期保留。不能在保留期后使用相同键重新提交未知操作。
- `_match` 要求回执 UUID、双方地址、全文、标签和空抄送/密送全部一致，伪造/错误邮件 ID 不能证明本次成功；查不到也不能证明未发送。
- 通道 delivered 与收件箱可见邮件属于不同证据，人工收件声明明确由用户提供；MockTransport 与合成邮箱只验证状态机，不是实际送达证明。
- 来源清除与网络回调并发时，保留外部结果且不恢复正文；对应 `test_source_clear_during_send_erases_body_but_preserves_external_result`。撤销授权和撤回邮件有不同边界。


## 跨店报表：口径、日历时间与派生内容生命周期

- **为什么跨店只能同币种加总？** `overview_calculation.py::totals` 对币种分组，完整值与已知子集分别计算。未覆盖店铺、空窗口和缺失退款不能当作零；展示实际计入店铺 ID，订单在店铺/币种内去重。
- **为何前日不总等于 UTC 24 小时？** `midnight` 将两端的日历日期分别附加 IANA 时区后转 UTC；`test_calendar_dst_and_nonpositive_base` 验证纽约春季切换日为 23 小时。日期与统计金额的缺口要分别解释。
- **如何避免多个店铺的半新半旧数据？** `OverviewService._shops` 先锁拥有者，再按 ID 锁店铺；读取使用当前读，复用导入的锁序。保存重算并对比每店 revision，防止预览后来源变化。
- **为什么摘要引用两期来源？** 对比值同样属于业务事实。OverviewSource 覆盖本期、对比期、成本、库存与消息引用；清除任意依赖批次都擦除整个摘要快照，保留范围与审计，避免通过对比值还原已清来源。
- **为什么有效期用 DATETIME(6)？** MySQL 默认 DATETIME 可能把小数秒舍入到下一秒，精确到期门禁会短暂延迟。库存源是微秒精度，派生报告的有效期也须保留相同精度，测试在截止瞬间断言 stale。
- **为什么不在统计页直接创建待办？** 查询与持久摘要是可重现的事实服务；运营候选、审批和执行复用已有受控业务流程，页面只链接已有待办并说明其状态是保存时快照。

## 统一工作清单：读取模型与执行门禁如何分开？

- `repositories/workbench.py` 用十种已有记录的 UNION ALL 元数据投影，所有分支先约束 owner；跨店报告用 EXISTS，避免一份摘要出现多行。原业务表保持唯一事实来源，清除不会遗漏一个新的正文缓存。
- `WorkbenchRepository.page` 使用 `(created_at, kind, id)` 严格排序。只有时间戳不足以处理同一微秒创建或不同表相同 ID；游标还绑定筛选摘要。总数按全部匹配记录计算，不用当前 20 条伪装总量。
- 列表显示的状态与执行许可不同：查询按统一 now 判断租约、有效期、规则和政策；真正的审批/执行继续由原服务重新锁定、核验当前版本。`test_expiry_unknown_and_read_has_no_side_effects` 证明读取不会新增步骤、审计或推进 Agent。
- 未知结果与过期来源同时存在时，首页优先显示未知并提供原邮件只读回查入口；不能因为材料已失效就暗示外部动作没有发生。`test_r2_unknown_retains_receipt_path_and_never_submits` 覆盖此情况。
- `WorkInbox.vue` 的请求序号和销毁标记隔离旧范围回包；失败时清除缓存，避免把上一店铺的数据当作新范围。`WorkInbox.spec.ts` 覆盖迟到成功、迟到失败和不可信文本转义。
- `AnalyticsService.change_todo` 给人工核对进度增加期望版本、同目标回放及审计事务；`test_analysis_todo_complete_replay_reopen_and_old_version` 验证完成→重开后旧请求冲突。完成不改变经营事实，来源变更保留 completed 并另标 stale。
- 深链定位不是授权：`deepLink.ts` 只校验输入和可选店铺，真正对象归属继续由服务器校验。R1 授权单独加载指定 ID，R2 仍打开完整外发预览，首页没有通用“全部批准”入口。

## 模型业务生成：怎样在可变表述中保持事实稳定？

- **为何 JSON schema 不能保证事实正确？** `analysis_explanation.py::compose` 再验证事实/建议 ID、唯一性与动作前提，强制保留覆盖与费用缺口。模型只能组合受控事实，金额与原始行始终来自 `profit_calculation.py`。
- **模型如何影响实际业务而不获取写权限？** `AgentService._accept_generation` 将 offer_todo 转为 waiting_approval；`analysis_todo` 仍须代码白名单和单次批准，随后调用 AnalyticsService。verify 回读真实待办，模型返回不能直接创建记录。
- **为何不把整个 AnalysisResult 发给模型？** 其中包含订单号、SKU 和导入来源。`explanation_payload` 投影匿名指标且最多 20 项 SKU，保留全部本地事实供用户核对。用户问题单独告知会原样发送。
- **拒答是否意味着没有收费？** `GenerationReply` 分离 content 与 cost。usage 有效的拒答、incomplete 或非法引用仍记已知费用；未知 usage 则保留预留。`test_generation_protocol_and_charge_classification` 覆盖这两类状态。
- **为什么在网络前提交、回来后又加锁？** 调用期间不能长期持有店铺锁；持久租约防重放，返回时版本/来源校验防止取消或清除后回写。`test_inflight_change_discards_text_keeps_cost_and_never_restores_erased_data` 检查暂停、取消、撤销和清除。
- **如何证明没有把聊天当成业务执行？** `test_question_explains_then_approves_saves_verifies_and_deduplicates` 检查审批前数据库无保存记录，批准后实际 AnalysisTodo 与 SavedAnalysis 存在，重复来源只保留一份待办；审计失败时两者均回滚。

## Listing 模型候选：从文字选择到受控业务版本

- `listing_composition.py` 用 ID 排列完整参数行，服务端构造标题与描述。描述校验集合相等、长度相等，既防重复/伪造，也防遗漏限制；结构化 JSON 只是第一层约束。
- `expected_product_source_row_id` 绑定用户同意发送的具体原文。只保存一个布尔同意无法阻止预览后商品被更新，服务端须在网络前检查来源版本。
- 资料来源和本地生效版本是两个独立并发条件。商品文件未变时另一候选仍可被批准，所以 `AgentService._current_listing` 在调用前和回包后检查 active_id，`ListingService.save_candidate` 保存时再检查。
- Agent 中的候选、Listing 待审草稿、本地生效版本各有真实状态；模型回包不能直接批准生效。`test_model_candidate_diff_approval_readback_dedupe_and_clear` 检查两道审批、回读、去重及清除。
- `test_save_revalidates_active_base_and_rolls_back_on_audit_failure` 验证草稿写入与审计同事务失败回滚；在途暂停/取消/清除用例验证网络请求已产生的费用和正文采纳分别处理。

## 客服模型：怎样保留人工接管与当前证据？

- `compose_support` 将模型意图与本地规则取并集，固定事实 ID 必须完整且唯一。模型省略 refund 或把下一步选为 offer_draft，仍无法擦除敏感诉求和物流缺口；`test_mixed_intents_cannot_downgrade_handoff_or_infer_identity` 验证这个不变量。
- 结构化订单字段留在本地不等于正文已脱敏。`support_request` 使用明确投影，`SupportModelContext.vue` 展示消息和选中政策，告知正文可能含个人信息，并绑定具体源行与政策版本。
- `prepare_candidate` 只允许人工核验的全部当前订单行关联，模型接收的是核验状态而非订单号。新增/撤销订单行改变关联证据，旧候选必须重建。
- 政策有效期会随时间变化，即使数据库没有写入也可能过期。`AgentService._current_support` 和最早 valid_until 在调用、审批和保存门禁重新判断；`test_policy_expiration_rechecked_at_each_gate` 覆盖三处边界。
- 只把模型选中的政策登记为依赖会遗漏已发送但未选中的正文；本实现为全部已发送政策建立关联。来源清除后回包不能复活内容，费用结算与正文采纳独立。
- `SupportService.save_candidate` 在外层 defer_commits/savepoint 下重验准备摘要、去重并保存。`test_save_and_audit_are_atomic` 检查审计失败回滚；重复候选保留人工已编辑草稿，避免把重跑当作重置。

## 多供应商模型：协议转换与业务权限

- `configured_model` 在服务端选择固定官方端点；客户端不能自填 URL，以免密钥被发送到任意主机。`_request` 明确禁重定向和环境代理，错误不包含远端正文或异常字符串。
- `DashScopeChatModel` 仅转换协议与 usage；下游仍校验同一事实编号契约并经过审批。严格 JSON 输出控制结构，事实正确性属于本地业务校验。
- `GenerationReply` 将内容可用性和费用可知性分开。截断或拒答有有效 usage 时仍需记费；超时无 usage 时保留预留，自动重发可能造成双倍费用。
- `reserve_generation` 对供应商声明的最大输出误差增加 10-token 余量；配置费率和 cost_note 随步骤保存。USD 预算折算是审计口径，不能冒充人民币实际账单。
- `test_dashscope_candidate_runs_through_approval_and_readback` 使用 MockTransport 贯通真实业务存储与审批；独立受预算限制的合成联网测试验证凭据和协议。两者证据用途不同。
