# SoloOps 鸿蒙 R2 · 跨账号接续记忆

## 最新接续检查点（2026-10-11）

- 鸿蒙分支最新提交已推送：`58f06d8456deb8c1a93b66aefacfa4267e09a0f8`。先读该SHA的docs/mobile/harmony-handoff.md顶部更新；下面账号切换记录为历史基线。
- 已恢复停止后清空的专用tmpfs库：确认0张表后导入原已校验备份；费用1138仍v1/2.3456，批次1181–1187和迁移版本恢复。未提交本轮费用修订。
- 合成API现在在本机127.0.0.1:18081；设备仍18080，使用hdc rport tcp:18080 tcp:18081。18080属于其他项目nx-keycloak，不停止它。
- 固定HAP覆盖安装、Asset会话/店铺918/工作台恢复均通过。随后API22再次离线，模拟器日志出现主机空闲268MB与std::bad_alloc。用户已被询问资源安排；不要擅自停止其他任务Android或Docker。
- HDC助手修复退出码0但[Fail]的错误检测；3项无数据库回归与Ruff通过。未扩大运行会清库的测试。剩余财务与H03–H21端测仍待继续。
- 上下文接近满时继续按用户要求保存推送、创建接续聊天、传入准确SHA与上述交接文档；创建后旧聊天停止写入。当前还未创建接续聊天。

更新：2026-10-11。用户要求把完整进度保存到GitHub后切换账号。本聊天在保存检查点后停止业务写入；新账号可直接按下文接手，不依赖聊天历史。

## 准确起点

- 仓库：[Changxin-YR/AI-E-commerce-Agent](https://github.com/Changxin-YR/AI-E-commerce-Agent)。
- 业务分支：`feat/soloops-mobile-m0b`。
- **已提交并推送的最新检查点：`7edb160c3f0c4b8d026d799e25970d8245492736`**。
- **先读：[完整账号切换交接](https://github.com/Changxin-YR/AI-E-commerce-Agent/blob/7edb160c3f0c4b8d026d799e25970d8245492736/docs/mobile/harmony-handoff.md)**。内含工作区、环境、固定HAP、已验收事实、数据库备份、剩余清单和操作方法。
- 核心业务代码修复提交`ac668c2bf14412add426a9b9cf23a7b6cb2513f4`；最新检查点补齐端测结果和设备助手。main不是当前鸿蒙进度分支。

## 当前结果

H01–H21核心源码覆盖完成；API22集中验收部分通过，尚未完成全部端测。按V1.3（21功能/149原API引用、H14补6操作）持续完成，不重写已实现模块，不等待逐包批准或CI。用户要求加快速度并保持质量，当前只运行合成模型/邮件替身，真实费用、邮件和平台写入0。

- 自动验证：23Flutter、12CSV跨端对照；后端全量基线890/529.36秒、定向97；新商品渠道契约1项；夹具隔离5项；Dart/Ruff/mypy180文件通过。完整后端基线通过后没有因小修复重复清库。
- 端上：登录/资料/建店918/会话重启恢复；批次1181–1187全部committed、errors0；巡检184、事项195审批/复检/完成核对。
- B1：257两次独立审批，7步、v10 succeeded；分析23与Listing92草稿分别落库。Listing91已批准、系统CSV保存603字节。
- 客服43/v2 human_review/en审阅，系统分享接收后保存1294字节完整CSV。库存过期未知和低库存区分正确。
- 利润存档5：售价25、成本8.1234、余额16.8766，费用/保本价未知。费用1138/v1 active，synthetic/generic，金额2.3456 USD，发生时间正确转UTC。
- 已修复并回归：导入修正原值捕获、长表单离屏校验、B1跨渠道商品误选。

## 下一步

从已保存费用1138之后继续财务闭环：费用修订/订单关联/映射、账单、订单核对、回款；随后经营分析/成本、跨店总览、规则授权、计划通知、质量/本地修订、替身外发。补语义映射/分片manifest、AI预算/暂停取消/未知结果、客服政策/审阅失效/人工凭据、冲突/来源清除/跨店/生命周期和布局。具体已过与待验状态见handoff和coverage，不能将部分设备通过写成全部完成。

## 本机关键保护

实际workdir：`C:/Users/27363/Desktop/AIEcommerceAgent/.local/worktrees/mobile-m0a`；分支上述。保存项目带空格旧路径不作为本轮workdir。一个聊天独占这个worktree，其他平台使用独立副本。用户本轮已明确允许鸿蒙/安卓模拟器短时并行；不停止其他任务的模拟器。

- 当前API22设备运行，HDC `127.0.0.1:5555`，API `127.0.0.1:18080`，入口`scripts/mobile/business_fixture.py`。最后设备页面为已保存费用1138。
- Docker `soloops-harmony-r2-mysql`，3315/`soloops_harmony_r2_test`，head`b42e83f516c0`，仍运行。tmpfs停容器会丢数据；backend pytest会清表，不能对这份保留库重跑。
- 账号切换前已本机备份`.local/mobile-business/harmony-account-switch.sql`，424238字节，SHA256`e67ce2a4bc09b8751c28f45855b3a162575327e44d8486c4ca88ccf29b377f82`。同电脑切换账号直接复用库；必要恢复仅限该专用库。
- 固定已安装HAP `.local/mobile-business/accepted-scope-fix.hap`，SHA256`3148726747764db13eb18de7e71885b69253f3b59274998fe4367bb0ab85ec0e`，103689862字节。SDK24编译/API22运行，工具链与恢复命令详见handoff。
- 本机配置/日志/备份/HAP没有上传GitHub。保护未提交`apps/soloops_flutter/ohos/build-profile.json5`和`apps/soloops_weapp/project.config.json`，不输出/覆盖/提交。
- context-memory checkout的README.md有用户MM改动，保持原样；后续仍只`commit --only HARMONY.md`。

## 新账号可复制的提示

请继续Changxin-YR/AI-E-commerce-Agent的鸿蒙API22完整R2验收。读取context-memory分支HARMONY.md，再读取feat/soloops-mobile-m0b分支docs/mobile/harmony-handoff.md；起点7edb160c3f0c4b8d026d799e25970d8245492736。复用指定worktree与合成环境，从费用1138后的财务闭环继续，按待验清单快速完成并保持质量；只使用本地模型/邮件替身。
