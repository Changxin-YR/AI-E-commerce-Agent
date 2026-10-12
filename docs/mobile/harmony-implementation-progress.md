# 鸿蒙完整业务版 · 实时进度

## 2026-10-12 续测（M0-C 第二轮；环境复用未重建，优先于下文全部历史状态）

- 环境核对通过、**未重建**：hdc `127.0.0.1:5555` 在线、`hdc rport tcp:18080 tcp:18081` 在位、合成 API 监听 18081（`SoloOps API`，132 路径）；固定 HAP 哈希 `31487267…ec0e` / 103,689,862 B 未变；保留库 67 表、head `b42e83f516c0`、批次 1181–1188 共 8 条；应用进程存活。
- **CI 补齐核对（本轮）**：匿名 REST 在 shell 被限流（403），改用抓取工具读 `actions/runs?branch=feat/soloops-mobile-m0c`。确认 `029b53b`(run 38152019827)、`e67bf35`(38153782085)、`e385cb3`(38153989215)、`e1917f1`(38154570627)、`c305b0c`(38154608925) 的 **"Verify mobile engineering" 全部 success**；HARMONY.md 里"未逐一确认"的 4 个 SHA 已闭环。
- **H19 商品本地修订端上通过**：上轮"选择商品行后已选择商品仍为 0"的根因查明——**"选择此商品"复选框是商品 `ExpansionTile` 的子项**，点行标题只会展开、不会勾选。展开后勾选 → 计数 1；批量前缀 `H19-` + 追加 `H19-APPEND` 应用到已选表单 → "创建修订差异预览" 得 **修订 #31 · v1 · 待审批**（当前有效商品数 0）；勾选"已核对全部商品的前后差异"后批准 → **v2 已应用**（当前有效商品数 1，`products` 1305 `Synthetic steel cup → H19-Synthetic steel cup`、`facts` 追加 `H19-APPEND`，输出批次 **#1189** `origin=manual_edit` committed）→ **v3 已撤销**（商品与批次 #1189 均回退 `revoked`）→ **v4 正文已清除**（`snapshot` NULL、`product_edit_sources` 0、批次 #1189 `cleared`）。差异页正确显示原/新名称、原/新参数与来源证据 `products-synthetic.xlsx · 源行 2 · 批次 #1182`。
- **H12 映射规则撤销/清除端上通过**：打开规则 **#310**（`user_import/generic`，`SyntheticShipping → 物流`，依据 `Synthetic-fee-name-mapping`）→「撤销规则」确认后 `fee_rules` 310 变 **`withdrawn` / v2** 且 `match_key` 置空，`fee_rule_revisions` 追加 `withdraw`；再「清除规则正文」确认后变 **`cleared` / v3**、`content` NULL，该规则三条历史正文全为 NULL，`active` 规则数 **0**。
- **H13 账单审阅结论预览/保存/版本/清除端上通过**：选「金额差异已说明 · 待跟进」预览时**服务端按待核事项拒绝**（提示"仍有待核事项，只能保存待核结论"）；改选「仍待核对」预览成功并列出两条 blocker（缺失一侧/重复凭据/异币种；未知收费分类/重复凭据/异币种/类别冲突），来源/规则修订 `10 / 140`。勾选核对后保存为 `statement_reviews` **#187 v1 active**（outcome=pending，说明原样落库，`statement_review_sources`=1）；改说明二次预览保存 → **v2**（revisions：v1 create / v2 update）；展开「审阅版本历史」点 v1 **回读出 v1 的历史快照**；「清除审阅正文」→ **v3 cleared**，三条历史 `snapshot` 全 NULL、来源 0。
- 另：中途移动会话过期一次（设备显示"登录已过期，请重新登录"），用合成账号 `harmony_r2` 重新登录后店铺 918 与首页计数恢复正常，不影响既有数据。
- **H14 订单账单核对"有差异"路径与结论保存端上通过**：原障碍是 `user_import/generic` 作用域没有订单行。先导入 `orders-user-import-synthetic.csv` → 批次 **#1191**（`SYN-U1/U2/U3`，3 新增，销售合计 120.0000 USD、退款 5.0000）；**第一次用 synthetic 作用域已有的 `SYN-G1..G3` 编号被服务端按 `source_scope` 明确拒绝**（"同店铺已有相同订单号/行号，但渠道或数据身份不同"），该批次 #1190 已清除——这是设计上的跨来源保护，不是缺陷。再造 `statements-order-linked-synthetic.csv`（账单行带 `order_id`）导入为批次 **#1192**（`SYN-ST-002` sale 120.0000→`SYN-U1`、refund 8.0000→`SYN-U3`）。口径选「退款前折后商品款」并填依据后运行：**`SYN-U1 · 账单销售款` = 「金额差异 · 差异 80.0000 USD」**（订单可比金额 40.0000 = 2×20−0 vs 账单 120.0000），展开可见订单行与账单行双方；`SYN-U2/SYN-U3` 销售款因无同订单号账单保持"待核实·差异未知"，`SYN-U3·账单退款` 因行退款是累计值、缺逐笔编号/时间/构成按设计保持未知，无订单号的账单行显示 `missing_order_reference`。结论预览同样只接受"仍待核对"，保存为 `statement_reviews` **#188（kind=orders）v1 active**、来源 3 条。
- 关键结论（H14）：**账单行必须带 `order_id` 才可能算出差额**——`order_comparison.py` 按 `(order_id, entry_type)` 分组，无订单号的账单行单独成组并直接判定 `missing_order_reference`。
- **H15 结算回款撤销/清除端上通过**：导入新账单批次 #1192 后，原结算 49 自动转为 **`stale`**（设备列表显示"来源变化 · 待重核"），说明来源修订联动生效；「撤销记录」→ **#49 v3 已撤销**（`settlements.status=withdrawn`、`settlement_revisions` 追加 v3 withdraw）；「清除正文」→ **#49 v4 正文已清除**（`status=cleared`，v1 create / v3 withdraw / v4 clear 三条 `snapshot` 全部 NULL，设备正文与依据输入框清空、操作按钮消失）。
- **H16 规则停用/重置/恢复 + AI 授权入口端上通过**：「停用规则」→ `business_rule_revisions` **#25 action=revoke**（阈值回默认 24）；「重置默认口径」→ **#26 action=reset**；在「规则版本历史」选中 #24 后「恢复历史 #24 为新版本」→ **#27 action=restore / restored_from_id=24 / max_age 12**。「管理 AI 运营授权」可进入 R1 有限次预授权面板，如实显示"**暂无授权，可在今日运营流程的待审批候选下创建**"且「刷新授权」可用（与 `internal_authorizations`=0 一致）；**创建有限次授权需先在今日运营流程产生待审批候选，本轮未创建**。
- **H17 计划启停/立即运行/通知深链/撤销端上通过**：「暂停」→ paused v2、`next_run_at` NULL、设备"下次 未安排"；「恢复」**被规则版本门禁挡住**并提示"经营规则版本已变化，请刷新规则并重新检查"——「修改计划」已重绑 **#27**，勾选核对后保存为 **v3（`config.rule_revision_id=27`）**，再恢复 → **active v4、`next_run_at`=2026-10-12 01:00 UTC（09:00+08:00）**；「立即执行一次」→ `schedule_occurrences` **#27**（trigger=manual、execution_id=**258**、status=succeeded、reason=`no_findings`）；通知「查看运行进度与审批」**深链直达"执行 #258 · 已完成"**（步骤"检查数据 data_check 62 ms、本次检查未产生异常候选"）；「标记已读」写入 `read_at`；「撤销」→ **revoked v5**。界面全程如实声明"当前服务未启用、超 24 小时记错过、暂停不补跑"。
- 说明：本轮**未真正启用自动调度服务**（服务未启用是部署事实），因此"实际周期到点运行"仍无法端测；手动触发与通知链路已独立验证。
- **H18 质量报告历史回读/清除端上通过**：列表显示 **报告 #31 · stale**（H19 本地修订改了商品，来源变化联动正确）；打开回读出检查时间/规则版本/来源修订 8/检查 4·受影响 2/缺失 2·待审 0 与逐商品结果（SYN-CUP 0、SYN-BOX 0、SYN-UNKNOWN 1、SYN-FIX 1）；「清除报告正文」→ 设备"#31 · 正文已清除"、`product_quality_reports.status=cleared`、`product_quality_sources` 0 条。
- **H09 经营分析端上通过**：默认口径（当前商品成本回推）下命中 3 个已支付订单行/6 件，净销售额 **115.0000**（=120.0000−退款5.0000），**成本、商品毛利、毛利率均为"未知"，完整排行可用 false**，并列出费用未归集/费用待核/半开时间窗等提醒；把「采购成本口径」切到**订单行历史成本依据**后，为 `SYN-U1/1` 登记 **8.1234 USD**（凭据 `SYN-COST-001`、凭据时间带 +08:00 偏移、来源批次 1191 行 20152）→ `order_cost_revisions` **#3 upsert/active**；重算得 **已知成本小计 16.2468（2×8.1234）、毛利已知行数 1**，而合计成本/毛利仍"未知"（部分数据不伪造合计），来源/计算版本 12→**13**；「保存当前分析报告」→ `saved_analyses` **#24 current**，旧报告 #23 转 `stale`。
- **H10 跨店总览端上通过**：日摘要（2026-10-11→10-12、USD）→"所选 **1** 家店铺；本地规则生成"，**"USD：可核对净销售额 未知/不完整；已知子集 0；已观察订单 0"**——空窗口未被当成零销售，并列覆盖说明与"口径与未获取项"逐条披露，逐店依据 `HarmonyR2Main · manual · US`；「保存持久摘要」→ `overview_reports` **#39 current**。**历史摘要列表与清除未再复核**（如实记在待验）。
- **踩坑记录**：`uitest uiInput text` 只能按单个无空格参数传入，而"订单行历史成本"的**凭据时间**字段必须带日期与时区偏移（如 `2026-10-08T09:00:00+08:00`），填错文本会只报"凭据时间：时间须包含有效日期和时区偏移"且不落库；修改任一字段会**重置确认勾选**，必须重新勾选才能保存。
- **H20 测试外发端上通过（全程替身，真实邮件 0）**：连通道 → 替身 `SyntheticMail` 把验证信写进 `.local/mobile-business/fixture-events.jsonl`（`mail_captured`），取出 8 位码 → **已验证 / 有效**。**关键前置**：页面只接受 `source_status=current` 的运营检查，原运行 184 因来源修订变化变 `stale` 被过滤；先跑「今日运营」得到**执行 #259**（5 个候选）→ **检查 #185** → 创建 **外发摘要 #25**（等待审批、内容版本 1、全文含 checked/partial/not_checked 与关联候选 #195–#199）→「保存单次批准」得 **限 1 次**审批 →「按有效授权提交一次」→ `accepted` + **通道回执 `7f1da7a8…`** + 授权**已消耗 1/1** →「只读回查」得 **通道报告送达** → 人工收件证据 `SYN-RECEIPT-001-合成收件声明` 落库 →「撤销通道」得**已撤销**（`revoked_at` 落库）。日志 `mail_captured`×2、`mail_reconciled`×1、`real_mail_calls: 0`。
- 附注：`test_mail_channels.status` 在撤销后仍为 `active`，撤销态由 `revoked_at` 派生——属实现方式，已如实记录不当作缺陷。
- 调试用只读接口探针（本机 18081）需带 `X-SoloOps-Client: mobile` 与 `Origin: http://127.0.0.1:18080`，`client_type` 只接受 `ohos|android|weapp`；token 存在 `.local/mobile-business/token.txt`（本机文件，不提交）。
- **H21 边界本轮验证三项**：①**离开恢复**——HOME 退桌面（焦点窗口 13、应用窗口 ZOrd -1）后 `aa start` 重入，**回到原页面、会话与页面状态保持**；②**断线错误**——撤掉 `hdc rport` 后读接口显示 **"暂时无法连接服务，请刷新重试。"**；③**未知结果与同次请求恢复**——先加载费用 #1139，再断链点「撤销费用」，应用**不静默重试**，按钮变 **"核对同次写入"**、撤销/清除置灰，此刻库内 `expenses 1139` 仍 `active` v1（**无半写**）；恢复链路后点"核对同次写入"补交同一次请求 → **#1139 withdrawn v2**（恰好一次，无重复）。**注意 #1139 因此已由 active 变为 withdrawn**（原 H12 证据仍保留在文档中，主费用 1138 未动）。
- **H21 版本冲突本轮已验**：先让应用加载"审阅 #188"（当时 v2），随后在数据库把该行 `version` 改成 **99**，再点「撤销审阅」并确认——服务端按过期版本拒绝，应用显示 **"核对存档版本已变化，请刷新。"**，数据库保持不变（仍 `stale`、revision 仍 1 条，**无半写/误覆盖**）；测试后已把该行 `version` 还原为 2。
- **H21 深浅色本轮已验**：在 Settings「显示和亮度 → 深色」开启（**深色 ✓ · 全天开启**）后回到应用，首页**完整以深色主题渲染**（深色底、浅色文字、主按钮转浅绿强调色、tabBar 与卡片可读）；随后已把模拟器**恢复为浅色**。
- **H10「清除摘要正文」本轮已验**：点历史条目 **#39** 会把它载入"已保存摘要"（页面出现"摘要 #39 · current + 保存时间"与「按原范围重算 / 清除摘要正文」两键），确认后设备提示 **"摘要正文已清除。"**、标题变 **"摘要 #39 · cleared"**、清除按钮消失；数据库 `overview_reports` 39 → `cleared`、`snapshot` NULL、`overview_sources` **0**，`overview_shops` 保留 1 条（与确认文案"保留范围、状态和审计记录"一致）。**H10 至此全部验证完毕。**
- **H16 AI 运营授权管理本轮完整验证（创建/消耗/撤销）**：跑「今日运营」得 **执行 #260**（5 个候选、等待审批）；展开「R1 内部有限次预授权」面板（显示"当前依据：执行 #260 · 版本 2"与授权范围），填 **3 次 / 24 小时** 并勾选核对后「保存预授权」→ 设备 **"有限范围授权已保存。"**、出现 **授权 #19 · active · 已用 0 / 3 次**，库内 `internal_authorizations` **#19**（`propose_tasks` / execution 260 / source_revision 13 / candidate_count 5 / max_uses 3 / v1）。展开卡片可见身份·渠道·币种、时间窗、规则/来源版本 `0 / 13`、阈值、绑定候选 5、授权与来源到期；「**为当前候选使用授权**」→ 执行 #260 转**已完成**、授权 **已用 1 / 3 次**（v2）、`authorization_uses` **#6**（execution 260 / operation_run_id **186**）；「撤销授权」确认 → 设备 **"授权已撤销。"**、卡片转 **#19 · revoked · 已用 1 / 3 次**，库内 `revoked_at` 落库、version 3，消耗记录保留。**H16 至此全部验证完毕。**
- **H21 横屏/大字体：已穷尽可脚本化手段，确认需人工**（详见 `harmony-r2-coverage.md` 的 H21 行）：横屏——`Emulator.exe --help` 无旋转项、DMS **由传感器驱动旋转且无设置朝向的 shell 接口**、`SensorService` 只读、Emulator 进程**唯一可见窗口是 Qt 手机画面（无工具栏）**、Settings 无旋转开关 → 只能由 **DevEco Studio 的 Device Manager** 手动转屏；大字体——Settings 字体大小滑块对 `uitest` 的 click/swipe/drag、获得焦点后的方向键、**以及模拟器窗口上的真实鼠标事件**全部无响应（该窗口对合成鼠标事件整体无响应，已用"返回"箭头做可逆校准验证），`param set` 亦被拒。
- 端上小坑：概览页正文较长，**从底部 tabBar 区域（y≈2500）起手的滑动不会滚动内容**，要在内容区（如 y 800→2300）滑动；另外 `dump` 偶尔给出合并过的陈旧节点，判断页面状态以 `snapshot_display` 截图为准。
- **本轮事故与恢复（重要）**：专用 API22 模拟器在内存压力下于 **08:07:40 崩溃并生成 minidump**；崩溃前画面先变黑，一度疑似应用渲染缺陷，**实际是模拟器故障**（应用的无障碍树当时仍完整，重启后渲染完全正常）。处理：结束微信开发者工具（12 个进程）释放内存 → 重启模拟器（冷启动，需直接前台运行 `Emulator.exe -start 22`，用 `Start-Process` 起不来）→ 重新 `hdc rport tcp:18080 tcp:18081` → 应用与库均正常（67 表 / head b42e83f516c0）。**教训：模拟器与微信开发者工具不要同时长跑。**
- **重要环境坑**：恢复设备链路必须用 **`hdc rport tcp:18080 tcp:18081`（Reverse）**，不能用 `fport`——用错方向时应用完全连不上 API，`fport ls` 里正确条目显示 `[Reverse]`。
- **H09 ask 与 H10 历史回读本轮补验通过**：把「受控经营问题」改成"低毛利商品有哪些"后点「用本地规则回答」，结果块的 `来源版本 / 计算版本 / 时间` 由 07:58:39 刷新为 **07:59:21**，说明确实发起了新请求并复用同一证据视图（受控问题、本地规则回答，**不调用外部模型**）；报告历史 **#24 current / #23 stale** 并列。跨店总览 `历史摘要` 列表显示 **#39 · current**，点开可**原样回读保存时的快照**；同时把窗口改为 2026-10-05→10-12 重算，得到 **"USD：可核对净销售额 115.0000；已知子集 115.0000；已观察订单 3"**，与先前空窗口"未知/不完整、0 单"形成对照。**「清除摘要正文」未验**：该按钮仅在记录被当作"已保存摘要"加载时才渲染，点历史条目只显示快照、未出现该按钮。
- **微信端运行时联调被本机环境阻塞**（详见 `docs/mobile/weapp-implementation.md`）：工程能在开发者工具中打开，但模拟器稳定报 **"模拟器启动失败 / TypeError: Failed to fetch"**，CLI 的 `preparing` 阶段同错（code 10）；已完全重启 IDE、并以 `--no-proxy-server` 启动，均失败；用户数据目录无缓存基础库、`WeappLog` 为空。强相关因素：本机系统代理 `127.0.0.1:7897`（`verge-mihomo`）下 `servicewechat.com` TLS 握手失败而直连正常（404）。**未擅自改动系统网络设置**，建议用户在 Clash 里把 `servicewechat.com` / `*.weixin.qq.com` 走 DIRECT 或临时关代理后重试。已按 `TARO_APP_API_BASE=http://127.0.0.1:18081` 重建并确认内联生效（本机 18080 属其他项目 nx-keycloak）。
- **测试工具修正（本轮）**：`scripts/mobile/ohos_ui.py` 的 `hide-ime` 原按布局树里是否出现输入法包名判断，实测常测不到——键盘开着时继续滑动，滑动落在键盘按键上，把 `、` 连续打进"修订依据"（服务端回读 `H19-本地修订验证、、、…`，已重新输入修正）。现改为读 `WindowManagerService` 窗口列表中 `softKeyboard` 的 ZOrd（-1 为收起），并在 `findtap` 每次滑动前先收起键盘。
- 另核：设备端弹过一次系统剪贴板权限框（"允许"soloops_flutter"复制来自剪贴板的内容？"，理由文案来自 `ohos/entry/.../element/string.json`），会抢焦点并使 `uitest dumpLayout -b <bundle>` 返回空树；已选"始终允许"解除，后续输入不再中断。
- 数据库回读注意：`docker exec … mysql` 默认字符集会把中文显示成 `?`，需加 `--default-character-set=utf8mb4`；已用 `HEX()` 证实库内是正确 UTF-8，不是写入损坏。
- 下一步：仅剩 **H21 横屏**（需 DevEco 模拟器工具栏手动转屏）与 **H21 大字体**（Settings 字号滑块对 uitest 无响应）；微信端登录/列表/写操作真实链路待解决驱动问题（automator 0.12.1 已是 npm 最新且与本机 IDE 不兼容，建议请用户手工登录一次交回截图）。

