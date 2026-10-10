# R2 缺陷修复与体验收敛接续

2026-10-10 19:15 Asia/Shanghai。主目录 C:/Users/27363/Desktop/AI E-commerce Agent，项目「电商智能体」。用户已授权按四包连续实施，具体范围 docs/r2-fix-scope.md、状态 docs/r2-fix-progress.md。包1完成；从包2开始。仅一个开发聊天写入，无子代理授权。

## 当前提交与证据

- main `adada50154d8dbc5e814961406747c0592120098` 已推送，仅补 AGENTS/范围/证据文档。业务代码 `90cc92903f4d7828e1857ac6d84bf436fbbaa321` 的 CI38046803979 / job114197876427 已核实相同SHA、completed/success，880后端/412.59秒、128前端、78浏览器/4.2分钟、Ruff258/mypy176及前端静态构建通过。
- P2-01：repositories/margin_sources.py 共用只读 EXISTS 来源谓词。首页首次读取识别 B1 所依赖 Listing 变化；列表/计数/分页/最近执行一致，GET不写业务状态。详情/审批继续按原锁和门禁检查。无关 Listing、无 Listing 依赖成本分支不误阻断。10新增后端用例及原1440/390 B1测试已验证。无迁移，head d93f6b210ac4。
- 本地125后端/90.25秒、8前端单元、7关键浏览器/28.5秒及静态通过。读 docs/r2-fix-p2-01.md，日志与证据在 .local/r2-fixes/。p2-readback.json另进程回读：桌面shop283/run260/analysis21/todo21/listing177，手机shop284/run261/analysis22/todo22/listing180；均7步双结果not_submitted。Listing批准后DB任务source仍current，首页派生stale/update_data=1，证明GET无写入。
- 工作区仅原未跟踪 docs/r2-final-special-acceptance.md、docs/uat/；完整保留，不删除。第二份报告原题“真实卖家使用验收”实际是Codex合成/自动化模拟，无真人；最终整理准确命名。
- `.context-memory/README.md` 是用户 MM（暂存及工作区均改），本轮不碰、不提交、不回滚。上下文只提交 R2-fixes.md；旧README/R2.md为历史，当前范围以此和主文档为准。

## 剩余工作（严格顺序）

包2 UAT-03/04：日期/时间选择、时区回显、7/30天快捷、保留高级精确ISO与UTC/IANA和[start,end)；DST歧义/不存在时间明确拒绝。Agent合法URL+任务记录恢复店铺/身份/渠道/对象；历史只读回显不继承新任务授权，重新执行仍核对范围/预算/审批，刷新不自动启动。客服保存后深链、刷新历史回读、跨店/无权/失效/撤销/清除准确提示，未保存编辑不得静默覆盖、不发送。桌面1440/手机390完整交互回归，独立提交/准确CI成功再包3。

包3 UAT-02：先提交最小方案，评估有界浏览器CSV拆分并复用import_split.py/manifest/原导入组协议。必须说明引号/转义/换行/BOM/多行、字节/行数/SHA256一致、内存/取消/中断/恢复、去重覆盖回退。少量可维护代码可安全实现则实施；复杂框架/大改需停自动拆分部分、记录风险并询问用户。无论拆分结论均改善超限、可执行下一步、进度/失败、对账及40000导入vs10000/1000分析限制提示。保留2MiB/2000单片/危险文件保护；合成测2001/10001行、跨片重复、失败继续、取消/整组撤销、退款/币种/日期/恶意格、重导不累加/完整性来源。独立提交/CI。

包4 UAT-01：默认管理员预部署，卖家得账号后网页经营。保留管理员CLI建号，最小完善登录账号获取、建店、首次导入引导。公开注册/用户管理需单独安全设计+确认。核心业务无需卖家命令行/DB/API。独立提交/CI。

最后四MVP+B1预算/断点/审批全回归；Ruff/mypy/pytest/ESLint/TS/build/Vitest/Playwright/准确最终CI。输出《SoloOps R2 基础版缺陷修复与用户体验收敛报告》，含P2-01原失败复验、UAT01–04分类处理状态、退化判断、B1受控写入、测试/CI/最终SHA、迁移回退、真实样本/真人/公网待验。全部完成停止。真人UAT不是本轮交付阻塞。

## 安全环境与执行提示

- 本轮新Docker项目soloops-r2-fixes-20261010，容器soloops-r2-fixes-20261010-mysql-test-1 / hostname189d09af3aee，卷fixes-data，**127.0.0.1:3313/soloops_r2_fixes_test**。测试只用此库。保护3307/3308/3309、专项3311/3312、模拟UAT33312、用户8002/5175。
- 启动器：`backend/.venv/Scripts/python.exe .local/r2-fixes/run.py`；mode pytest/npm/python/docker。清理继承SOLOOPS变量后固定3313、模型/外发/调度false，TEMP/TMP指向任务tmp（解决Windows Vitest rename EPERM）。旧ui模式未配置，不使用。
- 例：启动器后 `pytest tests/test_margin_workbench.py -q`，`python -m ruff check app tests migrations scripts ../scripts`，`python -m mypy app`，`npm run test:unit -- ...`，`npm run test:e2e -- ...`。后端和E2E串行共享3313；E2E自行启动8001/5174，必须用npm脚本先build，reuseExistingServer=false。Node .local/runtimes/node-v24.16.0-win-x64由启动器设置PATH。
- 沙箱禁本机网络/Docker管道/.git写索引；需经工具require_escalated执行对应隔离库测试、git提交推送。已正常获批，无自动审批拒绝。不要输出真实配置/凭据，忽略目录日志不提交。git普通快进不强推。
- GitHub使用 tools.mcp__codex_apps__github_fetch({url:REST URL})，返回JSON在structuredContent.content；只打印必要字段。日志 tools.mcp__codex_apps__github_fetch_workflow_job_logs({repo_full_name:'Changxin-YR/AI-E-commerce-Agent',job_id:...}) 返回structuredContent.content文本；运行中可能404，完成后可取。不要每分钟抓完整日志。
- Firecrawl --status fetch failed，官方资料改用web且仅主来源；每功能更新docs/references.md。前端沿用现有Vue深绿纸面设计。no-negative-echo应用于提交/交接；无需新框架或大重构。74SO/32原验收/47长期功能不变。付费模型、真实邮件、平台写入本轮0且禁止，历史许可不复用。
- 原聊天「验收 SoloOps R2 基础开发」01a1254c...曾同时写入。用户已在修复聊天明确授权通知其停写，由修复聊天接续；已确认其idle且未提交。不要再启动它。
- 用户已授权接近上下文上限时创建同项目local接续聊天。项目ID1c274a7b-2f1e-45ca-bf1b-10475766545b；交接前落盘推送，旧聊天停止写。新聊天须持续做完剩余授权目标，不停在计划或要求用户再次授权常规步骤。
