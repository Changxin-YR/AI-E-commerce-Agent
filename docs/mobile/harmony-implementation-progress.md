# 鸿蒙完整业务版 · 实时进度

更新：2026-10-11。实际工作区 `.local/worktrees/mobile-m0a`，分支 `feat/soloops-mobile-m0b`。执行 `docs/requirements/SoloOps-Mobile-V1.3.md`，21功能标识/149条API引用，H14补充6个路由操作另见 `harmony-api-supplement.md`。当前提交精确SHA由接续消息和context-memory/HARMONY.md给出。

## 当前结果

H01–H21核心业务源码已覆盖，集中验证已经开始。H11–H20全部新业务页、H02冲突/onboarding、H04独立manifest恢复和H21时区/日期/导航/离开保护均已写入。Dart无问题，17Flutter测试、12CSV跨端对照、97后端定向测试、Ruff/mypy180 app文件和完整业务HAP构建通过。完整表见 `harmony-r2-coverage.md`，精确证据见 `harmony-validation.md/json`。

**API22当前业务包尚未安装运行，完整卖家旅程与用户联调仍待做。** 不将历史M0技术证据当作本次业务结论。用户要求持续推进，不等待逐包批准或CI；Android与微信本轮仅方案，一次仅一台模拟器。

## 下一步直接执行

1. 读取AGENTS顶部、V1.3、本账本和validation。复用现有worktree/分支；业务页面已完成核心实现，不再从H11重新开发。
2. 新隔离MySQL已经运行：Docker `soloops-harmony-r2-mysql`，回环3315，数据库 `soloops_harmony_r2_test`，head `b42e83f516c0`。配置只在忽略目录 `.local/mobile-business/test.env` 与 `mysql.env`，不得输出或提交。此容器是tmpfs，停止会丢失合成测试库内容；只保存合成测试数据。现有业务库均未修改。编码/单测期间尚无隔离HTTP API。
3. 启动独立API（建议新的回环端口如18443 HTTPS沿用本地测试CA，或debug回环HTTP），使用3315数据库、合成账号/样本、明确关闭实际模型/邮件/平台写入。模型/外发使用现有测试替身；需要worker验证时仅隔离调度。先保留pytest所得合成状态或按测试准备脚本安全重建本库，不能连接其他数据库。
4. 启动DevEco Device Manager已有API22模拟器，RAM2048MiB；不并行开Android。API22历史可安装未签名x64调试HAP。当前路径 `apps/soloops_flutter/ohos/entry/build/default/outputs/default/entry-default-unsigned.hap`；SHA256 `32a7eb1c3ccca3207113f76d5f4c88a962b056c9dfcd95eec32f80b204f52c58`，103666758 bytes。HDC安装、HTTPS/HTTP映射、Asset登录/会话恢复/退出先验证。构建脚本 `scripts/mobile/build_ohos_probe.ps1`。
5. 用真实移动界面走完整卖家链：初始化、模板/导入映射审阅纠错、分片/独立清单恢复、巡检/待办复检、Agent/B1双审批、Listing交付、客服政策/审阅/人工凭据、库存/分析/总览、利润/费用/账单/订单审阅/回款、规则授权、调度通知、质量/本地修订、替身外发。核对数据库真实结果，记录每项证据并修复失败。
6. 专项：未知写入同UUID恢复、Agent进行中的暂停取消、版本冲突与来源清除、跨店来源/深链、前后台和重启、导出字节/分享消费时机、大字体/横屏/深浅色/长列表。新增EditGuard已覆盖费用/回款/规则/调度编辑/商品修订/外发/资料等，其他表单逐项在端上验证。对新发现的缺口继续实现。
7. 当前仅97项受影响后端定向测试，不是全后端回归。后续按实际接口/端测问题补充必要验证；最后向用户交付可操作测试入口与联调说明。无需等CI。

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
- 当前鸿蒙22/Android均关闭，HDC映射在本轮没有新增；DevEco可能开着。优先Device Manager已有22，CLI冷启曾挂住。
- 旧M0 HTTPS夹具已停止；本轮新建的只有3315合成MySQL。真实模型、真实邮件、实际平台写入为0。
- 本机证据 `.local/mobile-business/`；最后原始日志文件名见validation.json。不提交完整日志、配置、数据库或HAP。
- 历史API22 M0技术证据 `.local/mobile-m0b/20261011-ohos-acceptance/`，只供操作参考。

## 保存与接续

上下文接近满时自主更新文档、提交推送任务文件、更新独立context-memory/HARMONY.md后创建接续聊天，给精确SHA。该记忆checkout `C:/Users/27363/Desktop/AIEcommerceAgent/.context-memory` 的README.md有用户MM改动，只用commit --only提交HARMONY.md。新对话唯一写入；创建之后旧对话停止工作区写入。
