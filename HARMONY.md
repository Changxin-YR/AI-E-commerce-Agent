# SoloOps 鸿蒙完整 R2 · 当前接续记忆

更新：2026-10-11。主计划 `docs/requirements/SoloOps-Mobile-V1.3.md`；实时账本 `docs/mobile/harmony-implementation-progress.md`，覆盖表 `harmony-r2-coverage.md`，验证 `harmony-validation.md/json`。

## 当前结果

- 用户已授权持续完成鸿蒙API22全部R2业务、集中自查后联调；无需逐阶段批准或等待CI。Android/微信本轮仅方案。范围21功能标识/149条API引用，H14另新增6个持久审阅路由操作。
- 业务分支 `feat/soloops-mobile-m0b`，已提交并推送 **926136c4cd21d2de7e20080adefb9d712a67aa2b**。75文件，7568增321删。提交前任务源码/文档已核对，当前业务工作区只有两项受保护本机配置未提交。
- H11–H20核心原生业务页面全部实现：多方案利润/汇率、费用与映射、账单与订单审阅、回款、规则、计划通知、商品质量/修订、测试外发。H02补资料冲突回读与onboarding，H04补独立manifest恢复，H21补业务时区/日期、全部路由/query、离开保护/前台会话核对。详细文件/行为在progress。
- H14增加OrderStatementReviewService/schema/router，StatementReview.kind默认fees、订单审阅orders，原版本/幂等/来源清除共用；迁移head **b42e83f516c0** 接移动会话 **a31e72d405bf**。
- 本次验证：Dart analyze无问题，**17 Flutter tests**；**12组CSV Python/Dart逐字节一致**；**97后端定向/64.18秒**，包括移动Bearer/Web兼容、订单/费用审阅、订单核对、迁移回退/升级/Alembic差异和数据保护；Ruff规则/185文件格式、mypy180 app文件通过。
- 完整业务SDK24 x64 debug未签名HAP编译通过，103666758 bytes，SHA256 **32a7eb1c3ccca3207113f76d5f4c88a962b056c9dfcd95eec32f80b204f52c58**。实际文件大小/哈希以validation.json为准。当前业务尚未安装到API22；全部端到端业务与用户联调仍待做，历史M0通过不替代。

## 立即下一步

1. 按progress的「下一步直接执行」启动隔离HTTP API和合成卖家样本，使用已有模型/邮件测试替身。实际外部模型/邮件/平台写入仍关闭。当前仅数据库运行，没有新API，不能复用真实经营库。
2. 独立容器 **soloops-harmony-r2-mysql**，回环 **3315**，库 **soloops_harmony_r2_test**，head b42e83f516c0。配置在实际worktree `.local/mobile-business/test.env` / `mysql.env`，不得输出/提交。这是tmpfs，停止容器会丢合成数据；测试库外原数据未动。后续pytest与API业务旅程在此库串行，避免互相清数据。
3. 开DevEco Device Manager现有API22，RAM2048MiB，当前鸿蒙/Android均关闭。一次一台，编码时关闭空闲模拟器。此前API22接受未签名x64调试HAP，按历史HDC安装流程；不需要改签名配置。CLI冷启动曾挂住，优先已有22实例。
4. API22完整卖家旅程：登录/初始化→导入映射审阅/分片/独立清单→巡检待办→Agent/B1两次审批→Listing/客服→财务/规则计划→质量修订→替身外发。逐项真实数据库回读；异常/冲突/清除、未知结果同UUID、跨店、生命周期/重启、文件保存分享、横屏/大字体/深浅色全部核对。发现缺口继续修复。完整既有后端回归尚未执行，按影响适当补验。
5. 源码已进入集中自查阶段，不从H11重新开发。业务时间固定timezone0.10.1/IANA2025b，Dart3.6.2实际解析成功；夏令时缺失拒绝、重复明确选偏移。SDK依赖许可证已保存。当前HAP路径 `apps/soloops_flutter/ohos/entry/build/default/outputs/default/entry-default-unsigned.hap`；脚本 `scripts/mobile/build_ohos_probe.ps1`。

## 工作区和保护

实际workdir **C:/Users/27363/Desktop/AIEcommerceAgent/.local/worktrees/mobile-m0a**。保存项目“电商智能体”ID `1c274a7b-2f1e-45ca-bf1b-10475766545b` 的原带空格路径已过时；所有shell显式workdir。用户已授权实际worktree的require_escalated；普通沙箱git可能报must be run in a work tree。复用现有分支，不reset或另开worktree。

仅两项本机未提交配置：`apps/soloops_flutter/ohos/build-profile.json5`（签名）和 `apps/soloops_weapp/project.config.json`（AppID），不输出/覆盖/提交。

Flutter OH3.27.5-ohos-1.0.7/Dart3.6.2，工具链在**本worktree内** `.local/toolchains/flutter-oh-api22`；PUB_CACHE `C:/Users/27363/Desktop/max/pub-cache`，pub.flutter-io.cn。Python主仓库 `C:/Users/27363/Desktop/AIEcommerceAgent/backend/.venv/Scripts/python.exe`。SDK24编译、API22运行；HDC在DevEco/sdk/default/openharmony/toolchains。旧HTTPS夹具已停止，HDC映射本轮未改；新API未启动。历史API22操作证据 `.local/mobile-m0b/20261011-ohos-acceptance/`，新测试日志 `.local/mobile-business/`。

## 接续规则

上下文接近满时按已授权提交/推送、更新HARMONY.md并创建接续聊天；精确SHA与账本随消息传递。新对话独占工作区，旧对话停止写入。

**context-memory README.md仍有用户暂存/工作区MM改动，不得提交/覆盖/回滚。仅commit --only HARMONY.md，其他历史记忆保持。**
