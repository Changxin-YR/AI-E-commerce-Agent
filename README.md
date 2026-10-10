# SoloOps 接续上下文

更新：2026-10-10。基础版本B-01至B-14已全部通过；G-01至G-06完成，本人QQ摘要已真实收件并保存声明。后续长期扩展等待用户启动。一个开发聊天独占主工作区，不启用子代理或并行开发聊天。

## 当前目标与提交

- foundation-release约定四流程及B-01至B-14已完成；A-13本人邮件实发与收件已通过。保留全部74SO/32原验收/7长期E2E，27个已有模块和47个后续模块范围不变；按foundation-backlog等用户启动后续。真实经营数据及平台接口尚未验收。
- main **adddb19b58eb5772ff7ff04c029bca791fa7676b** 已正常推送：基础版最终验收/真实QQ收件/维护文档收尾，14文件仅文档。应用代码与383ca25完全一致（backend/frontend/scripts/.github diff为空），其CI38010808357已核实completed/success。最终文档提交CI38012735098亦已回读completed/success。
- 完整后端 **719 passed / 289.98秒**，Ruff规则/226文件格式、mypy159通过；前端26文件98单元/4.68秒、lint/type-check/build通过。最终邮件桌面/手机2流程/10.1秒通过，组件定向3项/1.51秒通过；已查看最终截图，390px无横溢。
- 3308迁移回退/升级及模型一致性已通过。3309保留验收库于本次先备份再升级至92c7ea53bd10，64表记录数与未改结构表CHECKSUM一致。3307开发库仍未升级，启用新API前须迁移。绝不对3309运行pytest/seed/清库。
- 主工作区干净；本次真实邮件总共2封（验证码1、经营摘要1），无重试。新增模型调用0。用户QQ地址/授权码在被忽略backend/.env，enabled=false，主3307库owner/shop仍未绑定；3309验收已关闭外发，模型/调度也关闭。

## QQ邮件已实现与已验收能力

- 用户明确要QQ邮箱发件和收件，且可发给其他人。QQ SMTP固定smtp.qq.com:465+证书校验，登录用客户端授权码。MailProvider.verify_sender替代verify_domain；固定本人账号/店铺和验证收件箱，生成摘要前可输入其他单个纯邮箱地址。
- 每封收件人保存在OutboundMessage.recipient，进入content_hash和按run/收发地址的dedupe_key，另一地址需新预览/独立审批；已有Resend通道仍只发已验证本人地址。provider随TestMailChannel持久化，旧消息recipient为空时回读原通道地址。
- SMTP最终DATA250才accepted/smtp_accepted，receipt_id为dispatch UUID，smtp_message_id显示稳定邮件头标识，不能当作远端送达证明。DATA超时unknown且不重发。QQ无回执查询API，reconcile返回409；unknown可追加独立人工收件声明，状态和回执不提升。QUIT失败不覆盖已取得250。原Resend指纹/只读回查保持兼容。
- `.local/qq_migration_check.py`仅3308回退升级验证脚本。截图在本机Temp/soloops-qq-mail-desktop.png和mobile.png，不提交。生产未加收件同步；真实邮件仍须明确地址和全文许可。

## G-05已完成，不重复付费验收

- 2026-10-09 23:54至23:56，已有北京百炼dashscope_chat/qwen3.7-flash，生产Agent API→受控服务→生产adapter。同组G-04合成资料在独立库新店#2导入。7次真实请求：今日运营；问数规划+解释2次；Listing；FAQ；物流退款混合；缺政策且未核验订单身份。
- 本轮授权人民币1元累计封顶。已执行**7次**，usage已知目录估算**0.0007750 CNY**，未知费用0；应用保守预算费用**0.000933 USD**，reserved0。7次最高档包络预留总和0.0830340元，均未超界，无重试。目录估算剩余0.9992250元；实际扣款以供应商账单为准。旧0.01元许可独立已用。
- 官方费率已复核：北京输入≤32K输入0.2/输出0.8元每百万tokens；最高档1.2/4.8。现有本机配置USD费率0.24/0.96，说明为最高档乘固定1CNY=0.20USD预算折算，非实时汇率。不能把USD预算数字当人民币扣款。
- 真实结果：9运营分支/5候选，审批检查#3/待办#7至#11，5项完成→重开→完成；问数75/62/13，CUP55/54/1，分析#2待办#1完成重开完成；完整商品名/不锈钢350mL Listing模型版本#2，人工标题整理版本#3批准本地；FAQ草稿#2人工编辑仍draft；混合物流+退款draft#3为human_review后存档，均not_submitted。
- 缺证据真实候选#7为handoff、无臆造政策/物流/退款。经导入修订FAQ消息后旧候选source_status=stale，按当前version审批HTTP409，客服记录仍2份。商品CUP成本18改19，原已完成分析保留13且stale，当前重算10；Listing批准指针和历史保留并明确stale。新本地operation_run #4来源current，可用于后续R2。
- 成功的5个执行重放相同request_id和advance仍原id/succeeded，付费数保持7。停付费API后用全关闭配置实际重启，原会话与6个执行+旧分析+旧Listing+当前检查共9份快照精确一致。
- 完整逐次token/时间/费用/审阅事实在docs/foundation-model-evidence.md，B-02至B-06通过。G-05不需要重复跑或再建新付费执行。

