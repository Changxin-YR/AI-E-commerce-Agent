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

## 运营模型的边界如何落在代码中

- `services/operation_explanation.py`：为什么让模型选择编号？结构化输出只能约束格式，仍需核对 ID、去重并从本地目录恢复全部分支和缺失。模型排序不会改变确定性检查结果，也不能隐藏无数据模块。
- `OperationsService.model_context` 和 `StartAgent.expected_operation_hash`：将页面同意绑定完整预览；不仅检查 revision，还包含库存时效形成的分支。前端请求序号处理迟到响应，状态在重新加载时立即清空。
- `AgentService._current_operations` 与 `RunInput.expected_preview_hash`：网络释放锁后重验当前证据；保存前再次在同一事务中校验，避免批准的是旧候选、写入的是新候选。服务层保留权限，Agent 复用受控接口。
- `test_operations_model.py`：在途取消/清除只影响内容采用，已知费用仍要记账；未知费用保留预留。审计失败回滚业务记录，重跑保留已完成事项，证明幂等不等于重置业务状态。
- `OperationFindingPreview.vue` 与 `AgentRunReview.vue`：候选提供逐行依据；业务深链带身份/渠道，确保从 Agent 回读真实记录后仍能在原业务页面处理。

## 定时调度与事务恢复

- 为什么不用进程内时间表保存任务？`models/schedules.py` 将计划、下一周期、执行与已读状态落在 MySQL；`services/scheduler.py` 只负责有界扫描，进程恢复可以从持久状态继续。
- 多 worker 如何避免重复？`SchedulesService.run_due` 先用户/店铺/计划当前读，再判断到期，周期唯一键保护相同计划时刻。`test_concurrent_workers_commit_one_cycle` 用两个 MySQL 会话验证只留下一个 Agent 执行与一个通知。
- 如何避免重试造成半个业务结果？`UnitOfWork.defer_commits` 把固定检查和通知纳入外层事务；Agent 数据库异常在组合模式下向外抛，原独立请求仍保留既有有界重试。`test_atomic_rollback_then_restart` 和 lifespan 测试分别验证事务与真实后台启动。
- 时区为何不能每天简单加 24 小时？运行时间是当地日历，DST 会跳过或重复时刻。`schedule_clock.occurrence` 用 IANA 时区、fold=0 和 UTC 往返核验；检查数据窗口则明确采用 N×24 小时，两种语义各自固定。
- 调度授权与审批的区别？计划确认仅允许固定本地检查和站内记录；`LocalOnlyModel` 无网络，新的来源仍停在原 Agent 审批。旧 R1 授权绑定快照，不能授权未来周期。
- 通知为何不复制正文？`ScheduleOccurrence.execution_id` 链回原服务，来源清除只需既有 AgentSource 依赖链，通知不保留另一个客户内容副本；不可把周期结束状态当成当前业务审批状态。

## 自然周期报告与服务组合

- `schedule_reports.report_scope` 如何计算月报？先将计划时刻转当地日期，取本月首作为不含的终点，逐次取前月首形成报告和对比期；闰月、年界和 23/25 小时自然日在 test_schedule_reports 中验证。月报不按固定小时数减算。
- `OverviewService._save` 如何同时支持人工与调度？两者共享锁定、计算和依赖保存；人工入口校验 expected_revisions，调度入口由已经确认的计划授权读取当前数据。事实计算、报告持久化仍在受控业务服务内。
- `ScheduleOccurrence.report_id` 如何处理来源清除？只连接已有报告，不复制快照；OverviewSource 追踪本期、对比期、成本、库存和消息依赖，通知深链回读已清除状态。报告、依赖与通知同事务，失败不会留下孤立快照。
- `ScheduleEditor.vue` 为何使用 epoch？报表和巡检使用不同配置语义，旧规则请求可能在切换后才返回。组件测试验证旧回包被丢弃，配置变化立即撤掉同意，切回巡检重新绑定有效版本。

## 商品质量：可解释检查与派生数据生命周期