## 2026-10-11 23:45 M0-C 新分支续接（优先于下文全部历史状态）

- 新分支 `feat/soloops-mobile-m0c`（自 m0b 尖端 40db69e 分出）。首个提交 `029b53b4e91891e71ee821fea89d7bc547b8fda1`：恢复 `scripts/mobile/tests/test_business_fixture.py` 的导入顺序（修复 m0b 尖端 CI 红灯 `I001`），并把 `feat/soloops-mobile-m0c` 加入移动 CI 触发分支。**m0b 尖端 `40db69e` 的 CI 是 failure（run 38151032924），不要以它作为继续基线。**
- Docker 未运行导致 3315 tmpfs 库再次清空；已启动容器 `soloops-harmony-r2-mysql` 并从已校验备份 `harmony-account-switch.sql` 恢复：67 表、head `b42e83f516c0`、批次 1181–1187 共 7 条、店铺 2 家。
- 合成 API 以 `business_fixture.build_app()` 直接监听 **127.0.0.1:18081**（未调用 `prepare_samples`，保留样本日期），设备经 `hdc rport tcp:18080 tcp:18081` 访问 18080。
- API22 模拟器 `Emulator.exe -start 22` 启动成功（HarmonyOS 6.0.2/API22）；固定 HAP 哈希未变（103,689,862 B / `31487267…ec0e`），覆盖安装通过；会话、店铺 `HarmonyR2Main`(918)、首页计数 5/1/3 均恢复。
- **本轮新增端测通过**：费用 1138 由 v1(2.3456) 修订为 v2(2.5678)，发生时间保持 12:00+08:00→04:00 UTC 且 v1 历史保留；随后 v3 关联订单行 `SYN-G1 / 1 · SYN-CUP`（来源 `orders-generic-synthetic.csv` 批次 #1187 源行 2），数据库回读 `v3/cv3/active`。证据 `.local/mobile-business/device/expense-revision-linkage-v3.json`。
- 操作要点：费用页默认"数据身份"是 `user_import`，费用 1138 属于 `synthetic`，必须先在"数据身份"里切到"合成测试数据"再查询，否则显示"当前范围没有记录"。
- 微信小程序业务端第一波（core/登录/首页/待办/导入/AI/Listing/客服/库存）在同一分支并行实施。
- **账单与映射（本轮新增通过）**：合成账单 `statements-synthetic.csv`（5 行 sale/fee/fee/payout/refund）经设备文件选择器导入，批次 **#1188 committed**；费用映射规则 **#310**（`SyntheticShipping → 物流`）预览影响账单行 #8280 后保存 v1（`fee_rules=1`/`fee_rule_revisions=1`）；"渠道账单与费用核对"按类型合计正确（费用 14.8456 / 回款 100.0000 / 退款 8.0000 / 销售款 120.0000 USD），凭据 **`SYN-EXP-20261011-01` 编号与金额一致、差额 0.0000**（对应新建的人工费用 **#1139**，user_import/generic），未匹配的 `SYN-FEE-001` 保持"仅账单有记录 · 无法确定"；跨身份（synthetic 费用 vs user_import 账单）按作用域正确隔离。证据 `.local/mobile-business/device/statements-and-mapping-rule.json`、`statement-review-and-match.json`。
- **结算回款（H15）本轮通过**：原账单 `SYN-ST-001` + 人工到账登记 `BANK-SYN-001`/`PAY-SYN-001`（100.0000 USD）→ 逐笔比较"编号与金额一致、差额 0.0000"，周期外明细保持未知，未知项（覆盖完整性、期初期末余额、银行证据）按原文保留；保存后 `settlements`/`settlement_receipts`/`settlement_revisions` 各 1 条并显示版本历史。证据 `.local/mobile-business/device/settlement-receipt-verification.json`。
- **订单账单核对（H14）本轮只部分验证**：设备端"匹配订单与账单"可运行，口径依据与来源覆盖完整性保持未知，账单销售款/退款显示"待核实 · 差异未知"，原因是当前 `user_import/generic` 作用域内没有订单行（批次 1184/1187 的订单属 synthetic 作用域）。**结论预览/保存与"有差异"计算路径仍未验证**，下一步需先在 user_import 作用域导入订单行。
- **经营规则（H16）本轮部分通过**：读取当前规则（#0 默认/停用）→ 修改 `max_age_hours 24→12` 与业务文本 → 勾选"已核对规则作用范围、阈值、预算与依据" → 保存并启用，数据库回读 `business_rule_revisions` id=24 / action=save / max_age=12 / qty=1 / margin=20.00 / USD。**停用、重置默认口径、版本恢复与 AI 运营授权管理仍未端测**。
- **定时运营（H17）本轮部分通过**：新建"每日运营检查"计划（daily 09:00 Asia/Shanghai，绑定规则 #24，表单只读显示 12/1/20.00）保存为 `operation_schedules` id=24/active/v1，`next_run_at`=01:00 UTC 即 09:00+08:00（时区换算正确）；界面如实声明服务未启用、超 24 小时记错过、暂停不补跑，`schedule_occurrences`=0。**启停/撤销/立即运行/通知深链与实际周期运行未端测**。
- **商品质量（H18）本轮通过**：`user_import` 作用域如实"未检查/0 商品"；切到合成作用域后检查 **4 商品 / 受影响 2 / 缺失 2 / 待审 0**，名称与参数、价格与采购成本、相似 SKU 三组均执行（规则版本 `product-quality-v1`）；勾选"已核对检查范围、规则结果与未检查项"后保存，落库 `product_quality_reports`=1、`product_quality_sources`=2。**报告历史回读/清除与关联修订深链未端测**。
- 下一步顺序：H12 费用映射规则 → H13 渠道账单 → H14 订单核对 → H15 回款 → H09/H10/H16–H20 → H21 边界与布局。