## G-06/A-13/B-07/B-08已完成

- 用户明确使用QQ发件、默认本人收件并可填写其他单个地址。本次本人真实邮箱地址仅在本机，不写到版本库或接续分支。未来新邮件仍按该封地址/全文独立许可；本次两封许可均已使用，不可沿用。
- 09:01生产TLS/SMTP AUTH核验成功；3309保留G04/G05库先备份foundation-qq-before-20261010-010136后升级92c7ea53bd10，64表行数一致/未改结构表CHECKSUM一致。实际SQL归属与HTTP登录确认owner1/shop2。
- 用户明示同意1封验证码：09:07:48（Asia/Shanghai）POST /api/shops/2/outbound/channel/connect一次，通道1为verifying且有SMTP接受标识；用户读取本人邮箱提供8位码，09:09:47 POST /channel/1/verify成功，active并清空验证码哈希。不要再请求验证码，不保存原码。
- 运营检查4来源current，R2预览1/version1，发件/收件同为本人QQ，主题“SoloOps 测试经营摘要 · 检查 #4”。实际地址/主题/完整正文已在确认卡展示；用户明确“已核对，同意发送这1封摘要”。09:12:48单次approve得到审批1，09:12:49 send一次，结果accepted/smtp_accepted/version3，审批used/max_uses1/used_count1。随后GET完全一致。
- 用户明确“已在收件箱收到，地址和正文一致”。09:15:25通过原receipt接口保存声明，证据位置为本人QQ收件箱按上述主题及09:12提交时间定位。received_at是声明保存时间，不能当精确送达时间。未另行核验邮箱原文头，Message-ID不等于远端送达证明。数据库1通道/1摘要/1审批、仅消耗1次，无重发。
- 完成后g06_server.py改外发false，实际停本次API子进程52496（父42808）再重启launcher43068。原会话、已接受摘要/全文/标识/人工收件声明/单次审批持久一致；仅channel_status按关闭配置变not_configured。6真实模型执行+分析历史+Listing历史+运营检查9快照与G05结果一致，账本仍7次/0.0007750元/未知0。after-restart.json是最后证据。
- 已完成docs/foundation-mail-evidence.md最终报告，foundation-mail-review.md为实际已获批发送正文。B-07/B-08/A-13关闭，B-01至B-14共14项通过；全部74SO、32原验收表行保留，敏感字段扫描和diff-check通过。应用代码未修改，常规719/98及原CI通过证据继续对应代码，不重复扩测。
- 日常邮件路径：启用并绑定实际运行实例→测试外发→选择运营检查→填单个收件人→生成预览→核对地址和全文→单次批准并提交→在QQ查看收件→记录收件证据。应用不做QQ收件箱同步。主3307库未升级/未绑定，不要将3309编号照抄到主配置；用户要求日常启用时先核对实际库、账号和店铺。

## G-06本机证据与辅助脚本

- .local/foundation-g06：migration.json、smtp-login.json、http-state.json（会话敏感）、verification-consent/result、mailbox-verified、summary-preview/consent/approved/result/readback/receipt、receipt-statement、database-audit、before-restart/after-restart。verification-review和summary-review为实际地址全文，仅本机。
- .local/g06_prepare.py为一次性备份/迁移/登录核验，拒绝已有邮件记录，不重跑；g06_http.py和g06_verify_and_preview.py已过其前置状态，不原样重跑。g06_send_verification.py、g06_send_summary.py使用独占本机许可文件防重跑，不删文件绕过保护。g06_closeout.py receipt仅供首次声明，after-restart可只读核对但业务来源随时间过期后原快照可能不再完全一致。g06_server.py现三开关false。
- g06_finalize_docs.py、g06_context.py等本轮整理脚本不要重跑，避免覆盖最终文档或恢复旧“待许可”状态。优先直接读当前文件与只读API，遵循真实时间与来源失效。

## 环境及证据保留

