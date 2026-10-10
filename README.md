# SoloOps 接续上下文

更新：2026-10-10。G-01至G-05已完成；QQ邮箱适配已完成，本人真实邮件验收仍待。一个开发聊天独占主工作区，不启用子代理或并行开发聊天。上下文近上限时先落盘提交推送，再创建新聊天接续，旧聊天停止写入。

## 当前目标与提交

- 交付foundation-release可运行基础版，四流程与B-01至B-14；长期扩展按foundation-backlog等用户启动。74SO、32原验收、7长期E2E保留。
- main **2a431ebbed147f78c43d559b2e36cdaaf77007e2** 已正常推送：G-06真实QQ SMTP登录及配置/备份升级证据，应用代码仍为383ca25。383ca25的CI38010808357已核实completed/success；本次仅文档提交未回读新CI。
- 完整后端 **719 passed / 289.98秒**，Ruff规则/226文件格式、mypy159通过；前端26文件98单元/4.68秒、lint/type-check/build通过。最终邮件桌面/手机2流程/10.1秒通过，组件定向3项/1.51秒通过；已查看最终截图，390px无横溢。
- 3308迁移回退/升级及模型一致性已通过。3309保留验收库于本次先备份再升级至92c7ea53bd10，64表记录数与未改结构表CHECKSUM一致。3307开发库仍未升级，启用新API前须迁移。绝不对3309运行pytest/seed/清库。
- 主工作区干净；真实邮件新增0，真实模型新增0。用户已填backend/.env授权码，QQ TLS/SMTP AUTH实际成功；backend/.env仍enabled=false、主库未绑定。实际验收API用忽略g06_server.py合并QQ配置与3309数据库，仅绑定owner1/shop2、外发启用，模型和调度关闭。

## QQ邮件改动与下一步

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

## G-06/B-07当前阻塞与准备

- 用户最新“填好了”，本机QQ授权码存在且真实SMTP登录已成功，2026-10-10 01:01:41 UTC，只执行AUTH/QUIT，未执行DATA。不打印凭据。用户选择QQ收发、默认本人、可填其他收件人，尚无任何一封真实发送许可。
- 已通过request_user_input_async展示真实本人收发地址、主题及模板，请求“现在发送1封验证邮件”的许可，**尚未收到回复**。不要重复问已有配置，也不要将填写授权码视为本封发送许可。按foundation-release第7节，验证码与摘要各自审批。
- 主代码+保留3309库API8002已就绪，模型/scheduler禁用。SQL查归属及实际登录会话验证owner1/shop2；通道provider=qq_smtp/configured=true/status=disconnected，无邮件记录。QQ实际地址仅在忽略backend/.env及本机HTTP预览中，勿提交文档。
- 验证邮件主题“SoloOps 测试邮箱验证”；正文“SoloOps 测试邮箱验证。验证码：{8 位随机码}。15 分钟内有效。此邮件仅验证本人测试邮箱，不含经营数据。”独立获准后调用实际POST /api/shops/2/outbound/channel/connect，json confirmed=true，一次提交。之后用户读QQ邮件给8位验证代码或在UI填写，POST /channel/{id}/verify；不要把邮箱客户端授权码当验证码。
- 本机.local/foundation-g06/http-state.json已有新登录cookies/csrf/通道预览；本机会话不能输出。g06_http.py只登录及读配置，当前断言disconnected，发信后不要原样重跑。g06_prepare.py包含一次性备份升级/只读SMTP核验，拒绝已有邮件记录，不能反复重跑。g06_server.py启动主代码API8002；实际secret仅运行时从本机.env读取。
- .local/foundation-g06/migration.json记录新备份foundation-qq-before-20261010-010136（.local/backups），旧head7e7851694067、新head92c7ea53bd10、64表行数一致/未改结构表CHECKSUM一致。smtp-login.json保存安全核验结果，verification-review.md是实际地址+模板。G-05账本哈希相同，新增模型调用0。
- 本人验证通过后，重新读取同组资料operation_run #4的当前来源/时效，必要时以本地规则重检，使用R2生成实际摘要并展示地址和全文，取得单次许可再提交。不能将overview_report当R2输入。已有docs/foundation-mail-review.md仅原稿，可能需按当前库存时效更新。
- B07须SMTP接受及实际收件两份证据，B08邮件段依赖B07。QQ未知仅人工核对原收件箱，不能重发或虚构回执；人工声明独立。完整当前证据docs/foundation-mail-evidence.md；基础版本仍未全部完成。完成后关闭验收API或外发开关。