- `product_quality_rules.assess` 为什么不输出综合质量分？已导入字段只覆盖名称、参数和金额，品牌/编码/图片等未知不能计为合格。逐项 missing/review、固定规则版本和未检查原因使结果可核对；相似 SKU 与同名属性多值只提示人工处理，不替卖家合并或选择规格。
- `ProductQualityService.save` 为什么既验 revision 又验 hash？revision 代表来源变化，hash 还覆盖范围、规则、完整证据与结果；排除计算时间使同一事实可重复预览。保存时重新计算，客户端不能伪造报告正文。
- `ProductQualityRepository.products` 为什么使用 with_for_update 与 populate_existing？在 MySQL RR 和 ORM 身份映射下，普通读取可能沿用旧快照；先用户/店铺锁，再当前读，把保存前核验和来源修改串行化。UUID 唯一键与两个会话竞争测试共同验证幂等。
- `ProductQualitySource` 为什么包含没有问题的商品批次？没有问题也是依赖来源得出的判断，相似 SKU 分组还依赖同组其他商品。任一来源清除必须擦整份结果，不能只登记存在缺失项的行。筛选中的 SKU 前缀也是商品信息，清除时一并擦除。
- `ProductQualityView.vue` 如何避免迟到响应和清除后的屏幕残留？范围改变递增 epoch，响应落地前复验；保存、刷新和清除先卸载快照组件，失败不会保留已失去确认的内容。组件测试覆盖迟到预览、确认重置、保存冲突和来源版本变化。

## 批量修订：投影、审批与完整来源链

- 为什么不能直接更新 Product.name 而保留旧 source_row_id？旧行只证明导入时的事实。`ProductEditService._batch` 建立独立 manual_edit 批次，保存原名称/参数、修订理由和新规范化资料，再通过 ImportService 更新当前投影；原文件事实仍可回读。
- 为什么源行 ID 未变也可能需要拒绝旧审批？来源可能被其他批次覆盖后又恢复。`EditSnapshot.source_revision` 绑定单调递增的店铺数据版本，`test_restored_source_never_reactivates_an_old_approval` 验证恢复旧源行不会使旧批准有效。
- 整批原子操作如何显示逐项失败？审批先检查所有商品，冲突项记录 conflict，其他项记录 blocked；只保存失败报告，不部分改商品。数据库故障或末尾审计错误由外层事务回滚，区别于已持久化的业务冲突。
- 为什么依赖中保存全部祖先？第二次人工修订包含第一次继承的资料，清除原始导入也须擦除二次修订。`ProductEditRepository.ancestors/affected` 物化可追溯集合，`ImportService.withdraw` 后代优先处理，同事务恢复剩余有效投影，避免嵌套提交和恢复已撤销祖先。
- 幂等如何兼容清除？请求只保留 UUID 与散列，重复创建回读当前记录；清除后 snapshot=None，重复请求不能从客户端旧正文重建它。审批只接受版本和 hash，不能重新提交任意 after 值。
- 历史执行成功是否代表现在仍有效？`current_count` 从 Product.source_row_id 当前锁定读计算，页面将“曾执行”与“仍为主档来源”分别展示；后续独立文件导入可以覆盖人工版本，历史记录仍保留实际执行结果。

## 实际费用：版本台账、直接归属与核对边界

- `ExpenseRevision.amount` 为什么用 Numeric(18,4) 而不只放 JSON？强类型十进制持久化保留金额精度；快照只保存其他事实，回读由服务重新组合，不引入两份金额口径。1000 笔合计仍使用 Decimal，币种分组处理。
- 为什么同时检查费用 version、订单 source_row_id 和店铺 data_revision？费用 version 阻断竞争修订；源行绑定确认对象，店铺 revision 阻断覆盖后恢复的旧确认。`test_order_link_scope_currency_and_source_revision` 和恢复测试验证这些边界。
- `ExpenseSource` 为什么保留旧版本来源？改为店铺费用后，旧订单号/金额仍在历史版本中。清除旧批次必须擦整笔历史与金额，依赖集合不能仅保留当前归属。末尾审计故障测试验证来源与费用一起回滚。
- UUID 与凭据去重为什么独立？UUID 解决同一次操作重发，摘要限制重放内容；规范化凭据键阻止新 UUID 重复录入同笔事实。撤销允许显式新录，旧 UUID 仍只能回读原记录，不恢复被清除的数据。
- 已录入实际费用为什么仍不能计算精确净利润？凭据文字只是卖家输入，尚未证明平台账单、物流、回款与费用完整性；店铺费用也未分摊。`ExpenseService.summary` 只返回分币种已知费用合计和覆盖边界，已有毛利与新品假设不受隐式影响。
- DATETIME(6) 和 IANA 偏移验证解决什么问题？UTC 统一持久化、微秒保证初次返回与回读一致；明确时区偏移可区分 DST 重复小时，并拒绝不存在的本地时间。前端始终附 IANA 显示时区。

