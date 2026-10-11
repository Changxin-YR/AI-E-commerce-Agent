# 微信开发账号切换接续

更新：2026-10-11（Asia/Shanghai）。用户要求将现有进度保存至GitHub后切换账号。本文件与源码一起版本管理，新账号无需依赖旧聊天记忆。

## 当前接续更新（2026-10-11，W08）

账号切换后的W06审查已完成；W07新增库存、页面生命周期保护和构建gzip统计收敛，提交7baacc7620c155240a76680fe432f8e546443949，CI成功。W08已新增经营分析、历史成本凭据与版本、报告/待办、AI同范围深链；精确后续提交请以当前分支HEAD及微信进度账本为准。旧文件下方W06立即下一步仅保留当时检查点，不作为当前起点。

下一任务：H10跨店总览→H11利润→H12费用/映射→H13/H14账单核对→H15回款→H16规则→H17定时→H18质量→H19修订→H20外发→H21共享导航及集中IDE/数据库验收。必须逐页实现业务输入、证据和动作，不能用导航或JSON查看器代替。

启动脚本已更新当前首页断言但尚未连接IDE；不要重复写M0断言。Taro配置通过compiler.vitePlugins的config钩子设置reportCompressedSize=false；代码压缩保留。Node24.16.0；本机出现间歇原生内存失败时顺序重跑并记录真实退出码，不修改其他端进程。

## 仓库与起点

- 仓库：https://github.com/Changxin-YR/AI-E-commerce-Agent
- 分支：`feat/soloops-wechat-r2`
- 唯一开发目录：`C:/Users/27363/Desktop/AI E-commerce Agent/soloops-wechat`
- 当前业务源码提交：`5ac0d43384fa58b29cf9e14c53f376cd58a27d69`（W06客服首轮检查点）。本文件随后独立提交；接续以该分支最新HEAD为准，包含本文件及上述代码。
- 前一完整离线验证检查点：`22e52747a37586c5930472bf8840eae6d8edd85d`（W05 Listing）；W04为 `f3e79b36c41912cb8b88828d9dbea603c535c9df`。
- 所有shell显式workdir到微信目录；保护PC、安卓、鸿蒙及其他聊天目录。

## 接续先读

1. `AGENTS.md` 中最新微信独立授权节。
2. `docs/mobile/wechat-implementation-progress.md`：逐包事实、H01–H21状态和待验项。
3. `docs/requirements/SoloOps-Mobile-V1.3.md`、`contracts/ui-contract.json` 按feature筛选。
4. 本文件列出的W06源码、接口和验证限制。

用户持续要求微信独立、高质量、快速完成完整R2，历史端顺序及逐包批准不作为停点；接近上下文上限时完成当前小任务、提交推送并接续。真实付费模型、邮件、平台写入仅用隔离替身测试。仓库分支推送已获明确授权，本次用户再次明确要求将现有Git进度放到GitHub。

## 已有覆盖

- W01：登录/会话/店铺/经营资料；Bearer仅内存，会话和切店generation保护。
- W02：文件导入/预览/映射/纠错/提交/回读/撤销/清除、大CSV逻辑分片与导入组续传。
- W03：三类收件箱、运营巡检、待办动作/自报证据/复检与历史。
- W04：十类Agent流程、预算/许可、版本审批和运行恢复、B1独立两次审批与独立结果GET、内部预授权、经营规则读取。
- W05：Listing商品分页、事实、候选、完整差异、另存/批准拒绝、版本历史、当前生效版本核验后复制/CSV分享。
- W06首轮：`pages/support/index.vue`、`components/SupportPolicies.vue`、`services/support-policy.ts`。消息50条分页、订单关联、政策100条分页/版本/清除、回复编辑/审阅/人工接管/归档重开、交付、人工证据冻结请求与50条游标历史。首页及 `/support` 消息/草稿深链已注册。

## 立即下一步

1. 审查W06首轮客服页面，重点：并发/切店/卸载后的旧结果、未保存表单与页面离开、人工记录同次恢复、政策更新后来源失效及草稿重新核验、未知写入结果回读。该包因用户切换账号提前保存，尚未完整验收。
2. 完成生产构建。此次正常权限构建转换200模块后出现V8 allocation failure并退出1。先检查压缩worker数量/运行时内存与项目配置，不修改其他聊天进程。沙箱内另有node_modules realpath EPERM，正常权限可越过该问题。
3. 离线检查通过后继续H08库存、H09分析、H10总览、H11利润、H12费用/映射、H13/H14账单核对、H15回款、H16规则授权、H17定时、H18质量、H19修订、H20外发及H21五入口/共享能力。
4. 集中IDE自查前，更新 `scripts/mobile/check_weapp_load.cjs` 的旧M0壳断言为当前登录/工作台；AppID、本机配置不提交。

## 验证事实

- Node24.16.0：`npm --prefix apps/soloops_weapp test` 为32/32通过；`npm --prefix apps/soloops_weapp run type-check` 通过。
- 本次生产build未通过，原因如上；W05曾192模块通过，不能代替W06结果。
- 本次未执行IDE业务操作、复制/分享、数据库端到端旅程或真实模型调用；无本次后端改动。
- 远程CI尚未核实。GitHub连接器仅查PR runs时的空结果不能认定push CI成功。
- `git diff --check` 提交前通过。

## 环境与约定

- Node路径：`C:/Users/27363/Desktop/AIEcommerceAgent/.local/runtimes/node-v24.16.0-win-x64`，前置PATH；默认系统Node版本不同。
- 依赖已安装；Taro4 / Vue3 / TypeScript，原生view/input/picker/switch，沿用绿色现有样式。
- Prettier：`C:/Users/27363/AppData/Local/npm-cache/_npx/83e71da30ae7cab2/node_modules/prettier/bin/prettier.cjs`，参数 `--write --single-quote --no-semi`。模板复杂handler移入script函数。
- 后端 `backend/app/api/routes/support.py`、`schemas/support.py`、`schemas/support_delivery.py`、`services/support.py`、`services/support_delivery.py` 为客服契约；Web参考 `frontend/src/views/SupportView.vue` 及Support组件。
- 微信复用 `services/support-types.ts`、`ReviewedDelivery.vue`；业务写入不自动重试，Decimal保持字符串，写后独立GET回读。
- 本目录未配置测试数据库，勿误用其他聊天数据库。
- firecrawl已认证但DNS ENOTFOUND；本次用官方Taro网页检索核对Textarea参数，研究记录已写 `docs/references.md`。
- 持续同步development、feature-matrix、references、interview-guide和微信进度账本，明确区分源码、离线验证及IDE/数据库验收。

## 新账号可直接使用的提示

> 继续仓库 Changxin-YR/AI-E-commerce-Agent 的 feat/soloops-wechat-r2 微信开发。仅操作 soloops-wechat 目录。先读 AGENTS.md、docs/mobile/wechat-account-handoff.md 和 wechat-implementation-progress.md；从W06客服首轮源码审查及构建内存失败处继续，随后按H08–H21完成。已有推进与推送授权，真实外部通道用隔离替身。