## 2026-10-11 21:35 接续环境复核（优先于下文历史状态）

- 已 fetch 并核对 GitHub 与本地起点 `7edb160c3f0c4b8d026d799e25970d8245492736`，继续同一鸿蒙分支和 worktree。
- 原 API 进程已退出；本机 18080 被其他项目的 nx-keycloak 使用。合成 API 已恢复到 **127.0.0.1:18081**，HDC 使用 `rport tcp:18080 tcp:18081`，应用地址仍是 18080。不停止其他项目服务。
- 专用 MySQL 曾停止，tmpfs 数据丢失。重启后查询确认业务库 0 张表，才恢复已校验的 `harmony-account-switch.sql`。恢复后 migration=b42e83f516c0、费用1138/v1 active、批次1181–1187共7条已回读。原备份保持不变，禁止向该保留库运行清表测试。
- 固定 HAP 哈希仍为3148726747764db13eb18de7e71885b69253f3b59274998fe4367bb0ab85ec0e；覆盖安装成功，Asset会话、店铺918、首页恢复，session/shops/workbench/onboarding均200。设备证据 `.local/mobile-business/device/resumed-installed.json` 与 `expense-restored-detail.json`。
- **端测当前阻塞：API22再次离线。** Emulator.log在21:27:55记录主机空闲268 MB，21:32:39记录std::bad_alloc。HDC最终返回Empty。未停止其他聊天的Android模拟器或Docker服务，已向用户询问资源安排。
- 本轮费用修订没有提交，费用1138仍v1/2.3456。不要将本轮尝试记为订单关联/修订通过。下一步仍从费用修订、订单关联及H12–H20剩余闭环继续。
- HDC存在退出码0但stdout/stderr返回[Fail]的情况；设备助手已改为立即抛出明确传输错误，避免误解析JSON。3项无数据库回归（先2失败/1通过，修复后3通过）、Ruff检查通过。
- UI输入3.4567曾回读为3.4567999999999999，来源尚未彻底核实；不要据此认定业务金额计算错误。重新输入与最终字段回读必做。键盘/动画改变布局后先等待稳定快照，再执行下一动作。
- 当前API进程入口直接调用 `business_fixture.build_app()` 后uvicorn监听18081，未调用prepare_samples，保留已有样本日期。日志为 `.local/mobile-business/resume-api.stdout.log` / `resume-api.stderr.log`。

