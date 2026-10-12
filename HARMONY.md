# SoloOps 手机三端 · 跨账号接续记忆

## 交接摘要（新对话从这里开始 · 2026-10-12 08:35）

- **分支/尖端**：`feat/soloops-mobile-m0c` @ **`5126fbb`**（已推送，CI success）；worktree `C:/Users/27363/Desktop/AIEcommerceAgent/.local/worktrees/mobile-m0a`。
- **接续记忆**：本文件（`context-memory` 分支）；入口文档 `docs/mobile/harmony-handoff.md` 顶部、`docs/mobile/weapp-implementation.md`。
- **本机环境**：**已核对并复用，无需重建**。设备 `127.0.0.1:5555` 在线；`hdc rport tcp:18080 tcp:18081` 在位（`[Reverse]`）；合成 API `127.0.0.1:18081` 返回 200；Docker `soloops-harmony-r2-mysql`（3315）67 表 / head `b42e83f516c0`；固定 HAP 哈希 `31487267…ec0e` 未变。
- **进度**：鸿蒙端 H19/H12/H13/H14/H15/H16/H17/H09/H10/H18/H20 **全部通过**；**H21 通过六项**（离开恢复、断线错误、未知结果与同次请求恢复、409 版本冲突、深浅色、错误文案）。微信端 wave 3 代码已提交并通过 type-check/构建；**微信开发者工具已能渲染小程序（登录页显示服务地址 18081），但"驱动"仍不通**。
- **剩余**：① H21 横屏（需 DevEco 模拟器工具栏手动转屏）；② H10「清除摘要正文」；③ H16 内部有限次预授权创建；④ 微信端登录/列表/写操作真实链路（换匹配版本的 `miniprogram-automator`，或请用户手工登录一次交回结果）。
- **硬约束**：只用合成数据与本地替身，真实模型/邮件/平台写入保持 0；`pytest backend/tests` **不得**对保留验收库运行；`apps/soloops_weapp/project.config.json` 与 `apps/soloops_flutter/ohos/build-profile.json5` 不提交不覆盖。

## 最新接续检查点（2026-10-12，M0-C 第五轮）

- **业务分支：`feat/soloops-mobile-m0c`**（worktree 不变：`C:/Users/27363/Desktop/AIEcommerceAgent/.local/worktrees/mobile-m0a`）。
- **本轮已推送的提交（自上轮尖端 `c305b0c` 起）**，全部已核 `Verify mobile engineering` CI：

  | SHA | 内容 | CI |
  |---|---|---|
  | `c455c39` | H19 商品本地修订通过 + `ohos_ui.py` 的 `hide-ime` 修正 | success (run 38182508982) |
  | `b73cb10` | H12 映射规则撤销/清除 + H13 账单审阅结论版本/清除 | success |
  | `213757f` | H14 订单账单核对"有差异"路径 + 结论保存 | success |
  | `c63e11b` | 微信端 wave 3（订单核对页、fee-rules 页、来源证据组件、tabBar 图标） | success (run 38183642727) |
  | `87f462f` | H15 结算回款撤销/清除 | success |
  | `7faf1de` | H16 规则停用/重置/恢复 + H17 计划启停/立即运行/通知深链/撤销 | success |
  | `dc911ca` | H18 质量报告历史/清除 + H09 经营分析 + H10 跨店总览 | success |
  | `32e2d6e` | H20 测试外发（替身全链路） | success (run 38185326598) |
  | `dc28a0a` | H21 边界：离开恢复 / 断线错误 / 未知结果与同次请求恢复 | success |
  | `4192691` | 微信端运行时联调尝试及其受阻证据 | success |
  | `0040b04` | H09 ask 与 H10 历史回读 | success |
  | `c217109` | H21 版本冲突（409） | success |
  | `56e525f` | H21 深浅色 + 模拟器崩溃事故记录 | success |
  | `5126fbb` | 微信端：模拟器已能渲染应用 + 更正代理结论 | success (run 38188367463) |

- 上轮"未核对"的 4 个 SHA 已闭环：`029b53b`、`e67bf35`、`e385cb3`、`e1917f1` 的 CI 均为 **success**。
- **CI 读取方式**：匿名 REST 从 shell 直接调会被限流 403；用抓取工具读
  `https://api.github.com/repos/Changxin-YR/AI-E-commerce-Agent/actions/runs?head_sha=<完整SHA>&per_page=1` 可正常返回。