- 主目录C:\Users\27363\Desktop\AI E-commerce Agent；Windows PowerShell，Vue3/TS/FastAPI/Python3.11/MySQL8.4，三层服务，Decimal/Numeric、UTC和显式时区/用户店铺隔离。
- **当前MySQL3309、验收API8002、测试前端5175均运行。前端PID39828，.local/foundation-g06/frontend-pid.txt；链接http://127.0.0.1:5175/，代理API8002。** g06_server.py已outbound/model/scheduler全部false；本次重启launcher43068，PID文件.local/foundation-g06/api-launch-pid.txt，停进程前按g06_server.py与父进程路径重新核实。主3307/3308及旧API8000未操作。
- G-04副本.local/foundation-g04，Compose项目soloops-foundation-g04，卷soloops-foundation-g04_mysql-data，库soloops_foundation_g04_test。启动保留库：在副本根`docker compose -p soloops-foundation-g04 --env-file .env -f compose.yaml -f compose.g04.yaml up -d --wait mysql`。不要重跑setup/bootstrap/seed，不要向该库运行pytest。
- G-04本机脚本.local/g04_prepare.py、g04_bootstrap.py、g04_http.py、g04_control.ps1、g04_browser.mjs、g04_audit.py；副本.local中initial/bootstrap/http-state/final-audit/samples/account，账号/会话严禁打印。副本.env真实模型/邮件关闭；常规scheduler原true，复用时须关闭。
- G-05本机.local/foundation-g05/ledger.json含7次usage及规范化合成响应，http-state.json含阶段快照，audit.json有合计。辅助脚本g05_server.py临时审计子类、g05_http.py、g05_closeout.py、g05_readback_server.py。不要直接重跑付费脚本，不要删除账本。readback-server为主代码+副本DB配置，模型/邮件/调度全关闭。
- g05_closeout.py restart-read可在只读配置API下回读9快照；它使用已有会话，过期需安全重新登录。辅助g05_docs.py/g05_update_docs.py只属本轮一次性整理，**不要重跑覆盖最新文档**。
- G-04在新配置/venv/独立容器空库0→64表，CLI创建账号及实际HTTP五文件导入75/62/13，14响应精确恢复。真实23:36停机到期，worker关闭不运行、启用恢复一期waiting_approval，批准后再重启1周期1执行6待办不变。详见foundation-runtime-evidence。
- G-03备份.local/backups/foundation-20261009-2304，64表head/行数/CHECKSUM一致，历史代表回读通过；恢复副本位于mysql-test(tmpfs停止丢失)，文件备份保留。
- 本地静态/测试用backend/.venv；pytest/迁移/E2E共享3308须严格串行。浏览器使用.local/runtimes/node-v24.16.0-win-x64与npm run test:e2e，禁用真实模型/邮件。全局24.15曾Windows原生崩溃，不复用。
- 普通开发、定向测试与正常提交推送已授权，不强推；沙箱Docker/MySQL/Git写索引受限时按权限机制升级。本轮无自动审批拒绝。gh未安装；GitHub fetch工具可读REST actions/runs?head_sha=...&event=push，正文在structuredContent.content里，返回时只输出必要字段，避免整份仓库元数据。Firecrawl已402，官方web工具fallback，不反复消耗接口，不编HTTP抓取脚本。
- docs/development39、testing34、interview、README、功能/原验收矩阵和foundation规格/验收/后续/维护/实发证据全部同步。context-memory独立分支只存重点，不合并main。
- 接续先读AGENTS.md与foundation-release/acceptance/backlog、runtime/model evidence。项目ID1c274a7b-2f1e-45ca-bf1b-10475766545b，换聊天用local同项目，单开发聊天独占。

## 已交付用户测试入口（2026-10-10）

- 用户要求已完成则提供测试链接；基础B01-B14已全部验收，未另建聊天。启动主代码Vite前端127.0.0.1:5175，连接保留的3309库/API8002，模型/真实邮件/调度仍关闭。用户可浏览合成历史与测试本地业务，不能据此宣称全部外部功能已启用。
- .local/TEST-ACCESS.md包含本机测试账号登录资料（密码不进版本库），当前账号test，选择店铺2「合成真实模型四流程验收 · foundation-g05」，必要时选合成测试数据与Amazon。已提供本机链接和本机登录文件路径，不是公网链接。
- 项目Playwright实际浏览器检查：登录成功、刷新会话有效、选店、摘要1 accepted及received_at回读、页面错误0、390px横溢0；test-link-check.json及test-link-desktop.png在.local/foundation-g06。应用代码没有修改，主工作区干净。
- 2026-10-10 09:32按用户要求简化本机账号：同一user1从foundation_g04改为test，使用既有AuthService重置12位密码并撤销7个旧会话，保留店铺1/2及邮件/收件记录。实际HTTP验证旧会话401、新登录成功，店铺列表和邮件完整响应保持一致；实际浏览器再验登录、刷新、原记录通过。只改3309本机数据和忽略文件，未修改应用代码；明文密码仅保留.local/foundation-g04/.local/account.json及.local/TEST-ACCESS.md等本机资料，禁止提交。安全结果在.local/foundation-g06/account-update.json。
- .local/foundation-g06/http-state.json已更新为新会话；G04/G05历史状态文件内会话均失效，历史证据保留，后续脚本需从当前account.json安全重新登录。不要重跑simplify_test_login.py或恢复旧凭据。当前范围只做简化账号及功能说明，长期扩展尚未启动。