更新：2026-10-11。实际工作区 `.local/worktrees/mobile-m0a`，分支 `feat/soloops-mobile-m0b`。执行 `docs/requirements/SoloOps-Mobile-V1.3.md`，21功能标识/149条API引用，H14补充6个路由操作另见 `harmony-api-supplement.md`。当前提交精确SHA由接续消息和context-memory/HARMONY.md给出。

## 当前结果

H01–H21核心业务源码已覆盖，集中验证已经开始。H11–H20全部新业务页、H02冲突/onboarding、H04独立manifest恢复和H21时区/日期/导航/离开保护均已写入。Dart无问题，23Flutter测试、12CSV跨端对照、97后端定向测试、Ruff/mypy180 app文件和完整业务HAP构建通过。完整表见 `harmony-r2-coverage.md`，精确证据见 `harmony-validation.md/json`。

**API22集中端测进行中：登录/经营资料/建店、重启恢复、商品CSV/XLSX、逐行纠错和订单导入已通过。完整卖家旅程与用户联调仍待做。** 不将历史M0技术证据当作本次业务结论。用户要求持续推进，不等待逐包批准或CI；Android与微信本轮仅方案，用户已于本轮明确允许鸿蒙与独立安卓任务的模拟器短时并行。

优先读取 [账号切换接续入口](harmony-handoff.md)，以其检查点和下一步为准。