## 渠道账单：业务键与核对事实的分离

- 为什么账单行键不等于费用匹配键？`import_validation.business_key` 绑定店铺下的身份、渠道、账单号和稳定行号，决定重导覆盖；`evidence.evidence_key` 统一凭据费用行编号规范化，决定两侧比较。不同账单行重复使用一个凭据时必须暴露歧义，不能静默去重或相加。
- 为什么所有行都是正数却有退款？`StatementData.entry_type` 表达经济含义，amount 表达绝对金额；拒绝无法解释的符号净额，销售款、退款、费用、回款分别合计。平台 payout 文件不证明银行到账，也不能再加进销售收入。
- 为什么不把金额相同当作自动匹配？`compare_fees` 只接受同范围的明确凭据编号；重复或异币种不计算差额。只有一对一同币种才使用 Decimal 相减，返回金额字符串和两侧版本/原行证据。
- 为什么只读结果也加锁？费用与账单可被其他请求修订；`StatementService.reconcile` 按用户/店铺串行化，在同一事务当前读两侧，`test_locked_current_read_refreshes_existing_orm_snapshot` 验证已有 RR 快照也能读到新金额。
- 扩展 ImportKind 为什么要检查下游分派？新类型会进入原有失效链。`OperationsRepository.invalidate` 仍失效整店报告，但四类候选不消费账单，须在模型分派前明确处理账单类型；测试捕获了遗漏的新类型 KeyError。
- 首次返回与重复读取时间为何可能不同？默认 MySQL DATETIME 只有秒精度并可能舍入，Python 对象仍带微秒；迁移将批次三种生命周期时间升级 DATETIME(6)，使提交重放与审计失败后的回读可精确比较。
- 如何限制大范围误导与浏览器残留？每侧限 1000 行/笔、366 天，超限整体拒绝；`StatementsView` 在刷新、范围变化与窗口恢复时卸载结果，用 epoch 阻断迟到回包。清除后新读取没有账单行，页面仍保留独立人工费用的单边缺失证据。

- 共享来源 watch 为什么使用 getter 数组？`watch([() => shopId, () => source.row_id], ...)` 比较实际标识值；返回新数组的单一 getter 会在父页面替换同源对象时触发回调，误清空已读内容。SupportSource 另用 epoch 使 A→B→A 的旧请求失效，两个组件用例直接验证这两种时序。

## 收费映射：独立规则、预览摘要与当前读

- 收费名为什么与凭据使用不同匹配策略？凭据的规范化用于找到同笔费用；收费项名称本身承载平台语义。`fee_rules.match_key` 对去首尾空白后的原字符取 SHA-256，避免数据库排序规则把不同大小写或全半角规则视为相同；`map_fees` 仍比较完整名称，不猜相似项。
- 预览为什么包含未命中的其它规则版本？当前分类依赖整个范围的规则集合，创建、修订或撤销规则都可能改变结果。`FeeRuleService._preview` 将完整集合和账单/费用版本绑定散列，保存重新计算；这是一种有意保守的确认策略。
- 内部服务调用为什么用 defer_commits？`StatementService.reconcile` 平常会结束只读事务；嵌入规则保存时提前提交会释放锁，留下检查后再修改的竞态。外层将其转换为 flush，使预览复验、规则版本与审计仍在同一事务。
- 为什么规则不随账单清除一起删除？规则只保存卖家独立输入的分类定义，没有账单/费用快照或来源引用。应用结果即时读取，不持久化人工已核对结论；若未来保存结论，必须另建全部历史依赖。`test_source_lifecycle_recomputes_without_saved_conclusions` 验证清除后无应用行，独立规则仍在。
- 为什么映射命中仍显示业务待核？类别只是人工规则，不证明费用适用性、金额、分摊或账单完整性；重复凭据、币种冲突和人工类别冲突保持待核。`test_duplicates_and_cross_currency_remain_unresolved` 与分类冲突测试保证不把技术命中称为财务确认。

