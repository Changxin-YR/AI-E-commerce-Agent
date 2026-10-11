# 鸿蒙 API22 R2 · 账号切换接续入口

## 2026-10-12 早晨 M0-C 第三轮（优先于下文全部状态）

- 环境**核对后直接复用，未重建**：hdc `127.0.0.1:5555` 在线；`hdc rport tcp:18080 tcp:18081` 在位；合成 API 监听 **18081**（`SoloOps API`，132 路径）；保留库 `soloops-harmony-r2-mysql` 67 表 / head `b42e83f516c0` / 批次 **1181–1188**；固定 HAP `.local/mobile-business/accepted-scope-fix.hap` 哈希 `3148726747764db13eb18de7e71885b69253f3b59274998fe4367bb0ab85ec0e`（103,689,862 B）未变，设备上应用进程存活。
- **CI 已闭环**：`feat/soloops-mobile-m0c` 的 `029b53b`(38152019827)、`e67bf35`(38153782085)、`e385cb3`(38153989215)、`e1917f1`(38154570627)、`c305b0c`(38154608925) 的 "Verify mobile engineering" 全部 **success**。注意：匿名 GitHub REST 从 shell 直接调会被限流 403，用抓取工具读同一 URL 即可。
- **H19 商品本地修订已通过**：根因是"选择此商品"复选框在**折叠的 `ExpansionTile` 内**——点行标题只展开不勾选。流程：展开行 → 勾选（计数 1）→ 批量前缀/追加应用到已选表单 → 创建差异预览 **#31 v1 待审批** → 勾选核对后批准 **v2 已应用**（商品 1305 改名 + `facts` 追加，输出批次 **#1189** `origin=manual_edit`）→ **v3 已撤销**（商品与批次回退）→ **v4 正文已清除**（`snapshot` NULL、来源 0）。
- **端上避坑（本轮新增，务必遵守）**：
  - **键盘开着时不要滑动页面**——滑动会落在键盘上，把 `、` 连续打进当前输入框。`ohos_ui.py` 的 `hide-ime` 已修好（读 `WindowManagerService` 里 `softKeyboard` 的 ZOrd），`findtap` 每次滑动前也会先收键盘。
  - 系统**剪贴板权限框**会抢焦点，使 `uitest dumpLayout -b <bundle>` 返回**空树**；已选"始终允许"解除。遇到空树先 `hidumper -s WindowManagerService -a '-a'` 看 `Focus window` 是不是 37（应用窗口）。
  - 中文校验：`docker exec … mysql` 默认字符集把中文显示成 `?`，必须加 `--default-character-set=utf8mb4`；用 `HEX()` 判断库内真值。
- **下一步顺序**：H12 映射规则撤销/清除 → H13 审阅结论预览/保存/版本/清除 → H14（先在 `user_import` 作用域导入订单行）→ H15 撤销/清除 → H16 停用/重置/恢复与 AI 授权 → H17 启停/撤销/立即运行/通知深链 → H09 分析、H10 总览、H18 历史回读/清除、H20 测试外发（仅替身）→ H21 边界。

## 2026-10-11 23:45 M0-C 接续环境复核（优先于下文历史状态）

