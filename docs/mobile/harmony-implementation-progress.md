# 鸿蒙完整业务版 · 实时进度

## 2026-10-11 23:45 M0-C 新分支续接（优先于下文全部历史状态）

- 新分支 `feat/soloops-mobile-m0c`（自 m0b 尖端 40db69e 分出）。首个提交 `029b53b4e91891e71ee821fea89d7bc547b8fda1`：恢复 `scripts/mobile/tests/test_business_fixture.py` 的导入顺序（修复 m0b 尖端 CI 红灯 `I001`），并把 `feat/soloops-mobile-m0c` 加入移动 CI 触发分支。**m0b 尖端 `40db69e` 的 CI 是 failure（run 38151032924），不要以它作为继续基线。**
- Docker 未运行导致 3315 tmpfs 库再次清空；已启动容器 `soloops-harmony-r2-mysql` 并从已校验备份 `harmony-account-switch.sql` 恢复：67 表、head `b42e83f516c0`、批次 1181–1187 共 7 条、店铺 2 家。
- 合成 API 以 `business_fixture.build_app()` 直接监听 **127.0.0.1:18081**（未调用 `prepare_samples`，保留样本日期），设备经 `hdc rport tcp:18080 tcp:18081` 访问 18080。
- API22 模拟器 `Emulator.exe -start 22` 启动成功（HarmonyOS 6.0.2/API22）；固定 HAP 哈希未变（103,689,862 B / `31487267…ec0e`），覆盖安装通过；会话、店铺 `HarmonyR2Main`(918)、首页计数 5/1/3 均恢复。
- **本轮新增端测通过**：费用 1138 由 v1(2.3456) 修订为 v2(2.5678)，发生时间保持 12:00+08:00→04:00 UTC 且 v1 历史保留；随后 v3 关联订单行 `SYN-G1 / 1 · SYN-CUP`（来源 `orders-generic-synthetic.csv` 批次 #1187 源行 2），数据库回读 `v3/cv3/active`。证据 `.local/mobile-business/device/expense-revision-linkage-v3.json`。
- 操作要点：费用页默认"数据身份"是 `user_import`，费用 1138 属于 `synthetic`，必须先在"数据身份"里切到"合成测试数据"再查询，否则显示"当前范围没有记录"。
- 微信小程序业务端第一波（core/登录/首页/待办/导入/AI/Listing/客服/库存）在同一分支并行实施。
- **账单与映射（本轮新增通过）**：合成账单 `statements-synthetic.csv`（5 行 sale/fee/fee/payout/refund）经设备文件选择器导入，批次 **#1188 committed**；费用映射规则 **#310**（`SyntheticShipping → 物流`）预览影响账单行 #8280 后保存 v1（`fee_rules=1`/`fee_rule_revisions=1`）；"渠道账单与费用核对"按类型合计正确（费用 14.8456 / 回款 100.0000 / 退款 8.0000 / 销售款 120.0000 USD），凭据 **`SYN-EXP-20261011-01` 编号与金额一致、差额 0.0000**（对应新建的人工费用 **#1139**，user_import/generic），未匹配的 `SYN-FEE-001` 保持"仅账单有记录 · 无法确定"；跨身份（synthetic 费用 vs user_import 账单）按作用域正确隔离。证据 `.local/mobile-business/device/statements-and-mapping-rule.json`、`statement-review-and-match.json`。
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