## 本机环境（本轮**核对后直接复用，未重建**）

- Docker `soloops-harmony-r2-mysql`（mysql:8.4，`/var/lib/mysql` 为 tmpfs，宿主 127.0.0.1:3315）保持运行；本轮开头核对为 **67 表 / head `b42e83f516c0` / 批次 1181–1188**，此后新增 **#1189**（商品本地修订输出，`manual_edit`）、**#1190**（跨作用域订单被拒，已清除）、**#1191**（user_import 订单行）、**#1192**（带 `order_id` 的账单）。**不要停容器**。
- 合成 API 监听 **127.0.0.1:18081**（`.local/mobile-business/resume_api_18081.py` → `business_fixture.build_app()`，不跑 `prepare_samples`）；18080 属其他项目的 nx-keycloak，勿占用。
- `hdc rport tcp:18080 tcp:18081` 在位；HDC target `127.0.0.1:5555`（API22 模拟器，RAM 2048）。
- 固定 HAP `.local/mobile-business/accepted-scope-fix.hap`：103,689,862 B、SHA256 `3148726747764db13eb18de7e71885b69253f3b59274998fe4367bb0ab85ec0e`，**本轮未变、未重建**。
- 数据库回读必须加 `--default-character-set=utf8mb4`，否则 `docker exec … mysql` 会把中文显示成 `?`（库内其实是正确 UTF-8，已用 `HEX()` 证实）。
- 微信开发者工具**确实在本机**：`D:/微信开发工具/微信web开发者工具/微信开发者工具.exe`（含 `cli.bat`）。上轮子代理"未安装"的判断是错的，勿沿用。

## 本轮已验证（设备端操作 + 数据库回读）

