# SoloOps R2｜Android、鸿蒙与微信小程序三端开发方案 V1.2（融合四项加固·执行基线）

> 2026-10-11；基于已冻结的 R2 基础业务版、V1.1、第二轮 DeepSeek 四项建议以及代码/官方资料复核。
>
> **性质：待实施的技术与验收规范，不是三端功能已完成证明。**
>
> 项目：<https://github.com/Changxin-YR/AI-E-commerce-Agent>
>
> 当前业务基线：`main` / `0a49a37dcd7f1ccf0acc2c0a225bfdc8d8bee686`。实施时必须重新核对实际 HEAD、工作树与目标 CI。

## 执行摘要（一页结论）

**用户确认路线**：第二版 R2 基础版为开发主线；原 V1.0 剩余 47 个长期模块留作后续功能池，不用它们否定当前 R2 验收。现有四条 MVP 和 B1 低毛利多步受控流程的本地/合成验证已通过，但真实卖家、正式外部平台写入、三端运行与公网部署不在当前通过范围内。

**冻结技术栈**：Android + HarmonyOS/OpenHarmony 使用同一份 Flutter/Dart 源码（采用 CPF-Flutter 的**经过 M0 实际锁定的 tag**）；微信使用 Taro 4 + Vue3 + TypeScript；一套 FastAPI/Service/Repository/MySQL；Web 原状保留。

**关键决策**：M0-A 可独立构建并验证静态契约；M0-B 单独验证实机。若 OHOS 受阻而 Android 和微信端各自验收达标，可以有条件地推进 Android/微信的 M1，OHOS 独立记录 BLOCKED；绝不推断其已经合格。Web/Android/OHOS/微信对**同一后端对象**的业务语义必须一致，但不要求布局或原生交互完全一样。

**四项校正**：

1. OHOS 故障不拖垮其余客户端，但不允许无声降级，最终覆盖范围改变必须再次取得用户授权。
2. M0-A 让 UI 契约成为可解析 JSON 并接入静态门禁；跨端真实 E2E 只有在对应客户端实际可运行以后才能记 PASS。
3. 不把 `token_version` 当作唯一标准：现有会话表已索引且支持 `DELETE WHERE user_id = ...`，先用最小侵入安全方案；并发竞争/全端范围在 M1 评测决定。
4. multipart 薄适配仅有界读取+鉴权+调用 **现有四参、末参 `bytes`** 的导入服务，严禁创造第二套 CSV 业务引擎。

## 0. 版本范围与决策

- **R2 第二版基础版是唯一当前业务开发基线**：A0—C、后续 P2-01 与 UAT-01—04 修复、四条 MVP、B1 低毛利受控流程。原 V1.0 剩余长期 SO 模块只作为后续迭代需求池，不能计入本轮失败，也不得偷偷开发。
- **不重建电商后台**：保留 FastAPI → Service/Agent → Repository → MySQL，保留原 Vue Web 19 个业务路由、数据/授权/来源/审批/审计和全部回归。
- **三端技术栈**：Android 与 HarmonyOS NEXT/OpenHarmony 共享同一份 Flutter/Dart 应用源码，以 CPF-Flutter 发布的 *固定、经过实测的稳定 tag* 构建 APK/HAP；微信小程序使用 Taro 4 + Vue 3 + TypeScript，产物独立；三端共享后端和版本化 OpenAPI 契约，**不共享 UI 源码**。
- **三端结果一致，不要求像素级/系统能力完全一致**。页面布局、键盘、文件选取可以平台差异化；业务操作的可达性、风险说明、服务端状态与历史回读不得漂移。
- 开发/合成环境验收与正式分发/上线验收分开。没有真实机器、微信后台资质或合格 HTTPS 的证据，不准宣称真实设备或生产上线通过。
- **各平台各阶段分别准入**：OHOS 的独立障碍不应自动阻断 Android 与微信小程序开发；但是 OHOS 的 BLOCKED / NOT_TESTED 必须保留，不能以其他平台通过冒充双端合格。

### 0.1 DeepSeek 评审处理记录

| 评审事项 | 结论 | 本修订落点 |
|---|---|---|
| Flutter OH 版本/插件风险 | 采纳 | M0 兼容矩阵、真实构建与关键能力 POC；拒绝以文档推定可用 |
| 微信主体/类目/备案 | 修正采纳 | 把 SoloOps 定义为**卖家经营管理工具**，不是销售平台；根据实际能力核验可用类目、主体、备案、域名；不一概断言个人主体不可发布 |
| UI 双写 | 采纳 | 共享 `ui-contract.md`、功能对照和跨端契约测试 |
| 任意字节分片重写 | 不采纳作为首选 | 优先利用 R2 已有有界逐行分片/导入组，增加最小 multipart 传输适配；确有证据才扩展协议 |
| 独立会话/注销/刷新 | 采纳并具体化 | M1 固定 Bearer 会话、服务端存哈希、端间隔离、吊销和竞态测试；原 Web Cookie/CSRF 保持 |
| 调度在线提示 | 采纳并纠正 | 区分 API 可达、调度已启用、调度心跳/最近扫描和最近实际运行；“无运行记录”不是“离线” |