- 当前业务分支为 **`feat/soloops-mobile-m0c`**（自 m0b 尖端分出，worktree 不变：`.local/worktrees/mobile-m0a`）。首提交 `029b53b4e91891e71ee821fea89d7bc547b8fda1` 修复了 m0b 尖端 `40db69e` 的 CI 红灯（`scripts/mobile/tests/test_business_fixture.py` 导入顺序 `I001`）并把 m0c 加入 CI 触发分支；**m0b 尖端 CI 为 failure，勿以其为基线**。
- 本机环境已按上文命令完整恢复：Docker `soloops-harmony-r2-mysql`（127.0.0.1:3315，tmpfs）从 `harmony-account-switch.sql` 恢复 67 表/head `b42e83f516c0`/批次 1181–1187；合成 API 监听 **18081**（`build_app()` 直连，不跑 prepare_samples）；`hdc rport tcp:18080 tcp:18081`；API22 模拟器运行中，固定 HAP 哈希未变（31487267…ec0e）并已覆盖安装。
- 设备状态：会话/店铺 918 恢复；费用 1138 已完成 **v1→v2 修订（2.5678）** 与 **v3 订单行关联（SYN-G1 / SYN-CUP，批次 #1187 源行 2）**，数据库回读 `v3/cv3/active`，证据 `.local/mobile-business/device/expense-revision-linkage-v3.json`。
- 提醒：费用页需先把"数据身份"切到"合成测试数据"才能看到 1138（默认 `user_import` 会显示"当前范围没有记录"）。
- **H13 已部分通过（截至本轮）**：账单按类型合计正确；凭据 `SYN-EXP-20261011-01` 与人工费用 #1139（2.3456 USD）**编号与金额一致、差额 0.0000**；`SYN-FEE-001` 无人工费用故保持"仅账单有记录·无法确定"。**费用核对审阅的结论预览/保存/版本/清除尚未端测**，是 H13 的下一步；随后 H14 订单账单核对、H15 结算回款（账单已有 payout 行 `PAY-SYN-001 · 100.0000 USD` 可直接用于回款核对）。
- 下一步：H12 费用映射规则 → H13 渠道账单 → H14 订单核对 → H15 回款 → H09/H10/H16–H20 → H21 边界/布局。
- **账单合成样本已就绪（本轮新增，可复现）**：`statements-synthetic.csv`（473 B）。放到设备 `Download` 后，在"首页 → 导入业务文件 → 报表类型=渠道账单 → 选择 CSV / XLSX → 下载与接收 → 下载管理器"选中它；映射会自动匹配，预览为"5 新增 / 0 更新"，确认后批次 **#1188 committed**，`statement_lines` 5 行。内容：
  ```
  statement_id,line_id,entry_type,amount,currency,occurred_at,evidence_ref,fee_name,settlement_id
  SYN-ST-001,1,sale,120.0000,USD,2026-10-08T09:00:00+08:00,,,
  SYN-ST-001,2,fee,12.5000,USD,2026-10-08T09:00:00+08:00,SYN-FEE-001,Platform commission,
  SYN-ST-001,3,fee,2.3456,USD,2026-10-11T12:00:00+08:00,SYN-EXP-20261011-01,SyntheticShipping,
  SYN-ST-001,4,payout,100.0000,USD,2026-10-10T10:00:00+08:00,PAY-SYN-001,,
  SYN-ST-001,5,refund,8.0000,USD,2026-10-09T11:00:00+08:00,,,
  ```
  第 3 行与人工费用 1138 同凭据编号（`SYN-EXP-20261011-01`），可直接用于账单/费用核对与回款核对。
- **映射规则已通过**：规则 **#310**（`SyntheticShipping → 物流`，依据 `Synthetic-fee-name-mapping`）预览影响账单行 #8280 后保存为 `当前有效 · v1`；`fee_rules=1`、`fee_rule_revisions=1`。
- 端上操作提醒：`uitest uiInput text` 只接受**单个**无空格参数（多词会被判参数数量错误）；表单必填项（如"映射依据"）留空时预览按钮不会提交，界面看起来"没反应"。键盘开合会改变布局坐标，输入后必须重新 dump 再取坐标。

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

更新：2026-10-11。用户要求保存到GitHub后切换账号；本聊天保存后停止业务写入。新聊天从本文件继续，不依赖旧聊天记录。

## 立即定位

- 仓库：`Changxin-YR/AI-E-commerce-Agent`。
- 业务分支：`feat/soloops-mobile-m0b`。切换后先fetch并核对该分支最新提交；不要使用main替代本分支的移动进度。
- 核心业务修复检查点：`ac668c2bf14412add426a9b9cf23a7b6cb2513f4`（B1范围修复、双审批端测）。本文件随之后的账号切换证据提交；精确最终SHA同步到`context-memory`分支的`HARMONY.md`。
- 实际本机工作区：`C:/Users/27363/Desktop/AIEcommerceAgent/.local/worktrees/mobile-m0a`。保存项目的带空格旧路径不用于本轮鸿蒙开发。
- 同一时刻仅一个聊天写该worktree。其他平台聊天有独立副本，不操作其进程或文件。