| 项 | 结果 |
|---|---|
| H19 商品本地修订 | **通过**。根因：`选择此商品` 复选框在**折叠的 `ExpansionTile` 内**，点行标题只展开不勾选。展开勾选后计数 0→1；批量前缀+追加应用到已选表单 → 修订 **#31** v1 待审批 → v2 已应用（商品 1305 改名 + `facts` 追加，输出批次 **#1189** `origin=manual_edit`）→ v3 已撤销（商品与批次回退）→ v4 正文已清除（`snapshot` NULL、来源 0） |
| H12 映射规则撤销/清除 | **通过**。规则 **#310** → `withdrawn` v2（`match_key` 置空）→ `cleared` v3（`content` NULL、该规则历史正文全清、active 规则 0） |
| H13 账单审阅结论 | **通过**。选"金额差异已说明·待跟进"预览时**服务端按待核事项拒绝**，只接受"仍待核对"；保存 `statement_reviews` **#187 v1 active** → 改说明二次保存 **v2** → 历史点 v1 可回读 → 清除 **v3 cleared**（三版 `snapshot` 全 NULL、来源 0） |
| H14 订单账单核对 | **通过**。先在 user_import 导入订单（批次 **#1191** `SYN-U1/U2/U3`；**沿用 synthetic 作用域的 `SYN-G1..G3` 会被 `source_scope` 拒绝**，该批次 #1190 已清除），再导入带 `order_id` 的账单（批次 **#1192** `SYN-ST-002` sale 120.0000→`SYN-U1`、refund 8.0000→`SYN-U3`）。口径选"退款前折后商品款"+填依据后 **`SYN-U1 · 账单销售款` = 金额差异 80.0000 USD**（订单可比 40.0000 vs 账单 120.0000）；其余按设计保持"待核实·差异未知"；保存 `statement_reviews` **#188（kind=orders）** |
| H15 结算回款撤销/清除 | **通过**。导入新账单后原结算 49 自动转 **`stale`**（设备"来源变化 · 待重核"）→ 撤销 **v3 `withdrawn`** → 清除 **v4 `cleared`**（v1 create/v3 withdraw/v4 clear 三条 `snapshot` 全 NULL） |
| H16 规则停用/重置/恢复 | **通过**。`business_rule_revisions` **#25 revoke**（阈值回默认 24h）→ **#26 reset** → 从版本历史恢复 #24 得 **#27 restore（`restored_from_id=24`、12h）**。**AI 授权面板**可进入、空态如实（"暂无授权，可在今日运营流程的待审批候选下创建"）、刷新可用，与 `internal_authorizations`=0 一致；**创建有限次授权未做**（需先跑今日运营产生待审批候选） |
| H17 定时运营 | **通过**。暂停 → `paused` v2（`next_run_at` NULL）→ **恢复被规则版本门禁挡住**（"经营规则版本已变化，请刷新规则并重新检查"）→ 修改计划重绑规则 **#27** 存为 v3 → 恢复 **active v4**（`next_run_at`=2026-10-12 01:00 UTC=09:00+08:00）→ 立即执行一次 → `schedule_occurrences` **#27**（execution_id **258**、succeeded、`no_findings`）→ 通知"查看运行进度与审批"**深链直达执行 #258** → 标记已读写入 `read_at` → 撤销 **revoked v5**。**自动调度服务本身未启用，"到点自动运行"仍无法端测** |
| H18 质量报告 | **通过**。报告 #31 因 H19 改商品转 **`stale`**；回读检查时间/规则版本/来源修订 8/检查 4·受影响 2/缺失 2·待审 0 与逐商品结果；清除后 `product_quality_reports.status=cleared`、`product_quality_sources` **0** |
| H09 经营分析 | **通过（含 ask）**。默认口径：3 个已支付订单行/6 件、净销售额 **115.0000**（=120.0000−退款5.0000），成本/毛利/毛利率**"未知"**、完整排行 false。切「订单行历史成本依据」并为 `SYN-U1/1` 登记 **8.1234 USD**（凭据 `SYN-COST-001`）→ `order_cost_revisions` **#3 upsert/active**；重算得**已知成本小计 16.2468（2×8.1234）、毛利已知行数 1**，合计仍"未知"；保存 `saved_analyses` **#24 current**，旧 #23 转 `stale`。**ask 已验**：受控问题改为"低毛利商品有哪些"后点「用本地规则回答」，结果块时间戳 07:58:39→**07:59:21**（确实发起新请求、复用同一证据视图、不调外部模型） |
| H10 跨店总览 | **通过（清除未验）**。日摘要（2026-10-11→10-12、USD）→ 1 家店铺、**"可核对净销售额 未知/不完整；已知子集 0；已观察订单 0"**（空窗口不当零销售）+ 覆盖说明/口径与未获取项 + 逐店依据 `HarmonyR2Main · manual · US`；保存 `overview_reports` **#39 current**。**历史回读已验**：列表显示 #39 current 且点开可原样回读保存时快照；另把窗口改 2026-10-05→10-12 重算得 **115.0000 / 已知子集 115.0000 / 已观察订单 3**（与空窗口对照）。**「清除摘要正文」未验**（该按钮仅在记录被当作"已保存摘要"加载时才渲染） |
| H20 测试外发 | **通过（全程替身，真实邮件 0）**。连通道 → 替身 `SyntheticMail` 把验证信写入 `.local/mobile-business/fixture-events.jsonl`（`mail_captured`），取 8 位码回填 → **已验证/有效**。**关键前置**：页面只接受 `source_status=current` 的运营检查，旧运行 184 因来源修订变化已 `stale` 被过滤；先跑「今日运营」得 **执行 #259**（5 候选，批准节点完成）→ **检查 #185** → 创建 **外发摘要 #25**（等待审批、内容版本 1、全文含 checked/partial/not_checked 与关联候选 #195–#199）→「保存单次批准」得**限 1 次**审批 →「按有效授权提交一次」→ `accepted`、**回执 `7f1da7a8…`**、授权**已消耗 1/1** →「只读回查」得 **通道报告送达**（`mail_reconciled`）→ 人工收件证据 `SYN-RECEIPT-001-合成收件声明` 落库 →「撤销通道」得**已撤销**（`revoked_at`）。日志 `mail_captured`×2 / `mail_reconciled`×1 / `real_mail_calls: 0` |
| H21 边界 | **六项通过**。①**离开恢复**：HOME 退桌面后 `aa start` 重入 → 回到原页面且会话与页面状态保持；②**断线错误**：撤掉 rport 后读接口显示 **"暂时无法连接服务，请刷新重试。"**；③**未知结果与同次请求恢复**：先加载费用 #1139 再断链点「撤销费用」，应用**不静默重试**而是进入待确认态、按钮变 **"核对同次写入"** 且撤销/清除置灰，库内仍 `active` v1（**无半写**）；恢复链路后补交同一次请求 → **#1139 withdrawn v2**（恰好一次）；④**版本冲突**：加载"审阅 #188"（v2）后把库内该行 `version` 改为 99 再点「撤销审阅」→ 服务端拒绝、界面显示 **"核对存档版本已变化，请刷新。"**、库内不变（revision 仍 1 条），测后已还原 `version=2`；⑤**深浅色**：Settings「显示和亮度 → 深色」开启后应用首页**完整以深色主题渲染**（深色底/浅色字/浅绿主按钮），随后已把模拟器**恢复为浅色**；⑥**错误文案**与长文本换行均可读。**未做**：横屏（DMS 无旋转指令）、大字体（Settings 字体大小滑块对 `uitest click/swipe/drag` 均无响应） |

