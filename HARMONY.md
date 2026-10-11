# SoloOps 手机三端 · 跨账号接续记忆

## 最新接续检查点（2026-10-12 早晨，M0-C 第三轮）

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
  | `dc911ca` | H18 质量报告历史/清除 + H09 经营分析 + H10 跨店总览 | **本文件提交后需复核** |

- 上轮"未核对"的 4 个 SHA 已闭环：`029b53b`、`e67bf35`、`e385cb3`、`e1917f1` 的 CI 均为 **success**。
- **CI 读取方式**：匿名 REST 从 shell 直接调会被限流 403；用抓取工具读
  `https://api.github.com/repos/Changxin-YR/AI-E-commerce-Agent/actions/runs?head_sha=<完整SHA>&per_page=1` 可正常返回。

## 本机环境（本轮**核对后直接复用，未重建**）

- Docker `soloops-harmony-r2-mysql`（mysql:8.4，`/var/lib/mysql` 为 tmpfs，宿主 127.0.0.1:3315）保持运行；本轮开头核对为 **67 表 / head `b42e83f516c0` / 批次 1181–1188**。**不要停容器**。
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
| H09 经营分析 | **通过**（除 ask/待办联动）。默认口径：3 个已支付订单行/6 件、净销售额 **115.0000**（=120.0000−退款5.0000），成本/毛利/毛利率**"未知"**、完整排行 false。切「订单行历史成本依据」并为 `SYN-U1/1` 登记 **8.1234 USD**（凭据 `SYN-COST-001`）→ `order_cost_revisions` **#3 upsert/active**；重算得**已知成本小计 16.2468（2×8.1234）、毛利已知行数 1**，合计仍"未知"；保存 `saved_analyses` **#24 current**，旧 #23 转 `stale` |
| H10 跨店总览 | **部分通过**。日摘要（2026-10-11→10-12、USD）→ 1 家店铺、**"可核对净销售额 未知/不完整；已知子集 0；已观察订单 0"**（空窗口不当零销售）+ 覆盖说明/口径与未获取项 + 逐店依据 `HarmonyR2Main · manual · US`；保存 `overview_reports` **#39 current**。**历史摘要列表与清除未复核** |

证据目录 `.local/mobile-business/device/`（本轮新增 `h19-*`、`h12-*`、`h13-*`、`h14-*`、`h15-*`、`h16-*`、`h17-*`、`h18-*`、`h09-*`、`h10-*` 的布局快照与 `*.jpeg` 截图）。
本机新增合成样本：`.local/mobile-business/samples/orders-user-import-synthetic.csv`（`SYN-U1/U2/U3`）、`statements-order-linked-synthetic.csv`（带 `order_id` 的账单）。

## 仍待端测 / 未完成

- **H20 测试外发**（仅替身）、**H21 边界**（横屏/大字体/深浅色/离开恢复/冲突/未知结果）——完全未做。
- H09 的 ask（"用本地规则回答"）与持久报告重算/核对待办联动未走。
- H10 历史摘要列表与清除未复核。
- H16 创建有限次授权未做（需今日运营流程产生待审批候选）。
- H17 "到点自动运行"无法端测（调度服务未启用，属部署事实）。
- 微信端 wave 3 **代码已通过 type-check 与构建并提交**，但**开发者工具运行时联调（登录/列表/写操作真实链路）仍未做**。

## 微信端 wave 3（`c63e11b`）

- 新增 `pages/order_reconciliation/`、`pages/fee_rules/`，抽出 `ui/SourceEvidence.vue` 并接入 statements / expenses / product_quality / order_reconciliation；tabBar 5 项补 **81×81 透明底 RGBA** 图标（10 个，361–710 B，自写 PNG 编码器生成，未加依赖）；`app.config.ts` 注册 2 页、`core/links.ts` 加映射、「我的」加 2 入口。
- **主代理复核**：`vue-tsc --noEmit` exit 0；`taro build` exit 0（6.49s）；`dist/app.json` **pages=24**、tabBar 5 项且图标路径齐备、`dist/assets/tabbar/` 10 个 PNG 落盘并通过 PNG 头校验。
- **与 Flutter 端的有意差异（不得写成已对齐）**：契约 `r2.order_reconciliation` 只声明 `reconcile`，故小程序订单核对页**只读、无"保存审阅"**；Flutter 端另有 `ReviewPanel(orders:true)` 走 `/order-statement-reviews`（后端有此路由但不在契约动作内）。`fee-rules/{id}/{action}` 服务端只接受 `withdraw`/`clear`，未臆造 `save`/`revoke`。
- **本机配置保护已核**：`apps/soloops_weapp/project.config.json`、`project.private.config.json`、`apps/soloops_flutter/ohos/build-profile.json5` 的 mtime 仍是 2026-10-11，本轮未被改动、未提交。

## 端上操作要点（本轮新增，务必遵守）

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

"请继续 `Changxin-YR/AI-E-commerce-Agent` 的 `feat/soloops-mobile-m0c` 分支（worktree `.local/worktrees/mobile-m0a`，最新已推送 `dc911ca`；先 `git fetch` 核对，若 HARMONY.md 提交在其后则以该 SHA 为准）。先读 `context-memory` 分支的 `HARMONY.md`、`docs/mobile/harmony-handoff.md` 顶部、`docs/mobile/weapp-implementation.md`。

环境**核对后直接复用，不要盲目重建**：`hdc list targets` 应为 `127.0.0.1:5555`；`127.0.0.1:18081` 有合成 API（`.local/mobile-business/resume_api_18081.py`，`build_app` 直连，不跑 `prepare_samples`）；`hdc rport tcp:18080 tcp:18081` 应在位；Docker 容器 `soloops-harmony-r2-mysql`（3315，tmpfs）**不要停**；固定 HAP 哈希须为 `3148726747764db13eb18de7e71885b69253f3b59274998fe4367bb0ab85ec0e`（103,689,862 B）。数据库回读加 `--default-character-set=utf8mb4`。

剩余顺序：**H20 测试外发（只做替身）→ H21 边界（横屏/大字体/深浅色/离开恢复/冲突/未知结果）→ 补 H09 ask 与持久报告联动、H10 历史摘要列表/清除、H16 创建有限次授权；然后做微信开发者工具的运行时联调**（工具在 `D:/微信开发工具/微信web开发者工具/微信开发者工具.exe`，工程 `apps/soloops_weapp`，需关闭域名校验并保证 18081 在跑）。

每完成一项：设备端操作 + 数据库回读 → 更新 `docs/mobile/harmony-r2-coverage.md`、`harmony-validation.json`、`harmony-implementation-progress.md`、`harmony-handoff.md` → 提交推送 → 用抓取工具核对**该 SHA** 的 `Verify mobile engineering` 为 success 再继续。只使用合成数据与本地替身，真实模型/邮件/平台写入保持 0；`pytest backend/tests` 不得对保留验收库运行；`apps/soloops_weapp/project.config.json` 与 `apps/soloops_flutter/ohos/build-profile.json5` 是本机配置，不提交不覆盖。"

## 交接约定

上下文接近上限时：先把进度/证据落盘、提交推送、更新本文件（在该 checkout 只用 `git commit --only HARMONY.md`，README.md 有用户本机改动），再创建接续聊天并给出精确 SHA 与上述入口。子代理成果必须由主代理独立验证（type-check/构建/数据库回读）后再提交。