### 0.2 第二轮 DeepSeek 加固裁决

| 提议 | V1.2 裁决 | 执行差异 |
|---|---|---|
| OHOS 阻塞允许部分推进 | 采纳 | **每端单独门禁**，若 Android 与 Taro 的 M0 准入满足，可启动面向这两端的 M1；OHOS 分支继续调查，不得标 PASS |
| UI 契约自动化 | 修正采纳 | M0-A 创建机器可读契约与静态验证，M2/M3 实现后才能执行 Flutter/Taro 实际操作对账；不能在没有界面时伪造 E2E |
| 全端退出必须 `token_version` | 不接受为唯一方案 | 现有 `login_sessions.user_id` 已有索引；比较带索引删除与用户级认证纪元，再选最小安全方案 |
| 文件薄路由复用 ImportService | 采纳并纠错 | 真实签名 `upload(owner_id, shop_id, options, data: bytes)`；不得传 `file_stream` 作为现有接口 |

## 1. 核验事实：不能误判为三端已完成

- R2 最终记录与 GitHub Actions：880 后端、158 前端单元、91 浏览器测试成功；准确 CI <https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38058670333>。
- 四条闭环：今日运营→审批→历史→新来源复检；商品 Listing→草稿→版本审阅→内部生效→复制/CSV；客服→订单和政策事实→敏感接管→人工交付自报；经营分析→确定性金额→来源/缺口→历史重算。
- B1：7 步低毛利复核、两次分别审批、两个服务端业务记录、预算/权限/来源/幂等门禁。
- 原基础版 **不提供** 平台实时授权同步、真实店铺刊登、真实买家自动发信、退款/自动发货；其状态语义必须原样保留为 `not_submitted` / `seller_reported` 等。
- 原后端写请求对 `X-SoloOps-Client: web` 和 CSRF 有固定假设；`/api/shops/{shop_id}/imports` 使用 `request.stream()` 原始字节协议；调度依赖 FastAPI 进程生命周期。以上均属于**跨端适配任务**，不属于原 R2 未闭环缺陷。

## 2. 版本化架构

```text
              Web Vue3/TS（保持现状）
                          │ Cookie/CSRF
 Flutter（Android & OHOS） ├── HTTPS + FastAPI 统一路由
                          │ Bearer device session（新增）
 Taro Vue3/TS 微信小程序 ────┘
                                ↓
       Current user / Shop DataScope / R0—R3 / Approval / Audit
                                ↓
            原 R2 Business Service / Agent / Repository
                                ↓
                         原 MySQL 数据库
```

目录（建议）：

```text
clients/soloops_flutter/{lib,android,ohos,test,integration_test}
clients/soloops_weapp/{src,test,e2e}
contracts/openapi.json
contracts/README.md
docs/mobile/{baseline.md,plugin-matrix.md,weapp-compliance.md,ui-contract.md,api-contract.md,upload-contract.md,session-contract.md,scheduler-contract.md,acceptance-matrix.md,device-evidence.md}
```

从 FastAPI OpenAPI 生成/验证 Dart 与 TypeScript DTO；处理 JSON Decimal 字符串、UTC 时间和 IANA 展示、未确认费用/来源时效、版本号及错误结构。**金额绝不以前端浮点数重新汇总。** 后端的 source_status、expected_version、reviewed_version、审批结果是唯一真相。生成 ID 的一致性定义：**对于同一服务端记录，任一端显示的 record_id 必须相同；不同测试店铺新建记录的自增 ID 不要求数字相同，应比较业务关联、金额、状态和来源。**

## 3. M0：可行性先行，禁止假兼容

### 3.1 Flutter OH SDK

- 查询 CPF-Flutter 最新已发布稳定 tag；记录原始版本、提交 SHA、Dart 版本、DevEco Studio/HarmonyOS SDK/JDK/Gradle、Windows/Linux/Mac 环境及安装指令，锁定版本。
- 用户期望同一 Flutter OH SDK 生成 Android APK 和 OHOS HAP。**必须实际验证**，不能从仓库 README 推断必然构建；若同一 SDK 构建 APK 存在回归，只能先提出“同一 Dart 代码、两套构建工具链”的有证据备选，不得未经许可悄悄更换技术路线。
- 先构建最小登录壳 + HTTPS 状态页，分别在 Android 和 OHOS 目标环境运行；HAP 仅编译不等于真机通过。缺物理设备时清楚写“待真机”，不捏造执行日志。
- 插件矩阵覆盖：Dart HTTP/超时/TLS、设备安全存储、普通设置存储、文件选取、文件读写/沙箱、下载/系统分享、剪贴板、URI/外链、国际化日期、路由及生命周期。每项给出插件/平台接口、版本与许可证、Android 结果、OHOS 结果、证据、替代方案、剩余风险。
- `dio` 属于 Dart 层网络库，不应无证据地归为缺少 OHOS 原生插件；`shared_preferences` 不是 Token 的安全存储。可用社区适配插件需锁版本并 POC，不能只列仓库名算通过。
- 安全存储替代顺序：已验证的安全插件 → ArkTS 受控系统安全存储平台通道 → 短期仅进程内会话、重开重新登录。**明文永久保存令牌不允许；将 OHOS 退化成只读也不能自动免除身份安全要求。**

