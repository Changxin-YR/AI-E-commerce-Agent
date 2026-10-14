# SoloOps 接续上下文

更新：2026-10-09 23:47（Asia/Shanghai）。基础G-01至G-04已完成并提交推送。交接后由新聊天独占主工作区，旧聊天停止写入；不要启动子代理或其他并行写入聊天。

## 用户当前要求

- 按 `docs/foundation-release.md` 的基础版本继续开发，完整实现四条流程及 B-01 至 B-14。长期扩展保存在 `foundation-backlog.md`，等用户以后启动；基础版本剩余项必须继续完成。
- 用户再次明确：主动关注上下文接近上限，先整理、提交、推送，再创建新本地聊天继续；不要在同一聊天长期积累，不必重复请求交接许可。
- 本轮真实模型已授权：已有北京百炼通道、合成数据，累计人民币 1 元封顶。当前本轮 0 调用、已知费用 0 元。未知费用先核对；每次调用预留上界并记录累计。旧的 0.01 元一次性许可已耗尽，与本轮独立。
- 本人邮件仍缺通道配置、验证的本人测试收件箱和本次单次发送许可。模型额度不授权邮件。保留 B-07/A-13 的真实提交与收件证据，等待期间推进其余工作。

## 当前提交与验证

- main **d5fe67feeecde74cd9927d10cc822651fc76155f** 已正常推送origin/main，13文件；主工作区干净。本次G-04新增首次安装/实际进程恢复证据，初始化脚本保护已有.local/test.env，并以独占模式创建三份配置。业务API/前端/迁移仍与8f6956f一致。
- 新提交[CI37954208866](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37954208866)在23:47核实时In progress，接续先查最终结果。基线[8f6956f CI37950996694](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37950996694)已核实Success，verify9分14秒/总9分18秒。
- 新增`test_local_setup.py` **4 passed / 1.01秒**；Ruff规则及格式 **223文件**、mypy **158 app文件**通过。沙箱默认Temp失败后用`--basetemp=../.local/pytest-setup-g04`通过，测试要求不变。
- 业务基线完整后端 **685 passed / 301.69秒**。Ruff规则与格式 **222文件**、mypy **158 app文件**通过；CI已包含根 scripts 检查。
- Vue lint/type-check/生产构建通过，Vitest **26文件97项 / 4.28秒**。
- 浏览器 58 项完整运行 **54通过/4断言失败，3.0分钟**；只修改费用规则旧URL断言和基础场景Z/+00:00时间点比较后，桌面/手机定向 **4项全部通过 / 46.8秒**。业务代码未在完整运行后改变。58项均有最终代码通过覆盖，不能写成单次58项全绿。
- `foundation.spec.ts` 覆盖同组资料四流程、完整范围/对象、返回原事项、审批/完成/重开、来源变化、刷新、退出再登录、经营摘要保存回读。Node24.16.0，Chromium1440×1000/390×844；实际查看Temp中的task-mobile和support-desktop截图，无横溢。日志/trace/截图不提交。
- 无新迁移，head仍 **7e7851694067**。原74 SO、32验收、7长期E2E完整保留，后续47 SO登记。开发文档三十六、测试三十一、README、矩阵及foundation规格/验收/维护/运行证据已同步。B-01/B-10/B-12已通过；B-06/B-07继续必验。

## 已实现基础缺口