证据目录 `.local/mobile-business/device/`（本轮新增 `h19-*`、`h12-*`、`h13-*`、`h14-*`、`h15-*`、`h16-*`、`h17-*`、`h18-*`、`h09-*`、`h10-*` 的布局快照与 `*.jpeg` 截图）。
本机新增合成样本：`.local/mobile-business/samples/orders-user-import-synthetic.csv`（`SYN-U1/U2/U3`）、`statements-order-linked-synthetic.csv`（带 `order_id` 的账单）。

## 仍待端测 / 未完成

- **H21 横屏**（`hidumper -s DisplayManagerService` 无旋转指令、无脚本化旋转入口，需 DevEco 模拟器工具栏手动转）与**大字体**（Settings 字体大小滑块对 `uitest click/swipe/drag` 均无响应）。
- **H10「清除摘要正文」**：该按钮仅在记录被当作"已保存摘要"加载时才渲染，点历史条目只显示快照、未出现按钮。
- H16 创建**内部有限次预授权**未单独做（H20 做的是外发「限一次预授权」，不是 R1 面板）。
- H17 "到点自动运行"无法端测（调度服务未启用，属部署事实）。
- **微信端运行时联调：模拟器已能渲染应用，但自动化驱动仍不通**。彻底结束全部 `wechatdevtools` 进程后全新启动 IDE，之前稳定复现的 **"模拟器启动失败 / TypeError: Failed to fetch" 消失**，模拟器稳定渲染出业务登录页（含**服务地址 `http://127.0.0.1:18081`**，即本轮 `TARO_APP_API_BASE` 构建结果）。**更正上轮结论**：把成因归结为"系统代理下 servicewechat.com TLS 失败"是**错的**——代理仍开启时重启 IDE 即可正常渲染，真实原因是 IDE 进程状态损坏/多实例；代理观察本身属实但已不作为结论，**无需改动系统网络设置**。仍阻塞：`cli auto` 本次成功（9420 监听、AppID 解析成功），但 **`miniprogram-automator@0.12.1` 与 IDE `v2.01.2510290` 不兼容**（`EMFILE core.wxvpkg` → `fd undefined`），且 **SendKeys 注入不到小程序渲染出的输入框**，因此**登录/列表/写操作真实链路仍未取得结果**（不得写成已验证）。后续可选：换匹配版本的 automator、请用户手工登录一次并交回截图、或走真机调试（需配合法域名）。

## 微信端 wave 3（`c63e11b`）

- 新增 `pages/order_reconciliation/`、`pages/fee_rules/`，抽出 `ui/SourceEvidence.vue` 并接入 statements / expenses / product_quality / order_reconciliation；tabBar 5 项补 **81×81 透明底 RGBA** 图标（10 个，361–710 B，自写 PNG 编码器生成，未加依赖）；`app.config.ts` 注册 2 页、`core/links.ts` 加映射、「我的」加 2 入口。
- **主代理复核**：`vue-tsc --noEmit` exit 0；`taro build` exit 0（6.49s）；`dist/app.json` **pages=24**、tabBar 5 项且图标路径齐备、`dist/assets/tabbar/` 10 个 PNG 落盘并通过 PNG 头校验。
- **与 Flutter 端的有意差异（不得写成已对齐）**：契约 `r2.order_reconciliation` 只声明 `reconcile`，故小程序订单核对页**只读、无"保存审阅"**；Flutter 端另有 `ReviewPanel(orders:true)` 走 `/order-statement-reviews`（后端有此路由但不在契约动作内）。`fee-rules/{id}/{action}` 服务端只接受 `withdraw`/`clear`，未臆造 `save`/`revoke`。
- **本机配置保护已核**：`apps/soloops_weapp/project.config.json`、`project.private.config.json`、`apps/soloops_flutter/ohos/build-profile.json5` 的 mtime 仍是 2026-10-11，本轮未被改动、未提交。