## 目标与授权

执行`docs/requirements/SoloOps-Mobile-V1.3.md`，持续完成鸿蒙API22完整R2、集中模拟器自查与用户联调。H01–H21源码已覆盖，149条原API引用及H14补充6路由操作；目前处于集中验收，尚未全量端测通过。无需真机，无需逐包确认或等CI。用户要求加快速度并保持质量，合并同类操作、复用已通过检查。

用户本轮明确允许鸿蒙和独立Android任务的模拟器短时并行。当前鸿蒙实例22，不停止其他聊天的Android实例。本轮模型、邮件和平台操作使用合成数据/本地替身，真实费用、真实邮件和实际平台写入均为0。

## 已完成与证据

| 范围 | 已确认结果 |
|---|---|
| 静态/自动检查 | Dart无问题；23Flutter测试；12组CSV跨端对照；后端全量基线890/529.36秒；97后端定向；最新ProductFacts契约1项；夹具隔离5项；Ruff/mypy180文件通过 |
| H01/H02 | 合成登录、经营资料、店铺918创建、模拟器重启/覆盖安装后会话恢复 |
| H04 | 模板系统保存；商品CSV1181新3、XLSX1182相同3；纠错1183新1；订单1184新3；库存1185新3；客服1186新2；generic订单1187新3，均committed/errors0 |
| H03 | 巡检184生成195–197；195审批/复检/完成核对，保持awaiting_source，未把人工完成当外部问题解决 |
| H05 | B1渠道筛选复验；执行257两次独立批准analysis_todo/listing_draft，7步完成、version10，分析23与草稿92分别落库 |
| H06 | Listing90生成、91编辑批准，92由B1另存draft且基线91仍approved；系统保存CSV取回603字节 |
| H07 | 混合物流退款诉求草稿43/v2保持human_review，缺口提示、en全文审阅通过；系统分享→另存为后取回1294字节完整CSV |
| H08 | 过期BOX为未知；CUP库存2/阈值5低库存；显示来源及关联事项195 |
| H11 | 利润存档5：售价25、成本8.1234、余额16.8766、余额率67.5064%；费用与保本价未知明确保留 |
| H12 | 费用1138/v1 active，synthetic/generic，2.3456 USD；12:00+08:00转04:00 UTC，数据库回读通过 |

已修复：导入编辑基线late捕获错误、长表单离屏导致Form/校验器卸载、B1跨渠道商品误选。对应回归和源码已推送。最新覆盖详见`harmony-r2-coverage.md`；机器可读结果及产物哈希见`harmony-validation.json`，不要把部分端测当成全部通过。

## 下一步按顺序推进

1. 先读本文件、AGENTS顶部、V1.3、progress和validation；核对git状态、本机服务、HDC和固定HAP哈希。当前位置为已保存费用1138页面，可回读后继续，勿重复创建同凭据费用。
2. 完成费用修订/订单关联/撤销、映射规则、渠道账单、订单核对审阅、回款登记/核对及历史。账单合成样本尚未导入；沿用隔离测试库。
3. 继续经营分析/订单行历史成本、跨店总览、经营规则与有限次授权、计划/通知、商品质量/本地修订、替身外发闭环。H09–H20源码无需重写。
4. 补H04语义映射审阅/个人模板、分片与独立manifest恢复；H05模型预算/暂停/取消/未知启动重试；H07政策、编辑使审阅失效、人工自报凭据。模型和邮件只用现有替身。
5. 补未知写入同UUID、版本冲突、来源清除/失效、跨店深链、前后台/重启、横屏/大字体/深浅色。已验收系统分享接收字节可复用，不重复执行相同检查。
6. 完整端测结束后整理用户可操作入口与联调说明；剩余问题必须保留真实状态。

## 本机恢复与保护

