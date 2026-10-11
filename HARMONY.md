# SoloOps 鸿蒙完整 R2 · 当前接续记忆

更新：2026-10-11。当前执行计划为业务分支内 `docs/requirements/SoloOps-Mobile-V1.3.md`；实时账本 `docs/mobile/harmony-implementation-progress.md`，覆盖表 `docs/mobile/harmony-r2-coverage.md`。

## 当前工作

- 用户授权连续完成鸿蒙全部R2业务后集中自查与联调。目标API22模拟器；Android和微信本轮保留方案。范围21功能标识/149条API引用，19个业务路由+登录+B1。
- 源码分支 `feat/soloops-mobile-m0b`，已提交/推送精确SHA **8abfb7ac3717a568918c1a90091888a1dc851369**。
- 本提交为H05–H10源码，26文件4318增59删：Agent/B1两次节点审批与有限次预授权，Listing版本/审批/交付，客服政策/消息/审阅/人工证据，库存，分析/历史成本，跨店分币种摘要。
- 前置bfd2286包含H04导入全核心、大CSV逻辑拆分/分组恢复、H03工作台/巡检/待办；更早58c4b44包含移动Bearer认证/迁移、ArkTS桥接、Dart网络和登录/资料/店铺。
- 当前只完成源码与格式化/差异检查（此前依赖已离线解析）；尚未业务analyze/test/HAP构建/API22端测。移动会话迁移尚未执行。
- 下一步立即H11利润测算，再H12费用/映射、H13账单、H14订单核对、H15回款、H16经营规则（授权已在Agent里）、H17调度、H18质量、H19本地修订、H20外发，补H21后集中验证。

## 代码与范围注意

- AI与客服五入口已经使用正式AgentPage和SupportPage。新目录 `features/agent/`、`listings/`、`support/`、`inventory/`、`analytics/`、`overview/`。
- Agent模板margin_review是B1，精确7天；分别审批analysis_todo与listing_draft，展示成本/费用/独立参数证据，各verify结果已能跳到分析/Listing。模型调用需界面明确数据授权；本轮实现没有调用付费模型。
- `businessRoutes`已注册/imports、/（task/run）、/settings、/agent、/listings、/support、/inventory、/analytics、/overview。剩余路由随模块补齐。
- 共用 `ui/business_scope.dart`、`content_evidence.dart`、`reviewed_delivery.dart`。SourceEvidence支持明确shopId，跨店来源不可使用当前店铺代替。awareDate已移至business_widgets.dart。
- 金额和成本使用Decimal字符串。分析SKU/订单每页50、来源每页30并延迟展开；客服导出每次服务端校验version。手工消息进入原ImportBatchPage审阅/提交。
- 日期仍是显式ISO偏移/API原时间；Overview手填业务日历日期，1/7/30日摘要以填写的结束日为准。H21须补业务时区友好日期/输入反馈；缓存timezone-0.10.0 SDK声明异常，需核对正确包或ArkTS Intl。
- 全量检查关注Agent并发暂停取消/未知启动请求、预算恢复反馈、版本冲突与来源清除、客服离开/切店保护、跨店证据与长列表。用户要求全部实现后集中自查。
- H02资料冲突/初始化细节、H04独立manifest恢复入口、全导航/日期/布局仍在账本，不将未验证状态写成通过。

## 工作区和保护

实际workdir `C:/Users/27363/Desktop/AIEcommerceAgent/.local/worktrees/mobile-m0a`；保存项目“电商智能体”ID `1c274a7b-2f1e-45ca-bf1b-10475766545b`的原带空格路径已过时。所有shell显式workdir，按已授权require_escalated；复用worktree，不reset或另建。

两项未提交本机配置须保持：apps/soloops_flutter/ohos/build-profile.json5（签名）与 apps/soloops_weapp/project.config.json（AppID）。不输出、不覆盖、不提交。

Flutter OH3.27.5-ohos-1.0.7/Dart3.6.2，实际worktree内 `.local/toolchains/flutter-oh-api22`；PUB_CACHE `C:/Users/27363/Desktop/max/pub-cache`。SDK24编译、API22运行。模拟器一次一台，鸿蒙22/Android均关闭，22 RAM原2048MiB；本轮未启动设备/服务。运行阶段用DevEco Device Manager已有22，CLI曾挂住。原数据库保留，最终隔离MySQL/API、合成样本、模型/邮件替身。

## 接续规则

上下文接近满时按授权保存、提交、推送并创建接续对话，提供精确SHA和账本；新对话独占工作区，旧对话停止写入。计划与记忆不因换对话重置。

context-memory的README.md有用户MM（暂存及工作区），不得提交/覆盖/回滚。本次只更新HARMONY.md，通过commit --only保存；其他历史记忆保留。
