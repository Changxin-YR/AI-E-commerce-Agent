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
| H03 首页/运营/待办 | 核心表单、状态动作、证据和复检已写入 | 跨模块目标页与业务日期显示待补；未验证 |
| H05–H20 | 待继续实现；AI/客服仅旧读取列表 | 下一项H05 Agent/B1，再H06 Listing、H07客服 |
| H21 共用 | 五入口、网络、业务注册路由、共用表单/来源展开 | 全部业务路由注册、业务时区/日期、集中异常/布局检查 |
| 集中自查/API22运行 | 尚未开始 | 全业务源码覆盖后进行 |

## 下一步直接做

1. 读取AGENTS顶部、V1.3与本账本；复用本worktree与分支继续。
2. 实现H05：`frontend/src/views/AgentView.vue`、`components/AgentRunReview.vue`、`components/InternalAuthorizations.vue`、`api/agent.ts`、`types/agent.ts`，以及对应authorization API/types/backend schemas。自然语言目标、模板/技能/模型状态、预算与数据授权、产品/消息上下文、启动/执行步骤、暂停/继续/取消/重试、逐节点审批、历史回读全部落实。
3. B1为 `margin_review` 模板。读取types剩余MarginEvidence及Web专用组件，完整实现两次审批、金额/成本来源/适用规则与结果深链；按已存在API校验合法payload，不写通用JSON编辑器。
4. 将 `product_app.dart` 的AI入口从RecordListPage替换为正式AgentPage，并在businessRoutes注册 `/agent`，支持execution、authorization与mode等query。接着H06 Listing、H07客服，再V1.3后续H08–H20。
5. H03目前含发往Agent/Listing/客服/库存/分析等目标的真实链接，目标未注册时只提示页面接入中；必须在对应业务模块实现时补齐，不能算深链已全覆盖。
6. 全部实现后统一：静态检查、HAP构建、认证/迁移/业务定向测试、CSV分片与Python/Web逐字节对照、API22完整卖家旅程、修复和用户联调。构建阻碍实现时可提前使用必要类型反馈。
7. 日期当前输入显式ISO偏移、展示API时间字符串；H21需补业务时区友好显示和日期选择。本机timezone-0.10.0缓存pubspec标记sdk <3.0.0，不应直接引用该缓存。可核对正确官方包或通过ArkTS Intl实现；不要把设备时区当业务时区。

## 本轮新增源码（H04/H03）

- `lib/features/imports/import_repository.dart`：原16个导入相关路由封装；所有写入携带原业务version。
- `imports_page.dart`：身份/类型/渠道/时区/导出时间、CSV/XLSX选择、CSV/XLSX模板下载、批次历史、分组游标。
- `import_batch_page.dart`：字段映射、别名/候选预设、个人模板、关键字段语义审阅、分页源行/旧值/新值、逐行修正、预览/提交、撤销/清除、错误文件保存分享。映射/修正使审阅与更新确认失效。
- `csv_split.dart`：独立isolate、可取消、进度、TransferableTypedData；严格跨块UTF-8、逻辑CSV记录、40MiB/40000记录/20片、单片2MiB/2000行、字段2000字符/64列、BOM/CRLF、SHA-256。
- `import_group_page.dart`：原文件拆分/建组、清单保存、同一文件指纹恢复、逐片上传/打开、已有分片选择、覆盖/重叠回读、整组撤销。
- `features/operations/operations_page.dart`：规则读取、范围表单、巡检预览与expected_preview_hash、request_id保存与未知结果同次核对、任务分页（50条）、历史/详情/来源。
- `operation_task_page.dart`：approve/reject/ignore/defer/complete/reopen/edit/record_evidence/wait_source/recheck；snapshot/业务进展、版本/证据/操作历史；完成核对与业务已解决分开。
- `features/workbench_page.dart`：三视图、身份/渠道/类型/分组、游标、recent_runs、onboarding、详情跳转。旧RecordListPage仍暂用于AI和客服。
- `core/business_navigation.dart`：注册表；`product_app.dart`现注册 /imports、/（task/run）、/settings。跨店query不匹配时要求先切店，防止在错误上下文打开。
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