### 3.2 微信小程序资质与能力

- 填写并核验主体（个人/个体工商户/企业）、AppID 与审核状态、实际使用的服务类目、是否有支付/消费者订单/电商交易场景。
- SoloOps 是**卖家经营工具**：核对可选工具/效率/企业管理类目，而不是因为“电商”名称强制套用电商平台交易资质。微信管理后台的最新服务类目与审核结果是最终依据；任何候选类目不得伪装成已经获批。
- 区分：**小程序 APP 备案**、**网站/API 服务器域名 ICP 或接入备案**、**微信 request/upload/download 合法域名配置**、**HTTPS 证书与 TLS 校验**。记录域名实际托管地区及适用条件；非测试正式部署不能依赖开发工具“不校验合法域名”。
- 资质或公网域名暂不可用时仍可在合规的本地/开发者工具环境完成代码演示，但必须标明“正式发布受阻”；不得承诺微信正式上线或绕过平台审核。

### 3.3 M0 技术证明交付

1. `plugin-matrix.md`（平台支持状态仅允许 PASS / FAIL / BLOCKED / NOT_TESTED）。
2. `weapp-compliance.md`（主体、类目、服务器域名和小程序备案独立证据）。
3. `ui-contract.md`（基础五入口/19业务子路由字段、按钮/状态映射、异常空态）。
4. 编译与启动记录：APK/HAP/小程序；编译日志、应用包路径、设备/模拟器型号、截图；缺设备时不声称真机。
5. POC：匿名访问 `/api/health/live` 与鉴权接口 401/403 校验；网络失败、正常恢复；文件/安全存储 POC。

**M0 分端通行原则**：APK、HAP 与微信小程序构建分别记录 PASS/FAIL/BLOCKED/NOT_TESTED。Android 与微信小程序的最低准入是对应构建、最小 HTTPS/认证拒绝 POC 与必要安全路径有可验证方案；这些满足时，**经阶段审批可以仅为 Android/小程序推进 M1 和后续相应客户端**。OHOS 构建或真机未通过，仍处于原状态，不代表整个 Flutter 双端通过；后续可独立补验。微信正式发布与开发验收分开。

## 4. M1：认证与安全 API（不得削弱 Web）

### 4.1 认证契约

- 原 `/api/auth/login`、Cookie `soloops_session`、CSRF 校验与浏览器退出保持不变；**不要全局删除 CSRF**。
- 独立的 `/api/mobile/auth/...` 或同等命名空间使用服务端不透明随机 Bearer；数据库只保存令牌哈希、用户、独立设备会话 ID、签发/最后使用/绝对过期/吊销状态、可审计客户端类型。不得将客户端提交的 header 当身份与权限依据。
- 固定“当前设备退出只吊销当前会话；重置密码吊销全部；显式全端退出（如果向用户开放）吊销 Web 与各设备会话”。客户端类别是会话记录元数据而非可信授权来源。
- 令牌更新可采用严格定义的安全滑动策略 + 绝对最长会话期；**优先安全、简单**，不将 30 天当作已确认产品需求。若采用刷新令牌，应实行一次性轮换、并发请求合并、回放检测、原子落盘和失效策略；不能不加防护地无限延长会话。
- 入口按账号和 IP/可信代理信息限流；跨域网页限制维持。写操作可接受合法 bearer，但必须验证真实 session，且走原 Service/Agent 的审批、幂等、店铺/资源版本校验。
- 同时提供 Bearer 与 Cookie，或者出现 Web/设备鉴权歧义时采用拒绝而不是猜测身份。原始 token、密码、模型 key 不进 URL、日志、追踪或普通配置。
- 微信初版允许原管理员预置的用户名密码登录，不强制接 `wx.login`；将来启用微信身份绑定时须服务端换取与核验微信凭证、显式账号绑定，不自动授予店铺权限。

### 4.2 测试门禁

单端退出/全端退出、密码重置、并发登录、过期/撤销、跨用户与跨店、混合认证拒绝、CSRF 维持、Origin/CORS、重放 Token、刷新增发竞态、令牌泄漏检查、源版本改变后拒绝审批。原 880/158/91 当前基线的相关测试必须保持通过；变动后完整 CI 在确切提交上复验。

## 5. 上传协议：复用已有 R2 数据治理

原实现：逐片最大 2 MiB、2000 行；导入组最多 40 MiB/40000 行/20 片；原始文件字节传给 ImportService，manifest、映射预览、commit、去重、撤销/清除已有实现。