## 下一步直接执行

1. 读取AGENTS顶部、V1.3、本账本和validation。复用现有worktree/分支；业务页面已完成核心实现，不再从H11重新开发。
2. 新隔离MySQL已经运行：Docker `soloops-harmony-r2-mysql`，回环3315，数据库 `soloops_harmony_r2_test`，head `b42e83f516c0`。配置只在忽略目录 `.local/mobile-business/test.env` 与 `mysql.env`，不得输出或提交。此容器是tmpfs，停止会丢失合成测试库内容；只保存合成测试数据。现有业务库均未修改。独立HTTP API已在127.0.0.1:18080运行，入口scripts/mobile/business_fixture.py；实际模型和邮件全部替身。
3. 复用正在运行的独立API（127.0.0.1:18080）、3315测试库、harmony_r2账号与店铺918。合成样本在.local/mobile-business/samples；设备浏览器Download/浏览器中已有本轮CSV/XLSX。pytest会清表，与端测串行；当前端测数据要保留。
4. 启动DevEco Device Manager已有API22模拟器，RAM2048MiB；本轮已获短时并行许可。API22历史可安装未签名x64调试HAP。当前路径 `apps/soloops_flutter/ohos/entry/build/default/outputs/default/entry-default-unsigned.hap`；SHA256 `3148726747764db13eb18de7e71885b69253f3b59274998fe4367bb0ab85ec0e`，103689862 bytes。HDC安装、HTTPS/HTTP映射、Asset登录/会话恢复/退出先验证。构建脚本 `scripts/mobile/build_ohos_probe.ps1`。
5. 用真实移动界面走完整卖家链：初始化、模板/导入映射审阅纠错、分片/独立清单恢复、巡检/待办复检、Agent/B1双审批、Listing交付、客服政策/审阅/人工凭据、库存/分析/总览、利润/费用/账单/订单审阅/回款、规则授权、调度通知、质量/本地修订、替身外发。核对数据库真实结果，记录每项证据并修复失败。
6. 专项：未知写入同UUID恢复、Agent进行中的暂停取消、版本冲突与来源清除、跨店来源/深链、前后台和重启、导出字节/分享消费时机、大字体/横屏/深浅色/长列表。新增EditGuard已覆盖费用/回款/规则/调度编辑/商品修订/外发/资料等，其他表单逐项在端上验证。对新发现的缺口继续实现。
7. 后端全量890项已通过（529.36秒），5项本地验收夹具隔离测试通过。后续按实际接口/端测问题补充必要验证；最后向用户交付可操作测试入口与联调说明。无需等CI。

