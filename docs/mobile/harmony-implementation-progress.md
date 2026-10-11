# 鸿蒙完整业务版 · 实时进度

更新：2026-10-11。工作区 `.local/worktrees/mobile-m0a`，分支 `feat/soloops-mobile-m0b`。目标：按V1.3连续完成R2全部业务，之后集中模拟器自查与联调。当前提交精确SHA由接续消息给出。

## 执行依据

- 主计划 `docs/requirements/SoloOps-Mobile-V1.3.md`；范围21功能标识/149条API引用，19个R2业务路由+登录+B1。
- 当前仅实施鸿蒙，API22模拟器可运行即可；Android、微信仅保留方案。
- 用户要求先全部功能实现，再集中自查与联调；各模块提交用于上下文保存，不是停工门槛。
- 上下文接近满时自主保存、提交、推送并创建接续对话；单一开发对话独占写入。
- 当前按功能代码实现状态记录；没有业务构建/测试结论。原业务库保留，最终使用隔离MySQL/API及合成数据。

## 目前源码覆盖

完整表见 `harmony-r2-coverage.md`。

| 范围 | 当前状态 | 后续 |
|---|---|---|
| 移动会话/系统桥接/网络 | 已写入源码 | 未集中验证 |
| H01 登录 | 核心表单与会话恢复/退出已写入 | 未验证 |
| H02 资料/店铺 | 表单、建店/切店、onboarding读取 | 冲突回读、引导细节待补 |
| H04 导入 | 全链核心源码已写入 | 未构建/业务验证；独立manifest导入按契约核对 |
| H03 首页/运营/待办 | 核心表单、状态动作、证据和复检已写入 | 全路由与业务日期待补；未验证 |
| H05 Agent/B1 | 模板/目标、上下文、预算授权、执行控制、B1两次节点审批/结果深链、历史、预授权增撤/使用/恢复 | 源码已写，未静态/运行验证 |
| H06 Listing | 商品事实、生成、编辑版本、差异、审批、内部生效、当前版本复制/CSV保存分享 | 源码已写，未验证 |
| H07 客服 | 手工消息→导入审阅、政策版本、消息/订单/政策、回复/接管/审阅/导出、人工证据与历史 | 源码已写，未验证 |
| H08 库存 | 身份/渠道/SKU/时效、快照/来源、分页与低库存待办关联 | 源码已写，未验证 |
| H09 分析 | 范围/受控问数、金额证据、历史成本录入撤销、持久报告/重算/核对待办 | 源码已写，未验证 |
| H10 跨店总览 | 店铺/平台/市场/币种/日期/对比、日周30日摘要、店铺金额与来源、保存/历史/清除 | 源码已写，未验证 |
| H11–H20 | 待继续实现；H16授权部分已在Agent内实现 | 下一项H11利润测算，然后费用、账单/核对/回款、规则、调度、商品质量/修订、外发 |
| H21 共用 | 五入口、路由注册、表单、来源、业务证据、文件交付、客服离开保护 | 业务时区/日期、全部剩余路由、集中异常/布局检查 |
| 集中自查/API22运行 | 尚未开始 | 全业务源码覆盖后进行 |

## 下一步直接做

1. 读取AGENTS顶部、V1.3与本账本；复用当前worktree与分支继续。H05–H10源码已写，不再从旧只读列表起步。
2. 从H11利润测算开始，读取Web的Profit视图及API/types、后端schema，完整落地场景输入/编辑、成本/税费/汇率、结果解释、场景历史及版本。随后H12费用与映射、H13账单、H14订单核对、H15结算回款。
3. 接着H16经营规则管理（有限次授权已在 `agent/authorizations_panel.dart`）、H17定时/通知、H18商品质量、H19本地修订、H20测试外发；逐一注册业务路由和“我的”工具入口。
4. 当前已注册：/imports、/（task/run）、/settings、/agent、/listings、/support、/inventory、/analytics、/overview。B1的分析和Listing结果已有目标页。剩余深链目标随对应模块接入。
5. 全部业务实现后统一：Dart analyze/test、HAP构建、移动认证迁移/Web兼容、定向业务测试、CSV分片逐字节对照、API22完整卖家旅程、修复和用户联调。没有本轮业务端测结论。
6. H21日期仍使用显式ISO偏移输入/API原时间。Overview按业务时区日历日期手填，快捷摘要从明确结束日向前1/7/30天。需补全友好日期选择、业务时区显示与合法输入反馈；不能采用设备时区替代业务时区。缓存timezone-0.10.0的SDK声明异常，可核对正确官方包或ArkTS Intl。
7. 集中检查特别关注：Agent开始/节点动作与暂停取消并发、预算恢复对话框输入反馈、未知写入同请求ID恢复、跨店来源回读、客服未保存正文/自报证据的返回/切店/切入口、来源失效后回读、长列表和大字体。历史M0通过不代表这些业务通过。