1. **优先**使用小程序经过实测的文件选择能力 + `Taro.uploadFile` 传单片 multipart，由新的**薄路由**在有界流式解析及合法鉴权后提取**原始文件内容**交给现有 `ImportService.upload(owner_id, shop_id, options, data: bytes)`。Web 原始字节路由完全保留，两个入口结果一致。
2. 上传适配层只负责 **Bearer 身份、资源/店铺范围、multipart 单文件字段及有界大小读取**；调用原 ImportService 后由已有服务校验 2000 行、CSV/XLSX、映射、哈希/manifest/数据身份/来源/店铺、去重/撤销等业务规则。ASGI/反向代理也必须限制 **整个 multipart 请求体** 和表单数量；不能仅在表单解析完成后检查长度，更不能先将无界请求读入内存。
3. 大文件优先复用 R2 的“CSV 逻辑记录有界分片 + 持久化 import-groups”；不能按 512 KB 生切导致跨行引号/UTF-8 被破坏。不同大小的协议建议必须先论证需求、边界与现有导入组的关系。
4. 客户端故障恢复：每片业务 UUID、来源指纹、预览/提交状态持久回读；未知提交结果**先查询，不盲目重传导致覆盖**；重复上传不得导致订单、金额双计。
5. 小程序无法可靠处理大文件时，明确“小文件可用，超限移至 Web”并提供准确提示，不做无效按钮。所谓“移动端可查看全部 R2 页面”不等于移动端必须独立处理 40 MiB 文件。

测试：单片失败、安全重试、重复片、片序变化、跨片重复订单、恶意多行 CSV、编码/BOM、断点回读、整组撤销、错误行、异币种/退款、来源更新导致旧审批失效、无效权限及单片超限。若未来确需新增完整字节分片/合并协议，作为另一个单独设计/验收工作包，不与 M3 首版耦合。

## 6. `docs/mobile/ui-contract.md` 必备字段

每个 R2 原业务页面/移动子页记录（同时产出 `contracts/ui-contract.json` 作为机器可读来源）：`page_key`、Web route、服务端 API、Flutter route、Taro route、可见状态、币种/时间/来源显示、全部原有按钮、按钮合法前置条件、请求 payload、完成/冲突/错误后显示、数据撤销/清除及跨端回读方法。

五主入口：首页（经营/来源）；待办（待执行/待审批/待复检）；AI（原有技能/授权/预算/低毛利 B1）；客服（原文/政策/已审阅版本/人工交付）；我的（店铺、经营资料、定时摘要、导入/其他 R2 入口）。**UI 可不同，服务端状态必须一致。**

硬性反例：已导出的 Listing 显示“平台已上架”；客服 `seller_reported` 显示“真实买家已收到”；已处理事项显示“异常已解决”；历史毛利当作当前净利润；看见 403 或 stale 却继续批准；应用刷新自动重复执行 Agent；切店后迟到响应覆盖另一店内容。

**跨端检查**：对同一个已存在的记录，Web/Android/OHOS/微信展示相同 record_id、事实金额、版本、来源状态与可执行动作；不同测试环境要按语义比较结果，不强求数据库自动 ID 相同。M0-A 仅校验机器可读契约是否覆盖现有 Web 路由与必备字段；M2/M3 再在真实页面/模拟设备上采集服务端记录与动作结果，执行 Flutter 集成测试、小程序自动化与 Web Playwright 对账。若无对应客户端实际运行，不得填 E2E PASS。

## 7. 调度与在线语义

- 原 R2 调度依赖 API 存活并且 scheduler_enabled 开启，约 30s 扫描；并非手机后台执行。关机/进程退出期间无法承诺持续自动运营；有界恢复及 missed 规则保持。
- **不得用“API 健康 GET 成功”“开关 enabled”“最近保存的业务周期存在”单独宣称调度正在运行。** 如果需要在线指示，M1/M2 在服务器端增加可验证的 `last_scheduler_scan_at` / 调度实例心跳及过期策略；设计多 worker、服务重启和持久更新频率、读写负担；或者 UI 仅显示“调度配置已开启；运行状态尚未确认”，避免假在线。
- 手机 UI 分别显示：服务可达性、调度配置状态、最后确认扫描时间（若有可靠数据）、最近计划实际执行与结果、下一计划时间（按原算法）；网络离线时显示“无法获取当前状态（显示上次成功同步时间）”，**不是**“已证明服务进程停止”。
- 不在 M2/M3 默认承诺系统 push、微信订阅消息；现有应用内记录/深链、已读未读先闭环，新增推送须另立授权与实发测试包。

## 8. 分期执行与停工门槛

| 阶段 | 开发范围 | 准入/退出证据 |
|---|---|---|
| M0-A | 仓库只读审计、SDK 选型锁定、Flutter Android/HAP 构建、Taro 编译、插件与资质清单、机器可读 UI 契约及静态校验 | 分别记录三端构建；未通过的平台标 FAIL/BLOCKED，不冒称总通过；通过的平台可申请下一包准入 |
| M0-B | Android/OHOS 实机最小启动，安全存储/文件/HTTPS POC；微信开发者工具与真实微信加载 | 有实际设备与日志才可 PASS；无设备写 NOT_TESTED；不谎称 |
| M1 | Bearer 适配、Web 不回归、店铺切换与登录退出/过期 | 服务端全局契约通过；Android/小程序可根据 M0 平台门禁先接入，OHOS 未通过时独立保留阻塞 |
| M2a | Flutter Android 四 MVP+B1、五主入口及来源/审批 | Android 构建+实测、内部结果和 Web 读回一致 |
| M2b | 复用同一 Dart 工程完成 OHOS 适配与四 MVP+B1 | HAP+OHOS 实机；安全存储/文件/异常流程；不能无声降级 |
| M3a | 微信小程序核心四 MVP+B1、小文件导入和 UI 契约对账 | 开发者工具/体验版（条件具备时）+接口与业务一致性 |
| M3b | 文件边界、真机微信验证、主体/类目/备案上线门禁 | 开发验收通过与上线许可分开，不混淆 |
| M4a | 剩余 R2 页面和必要动作逐项映射、真实可用功能 | R2 页面 × Flutter Android × OHOS × WeApp × Web 矩阵 |
| M4b | 跨端回归与真实用户 UAT、数据恢复/线上安全证据 | 合成/真人/生产分层签字，保留未达条件 |

