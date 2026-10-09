# SoloOps 接续上下文

更新：2026-10-09。本轮基础版本第一阶段已提交推送。交接后由新聊天独占主工作区，旧聊天停止写入；不要启动子代理或其他并行写入聊天。

## 用户当前要求

- 按 `docs/foundation-release.md` 的基础版本继续开发，完整实现四条流程及 B-01 至 B-14。长期扩展保存在 `foundation-backlog.md`，等用户以后启动；基础版本剩余项必须继续完成。
- 用户再次明确：主动关注上下文接近上限，先整理、提交、推送，再创建新本地聊天继续；不要在同一聊天长期积累，不必重复请求交接许可。
- 本轮真实模型已授权：已有北京百炼通道、合成数据，累计人民币 1 元封顶。当前本轮 0 调用、已知费用 0 元。未知费用先核对；每次调用预留上界并记录累计。旧的 0.01 元一次性许可已耗尽，与本轮独立。
- 本人邮件仍缺通道配置、验证的本人测试收件箱和本次单次发送许可。模型额度不授权邮件。保留 B-07/A-13 的真实提交与收件证据，等待期间推进其余工作。

## 当前提交与验证

- main **8f6956fb15944015abe798b497a8657923dd6653** 已正常推送 origin/main，63 文件；主工作区干净。提交内容包括接手的订单/账单只读待核清单、基础跨页闭环、统一样本和隔离恢复。
- 本提交 GitHub CI 尚未核实，接续先查看；[基线1763c40 CI37941439350](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37941439350) 已核实 Success，verify 8分47秒。
- 完整后端 **685 passed / 301.69秒**。Ruff规则与格式 **222文件**、mypy **158 app文件**通过；CI已包含根 scripts 检查。
- Vue lint/type-check/生产构建通过，Vitest **26文件97项 / 4.28秒**。
- 浏览器 58 项完整运行 **54通过/4断言失败，3.0分钟**；只修改费用规则旧URL断言和基础场景Z/+00:00时间点比较后，桌面/手机定向 **4项全部通过 / 46.8秒**。业务代码未在完整运行后改变。58项均有最终代码通过覆盖，不能写成单次58项全绿。
- `foundation.spec.ts` 覆盖同组资料四流程、完整范围/对象、返回原事项、审批/完成/重开、来源变化、刷新、退出再登录、经营摘要保存回读。Node24.16.0，Chromium1440×1000/390×844；实际查看Temp中的task-mobile和support-desktop截图，无横溢。日志/trace/截图不提交。
- 无新迁移，head仍 **7e7851694067**。原74 SO、32验收、7长期E2E完整保留，后续47 SO登记。开发文档三十四/三十五、测试二十九/三十、README、矩阵及foundation四文档已同步。

## 已实现基础缺口

- G-01：AnalysisInput可选channel，省略保持原全部渠道及旧哈希兼容；服务SQL/保存/Agent/驾驶舱范围一致。运营事项以当前来源及所有权给出精确库存SKU、产品Listing、消息客服、分析窗口入口；旧来源或规则隐藏入口。前端有界query校验、完整范围、回原事项、跨店去除return_task；Agent结果深链保存原scope。修复分析误带库存时效422和Listing另存刷新仍指旧版本。
- G-02：`scripts/foundation_samples.py` 生成五份合成CSV与manifest，统一UTC锚点/政策期/库存时效。3商品、5订单、3库存、2消息。主Amazon/USD销售75、成本62、毛利13、qty4；全部渠道USD87但成本/毛利未知并有EUR边界。修订CUP成本后主范围毛利10。5当前事项，来源更新保留旧completed/stale历史并形成新候选。样本和完整复现见 examples/foundation、foundation-user-guide。
- G-03：`scripts/database_backup.py` 容器mysqldump、前后head/行数/checksum、SHA256清单；只向mysql-test中新建soloops_restore_*_test恢复，拒绝已有目标。SQL用临时受限账号执行，数据库权限转义下划线，禁local-infile/客户端命令，finally删除临时账号；凭据不在参数或输出。11项防护测试通过。
- 接手SO-056只读核对：精确原字符order_id及用户/店铺/身份/渠道；先窗口候选再读取所有相关当前来源，两侧各1000上限。卖家声明口径、同币种同当地日、双方窗内单行单sale且折扣/状态已知才算Decimal差额。累计退款仍待核，无迁移。35后端/6Vue/2浏览器已纳入本轮验证。

## 隔离恢复的实际证据