## 人工核对结论存档：可解释的状态与历史（2026-10-09）

- **为什么哈希还要包含变更号？** `services/statement_reviews.py` 除输入和比较快照外绑定来源、费用与规则变更号。只哈希当前集合，会让“新增再清除”后的原集合恢复旧预览；`repositories/expenses.py::scope_revision` 包含全部历史动作，单测覆盖恢复原样仍冲突。
- **失效与历史为何分开？** `StatementReview.version/content_version` 区分状态变化和人工保存。来源变化仅使 active→stale，旧正文用于追溯；新的明确确认才产生新正文。当前读只返回依据，不自动把旧结论激活。
- **怎么避免历史数据泄漏？** 三类依赖表累计登记账单批次、费用和规则，费用再展开全部历史批次。`StatementReviewRepository.purge/clear` 清全部快照，导入/费用/规则清除与最后审计处于同一事务；跨窗口修订也不能丢失旧依赖。
- **有界历史怎么读取？** 清单每页 20 条元数据；历史摘要只取 JSON conclusion；完整依据按版本读取，每版本最多 2 MiB，避免一次返回全部历史快照。金额原数据仍用 Numeric，计算用 Decimal。
- **如何证明页面可用？** `StatementReviews.spec.ts` 验证确认绑定、文本转义、迟到请求丢弃、失败隐藏正文及原 UUID 重试；`statement-reviews.spec.ts` 从导入到结论、当前回读、历史、撤销/清除与来源清除，在桌面和 390px 手机验证。

## 结算周期：声明、来源和到账凭据（2026-10-09）

- **为什么周期不是回款日期过滤器？** `StatementRepository.by_statement` 精确绑定原账单号，保留周期之后的回款；`SettlementService._calculate` 单独标识周期外非回款行。结算归属依据源标识和卖家周期说明，日期相同不能证明归属。
- **金额一致为什么仍待银行核验？** `ManualReceipt` 记录卖家声明，`compare_payouts` 只比较引用、币种和 Decimal 金额。coverage/balance/bank 三个状态分别保留未知；缺登记不能推断没到账，重复拆分不能加总抵销。
- **如何阻断重复使用凭据？** `SettlementReceipt.receipt_key` 仅最新版本持有规范化占用，同范围唯一约束和用户锁防并发。修订释放旧占用但保留历史 Numeric 值；清除删除全部历史数值。原账单号采用精确字符键，语义与凭据键不同。
- **为什么当前占用恢复原样仍不能使用旧预览？** `SettlementRepository.scope_revision` 取同身份渠道全部修订变更号，包含撤销和清除。来源版本和该变更号共同绑定预览，`test_registry_restoration_invalidates_old_preview` 验证创建再撤销的恢复场景。
- **历史清除如何跨修订生效？** `SettlementSource` 累计全部版本的批次。`purge` 擦除整份登记快照、Numeric 到账历史和依赖，导入末尾审计失败整笔回滚。`test_clear_after_receipt_revision_erases_every_numeric_history` 及历史换账单用例验证。
- **前端如何处理原确认和未知写入？** `SettlementRecords.vue` 绑定全部周期/凭据输入；`SettlementRecords.spec.ts` 验证 epoch、原 UUID 回查、范围切换、原子当前回读和清除正文。桌面/手机 `settlements.spec.ts` 走实际 API 与原始行。
## 订单金额核对：关联成立与金额可比（2026-10-09）

- **关联相同订单为什么还不能算差额？** `OrderReconciliationScope` 默认金额口径未知。`compare_group` 同时检查卖家声明、行数、币种、状态、日期和折扣；账单 sale 可能包含运费税费，技术关联不能替代业务金额定义。
- **为什么要在窗口外寻找同订单行？** `OrderReconciliationRepository` 先选窗口候选，再对其订单号读取同范围全部当前行。`test_all_dates_lookup_prevents_hidden_duplicates` 验证一笔窗外交易不会被截断后伪装成一对一。
- **如何避免数据库近似匹配？** 订单号使用 MySQL BINARY 比较，而非凭据的 NFKC/casefold；`test_unknowns_never_compute` 验证 O1、o1、Ｏ１各自独立。所有 JOIN 都验证当前店铺、owner、身份、渠道和 committed 来源。
- **累计退款能否与某笔退款直接比？** 当前字段缺逐笔退款时间和标识，`refund_transaction_unknown` 始终保留。两边金额刚好相等也不能证明是同一退款，更不能证明资金已退回。
- **数值与时间如何核验？** Decimal 保留四位小数，差额方向固定账单减订单；退款不重复扣销售。UTC 存储，显式 ZoneInfo 比当地日期；测试覆盖同一北京时间日期却跨 UTC 日期的情况。
- **只读结果如何处理失效？** 不持久化派生结论，来源生命周期由现有投影处理。页面在范围/focus/输入变化后撤结果和口径，epoch 防旧请求覆盖新请求；`OrderReconciliation.spec.ts` 验证迟到回包与未知结果可见。