## 本轮源码（H11–H21）

- `features/profit/`：最多5方案，9类固定或比例费用，空白未知/明确零、成本依据、手工汇率预览确认与BigInt舍入、结果/敏感性/保本原因、幂等存档/历史/清除。
- `features/finance/`：费用增改/精确金额/原订单来源选择/撤销/清除；费用规则预览摘要/保存与版本历史；账单费用核对、订单销售口径与完整差异来源；通用版本审阅；回款手工登记/核对/窗外与未知证据/历史。未知写入保存原body和request_id用于核对。
- H14后端：schemas/services/api `order_statement_reviews.py`，StatementReview.kind和repository分页域过滤；迁移b42e83f516c0。原费用审阅限制fees，新订单为orders，原清除/依赖和UUID版本架构共用。默认旧行fees，有orders时拒绝降级。6个接口操作见supplement。
- `features/rules/`：经营规则范围/预算/依据/经营文本、版本增改/启停/重置/恢复，有限次授权沿用Agent页。
- `features/schedules/`：计划周期/时区/免打扰/范围/规则、增改/启停/撤销/立即运行、通知已读/历史/深链/实际周期。
- `features/products/`：质量范围预览/持久报告/来源/清除；本地修订批量名称/事实/差异/审批/应用结果/撤回/清除与导入批次深链。
- `features/outbound/`：通道验证/配置状态、运营摘要、邮件全文/地址/内容hash、编辑/审批/限次授权、单次提交/回执核对/人工收件。代码已接API，但本轮未发真实邮件。
- `core/business_time.dart` / `ui/business_time_fields.dart`：IANA时区、日期/时间选择、严格溢出校验、DST重复选择/缺失拒绝；FactLine业务时区显示、原值tooltip。依赖timezone0.10.1（2025b），Dart3.6.2解析和编译通过。
- `ui/edit_guard.dart` / AppState：当前路由未保存输入/未知请求提示、返回/切店/深链联动；恢复前台核对会话、保留本地输入。ApiClient连接后再次检查generation，401失效在途请求。
- H02：资料冲突/未知写入回读替换、onboarding下一步。H04：独立manifest验证/建组恢复/逐片选择；系统文件过滤增加JSON。
- `product_app.dart`注册21个路径（包含fee-rules与订单核对别名），原19业务路由均可到达；五主入口与工具入口齐全。

