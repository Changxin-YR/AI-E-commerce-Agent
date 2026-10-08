# SoloOps 重点上下文

本分支只存稳定要求、当前状态和下一步。业务代码在 main，勿将 context-memory 合并到 main。更新：2026-10-08。

## 用户要求和授权

- 完整按 docs/requirements/SoloOps-V1.0.md 逐步实现，先 P0 23 个最小模块/四条 MVP，通过适用 A-01—A-32 后继续 P1/P2。74 个 SO、32 个验收项不得删减，不将计划当实现。
- 简体中文；Vue 3 + TypeScript、FastAPI/Python、MySQL；接口→业务服务→repository 三层，小函数和有意义的组件，克制使用框架。Agent 只能调用受控业务服务。
- 每个功能前查 GitHub/官方资料，记录来源、许可证与适配；完成后对应测试、更新文档、提交推送。用户已授权 main 和 context-memory 推送，禁止强推。
- 用户已授权上下文压力时创建新本地项目聊天继续，先推送并保存重点；避免两个聊天同时修改工作区。
- 需用户决定的事项累积在 docs/questions.md；账号授权、真实事实、模型预算不得由模型代用户确认。无模型凭据不宣称真实 LLM Agent 已验证，无外部授权不执行真实买家消息或平台写入。

## 当前提交和环境

- 仓库：https://github.com/Changxin-YR/AI-E-commerce-Agent.git
- 工作目录：C:\Users\27363\Desktop\AI E-commerce Agent；本分支工作树 .context-memory 已忽略。
- main 最新功能提交：f0ea3428350a989683190b9f0fe437119688ff74，已推送。主题：可追溯 CSV/Excel 商品与订单导入。
- main 当前 HEAD：138f09c（补充 CI 成功证据），已推送，工作区干净。
- 前一基础迭代 acbceb8、文档 57dfe05；基础迭代 CI 成功。本次功能提交 CI：https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37794268422 ，已确认 completed / success，Ubuntu / MySQL 全部通过。
- backend/.venv 是 Python 3.11；frontend/node_modules 已安装。Docker MySQL 8.4：业务 localhost:3307，隔离测试 localhost:3308。
- 密钥配置在被忽略的 .env、backend/.env、.local/test.env；不要打印或提交。
- 后端 SQLAlchemy/PyMySQL/Alembic、Pydantic、pwdlib；导入增加 openpyxl/defusedxml。锁在 backend/uv.lock、frontend/package-lock.json。
- Windows 优先 .venv/Scripts/python -m pytest/ruff/mypy/alembic，部分独立可执行 trampoline 路径有问题。网络/MySQL/Docker/Vitest 常需 require_escalated，按现有授权推进。
- pytest 与 Playwright 不得并行，都清理同一个 _test 隔离库。Playwright 启动 8001/5174；日常开发 8000/5173。
- Firecrawl 已确认 402，用 web 官方检索与 GitHub connector，勿反复尝试计费调用。

## 已交付

账号 CLI 创建/恢复、登录/退出、HttpOnly/SameSite、CSRF、过期/锁定、经营档案 version 并发保护、店铺拥有者隔离与审计。

商品/订单 CSV/XLSX 上传、CSV/Excel 模板、来源/数据身份/时区、候选映射、手动映射、个人模板、预览、逐行修正、错误 CSV、批次历史、新旧值覆盖确认、MySQL 业务投影、源行溯源、重复提交/跨文件去重、撤销和清除。examples/imports/ 全是合成数据；两种平台风格列名不是官方已验证预设。

SO-001/008/027/066/074 仅基础切片；四条 MVP 仍未完成。A-02/17/18 有合成本地证据，A-04/09/19/20/30 仅导入部分通过，见 docs 两份矩阵。

## 关键实现和约束