## 基础闭环：跨页契约与可恢复数据（2026-10-09）

- **为什么跨页不能只传店铺ID？** 同店可能包含多身份、渠道、窗口和对象。`OperationTask.destinations`由受控服务从当前来源生成；`scopeQuery/applyLinkedScope`传递并校验范围，目标API再次做权限检查。后端定向测试证明另一店铺同类对象不能误命中。
- **为什么不把整个表单直接传给所有接口？** 运营检查包含库存时效，分析接口仅接受统计字段。连续场景发现多余字段导致422，`AnalyticsView`现在按目标契约应用范围；单测锁住这个跨域字段边界。
- **刷新后为什么会打开旧版本？** 页面选中状态与URL不同步。`ListingsView.updateResult`保存新待审版本后替换URL编号，浏览器场景覆盖编辑、批准和刷新回读。
- **来源变化为什么保留已完成历史？** 处理状态说明卖家做过什么，来源状态说明旧依据是否仍适用。修订成本后旧低毛利事项completed/stale保留备注，新证据形成待审批候选；`foundation.spec.ts`同时验证旧记录和新金额。
- **恢复为什么不用管理员导入整个SQL？** `database_backup.restore`用root建立新库，再用仅限该库的临时用户导入，已有目标直接拒绝。SQL内容即使带其它库语句也受数据库权限约束；测试验证失败路径清理账号且不输出私密错误。
- **如何证明备份可用？** 文件SHA256只证明文件未改变，恢复后的表行数、CHECKSUM和迁移版本证明数据一致；本轮还回读了任务状态、历史金额、批准版本、客服存档和报告，不能用文件存在代替恢复证据。

## 首次安装与进程恢复（2026-10-09）

- **为什么单元测试之外还要启停实际进程？** TestClient/直接tick能验证分支，但不能证明启动目录的.env、迁移、会话持久化和lifespan worker共同工作。G-04从空库启动Uvicorn，经HTTP保存14份快照，再实际停止/启动比较；证据见foundation-runtime-evidence。
- **暂停计划、关闭worker与关闭API有何区别？** SchedulesService.act暂停会清空next_run_at，恢复从当前日历计算未来时刻；scheduler_enabled只控制main.py中的serve任务，计划到期仍保留。进程恢复时run_due按最新周期和唯一slot_key处理，24小时窗口内执行，其余记录missed；多个实例各自的开关不能当作全库关闭。
- **初始化如何避免误覆盖？** scripts/setup_local.py先检查开发与测试三份配置，write_new用独占创建防止预检后同名文件出现时被覆盖。test_local_setup.py验证已有配置保持字节不变，G-04对原工作区配置另做SHA256前后核验。

## 真实模型验收中的事实与费用（2026-10-10）

- **如何证明模型结果可保存而且可追溯？** Agent API真实执行后逐步审批，再回读分析/Listing/客服/运营记录，核对模型步骤usage；修改来源后旧候选审批409、历史金额保留。G-05证明生产适配器与三层业务链实际配合，而不仅是网络连通。
- **为什么有两份费用值？** agent_model._cost使用部署的最高档USD预算费率并向上取整，预算用于拒绝超额请求；验收人民币账本按官方当前档位和供应商usage核算目录估算。0.000933 USD与0.0007750 CNY不是实时汇率换算，实际扣款另看账单。未知usage保留预留并停止重试。
- **正常记录为什么不能写成异常？** operation_checks中Branch.count统计读取记录数，Finding才代表候选问题；outbound.py邮件摘要需沿用该口径。test_outbound.py加入正常订单，锁定检查记录数与异常含义的区别。