## 端上操作要点（本轮新增，务必遵守）

- **恢复设备链路只能用 `hdc rport tcp:18080 tcp:18081`（Reverse），绝不能用 `fport`**：用错方向时应用完全连不上 API（页面显示"暂时无法连接服务，请刷新重试。"），`fport ls` 里正确条目带 `[Reverse]`。
- **微信开发者工具排障要点**：①模拟器报 **"模拟器启动失败 / TypeError: Failed to fetch"** 时，**先彻底结束全部 `wechatdevtools` 进程再全新启动 IDE**（多实例/损坏状态是主因，与系统代理无关）；②IDE 窗口标题**不会**出现在 `Get-Process ... MainWindowTitle`，要用 `EnumWindows` 按标题子串查找（如 `soloops_weapp - 微信开发者工具`）；③`cli auto --auto-port 9420` 可成功开启自动化端口，但在该项目里用 **`node scripts/mobile/check_weapp_runtime.cjs`** 连接时 `miniprogram-automator@0.12.1` 会失败（`EMFILE core.wxvpkg` / `fd undefined`）；④**SendKeys 能到达 DevTools 外壳（如 Ctrl+B 触发编译）但注入不到小程序渲染出的输入框**。
- **模拟器与微信开发者工具不要同时长跑**：本轮两者并行时主机空闲内存降到约 2.4 GB，**模拟器于 08:07:40 崩溃并生成 minidump**；崩溃前画面先变黑，**一度疑似应用渲染缺陷，实为模拟器故障**（当时应用的无障碍树仍完整，重启后渲染正常）。恢复步骤：结束 `wechatdevtools` 全部进程 → **前台直接运行 `Emulator.exe -start 22`（`Start-Process` 起不来，且首次冷启动约 20 秒后才出现在 `hdc list targets`）** → 重新 `hdc rport` → 应用会话与库均正常。
- **模拟器黑屏 ≠ 应用缺陷**：先用 `hidumper -s WindowManagerService -a '-a'` 看应用窗口是否仍在前台且 `uitest dumpLayout` 能否取到完整树；若树完整而画面全黑，优先怀疑模拟器显示/合成器异常。
- **截图判活**：`snapshot_display -f /data/local/tmp/x.jpeg` 两次哈希完全相同通常意味着画面冻结（模拟器异常），不是真的没变化。
- **做断线类测试要"先加载记录、再断链"**：页面离线时无法加载列表，只有已加载的记录才能触发写操作的待确认态。
- **HarmonyOS Settings 可用 `aa start -b com.huawei.hmos.settings -a com.huawei.hmos.settings.MainAbility` 打开**（`DarkModeExtensionSettingsAbility` 等扩展能力无权限直接启动）；`uitest dumpLayout -b <settings bundle>` 取不到树，改用 `snapshot_display` 截图 + 按坐标点击（预览图 874×1890 → 实机 1320×2856，比例 1.5103）。**滑块类控件（如字体大小）对 click/swipe/drag 均无响应。**
- **只读 API 探针**（可选，本机 18081）：必须带 `X-SoloOps-Client: mobile` 与 `Origin: http://127.0.0.1:18080`，`client_type` 仅 `ohos|android|weapp`；否则返回 403 `client_rejected` 或 422。token 存 `.local/mobile-business/token.txt`（本机文件，勿提交）。

