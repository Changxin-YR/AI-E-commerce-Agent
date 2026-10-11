# SoloOps 鸿蒙完整 R2 · 当前接续记忆

更新：2026-10-11。当前最新开发计划为业务分支内 `docs/requirements/SoloOps-Mobile-V1.3.md`；实时账本 `docs/mobile/harmony-implementation-progress.md`，覆盖表 `docs/mobile/harmony-r2-coverage.md`。

## 当前工作

- 用户授权连续完成鸿蒙全部R2业务后集中自查与联调。目标API22模拟器；Android和微信本轮保留方案。范围21功能标识/149条API引用。
- 源码分支 `feat/soloops-mobile-m0b`，已提交/推送精确SHA **bfd2286929d7682cc51739b60530f583fe32a220**。
- 本提交增加H04导入业务闭环、后台逻辑CSV拆分/分组恢复、H03工作台筛选/巡检/待办全动作/证据与来源复检。24文件，2621增101删。
- 上一提交58c4b44包含移动Bearer认证/迁移、ArkTS桥接、Flutter网络、登录/资料/建店基础。
- 当前只完成源码与普通格式化/离线依赖解析/保存差异检查；尚未业务analyze/test/HAP构建/API22端测。移动会话迁移尚未执行。
- 下一步立即H05 Agent/B1（margin_review两次审批），然后H06 Listing、H07客服、剩余H08–H20；AI/客服现在仍是旧只读列表，须替换。完整业务后集中验证。

## 代码与范围注意

- 新页面 `lib/features/imports/`、`features/operations/`；共用 `ui/business_widgets.dart`、`ui/source_evidence.dart`。
- `core/business_navigation.dart`是业务路由注册表，`product_app.dart`已注册/imports、/（task/run）、/settings，其余随模块完成加入。完整跨模块深链仍待实现。
- 日期当前为显式ISO时区输入/API原时间显示；H21须补业务时区友好日期能力。
- 新增crypto3.0.5、typed_data1.4.0，已从原PUB_CACHE离线解析并保存BSD许可证。其他业务服务继续复用原后端。
- 不把历史M0通过当作本次业务通过，不扩大74SO长期ERP范围，不以旧逐包审批/CI作为继续开发门槛。

## 工作区和保护

实际workdir `C:/Users/27363/Desktop/AIEcommerceAgent/.local/worktrees/mobile-m0a`；保存项目“电商智能体”ID `1c274a7b-2f1e-45ca-bf1b-10475766545b`的原带空格路径已过时。所有shell显式workdir，按已授权require_escalated；复用worktree，不reset。

两项未提交本机配置须保持：apps/soloops_flutter/ohos/build-profile.json5（签名）与 apps/soloops_weapp/project.config.json（AppID）。不输出、不覆盖、不提交。

Flutter OH3.27.5-ohos-1.0.7/Dart3.6.2，`.local/toolchains/flutter-oh-api22`；PUB_CACHE `C:/Users/27363/Desktop/max/pub-cache`。SDK24编译、API22运行。模拟器一次一台，鸿蒙22/Android均关闭，22 RAM原2048MiB。运行阶段用DevEco Device Manager已有22，CLI曾挂住。原数据库保留，最终隔离MySQL/API、合成样本、模型/邮件替身。

## 接续规则

上下文接近满时按授权保存、提交、推送并创建接续对话，提供精确SHA和账本；新对话独占工作区，旧对话停止写入。当前线程将在创建接续后停止写入。

context-memory中的README.md已有用户MM（暂存及工作区），不得提交/覆盖/回滚。本次仅HARMONY.md新增，通过commit --only保存。其他历史记忆文件保留为历史记录。