- api/routes/imports.py → services/imports.py → repositories/imports.py；import_parser.py 有界解析，import_validation.py 规范化，import_catalog.py 字段及别名。
- import_batches/import_rows 保存批次和每行版本；products/order_lines 是当前业务投影，source_row_id 指向来源。mapping_templates 个人拥有者隔离。
- 迁移 0776318e56e3 已应用本地两库；隔离库 upgrade→downgrade 到前一版本→upgrade/check 通过。MySQL downgrade 需按依赖删表，不能先删外键支撑索引。
- 商品键店铺+SKU，订单行键店铺+订单+行号；标识符大小写敏感。金额 Decimal/Numeric(18,4)，历史 JSON 为规范十进制字符串，时间 UTC/DATETIME(6)。
- 成交单价为折扣前单价，折扣/退款为行总额。未知费用和成本为 null，不补零。枚举状态 paid/pending/cancelled/refunded/partially_refunded/test；缺状态拒绝，取消/待支付/测试提示不计入已支付销售。
- 上传只建草稿；预览保存映射、原值、修正、差异和店铺数据版本。所有行有效才能整批确认，覆盖需明确勾选。每批确认幂等。
- 用户行锁串行化提交，关键查询使用当前读，防止认证阶段的 MySQL RR 快照读旧数据。预览后 shop.data_revision 变化则 409。
- shops.data_revision 在提交/撤销时递增。ImportBatch.applied_revision 决定版本顺序。撤销从仍有效批次按业务键选择最新版本恢复，不机械恢复 previous，防止复活已撤销祖先；独立批次不受影响。
- **当前没有派生统计/任务表。下个切片必须实现来源版本失效和批次删除的派生清理，不能把 data_revision 预留称为已完成机制。**
- 草稿完整有界表格保留 24h 有效期，过期不可提交、后续导入访问时清理；确认立即丢弃未映射列。清除删源行/修正/旧值快照/文件名，只留状态、计数/版本与必要审计。留存期限仍在 questions.md 待确认。
- 限制 2 MiB / 2000 行 / 64 列 / 单元格 2000 字符；XLSX 单表、ZIP 解压 16 MiB / 256 项；拒宏、公式、外链、嵌入对象和实体扩展。错误 CSV 防公式注入；Vue 转义展示不可信文本。
- 前端入口 ImportsView.vue，映射/明细拆为 ImportMapping.vue、ImportRows.vue。沿用现有绿色工作台样式。

## 验证

- pytest 59 项通过（原 19 + 本轮 40），包含真实 MySQL 并发重放仅一次、中途失败全回滚、乱序撤销、独立批次、Decimal/微秒、隔离、ZIP/XML/公式/时间/状态等。
- Ruff 格式/规则通过，mypy 36 个 app 文件通过。
- Vue lint/build/type-check 通过；Vitest 3 文件/5 项；Playwright Chromium 5 项通过。
- 桌面和 390×844 手机截图实际查看，手机无水平溢出；截图/trace 被忽略未提交。
- 两库 upgrade/check 无漂移；隔离库回退/再升级通过。Starlette httpx 弃用提示仍有，不影响测试。
- 所有验证是合成数据，真实用户文件、平台权限、模型与外发待验证。

## 下一步立即开发

从 **MVP-04 确定性已知毛利与受控经营问数** 开始实际编码，先官方资料→references→前后端/迁移/测试→docs→提交推送。

1. 按拥有者、店铺、显式时间窗、币种、数据身份约束读取有效订单行。明确取消、退款、待支付、测试的处理；退款不等于可恢复库存/采购成本，缺退货数量不能假定。
2. Decimal 计算销量、销售额、已知成本/毛利。缺折扣/退款/成本或币种不一致必须标明缺口，不能精确净利润或误导性完整排行。当前商品采购成本用于历史订单时明确成本口径和时效。
3. 界面展示筛选范围、公式、行命中、费用缺失、批次与源行链接。保存分析/待办时记录来源 revision，导入变化即失效或重算，清除批次时清理依赖内容并保护独立结果。
4. 受控问数仅声明的意图/技能与只读 repository，不让模型任意 SQL。供应商/凭据/预算仍待用户，模型适配器和测试替身状态必须如实标记。
5. 然后 Listing MVP-02、客服 MVP-03、今日运营 MVP-01，继续全部 P0 适用验收，再 P1/P2。每个小功能完成即推送，不只给计划。

持续维护 docs/development.md、interview-guide.md、references.md、feature-matrix.md、acceptance-matrix.md、testing.md、questions.md。完整需求原文不修改，不保存完整聊天。