## 环境及证据保留

- 主目录C:\Users\27363\Desktop\AI E-commerce Agent；Windows PowerShell，Vue3/TS/FastAPI/Python3.11/MySQL8.4，三层服务，Decimal/Numeric、UTC和显式时区/用户店铺隔离。
- **当前MySQL3309与QQ验收API8002运行，前端5175未启动。** API启动器PID记录在.local/foundation-g06/api-launch-pid.txt（本次42808），实际子进程需按g06_server.py命令行确认后停止。主开发3307、测试3308和旧API8000未操作。
- G-04副本.local/foundation-g04，Compose项目soloops-foundation-g04，卷soloops-foundation-g04_mysql-data，库soloops_foundation_g04_test。启动保留库：在副本根`docker compose -p soloops-foundation-g04 --env-file .env -f compose.yaml -f compose.g04.yaml up -d --wait mysql`。不要重跑setup/bootstrap/seed，不要向该库运行pytest。
- G-04本机脚本.local/g04_prepare.py、g04_bootstrap.py、g04_http.py、g04_control.ps1、g04_browser.mjs、g04_audit.py；副本.local中initial/bootstrap/http-state/final-audit/samples/account，账号/会话严禁打印。副本.env真实模型/邮件关闭；常规scheduler原true，复用时须关闭。
- G-05本机.local/foundation-g05/ledger.json含7次usage及规范化合成响应，http-state.json含阶段快照，audit.json有合计。辅助脚本g05_server.py临时审计子类、g05_http.py、g05_closeout.py、g05_readback_server.py。不要直接重跑付费脚本，不要删除账本。readback-server为主代码+副本DB配置，模型/邮件/调度全关闭。
- g05_closeout.py restart-read可在只读配置API下回读9快照；它使用已有会话，过期需安全重新登录。辅助g05_docs.py/g05_update_docs.py只属本轮一次性整理，**不要重跑覆盖最新文档**。
- G-04在新配置/venv/独立容器空库0→64表，CLI创建账号及实际HTTP五文件导入75/62/13，14响应精确恢复。真实23:36停机到期，worker关闭不运行、启用恢复一期waiting_approval，批准后再重启1周期1执行6待办不变。详见foundation-runtime-evidence。
- G-03备份.local/backups/foundation-20261009-2304，64表head/行数/CHECKSUM一致，历史代表回读通过；恢复副本位于mysql-test(tmpfs停止丢失)，文件备份保留。
- 本地静态/测试用backend/.venv；pytest/迁移/E2E共享3308须严格串行。浏览器使用.local/runtimes/node-v24.16.0-win-x64与npm run test:e2e，禁用真实模型/邮件。全局24.15曾Windows原生崩溃，不复用。
- 普通开发、定向测试与正常提交推送已授权，不强推；沙箱Docker/MySQL/Git写索引受限时按权限机制升级。本轮无自动审批拒绝。gh未安装；GitHub fetch工具可读REST actions/runs?head_sha=...&event=push，正文在structuredContent.content里，返回时只输出必要字段，避免整份仓库元数据。Firecrawl已402，官方web工具fallback，不反复消耗接口，不编HTTP抓取脚本。
- docs/development38、testing33、interview、README、矩阵、foundation证据/维护已同步。context-memory独立分支只存本文重点，不合并main，不提交完整聊天/本机日志。
- 接续先读AGENTS.md与foundation-release/acceptance/backlog、runtime/model evidence。项目ID1c274a7b-2f1e-45ca-bf1b-10475766545b，换聊天用local同项目，单开发聊天独占。