必须每包保留：准确 Git SHA、修改文件、测试命令/日志、设备型号与系统、截图或实际数据回读、功能通过/受阻原因、迁移前备份及回滚说明。高风险写入和真实外发仍需独立许可。

## 9. M0 交付路径与检查表

```text
docs/mobile/baseline.md
docs/mobile/plugin-matrix.md
docs/mobile/weapp-compliance.md
docs/mobile/ui-contract.md
contracts/ui-contract.json
scripts/validate_ui_contract.py（或同等无业务副作用的检查器）
docs/mobile/api-contract.md
docs/mobile/upload-contract.md
docs/mobile/session-contract.md
docs/mobile/scheduler-contract.md
docs/mobile/m0-report.md
```

每个产物状态必须明确：`PASS` / `FAIL` / `BLOCKED` / `NOT_TESTED`；不能将计划中的测试写成已运行结果。硬件、微信 AppID、签名或备案无法直接获得时，只完成能实际完成的部分，列出必要的用户输入/环境条件；不得制造截图、构建包、云部署或假公网证据。

## 10. 参考来源（核验日期 2026-10-11）

- Flutter OH SDK/tag 与兼容路线：<https://gitcode.com/CPF-Flutter/flutter_flutter>
- Flutter OH SDK 组织与适配插件：<https://gitcode.com/CPF-Flutter>、<https://gitcode.com/CPF-Flutter/flutter_packages>
- Taro 4 上传 API：<https://docs.taro.zone/docs/apis/network/upload/uploadFile/>
- Taro 4 网络请求：<https://docs.taro.zone/docs/apis/network/request/>
- 工信部 APP 备案通知：<https://www.gov.cn/zhengce/zhengceku/202308/content_6897341.htm>
- 工信部备案解读：<https://www.miit.gov.cn/jgsj/xgj/hlwgl/art/2023/art_564bf0759d7e41d5b4aa8ce4996b9e84.html>
- 微信服务类目与审核标准以微信公众平台实际后台当前展示为准；本修订不声称已代用户核验其账号资质。
- R2 完成与上线门禁：<https://github.com/Changxin-YR/AI-E-commerce-Agent/blob/main/docs/r2-fixes-final-report.md>、<https://github.com/Changxin-YR/AI-E-commerce-Agent/blob/main/docs/r2-deployment-gates.md>

**最终决定：先执行 M0-A，随后按平台证据进行 M0-B；不立即批量创建业务 UI。Android 与 Taro 满足各自技术门禁时，可以申请先启动 M1 与 M2a/M3a；OHOS 保留独立 M2b 及真实设备门禁。**

## 11. V1.2 新增实施约束（优先于前文含糊表述）

### 11.1 单平台放行与状态管理

以平台和验证层次构成二维矩阵：`Android/APK Build`、`OHOS/HAP Build`、`WeApp/Compile`、`Android/Device`、`OHOS/Device`、`WeApp/DeveloperTool`、`WeApp/RealWeChat`、`WeApp/Publish`。每个单元格只允许 `PASS`、`FAIL`、`BLOCKED`、`NOT_TESTED`，并附时间、机器/SDK 版本、命令、Exit Code、日志与真实产物路径。**某一项 PASS 不提升其他项状态**。

- M0-A 在同一 Dart 代码库中验证 Android 和 OHOS 独立构建。缺少 OHOS 工具链或构建失败时，以证据保留 BLOCKED/FAIL，不用 Android APK 成功反推 OHOS 可用。
- 若 Android APK 与 Taro 编译/最小通信各自满足门禁，而 OHOS 尚未满足，项目允许只对 Android + WeApp 继续 M1；无需为通过演示人为禁用 OHOS 检查。M1 的服务端契约仍应面向所有合法 Bearer 客户端设计；OHOS 不获得未经测试的客户端 PASS。
- 独立 M0-B 真机/模拟器证据不和 M0-A 编译证据混淆。模拟器 PASS 不等于真机 PASS；无设备写 NOT_TESTED。若必须适用安全存储，平台“仅查看”不自动解除存储安全要求。
- 所有功能覆盖差异在 UI 契约中标明 `supported` / `requires_native_adapter` / `blocked`，用户不能看到无响应或伪成功的按钮。范围变更（尤其 OHOS 长期降级）必须得到用户明确批准。

### 11.2 可执行 UI 契约：分两步实施

**M0-A 必须交付：**