- Python：`C:/Users/27363/Desktop/AIEcommerceAgent/backend/.venv/Scripts/python.exe`。
- Flutter OH3.27.5-ohos-1.0.7/Dart3.6.2：本worktree`.local/toolchains/flutter-oh-api22/bin/flutter.bat`。`PUB_CACHE=C:/Users/27363/Desktop/max/pub-cache`，`PUB_HOSTED_URL=https://pub.flutter-io.cn`。
- SDK24编译/API22运行。HDC：`C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe`；target `127.0.0.1:5555`；bundle `dev.soloops.soloops_flutter` / `EntryAbility`。优先DevEco Device Manager已有22实例，RAM2048。
- 固定已安装包：`.local/mobile-business/accepted-scope-fix.hap`，103689862字节，SHA256 `3148726747764db13eb18de7e71885b69253f3b59274998fe4367bb0ab85ec0e`。构建`scripts/mobile/build_ohos_probe.ps1`。IDE默认构建可能覆盖原输出，安装前校验固定副本。
- 独立API：`http://127.0.0.1:18080`，入口`scripts/mobile/business_fixture.py`，当前运行；重启先检查IPv4该端口的进程命令行，避免同端口其他服务。用隐藏窗口启动，日志写`.local/mobile-business/api.stdout.log`/`api.stderr.log`。
- HDC端口映射：`hdc -t 127.0.0.1:5555 rport tcp:18080 tcp:18080`。应用登录合成账号`harmony_r2`，合成测试密码从fixture源码常量读取；owner995/shop918、店名HarmonyR2Main。
- Docker：`soloops-harmony-r2-mysql`，127.0.0.1:3315，专用库`soloops_harmony_r2_test`，迁移head`b42e83f516c0`。此容器tmpfs，停容器会丢库；目前保持运行。`pytest backend/tests`会清表，不能针对本次保留库重跑全量测试。
- 本机配置`.local/mobile-business/test.env`/`mysql.env`不输出、不上传。账号切换前已生成逻辑备份`.local/mobile-business/harmony-account-switch.sql`，424238字节，SHA256 `e67ce2a4bc09b8751c28f45855b3a162575327e44d8486c4ca88ccf29b377f82`。仅在专用测试库确需恢复时使用，先保全现存数据。切换Codex账号而电脑不变时，直接复用原库即可。
- 本机证据在`.local/mobile-business/`：`b1-db.json`、`account-switch-db.json`、`journey-db.json`、`device/`，合成样本`samples/`；原始文件/配置/日志/HAP/SQL不进入GitHub。
- 两项用户本机配置不覆盖、不提交：`apps/soloops_flutter/ohos/build-profile.json5`、`apps/soloops_weapp/project.config.json`。
- 工作区在旧沙箱根之外，本机工具可能需`require_escalated`；普通沙箱git的“must be run in a work tree”不是仓库损坏。

## 提速操作约定

`scripts/mobile/ohos_ui.py`每步读取新鲜布局；`findtap`/`findtapup`处理滚动，`--quiet`跳过重复动作后布局；到业务节点再`dump 标签`保存证据。文本匹配使用实际标签或源码，不猜按钮名。`@input:N`包含所有TextInput（含只读FactLine），键盘改变视口后重新核对索引。

`input`等待焦点与全选完成后再注入文本；随后用`hide-ime`仅在键盘存在时收起。`key 2`用于有意系统返回。输入完成须回读最终字段，写入后核对服务器结果和数据库。模拟器原生节点标识随布局采集变化，不能跨快照缓存。系统选择器/分享面板可能异步出现，应读取稳定界面再继续。保存的合成文件位于`/storage/media/100/local/files/Docs/Download/`，只读取本任务文件。

## 给新账号的接续提示

“请继续仓库Changxin-YR/AI-E-commerce-Agent的鸿蒙API22完整R2验收。先读取context-memory分支HARMONY.md及feat/soloops-mobile-m0b分支docs/mobile/harmony-handoff.md。复用指定worktree、专用合成库与固定HAP，从费用1138之后的财务闭环继续；保持已有通过证据，按待验清单快速完成，不重写已实现模块。只使用本地模型/邮件替身。”
