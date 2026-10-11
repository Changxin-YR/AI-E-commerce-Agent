# 鸿蒙 API22 R2 · 账号切换接续入口

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