- `contracts/ui-contract.json`：每个业务功能稳定标识 `feature_id`、`web_route`、`api_method/path`、`data_fields`、`statuses`、`allowed_actions`、`guard_conditions`、`display_semantics`、`evidence_requirements`。覆盖 R2 **现有** Web 19 路由与四 MVP+B1；不能凭空声明未实现的长期功能。
- `docs/mobile/ui-contract.md`：供开发者阅读的人类版本，基于同一机器可读契约描述五主入口、跨端页面与状态差异；若有双份同步风险，以 JSON 为可执行基线，文档修改同步校验。
- `scripts/validate_ui_contract.py` 或同等检查器：验证 JSON 可解析、ID 唯一、方法/路径字段完整、状态/动作字典合法、R2 页面映射无遗漏、`not_submitted`、`seller_reported`、`stale` 等风险语义不丢失；在 CI 运行。不得直接假设正则静态提取所有 Vue 运行时按钮具有完整准确性；覆盖范围由人工核对与自动可检条件结合。
- 使用现有 OpenAPI 导出校验已存在接口/方法可解析，避免拼写错误；M0-A 没有新移动 UI 时，只能称 **契约静态测试 PASS**，不能称多端操作一致性 E2E PASS。

**M2a/M2b/M3 必须交付：**

- 同一合成店铺内，通过真实客户端操作产生/读取同一个后端记录，比较 `record_id`、`expected_version`、`source_status`、`reviewed_version`、审批允许动作、金额/币种与实际持久状态；Web 由 Playwright，Flutter 由可执行集成测试，WeApp 由开发者工具自动化/真实环境支持的手段验证。
- Android 与 OHOS 客户端本质上共享 Flutter 代码，但平台插件与系统交互差异仍需分端验证。不能以 Flutter Android E2E 自动替代 OHOS 真机。
- 使用 `semantic_assertions.json` 或同等结构记录业务最终状态；对不同独立测试店铺新建的记录只比语义不比自增 ID；对同一现存记录必须匹配相同 ID。

### 11.3 多端会话吊销：禁止提前指定唯一实现

当前真实源码（2026-10-11 已核对）：`backend/app/models/identity.py` 中 `login_sessions.token_hash` 为主键、`user_id` 有索引；`backend/app/repositories/identity.py` 的 `delete_user_sessions(user_id)` 通过带条件的 SQL DELETE 删除会话；`backend/app/services/auth.py` 已在重置密码时调用。因此 DeepSeek 所述“遍历所有 token 必然锁表”**并非当前代码的事实**。

M1 由 Codex 给出 **带索引会话删除** 与 **用户级认证纪元（`token_version` 或同等设计）** 的对比，说明索引、并发、全端范围、兼容迁移、性能与审计。默认最小侵入方案是**服务端持久不透明令牌，带索引的当前会话吊销**；显式全端退出若被批准，再选择可靠的跨 Web+设备方案，优先用事务与索引满足需求，而不因为抽象性能担忧额外加表/字段。确实需要大量设备会话、瞬时批量吊销且有压测证据时才考虑版本化。

若采用 `token_version`：**不透明 token 不包含可读 version claim**；版本要存于对应会话行/服务器状态，并在每次鉴权时与 `users` 侧版本做可信校验，既适用于 Web Cookie 又适用于设备 Bearer。必须设计老会话升级兼容、登录与全端退出并发次序、重置密码有效性，以及是否在请求进行中仍可发生写入；对高风险业务写入保留已有服务层审批/来源/版本检查。**单次退出仅使本设备 token 失效**，不应无意误杀其他端。不能将 header、设备类型或可伪造的时间戳作为认证依据。

OWASP 建议在服务端主动使注销/过期会话失效，并明确设置空闲/绝对过期；这些是目标，具体采用 DELETE 还是版本化应根据现有架构实施：<https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html>。

### 11.4 文件上传薄路由必须沿用真实签名

现有函数签名（来自 `backend/app/services/imports.py`）：

```python
def upload(self, owner_id: int, shop_id: int, options: UploadOptions, data: bytes) -> BatchOutput:
    ...
```

小程序网络库 `Taro.uploadFile` 发送 `multipart/form-data`，与现有网页端原始字节流不同。M3 新上传入口最多负责请求级大小与表单数量上限、认证和授权、提取**单一文件的原始字节**、转换已验证的上传元数据；然后调用**同一 `ImportService.upload(owner_id, shop_id, options, data)`**。旧 Web 入口继续可用。

- 不在适配路由内实现 CSV/XLSX 业务解析、映射、订单行计算、业务去重、报表生成、导入组新状态机；这些只能在既有 Services 中。
- 注意 FastAPI/Starlette 的 multipart parser 可能在进入路由函数前就消费请求体：必须设置 ASGI/网关总体请求体上限、字段数/文件数限制、解析失败控制；`Content-Length` 可协助初筛但不能作为唯一限制。保持 **文件内容 2 MiB** 与协议总负载上限分别定义。
- 自动化验证建议采用 *正向动态证据*：替换/监控 `ImportService.upload` 调用并核对入参、调用次数、真实导入批次 ID；测试原始字节入口与 multipart 入口的预览/提交/撤销结果一致；加仓库静态检查确保 adapter 未引用 `csv/openpyxl/import_parser` 等解析模块（静态检查只是辅助，不能取代行为测试）。
- 严格禁止以 `ImportService.upload(file_stream, ...)` 调用——现有实现入参是 `bytes`；如确需流式改造，这是独立接口重构，必须另行验收且不能破坏 Web。