- G-01：AnalysisInput可选channel，省略保持原全部渠道及旧哈希兼容；服务SQL/保存/Agent/驾驶舱范围一致。运营事项以当前来源及所有权给出精确库存SKU、产品Listing、消息客服、分析窗口入口；旧来源或规则隐藏入口。前端有界query校验、完整范围、回原事项、跨店去除return_task；Agent结果深链保存原scope。修复分析误带库存时效422和Listing另存刷新仍指旧版本。
- G-02：`scripts/foundation_samples.py` 生成五份合成CSV与manifest，统一UTC锚点/政策期/库存时效。3商品、5订单、3库存、2消息。主Amazon/USD销售75、成本62、毛利13、qty4；全部渠道USD87但成本/毛利未知并有EUR边界。修订CUP成本后主范围毛利10。5当前事项，来源更新保留旧completed/stale历史并形成新候选。样本和完整复现见 examples/foundation、foundation-user-guide。
- G-03：`scripts/database_backup.py` 容器mysqldump、前后head/行数/checksum、SHA256清单；只向mysql-test中新建soloops_restore_*_test恢复，拒绝已有目标。SQL用临时受限账号执行，数据库权限转义下划线，禁local-infile/客户端命令，finally删除临时账号；凭据不在参数或输出。11项防护测试通过。
- 接手SO-056只读核对：精确原字符order_id及用户/店铺/身份/渠道；先窗口候选再读取所有相关当前来源，两侧各1000上限。卖家声明口径、同币种同当地日、双方窗内单行单sale且折扣/状态已知才算Decimal差额。累计退款仍待核，无迁移。35后端/6Vue/2浏览器已纳入本轮验证。

## 隔离恢复的实际证据

- 已执行 backup --service mysql-test --name foundation-20261009-2304，以及 restore --name foundation-20261009-2304 --target soloops_restore_foundation_20261009_test。
- 64表、head、行数和CHECKSUM一致；只读回查2主店、6完成事项、2失效但已完成低毛利事项、2历史批准Listing、2历史毛利13分析及完成待办、2客服存档、2经营摘要，临时恢复账号0。再次同目标恢复被拒绝。
- 备份在忽略目录 `.local/backups/foundation-20261009-2304`；只读回查脚本 `.local/foundation_restore_readback.py`。源soloops_test之后被全套测试重置；恢复副本仍在mysql-test容器，tmpfs随容器停止丢失，文件备份保留。不能把该副本当作首次安装证据。

## G-04实际运行证据及保留环境

- 完整报告`docs/foundation-runtime-evidence.md`；从Git源码导出的`.local/foundation-g04`独立副本，初始化补丁与main一致。新venv锁定安装47包，前端npm ci293包审计0漏洞，Node24.16.0生产构建/type-check通过。数据库0→64表/head7e7851694067，账号CLI密码标准输入。
- Compose项目`soloops-foundation-g04`、独立持久卷`soloops-foundation-g04_mysql-data`，MySQL3309、库`soloops_foundation_g04_test`、API8002/前端5175。验收结束这三个服务均已停止，卷保留。开发mysql3307、测试mysql3308及旧API8000未被操作；原三份配置SHA256一致。
- 实际HTTP经营资料/店铺/5文件预览确认，3商品/5订单/3库存/2消息、2有效政策；Amazon/USD销量4、销售75/成本62/毛利13。保存完成事项、批准Listing、人工客服存档、分析和摘要。原会话及14份响应快照在多次API进程重启后精确一致。
- 用真实时间15:36UTC/北京时间23:36创建计划、暂停→恢复，然后停API跨过到期；scheduler=false启动时历史0并保留到期，true重启仅恢复1期waiting_approval。受控批准推进succeeded后再次重启，1周期/1执行/6任务编号均不变。第二次检查窗口不同，低毛利新范围候选使任务从5变6，不能把它写成重复任务。调度历史保存触发状态waiting_approval，当前执行另从Agent回读succeeded。
- 新副本Chromium桌面1440×1000/手机390×844登录/选店/刷新/持久会话通过，错误0/横溢0；手机截图已查看。
- 忽略目录保留`.local/g04_prepare.py`（只能新建，勿重复）、g04_bootstrap.py（要求空库，勿重跑）、g04_http.py（seed只能一次；read/schedule-read可回读）、g04_control.ps1、g04_browser.mjs、g04_audit.py。副本`.local`内有initial/bootstrap/http-state/final-audit、samples.json和截图；account.json及http-state含账号/会话，禁止打印或提交。
- 可按完整前缀`docker compose -p soloops-foundation-g04 --env-file .env -f compose.yaml -f compose.g04.yaml up -d --wait mysql`（在副本根）重启3309保留数据。G-05可复用同组数据或另建合成店铺；先核对政策时效、当前源与样本scope。不要用setup或pytest重置该证据库。复制的backend/.env默认模型/邮件关闭、调度true；G-05如果复用应关闭调度并仅从主backend忽略配置安全加载既有模型字段。