- 已执行 backup --service mysql-test --name foundation-20261009-2304，以及 restore --name foundation-20261009-2304 --target soloops_restore_foundation_20261009_test。
- 64表、head、行数和CHECKSUM一致；只读回查2主店、6完成事项、2失效但已完成低毛利事项、2历史批准Listing、2历史毛利13分析及完成待办、2客服存档、2经营摘要，临时恢复账号0。再次同目标恢复被拒绝。
- 备份在忽略目录 `.local/backups/foundation-20261009-2304`；只读回查脚本 `.local/foundation_restore_readback.py`。源soloops_test之后被全套测试重置；恢复副本仍在mysql-test容器，tmpfs随容器停止丢失，文件备份保留。不能把该副本当作首次安装证据。

## 接续立即执行

1. 先读 AGENTS.md、foundation-release/acceptance/backlog/user-guide，核实8f6956f的CI；失败先修。不要从旧财务扩展建议另开范围。
2. **G-04/B-01/B-10**：隔离全新配置与数据库，实际完成迁移、账号、店铺、导入和金额回读；实际API进程重启后核实持久记录，并验证调度启停/最近一期恢复及不重复。`scripts/setup_local.py` 目前固定ROOT、拒绝覆盖已有配置，可按实际需要实现安全隔离入口。保留已有.env与开发库，不用重置既有库来伪装首次运行。源_test共享测试串行；新库有明确_test后缀及隔离权限。当前开发API8000仍为本阶段前的旧进程，新路由尚未重启部署；先查端口/CIM命令行再操作，不能沿用历史PID。后台Start-Process使用WindowStyle Hidden。
3. **G-05/B-06**：真实四流程验收，¥1累计上限且本轮0调用。读取现有配置时只输出安全模型/费率字段，不打印.env/密钥。已知provider dashscope_chat、模型qwen3.7-flash、北京endpoint，须核实当前官方费率及现有USD预算换算，再预留每次费用上界。通过项目受控服务/adapter运行，同样本今日运营、问数（可能规划+解释两次）、Listing、FAQ及混合敏感客服；未知响应先查记录，不盲目重试。逐次token/时间/结果和已知估算费用留可审查证据，费用未知立即暂停付费部分。模型实现在app/services/agent_model.py；正常pytest/E2E保持真实调用关闭。官方资料见references与testing历史27节，费率必须重新核实。
4. **G-06/B-07**：等待本人通道/验证收件箱/本次单次发送许可后，沿现有R2发送本人运营检查摘要，保存真实回执和实际收件佐证。R2目前支持operation_run摘要，不能假设overview_report可发。不要把替身或“审批通过”等同实际送达。尚未取得这些外部条件，继续独立工作。
5. 对应改动测试、静态检查、开发/测试/知识点/矩阵/问题记录同步后正常提交推送main与context-memory。基础版本全部验收前不得标记完成。已通过检查不无故重复扩大测试。

## 环境与操作约束

- Windows PowerShell；工作区 `C:\Users\27363\Desktop\AI E-commerce Agent`。Vue3/TS、FastAPI/Python3.11、MySQL8.4，API→service→repository。金额Decimal/Numeric、UTC保存/显式IANA显示，当前用户/店铺约束；Agent只能调用受控业务服务。
- 每功能先查官方/GitHub并更新references许可证/借鉴/适配；Firecrawl已确认402，用官方web工具fallback，不反复尝试计费接口，不编HTTP抓取脚本。
- backend/.venv、frontend/node_modules已存在。MySQL开发3307、测试3308；容器soloops-mysql-1和soloops-mysql-test-1。pytest/迁移/E2E/测试库恢复必须串行。真实模型、邮件、常规定时在常规测试中关闭。
- E2E在frontend目录使用 `npm run test:e2e`（先生产构建，测试器管理API8001/preview5174，CI=true）。临时将 `.local/runtimes/node-v24.16.0-win-x64` 加入PATH，不能用全局24.15.0；后者曾Windows TCP原生崩溃，详见testing二十八。全局安装未改。
- 沙箱MySQL socket10013、Vitest EPERM、Git索引只读时使用已授权允许环境；不重复请求用户确认普通开发/检查/正常推送。没有自动审批拒绝遗留。gh未安装，GitHubconnector不可用时可用IAB公开页面看CI。Browser插件不可用，浏览器测试沿项目Playwright。
- 真实客户、密钥、本机配置、日志、截图/trace不提交；`.local`和`.context-memory`在main忽略。context-memory独立分支只存本文重点，不合并main、不保存整段聊天。禁止强推。
- 项目ID `1c274a7b-2f1e-45ca-bf1b-10475766545b`（电商智能体）。切新聊天用local同项目，先落盘推送、传明确起点，交接后旧聊天停止修改。当前没有需要创建的定时自动化；用户要求的是上下文接近上限时主动换聊天。