## 此前源码（已合入当前基线）

8abfb7a：H05–H10 Agent/B1、有限次授权、Listing、客服/政策/人工消息、库存、分析/成本、跨店总览；bfd2286：H04导入全核心与H03工作台/巡检/待办；58c4b44：移动Bearer认证/迁移、ArkTS桥接、Dart网络/登录/资料/店铺。审阅、预算、权限和来源失效沿用服务层。当前测试已包含这些源码编译，但不等同于端上业务通过。

## 环境与保护

实际绝对路径 `C:/Users/27363/Desktop/AIEcommerceAgent/.local/worktrees/mobile-m0a`。保存项目路径 `C:/Users/27363/Desktop/AI E-commerce Agent` 已过时；所有shell显式workdir。实际worktree在沙箱写目录外，用户已授权使用require_escalated继续；普通沙箱git可能报 must be run in a work tree。

- **本机未提交配置保护**：`apps/soloops_flutter/ohos/build-profile.json5`（签名）和 `apps/soloops_weapp/project.config.json`（AppID），不输出/覆盖/提交。
- Flutter OH3.27.5-ohos-1.0.7/Dart3.6.2，工具链为本worktree内 `.local/toolchains/flutter-oh-api22`，不要误用主仓库同名路径。PUB_CACHE `C:/Users/27363/Desktop/max/pub-cache`，镜像pub.flutter-io.cn。
- Python `C:/Users/27363/Desktop/AIEcommerceAgent/backend/.venv/Scripts/python.exe`。SDK24编译、API22运行；HDC `C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe`。
- 当前单台鸿蒙API22已运行，HDC target127.0.0.1:5555，18080反向映射可用。编码前关闭闲置模拟器；启动优先Device Manager已有22。
- 本轮验收服务scripts/mobile/business_fixture.py绑定127.0.0.1:18080，仅允许专用3315数据库。真实模型、真实邮件、实际平台写入为0。
- 本机证据 `.local/mobile-business/`；最后原始日志文件名见validation.json。不提交完整日志、配置、数据库或HAP。
- 历史API22 M0技术证据 `.local/mobile-m0b/20261011-ohos-acceptance/`，只供操作参考。

