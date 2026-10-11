# 微信 R2 连续开发账本

更新：2026-10-11（Asia/Shanghai）。

## 执行授权与工作区

用户要求按既有功能清单连续、高质量开发微信小程序，并在上下文接近上限时完成当前小任务后提交推送，创建新对话接续直到完成。

- 专用目录：`C:/Users/27363/Desktop/AI E-commerce Agent/soloops-wechat`
- 分支：`feat/soloops-wechat-r2`；起点：`926136c`（已包含移动认证与鸿蒙R2业务接口）。
- 原始范围：`docs/requirements/SoloOps-Mobile-V1.3.md` H01–H21、`contracts/ui-contract.json` 19业务路由及B1；V1.0的74项为长期总账。
- 本轮用户已授权微信独立实施，历史文档中的开发端顺序不作为停点。
- 其他目录有PC/安卓/鸿蒙开发活动，当前聊天只写本目录。

## W01：会话与经营初始化

已实现：

- HTTPS地址校验，用户名/密码移动登录，`client_type=weapp`。
- Bearer仅保存在内存，重开登录；存储只保存非敏感服务地址。
- 会话到期、401清理、返回前台查询会话；当前设备退出、确认后全设备退出。
- 请求30秒超时，结构化业务错误，版本冲突原样展示；业务写入不自动重试。
- 店铺选择、币种/时区显示、建店、经营档案读取和版本化保存、初始化提示。
- 切店或换账号使旧请求失效，旧401不影响新上下文。
- 统一基础样式、安全区、加载/错误/空态、重复提交禁用。

证据：

- Node24.16.0，`npm run type-check` 通过。
- `node --test tests/client.test.mjs`：9/9通过，涵盖HTTPS、密码空格、无会话、401、切店竞态、登录竞态、409、全设备退出及断网。
- `npm run build:weapp` 通过，136模块；生成工作台、经营资料、诊断页。
- 构建在Windows沙箱因依赖realpath权限中断后，经正常权限构建通过。
- 尚未执行本轮开发者工具UI或真实后端旅程，不能把编译结果称为业务联调完成。

## 完整范围进度

| 功能 | 当前状态 |
|---|---|
| H01 登录/会话 | 已实现，单测/编译通过，开发者工具待验 |
| H02 经营资料/店铺 | 已实现，类型/编译通过，端到端待验 |
| H03 首页/待办 | 待实现 |
| H04 文件导入 | 下一小任务 |
| H05 AI/B1 | 待实现 |
| H06 Listing | 待实现 |
| H07 客服 | 待实现 |
| H08 库存 | 待实现 |
| H09 分析 | 待实现 |
| H10 总览 | 待实现 |
| H11 利润 | 待实现 |
| H12 费用/映射 | 待实现 |
| H13 账单 | 待实现 |
| H14 订单账单核对 | 待实现 |
| H15 结算回款 | 待实现 |
| H16 规则/授权 | 待实现 |
| H17 定时运营 | 待实现 |
| H18 商品质量 | 待实现 |
| H19 本地修订 | 待实现 |
| H20 外发管理 | 待实现，使用隔离替身 |
| H21 公共能力 | 已完成请求/会话/店铺上下文；五入口、文件、深链等待补 |

## 下一步精确起点

1. 继续W02文件导入：读 `backend/app/api/routes/imports.py`、`frontend/src/views/ImportsView.vue`及其组件、`contracts/ui-contract.json` 的 imports 相关条目。
2. 检查现有移动 multipart 入口及认证中间件，微信使用 `chooseMessageFile`/`uploadFile` 对齐原ImportService，避免另起业务语义。必要后端薄适配可在本分支实现。
3. 完成文件选择、类型/数据身份、字段映射、预览/语义审阅/纠错、提交、批次/组回读及撤销，保留大CSV逻辑记录拆分范围；维护未完成动作账本。
4. 之后按H03/H05/H06/H07核心闭环、其余业务顺序推进，补五主入口。业务页面必须专用可操作，不以导航或JSON展示算完成。
5. 汇总开发者工具自查时复用 `scripts/mobile/check_weapp_load.cjs`，先读其参数；AppID和本机配置属于本机文件，不提交。

## 环境与接续

- Node：`C:/Users/27363/Desktop/AIEcommerceAgent/.local/runtimes/node-v24.16.0-win-x64/node.exe`。默认系统Node是24.15.0，检查时显式在PATH前置24.16.0目录。
- 微信包：`apps/soloops_weapp`，依赖已按锁文件安装。运行 `npm test`、`npm run type-check`、`npm run build:weapp`。
- CI：`.github/workflows/mobile-m0a.yml` 已增加微信分支及 `npm test`，推送后查看精确SHA结果。
- 后端认证接口已支持 `weapp`，已有权限/店铺归属/版本冲突规则继续生效。
- 研究：firecrawl调用受网络DNS限制，已通过官方Taro网页检索核对request参数；参见 `docs/references.md`。
- 用户已授权创建接续聊天及在其中继续开发。交接后旧聊天停止写入；新聊天先读取本账本、AGENTS及实际Git状态，继续下一项。