## 接续立即执行

1. 先读AGENTS.md、foundation-release/acceptance/backlog/user-guide及foundation-runtime-evidence，核实d5fe67f的CI37954208866，失败先修；G-04已完成，不要重做或扩大长期功能。
2. **立即推进G-05/B-06**：真实四流程验收，¥1累计上限且本轮仍0调用/已知0元。读取现有配置只输出安全模型/费率字段，不打印.env/密钥。历史已知provider dashscope_chat、qwen3.7-flash、北京endpoint；先核实当前官方费率、现有USD预算换算及每次包络费用上界。通过项目Agent受控服务/adapter、同组合成资料执行今日运营、问数（可能规划+解释2次）、Listing、FAQ和混合敏感客服；保存后核验事实、审批、来源变化/缺证据边界。未知响应先查持久记录，不盲目重试；费用未知暂停付费部分。逐次token/时间/脱敏结果、已知估算费用和人民币累计记证据。模型实现在app/services/agent_model.py，历史费率/协议见references和testing27，必须重新核实。常规pytest/E2E真实模型/邮件关闭。
3. **G-06/B-07**仍等待本人通道配置、验证本人收件箱及本次单次发送许可；模型额度不包含邮件。条件到位后沿R2发送已审阅且有来源的operation_run经营摘要，保留真实回执及实际收件佐证。R2不支持overview_report，不可混淆。缺条件时继续独立收尾，基础版本不能标全部完成。
4. 对应改动测试、静态检查、开发/测试/知识点/矩阵/问题同步后正常提交推送main与context-memory，不强推。通过的检查不无故重复扩大；上下文接近上限同样先保存推送再新建接续聊天，旧聊天立即停止工作区写入。

## 环境与操作约束

- Windows PowerShell；工作区 `C:\Users\27363\Desktop\AI E-commerce Agent`。Vue3/TS、FastAPI/Python3.11、MySQL8.4，API→service→repository。金额Decimal/Numeric、UTC保存/显式IANA显示，当前用户/店铺约束；Agent只能调用受控业务服务。
- 每功能先查官方/GitHub并更新references许可证/借鉴/适配；Firecrawl已确认402，用官方web工具fallback，不反复尝试计费接口，不编HTTP抓取脚本。
- backend/.venv、frontend/node_modules已存在。MySQL开发3307、测试3308；容器soloops-mysql-1和soloops-mysql-test-1。pytest/迁移/E2E/测试库恢复必须串行。真实模型、邮件、常规定时在常规测试中关闭。
- E2E在frontend目录使用 `npm run test:e2e`（先生产构建，测试器管理API8001/preview5174，CI=true）。临时将 `.local/runtimes/node-v24.16.0-win-x64` 加入PATH，不能用全局24.15.0；后者曾Windows TCP原生崩溃，详见testing二十八。全局安装未改。
- 沙箱MySQL socket10013、Vitest EPERM、Git索引只读时使用已授权允许环境；不重复请求用户确认普通开发/检查/正常推送。没有自动审批拒绝遗留。本轮新增4项测试用工作区basetemp避免沙箱Temp创建失败。gh未安装，GitHubconnector不可用时可用IAB公开页面看CI。Browser插件不可用，浏览器测试沿项目Playwright。
- 真实客户、密钥、本机配置、日志、截图/trace不提交；`.local`和`.context-memory`在main忽略。context-memory独立分支只存本文重点，不合并main、不保存整段聊天。禁止强推。
- 项目ID `1c274a7b-2f1e-45ca-bf1b-10475766545b`（电商智能体）。切新聊天用local同项目，先落盘推送、传明确起点，交接后旧聊天停止修改。当前没有需要创建的定时自动化；用户要求的是上下文接近上限时主动换聊天。