### 11.5 合规与版本路线最后确认

SoloOps 是“供卖家处理经营数据的工具”，**不是直接面向买家的交易商城**。这有助于选择合理类目，但**不等于自动获得资质豁免**。是否可以使用个人主体、哪些类目开放及是否有特殊审核，必须以用户微信公众平台当前后台与业务功能审核为准；不能仅凭产品名称判断。开发阶段不要求用户立即注册企业或个体工商户，也不得保证个人主体一定能发布。备案与 HTTPS 的正式分发门槛独立评估；工信部 APP 备案解读见 <https://www.miit.gov.cn/jgsj/xgj/hlwgl/art/2023/art_564bf0759d7e41d5b4aa8ce4996b9e84.html>。

## 12. V1.2 冻结与开工规则

- V1.2 是技术与验收基线，**不是业务开发已完成证明**；当前 R2 业务主线仍冻结为通过验收的版本。
- 第一个开发指令**只执行 M0-A**，不得连带执行 M0-B/M1/M2/M3/M4；V1.2 的 M1/M3 约束此刻只是将来实施的规范。
- M0-A 可提交 SDK/工程/静态契约验证与真实日志；不修改登录服务、数据库迁移、业务计算、原 Vue 页面，不执行付费模型、真实邮件或平台写入。
- 每阶段提供清晰的“PASS 项、FAIL/BLOCKED 项、NOT_TESTED 项 + 精确证据”，由用户决定进入哪个端的下一阶段；未经授权不得变更平台覆盖与安全底线。


## 13. API、状态、UI 和 CI 可执行验收样例（新增）

### 13.1 UI 契约最小机器格式（示例，非现存接口定义）

下例为**格式示意**，`api_path` 等字段必须由 Codex 对照当前 FastAPI 实际 OpenAPI 生成，不能把下面的示例当作仓库已存在 API：

```json
{
  "schema_version": "1.0",
  "features": [
    {
      "feature_id": "listing.delivery.view",
      "web_route": "/listings",
      "flutter_route": "/ai/listing",
      "weapp_route": "/pages/ai/listing",
      "api_method": "GET",
      "api_path": "<从当前 FastAPI OpenAPI 核实后填入>",
      "data_fields": ["id", "version", "source_status"],
      "guard_conditions": ["归属店铺", "批准版本有效", "来源未过期"],
      "display_semantics": {
        "not_submitted": "仅本地保存/可人工交付，不代表已向外部平台提交",
        "stale": "来源已变化，须重新核对"
      },
      "evidence_requirements": ["API 原始响应", "客户端记录 ID", "版本号"]
    }
  ]
}
```

**静态门禁**：Schema 校验、`feature_id` 唯一、有效 HTTP 方法、API 路径真实存在、19 个已有 Web 页面可映射、四 MVP+B1 相关动作存在且每个涉及安全的动作定义了 `guard_conditions`，风险状态文案必须保留。若界面按钮由动态数据生成，静态扫描无法完整判断，须记录人工映射核验；不得声称“脚本证明所有按钮已一致”。

**运行门禁**：在 M2a/M2b/M3 各阶段产出服务端 `semantic_assertions.json`（证据快照，不含凭据和个人信息）。对同一个后端 record，以 Web 和实际客户端各自独立读取核对：店铺 ID、record_id、金额字符串、货币、版本、来源、审批/人工自报状态、是否允许下一步动作；对不同独立店铺的记录只比较语义而不是数据库自增数字。

### 13.2 会话吊销的并发与性能准则

- M1 首选 **高熵不透明 Token + 服务端摘要 + 有状态会话**；当前 Web 的 `login_sessions` 和相关索引保持兼容，设备端是否复用表或新建受控设备会话表，以最小修改、安全隔离和迁移安全为依据。
- **当前设备退出**：仅撤销当前 token；必须证明另一个设备及 Web 登录不受影响。
- **密码重置**：撤销所有有效 Web 和设备会话，并确保被偷取的旧凭据继续访问会失败。
- **全端退出（若本轮决定开放）**：在事务与锁策略下保证符合定义的线性化顺序；锁定用户避免与并发登录/刷新发生难以解释的窗口。可以通过索引 DELETE 或用户级认证纪元实现，记录 SQL 查询计划和必要压测；不盲目增加 `token_version`。
- **设备 Token 生命周期**：必须有服务端强制绝对过期，空闲期限与续期机制如果暂不实现也应写明。不要用客户端可伪造时间替代服务端策略。小程序不应永久明文持久化高价值 Bearer；确无安全存储路径时，先用短期/内存会话并明确重登体验。
- **双凭据拒绝**：同一请求同时携带 Cookie 和 Bearer 时拒绝并审计，不按 header 猜身份；合法的 Bearer 写请求也必须通过原业务权限、来源和审批服务。
- **性能原则**：小规模个人卖家无需凭空设定百万设备；以真实查询计划、合理压力模拟和并发验收选实现，不用假设“DELETE 必然锁全表”。