- **键盘开着时不要滑动页面**：滑动会落在键盘按键上，把 `、` 连续打进当前输入框。`scripts/mobile/ohos_ui.py` 的 `hide-ime` 已修好（改读 `WindowManagerService` 窗口列表里 `softKeyboard` 的 **ZOrd** 判断），`findtap` 每次滑动前也会先收键盘。
- **系统剪贴板权限框**会抢焦点，使 `uitest dumpLayout -b <bundle>` 返回**空树**；本机已选"始终允许"解除。遇到空树先 `hidumper -s WindowManagerService -a '-a'` 看 `Focus window` 是否 37（应用窗口）。
- `uitest uiInput text` **只接受单个无空格参数**（多词用连字符）；中文可用。
- **折叠控件**：`选择此商品`、`R1 内部有限次预授权`、`审阅版本历史` 等都是 `ExpansionTile`，必须先点标题展开才能操作子项。
- **带时间偏移的字段**（如"订单行历史成本"的**凭据时间**）必须填 `2026-10-08T09:00:00+08:00` 这种形式，填错只报"时间须包含有效日期和时区偏移"且不落库；**改动任一字段会重置确认勾选**，保存前要重新勾选。
- `match`/`tap` 是**精确匹配或 `文本\n` 前缀**：`恢复历史 #24 为新版本` 这类按钮不能用 `恢复历史` 去匹配；同一文本多处出现时会报"found N"，改用 `findtap` 或直接 `uitest uiInput click x y`。
- UI 文本读取用 `read` 工具或 `utf8mb4`，PowerShell 直接 `Get-Content` 会显示乱码。
- `pytest backend/tests` 会清表，**禁止对保留验收库运行**。
- 真实模型、真实邮件、真实平台写入保持 0，只使用本地合成/替身。

## 新对话可直接复制的接续提示

"请继续 `Changxin-YR/AI-E-commerce-Agent` 的 `feat/soloops-mobile-m0c` 分支（worktree `.local/worktrees/mobile-m0a`，最新已推送 `5126fbb`；先 `git fetch` 核对，若 HARMONY.md 提交在其后则以该 SHA 为准）。先读 `context-memory` 分支的 `HARMONY.md`、`docs/mobile/harmony-handoff.md` 顶部、`docs/mobile/weapp-implementation.md`。

环境**核对后直接复用，不要盲目重建**：`hdc list targets` 应为 `127.0.0.1:5555`（本轮崩溃过一次，已重启恢复；**不要与前台的微信开发者工具同时长跑**）；`127.0.0.1:18081` 有合成 API（`.local/mobile-business/resume_api_18081.py`，`build_app` 直连，不跑 `prepare_samples`）；**`hdc rport tcp:18080 tcp:18081`（Reverse，不是 fport）** 应在位；Docker 容器 `soloops-harmony-r2-mysql`（3315，tmpfs）**不要停**；固定 HAP 哈希须为 `3148726747764db13eb18de7e71885b69253f3b59274998fe4367bb0ab85ec0e`（103,689,862 B）。数据库回读加 `--default-character-set=utf8mb4`。

H19/H12/H13/H14/H15/H16/H17/H09/H10/H18/H20 已端测通过；H21 已通过六项（离开恢复、断线错误、未知结果与同次请求恢复、409 版本冲突、深浅色、错误文案）。剩余顺序：**补 H21 横屏（需 DevEco 模拟器工具栏手动转屏）、H10「清除摘要正文」、H16 内部有限次预授权创建；微信端运行时联调**——模拟器现已能正常渲染小程序（登录页显示服务地址 18081），只需解决"驱动"问题：换用与该 IDE 版本匹配的 `miniprogram-automator`，或请用户手工登录一次交回结果；工程 `apps/soloops_weapp`，构建需 `TARO_APP_API_BASE=http://127.0.0.1:18081`（本机 18080 属其他项目 nx-keycloak）。

每完成一项：设备端操作 + 数据库回读 → 更新 `docs/mobile/harmony-r2-coverage.md`、`harmony-validation.json`、`harmony-implementation-progress.md`、`harmony-handoff.md` → 提交推送 → 用抓取工具核对**该 SHA** 的 `Verify mobile engineering` 为 success 再继续。只使用合成数据与本地替身，真实模型/邮件/平台写入保持 0；`pytest backend/tests` 不得对保留验收库运行；`apps/soloops_weapp/project.config.json` 与 `apps/soloops_flutter/ohos/build-profile.json5` 是本机配置，不提交不覆盖。"

## 交接约定

上下文接近上限时：先把进度/证据落盘、提交推送、更新本文件（在该 checkout 只用 `git commit --only HARMONY.md`，README.md 有用户本机改动），再创建接续聊天并给出精确 SHA 与上述入口。子代理成果必须由主代理独立验证（type-check/构建/数据库回读）后再提交。