## 保存与接续

上下文接近满时自主更新文档、提交推送任务文件、更新独立context-memory/HARMONY.md后创建接续聊天，给精确SHA。该记忆checkout `C:/Users/27363/Desktop/AIEcommerceAgent/.context-memory` 的README.md有用户MM改动，只用commit --only提交HARMONY.md。新对话唯一写入；创建之后旧对话停止工作区写入。

## API22纠错复测（2026-10-11）

批次1181商品CSV新增3条，1182同商品XLSX相同3条；1183缺少name的行通过编辑、离开提示返回、重新预览、确认后新增SYN-FIX。数据库确认name为SyntheticFixedCup，corrections只保存name。发现并修复late初始化在保存时读取已改控制器值的问题；在initState捕获基线，同时按映射列读取原值，补充离开保护与2项回归。批次1184合成订单新增3条。

锁定脚本构建HAP已安装API22，冷启动保留登录与店铺918。构建和安装需紧邻校验HAP哈希，DevEco默认构建可能覆盖输出并造成Flutter ArkTS模块缺失；正确重建并覆盖安装已恢复。设备助手scripts/mobile/ohos_ui.py保存布局/截图，空前台或禁用目标拒绝操作。

长表单离屏故障：PageBody保持Form与校验字段挂载，普通记录仍用ListView。两种嵌套Form回归先失败后通过；23项Flutter与Dart通过。固定安装副本.local/mobile-business/accepted-scope-fix.hap已装API22。库存批次1185已上传，后续状态见validation。

端测推进：库存1185新增3、客服1186新增2；六批次全部committed。巡检184及低库存事项195审批/复检/完成核对通过，业务结论保持待新来源。下一步B1目标商品渠道筛选（256被scope_mismatch正确阻断），随后Listing有效基线与B1双审批。

## B1范围修复与设备恢复（2026-10-11）

ProductFacts增加可空source_channel，当前商品从真实批次提供渠道，历史快照缺失字段保持可读。B1按身份和渠道筛选，在切换范围/流程与启动前均复核；其余Listing流程保留身份范围。23项Flutter、1项无数据库契约回归、Dart、Ruff和mypy180文件通过。固定scope修复包已校验并安装API22，会话/店铺恢复，继续同渠道订单和双审批端测。

API22 B1双审批通过：同渠道订单批次1187新增3行；Listing 91编辑后批准、系统CSV保存通过。B1执行257完成7步、version10，两个approve分别绑定analysis_todo和listing_draft；分析23已存档、Listing 92仍为draft且基线91仍approved。只读数据库回查见b1-db.json。实际模型/邮件/平台写入保持0。

## 账号切换检查点（2026-10-11）

接续统一入口为 `harmony-handoff.md`。客服43/v2保持human_review并完成en全文审阅；系统分享接收方“另存为”保存CSV，取回1294字节、完整2行。Listing91系统保存CSV取回603字节、完整2行，哈希见validation.json。库存页面确认BOX过期为未知、CUP低于阈值并链接195。利润存档5保存售价25、成本8.1234，余额16.8766、余额率67.5064%，费用及保本价未知。费用1138/v1 active，synthetic/generic，金额2.3456 USD，发生时间12:00+08:00持久为04:00 UTC。均已只读数据库回查（account-switch-db.json）。

本次停止在费用1138保存后的页面，业务数据已持久化。合成数据库本机备份 `.local/mobile-business/harmony-account-switch.sql`，424238字节；SHA256 `e67ce2a4bc09b8751c28f45855b3a162575327e44d8486c4ca88ccf29b377f82`。备份与原始日志不入Git，GitHub保留脱敏结论、复现代码与接续步骤。API22其他业务与边界场景仍未全部验收。