### 13.3 上传最小功能边界与安全准则

当前服务端签名是：

```python
ImportService.upload(owner_id: int, shop_id: int, options: UploadOptions, data: bytes)
```

- 旧 Web 接口仍接收原始字节流，**不得为了小程序而强制改变**。
- 新小程序 multipart 入口只能负责会话、店铺身份、单文件字段、请求总体大小/字段数量限制、提取文件名与原始 bytes，并调用原 Service；不准在路由中导入 `csv`、`openpyxl` 或自行统计订单、做退款/币种算法。
- 限额分层：入口层限制**整个 HTTP 请求体**（包含 multipart 开销）；服务层限制**文件内容**最大 2 MiB 和原业务 2000 行；不可仅在 Starlette 完成无界表单解析后才检验大小。应检查反向代理/ASGI 解析策略，而不是只相信 `Content-Length`。
- 功能结果最小断言：用同一合成 CSV 经原始字节和 multipart 入口分别上传，比较导入行、预览、校验错误、审批、commit、撤销；同用户重复提交不得产生双重累计；未知提交结果先回查既有批次。
- 若小程序平台端读取复杂 40MiB CSV 的能力不足，允许首版小文件上传/大文件跳 Web，必须有可见理由和有效路径，不增加不可点击的占位按钮。

### 13.4 三端分阶段门禁定义（必须每端独立）

| 平台层级 | M0-A 证明 | M0-B 证明 | 进入业务开发最低准入 | 暂未满足时 |
|---|---|---|---|---|
| Android | 真实 APK + 编译日志 | 安卓实机/模拟器安装启动证据（明确环境） | HTTPS/401 及必要存储策略有效 | Android 功能开发受阻 |
| 鸿蒙 | 真实 HAP + 编译日志 | **鸿蒙物理设备**启动/关键插件/存储证据 | 与 Android 复用 Dart，原生桥接可用 | `BLOCKED` / `NOT_TESTED`，继续专项调查，不拖累已过的其他端 |
| 微信 | Taro 编译至 miniprogram | 微信开发者工具或真实微信各自明确记录 | 域名访问和客户端安全路径经过验证；合法开发环境 | 可以先做静态工程，无法宣称体验版/发布通过 |

**关键语义**：编译通过≠已安装；模拟器通过≠真机通过；开发者工具通过≠微信正式发布；API `/health/live` 通过≠调度进程仍活跃；运行了模型替身≠真实模型验证；人工自报≠外部平台已提交。

## 14. M0-A 首包的冻结任务与交付物（建议立即执行）

**允许修改**：新的 `clients/` 示例壳、`contracts/`、`docs/mobile/`、无业务副作用的契约校验脚本、必要的 M0 检查 CI。未经用户批准不修改 `backend/app`、`backend/migrations`、现有 `frontend/src`，不创建正式生产账户/密钥/数据库迁移。

**必须交付**：

1. 当前 HEAD + 工作树保护记录，R2 最新 CI 链接与哈希；不能擅自删除旧业务功能。
2. Flutter OH 精确 tag/commit、`flutter doctor -v`、Android APK、OHOS HAP 的真实构建日志；如不可构建，提供阻塞工具链证据，不伪造产物。
3. Taro4/Vue3/TS 小程序最小工程，实际编译日志；微信工具链/账号缺失时标识真实状态。
4. `plugin-matrix.md`：网络/TLS、设备安全存储、文件选择、文件读写/下载、剪贴板、外链、分享、系统兼容性各项状态、版本、替代路线及证据。
5. `weapp-compliance.md`：AppID/主体/服务类目/小程序备案/域名/证书/用户权限要求的事实与未知项，不强制开发前注册企业。
6. `contracts/ui-contract.json` + `docs/mobile/ui-contract.md` + 可运行静态验证脚本；实测不存在的 Flutter/小程序页面不能标记 E2E PASS。
7. `m0-report.md`：平台×证据矩阵，真实文件路径、日志与下一步准入判断；失败与阻塞也必须输出完成报告。

**终止条件**：M0-A 完成即停止，等待用户审核；不得自动推进认证架构迁移或四条 MVP UI。此文件是**待执行规划**，不是已经执行的工作记录。

## 15. 附加可信来源

- CPF Flutter OH 社区稳定版本策略和 tag 格式：<https://gitcode.com/CPF-Flutter/flutter_flutter>
- CPF Flutter 版本与插件组织：<https://gitcode.com/CPF-Flutter>
- Taro4 `uploadFile` 发送 multipart/form-data：<https://docs.taro.zone/docs/apis/network/upload/uploadFile>
- FastAPI `UploadFile` 与 SpooledTemporaryFile：<https://fastapi.tiangolo.com/tutorial/request-files/>
- 工信部关于 APP（含小程序分发）备案的正式通知：<https://www.miit.gov.cn/jgsj/xgj/wjfb/art/2023/art_dd783a581c9644a4aee10afa582811db.html>
- OWASP 会话生命周期与主动吊销要求：<https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html>
- OWASP ASVS v5.0 会话吊销：<https://github.com/OWASP/ASVS/blob/master/5.0/en/0x16-V7-Session-Management.md>
