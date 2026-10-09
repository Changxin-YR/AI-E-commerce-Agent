# SoloOps 接续上下文

更新：2026-10-10 00:07（Asia/Shanghai）。G-01至G-05已完成；主工作区由当前开发聊天独占，不启用子代理或并行开发聊天。用户要求上下文接近上限时先落盘提交推送，再创建新聊天接续，旧聊天停止写入。该许可不需要重复取得。

## 当前目标与提交

- 交付docs/foundation-release.md可运行基础版，四流程及B-01至B-14；长期扩展按foundation-backlog.md等用户启动。74SO、32原验收、7长期E2E全部保留，不能把计划写成实现。
- main **b1f3d751fdc87a798a72245bdb9cfc7b5d8f94a1** 已正常推送，16文件。仅业务增量为outbound.py将分支count从异常数改成检查记录数；相关全过程测试加入一条正常已履约订单。其余模型/四流程/前端/迁移与d5fe67f相同。
- 新[CI37956738913](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37956738913)于00:06为In progress，继续时先查最终结果，失败先修。基线[d5fe67f CI37954208866](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37954208866)已核实Success，verify10分17秒/总10分20秒。
- 本轮定向152 passed/68.38秒：test_outbound、test_dashscope_model、test_analysis_model、test_listing_model、test_support_model、test_operations_model。Ruff规则/223文件格式、mypy158 app文件通过。测试仅3308库，关闭真实模型/邮件/调度；无迁移，head7e7851694067。
- 继承业务基线完整后端685 passed/301.69秒；G-04初始化4项/1.01秒通过。Vue97单元、lint/type-check/构建通过；浏览器完整58项为54通过/4断言失败，修正断言后定向4项/46.8秒通过，不写成本地单次58全绿。前端本轮未改。

## G-05已完成，不重复付费验收

- 2026-10-09 23:54至23:56，已有北京百炼dashscope_chat/qwen3.7-flash，生产Agent API→受控服务→生产adapter。同组G-04合成资料在独立库新店#2导入。7次真实请求：今日运营；问数规划+解释2次；Listing；FAQ；物流退款混合；缺政策且未核验订单身份。
- 本轮授权人民币1元累计封顶。已执行**7次**，usage已知目录估算**0.0007750 CNY**，未知费用0；应用保守预算费用**0.000933 USD**，reserved0。7次最高档包络预留总和0.0830340元，均未超界，无重试。目录估算剩余0.9992250元；实际扣款以供应商账单为准。旧0.01元许可独立已用。
- 官方费率已复核：北京输入≤32K输入0.2/输出0.8元每百万tokens；最高档1.2/4.8。现有本机配置USD费率0.24/0.96，说明为最高档乘固定1CNY=0.20USD预算折算，非实时汇率。不能把USD预算数字当人民币扣款。
- 真实结果：9运营分支/5候选，审批检查#3/待办#7至#11，5项完成→重开→完成；问数75/62/13，CUP55/54/1，分析#2待办#1完成重开完成；完整商品名/不锈钢350mL Listing模型版本#2，人工标题整理版本#3批准本地；FAQ草稿#2人工编辑仍draft；混合物流+退款draft#3为human_review后存档，均not_submitted。
- 缺证据真实候选#7为handoff、无臆造政策/物流/退款。经导入修订FAQ消息后旧候选source_status=stale，按当前version审批HTTP409，客服记录仍2份。商品CUP成本18改19，原已完成分析保留13且stale，当前重算10；Listing批准指针和历史保留并明确stale。新本地operation_run #4来源current，可用于后续R2。
- 成功的5个执行重放相同request_id和advance仍原id/succeeded，付费数保持7。停付费API后用全关闭配置实际重启，原会话与6个执行+旧分析+旧Listing+当前检查共9份快照精确一致。
- 完整逐次token/时间/费用/审阅事实在docs/foundation-model-evidence.md，B-02至B-06通过。G-05不需要重复跑或再建新付费执行。

## G-06/B-07当前阻塞与准备

- 尚缺本人Resend发送配置、已验证的本人测试收件箱及本次单次发送许可。已向用户询问准备情况，当前未收到新增配置或许可。模型额度不覆盖邮件。
- 已准备docs/foundation-mail-review.md全文，来自**3309独立库店铺#2的operation_run #4**；不能用overview_report当R2输入。该文件只是本地审阅稿，通道not_configured，验证码/经营摘要均0发送、外发记录0。
- 实际R2创建要求active通道。本人配置在本机忽略backend/.env，包含API_KEY、SENDER、TEST_RECIPIENT、DOMAIN_ID、OWNER_ID、SHOP_ID。连接动作会发验证码邮件，必须取得对应许可；15分钟验证码验证后，再展示确切地址/全文并取得摘要单次发送许可。不得把密钥打印或放聊天。
- 使用同库#2与会话核对owner，不沿用其他库编号。文档正文可能因源/库存时效变化需重新检查生成，再全文审阅批准。最终保留真实提交回执与本人实际收件佐证；unknown只回查不重发。用户未提供条件前不标基础版全部完成、不把长期模块作为替代工作。
- 使用配置步骤已补foundation-user-guide。当前邮件正文标签已修为检查记录数，区分读取量与候选数。

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
- docs/development37、testing32、interview、README、矩阵、foundation证据/维护已同步。context-memory独立分支只存本文重点，不合并main，不提交完整聊天/本机日志。
- 接续先读AGENTS.md与foundation-release/acceptance/backlog、runtime/model evidence。项目ID1c274a7b-2f1e-45ca-bf1b-10475766545b，换聊天用local同项目，单开发聊天独占。