## 本轮新增源码（H05–H10）

- `features/agent/agent_page.dart`：10种模板、自然语言目标、技能与模型费率状态、业务范围/规则、商品/消息分页选择、完整事实/订单/政策上下文、各类模型数据授权、步数/时长/USD字符串预算。逐节点推进到审批或终态；控制与执行循环有epoch，批准后继续执行期间可暂停/取消。保存开始请求ID，未知启动结果可核对同次请求；失败后版本回读。
- `agent_run_view.dart`：执行范围/来源/费用/步骤历史、运营候选、问数解释、Listing/客服候选。B1展示金额与成本口径、缺口、独立参数遗漏；分析存档与Listing草稿各自审批；verify输出分别深链。费用字符串原样保留。
- `authorizations_panel.dart`：当前daily候选创建1–20次、1–168小时授权，按预览version绑定；读取/分页/指定ID，使用授权、按范围运行、撤销、消耗历史与新增候选撤回。
- `features/listings/listings_page.dart`：商品分页、原事实与来源、草稿生成、完整前后差异、修改另存/历史恢复、版本审批、本地生效、当前有效版本复制/CSV保存分享。
- `features/support/`：SupportPage替换主入口旧读取列表；消息/草稿历史、全订单关联确认与政策选择、本地和AI候选入口、回复编辑/人工接管/存档重开、全文与目标语言审阅、导出与人工交付自报证据/游标历史。PoliciesPage支持政策新版本和清除；ManualMessagePage以CSV原字节进入ImportBatchPage完成审阅、预览与提交。
- `features/inventory/inventory_page.dart`：快照身份/渠道/时效/SKU、50条分页、来源详情、低库存待办按原对象关联及逐页查找；未知库存与未检查保留语义。
- `features/analytics/`：本地calculate/ask、范围与成本口径、分析金额/来源、source revision刷新、持久报告保存/回读/重算、核对待办创建/完成/重开、订单行成本凭据upsert/revoke及历史、expected_version/revision/request_id。
- `features/overview/overview_page.dart`：最多20店、平台/市场/币种筛选，显式业务日期与对比期，日周30日快捷窗口；分币种汇总、逐店本期/对比金额/库存/消息/待办/来源；预期修订保存、游标历史、回读/重算/清除。
- `ui/business_scope.dart` / `content_evidence.dart`：业务范围表单与B1精确7天窗口；商品/政策/回复/金额证据组件。SKU与订单行每页50，来源每页30且展开时才枚举。SourceEvidence支持明确shopId和行切换epoch，供跨店回读。
- `ui/reviewed_delivery.dart`：每次经服务端delivery接口核对版本，再调用Clipboard/ArkTS保存或分享原CSV；显示系统接管语义。
- `ui/business_widgets.dart`：awareDate从operation_task_page迁移为公共函数，其他既有待办行为不变。
- `core/app_state.dart` / `product_app.dart` / `account_pages.dart`：客服未保存修改保护覆盖系统返回、底部入口与切店/退出；AI/客服已换为正式页面，注册6个新增路由和工具入口。
- 本轮没有新增依赖；只运行Dart格式化（已修复发现的语法问题）与git diff --check。尚未analyze/test/HAP构建/设备运行。


## 本轮新增源码（H04/H03）

- `lib/features/imports/import_repository.dart`：原16个导入相关路由封装；所有写入携带原业务version。
- `imports_page.dart`：身份/类型/渠道/时区/导出时间、CSV/XLSX选择、CSV/XLSX模板下载、批次历史、分组游标。
- `import_batch_page.dart`：字段映射、别名/候选预设、个人模板、关键字段语义审阅、分页源行/旧值/新值、逐行修正、预览/提交、撤销/清除、错误文件保存分享。映射/修正使审阅与更新确认失效。
- `csv_split.dart`：独立isolate、可取消、进度、TransferableTypedData；严格跨块UTF-8、逻辑CSV记录、40MiB/40000记录/20片、单片2MiB/2000行、字段2000字符/64列、BOM/CRLF、SHA-256。
- `import_group_page.dart`：原文件拆分/建组、清单保存、同一文件指纹恢复、逐片上传/打开、已有分片选择、覆盖/重叠回读、整组撤销。
- `features/operations/operations_page.dart`：规则读取、范围表单、巡检预览与expected_preview_hash、request_id保存与未知结果同次核对、任务分页（50条）、历史/详情/来源。
- `operation_task_page.dart`：approve/reject/ignore/defer/complete/reopen/edit/record_evidence/wait_source/recheck；snapshot/业务进展、版本/证据/操作历史；完成核对与业务已解决分开。
- `features/workbench_page.dart`：三视图、身份/渠道/类型/分组、游标、recent_runs、onboarding、详情跳转。AI与客服主入口已由H05/H07正式页面替换。
- `core/business_navigation.dart`：注册表；`product_app.dart`随后已扩展至H10的9个路径。跨店query不匹配时要求先切店，来源组件另支持显式shopId回读。
- `ui/business_widgets.dart` / `source_evidence.dart`：可用表单、异步反馈、来源字段按analytics/sources真实回读。FormInput支持enabled；PageBody支持空列表下拉刷新。
- 依赖新增crypto3.0.5、typed_data1.4.0，离线pub已解析，BSD声明保存licenses。只运行Dart格式化，未运行analyze/test或HAP构建。

