# SoloOps 接续上下文

更新：2026-10-10。G-01至G-05已完成；QQ邮箱适配已完成，本人真实邮件验收仍待。一个开发聊天独占主工作区，不启用子代理或并行开发聊天。上下文近上限时先落盘提交推送，再创建新聊天接续，旧聊天停止写入。

## 当前目标与提交

- 交付foundation-release可运行基础版，四流程与B-01至B-14；长期扩展按foundation-backlog等用户启动。74SO、32原验收、7长期E2E保留。
- main **383ca25e9c7f7e6894b4a2a45fd156fac3ce4d6a** 已正常推送（32文件）：QQ SMTP、逐封收件地址审批、配置切换准确预览、独立SMTP接受和人工收件声明，迁移92c7ea53bd10；新CI尚未回读，不能标成功。基线b1f3d75的CI37956738913已核实Success（6分47秒）。
- 完整后端 **719 passed / 289.98秒**，Ruff规则/226文件格式、mypy159通过；前端26文件98单元/4.68秒、lint/type-check/build通过。最终邮件桌面/手机2流程/10.1秒通过，组件定向3项/1.51秒通过；已查看最终截图，390px无横溢。
- 3308测试库迁移92c7ea53bd10→7e7851694067→92c7ea53bd10及Alembic模型一致性通过。**3307开发库与3309保留验收库仍未做新迁移**，启用对应API前须升级并保留业务数据。常规pytest/E2E/迁移共享3308，必须串行；不能对3309执行清库测试。
- 主工作区干净；真实邮件新增0，真实模型新增0。仅backend/.env已在本机预填用户提供的QQ发件/默认收件地址、provider=qq_smtp、enabled=false，授权码仍空；文件被Git忽略。用户邮箱不提交文档或上下文分支。

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

- **等待客户端授权码在本机填入，以及验证码和摘要的分别发送确认、真实收件。** 用户选择功能与邮箱地址不等于已批准向任何联系人实际发送。不要把模型人民币1元额度用于邮件。已向用户说明在backend/.env第14行SOLOOPS_OUTBOUND_SMTP_AUTHORIZATION_CODE填写，勿发聊天；启用前还需核对当前实例owner/shop。不要读取并打印密钥。
- 用户实际地址仅在忽略backend/.env，发送和默认收件同一QQ邮箱。该文件数据库指向主开发库；复用3309验收时必须从G04配置选择正确DB并核对3309登录会话owner与店铺#2，不能假定跨库编号一致。先对目标库执行新迁移，不重跑setup/bootstrap/seed，不清空G05证据。
- QQ设置开启含SMTP的服务、生成授权码；服务商按完整邮箱地址/授权码认证。配置完整并获确认后才启用邮件开关。先展示实际本人地址和验证码模板，获独立确认后发送1封验证邮件，输入8位验证码（15分钟）完成验证。然后重新生成当前来源的经营摘要、展示实际地址/全文并获得单次发送许可。
- 已有docs/foundation-mail-review.md来自**3309独立库店铺#2的operation_run #4**，仅本地审阅稿；库存时效已可能变化，发送前重新检查/回读来源，不能把overview_report当R2输入。真实外发记录仍0，验证码和摘要仍0发送。
- 本人B07验收须SMTP接受及实际收件两份证据，B08邮件段依赖B07。QQ未知仅人工核对原收件箱，不能重发或虚构回执；人工声明保留独立状态。配置与步骤见foundation-user-guide新的“QQ邮箱配置与本人收件验收”。

## 环境及证据保留

- 主目录C:\Users\27363\Desktop\AI E-commerce Agent；Windows PowerShell，Vue3/TS/FastAPI/Python3.11/MySQL8.4，三层服务，Decimal/Numeric、UTC和显式时区/用户店铺隔离。
- **当前隔离API8002/前端5175/MySQL3309均停止，持久卷保留。** 开发3307、测试3308及旧API8000未操作启停。G-05常规pytest只重置原3308测试库，不碰3309。
- G-04副本.local/foundation-g04，Compose项目soloops-foundation-g04，卷soloops-foundation-g04_mysql-data，库soloops_foundation_g04_test。启动保留库：在副本根`docker compose -p soloops-foundation-g04 --env-file .env -f compose.yaml -f compose.g04.yaml up -d --wait mysql`。不要重跑setup/bootstrap/seed，不要向该库运行pytest。
- G-04本机脚本.local/g04_prepare.py、g04_bootstrap.py、g04_http.py、g04_control.ps1、g04_browser.mjs、g04_audit.py；副本.local中initial/bootstrap/http-state/final-audit/samples/account，账号/会话严禁打印。副本.env真实模型/邮件关闭；常规scheduler原true，复用时须关闭。
- G-05本机.local/foundation-g05/ledger.json含7次usage及规范化合成响应，http-state.json含阶段快照，audit.json有合计。辅助脚本g05_server.py临时审计子类、g05_http.py、g05_closeout.py、g05_readback_server.py。不要直接重跑付费脚本，不要删除账本。readback-server为主代码+副本DB配置，模型/邮件/调度全关闭。
- g05_closeout.py restart-read可在只读配置API下回读9快照；它使用已有会话，过期需安全重新登录。辅助g05_docs.py/g05_update_docs.py只属本轮一次性整理，**不要重跑覆盖最新文档**。
- G-04在新配置/venv/独立容器空库0→64表，CLI创建账号及实际HTTP五文件导入75/62/13，14响应精确恢复。真实23:36停机到期，worker关闭不运行、启用恢复一期waiting_approval，批准后再重启1周期1执行6待办不变。详见foundation-runtime-evidence。
- G-03备份.local/backups/foundation-20261009-2304，64表head/行数/CHECKSUM一致，历史代表回读通过；恢复副本位于mysql-test(tmpfs停止丢失)，文件备份保留。
- 本地静态/测试用backend/.venv；pytest/迁移/E2E共享3308须严格串行。浏览器使用.local/runtimes/node-v24.16.0-win-x64与npm run test:e2e，禁用真实模型/邮件。全局24.15曾Windows原生崩溃，不复用。
- 普通开发、定向测试与正常提交推送已授权，不强推；沙箱Docker/MySQL/Git写索引受限时按权限机制升级。本轮无自动审批拒绝。gh未安装，CI可用IAB公开页。Firecrawl已402，官方web工具fallback，不反复消耗接口，不编HTTP抓取脚本。
- docs/development38、testing33、interview、README、矩阵、foundation证据/维护已同步。context-memory独立分支只存本文重点，不合并main，不提交完整聊天/本机日志。
- 接续先读AGENTS.md与foundation-release/acceptance/backlog、runtime/model evidence。项目ID1c274a7b-2f1e-45ca-bf1b-10475766545b，换聊天用local同项目，单开发聊天独占。