## 之前已有基础（仍未业务验证）

- `backend/app/api/routes/mobile_auth.py`：移动login/session/logout/logout-all，不透明Bearer，复用会话hash；账号锁定+IP20次/分钟，绝对有效期。
- `services/auth.py`：设备client_type、session_id、issued/last_used、当前设备/全部吊销；密码重置沿用同表会话删除。
- dependencies/middleware：拒绝Cookie+Bearer混用；设备Bearer进入原服务；Web Cookie仍需CSRF和来源校验。Web session/logout拒绝Bearer。
- `migrations/versions/a31e72d405bf_mobile_sessions.py`：接d93f6b210ac4，加列迁移。未对任何库执行。
- `lib/core/api_client.dart`：45秒截止、8MiB响应、原字节分块上传、拒绝重定向、401、generation、未知写入不自动重放。debug仅回环HTTP；现有M0证书可注入loopback HTTPS。
- AppState / DeviceBridge：账号/店铺、Asset持久会话、preferences地址/店铺、文件选择40MiB、保存分享。ArkTS API22类型/UTD仍待业务构建核对；share dismiss删除临时文件的消费时机待联调。
- `main()`已改ProductApp，旧诊断SoloOpsApp保留历史测试；新业务测试应覆盖ProductApp。

## 环境与保护

实际绝对工作区：
`C:/Users/27363/Desktop/AIEcommerceAgent/.local/worktrees/mobile-m0a`。
保存项目路径 `C:/Users/27363/Desktop/AI E-commerce Agent` 已过时。所有shell显式workdir；普通沙箱git可能报“must be run in a work tree”，用户已授权require_escalated在实际worktree继续。

- Flutter OH固定3.27.5-ohos-1.0.7 / Dart3.6.2，工具链 `.local/toolchains/flutter-oh-api22`。
- PUB_CACHE `C:/Users/27363/Desktop/max/pub-cache`，PUB_HOSTED_URL `https://pub.flutter-io.cn`。Dart可直接调用SDK bin/cache/dart-sdk/bin/dart.exe。
- Python主仓库 `backend/.venv/Scripts/python.exe`。SDK/构建 `scripts/mobile/build_ohos_probe.ps1`。本机SDK24编译，以API22运行判断兼容。
- HDC在DevEco/sdk/default/openharmony/toolchains/hdc.exe；运行时优先Device Manager已有实例22，CLI冷启动曾挂住。
- **保护本机未提交配置**：`apps/soloops_flutter/ohos/build-profile.json5`（签名）、`apps/soloops_weapp/project.config.json`（AppID）。不输出、不覆盖、不提交。
- 模拟器一次一台，编码时关闭。鸿蒙22与Android均已关闭；22 RAM恢复2048MiB。DevEco可能保持打开。字体滑块1；浅色已切换，旋转锁ON在业务安装时顺手核对。
- 旧M0 HTTPS夹具PID16356/44528已停止，HDC映射为空。本轮未启动新服务/设备。
- 付费模型、真实邮件、真实平台写入不作为此次开发依赖；最终联调使用隔离替身和合成数据。

## 历史技术证据

Android历史技术补齐016a1a5。鸿蒙M0曾在API22最终HAP通过26项新增断言和10项基础回归；HAP SHA256 `fc6a6ceed0bcdc4d35229943b4ddc9769276aa782fdef708f757fec1f545c742`。证据 `.local/mobile-m0b/20261011-ohos-acceptance/` 和 `.local/mobile-m0b/20261011T082953Z-ohos-emulator/results.json`。这些不代表当前业务版已验证。

## 接续保存规则

保存实现中代码时明确未测试状态和下一精确入口，提交/推送后给出精确SHA，更新context-memory；创建接续对话后旧对话停止工作区写入。持续沿用V1.3，不因新对话重置需求。
