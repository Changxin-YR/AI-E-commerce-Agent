# SoloOps R2 基础版缺陷修复与用户体验收敛报告

日期：2026-10-10（Asia/Shanghai）。本轮起点 ef3eaa6b8ce2b0086e733270ec2f07f9331d9573；范围见 [修复约定](r2-fix-scope.md)。最后业务提交a84ffa3e88abc66ad45df3740591a206115ade15；准确CI已核实completed/success。四个修复包及最终回归完成，本轮开发停止。

## 交付与问题处理

| 问题 | 最终处理 | 证据与边界 |
|---|---|---|
| P2-01 首页B1来源不同步 | 已修复 | 首页和详情共用依赖谓词，首次GET识别当前Listing基线改变；列表/计数/分页一致，GET不写任务、审计或结果。原失败测试保留通过，见r2-fix-p2-01.md。 |
| UAT-01 首次使用 | 交付路径与体验已改善 | 明确管理员预部署及账号交付；桌面/手机独立账号从网页建店、下载模板、映射预览、确认导入、刷新回读通过。经营档案可后补。见[r2-fix-uat-01](r2-fix-uat-01.md)。 |
| UAT-02 大文件入口 | 已修复网页流程缺口 | 浏览器CSV准备、原件核对恢复、逐片预览确认；2001/10001、跨片重复、失败重试、整组撤销已在本地通过。40MiB/40000记录/20片和每片2MiB/2000记录保持。 |
| UAT-03 日期门槛 | 输入体验已改善 | 原生日期时间、IANA时区、7/30天和高级准确表达式；DST歧义/不存在时间拒绝，保留UTC和[start,end)口径。真人易用性仍待观察。 |
| UAT-04 任务连续性 | 已修复已确认断点 | Agent/客服保存记录的URL、刷新与历史回读；新任务授权重核，未保存编辑保护，读取可离页、写入中保护，迟到结果不回写新页。 |

导入容量与分析容量差异已提前展示。经营分析/运营/总览单次10000行、部分核对1000行保持；单日超上限的完整自动汇总本轮延期。源数据可完整导入不表示可以无限范围统计。Shopify/Amazon订单预设、真实平台格式与47项长期模块按原清单保留，未列作本轮实现。

## 四条业务闭环和B1

当前本地完整91项浏览器、880项后端以及准确业务提交CI均通过。在实际覆盖的合成范围内未发现四MVP退化，以下原业务断言全部保留：

| 流程 | 关键验收内容 |
|---|---|
| MVP-01 今日运营 | 导入、5项候选、审批、完成/重开、重复检查去重；新有效来源复检与历史备注回读。人工完成只是核对，更新后仍异常保持still_anomalous。 |
| MVP-02 Listing | 有来源商品事实、模型替身/本地候选、人工编辑、版本审批、本地生效、剪贴板和CSV实际内容、旧来源失效后重新批准；external_status保持not_submitted。 |
| MVP-03 客服 | 原文、订单和有效政策、多意图/退款敏感接管、草稿编辑与历史、版本审阅、实际复制/导出、人工证据和重登回读；人工操作是seller_reported，不伪造发送回执。 |
| MVP-04 经营分析 | 同店Amazon/USD销售75.00、当前成本62.00、毛利13.00；修订后10.00，旧报告保持原值并标来源变化；历史成本凭据、异币种、退款和费用缺口保持原契约。 |
| B1 低毛利复核 | 缺成本/可信历史成本/独立参数遗漏/混合分支；两次独立批准、7个步骤、分析与Listing两个实际内部结果。拒绝第二节点保留第一结果；跨用户/店铺/R3拒绝，步骤/累计时长预算、三次只读熔断、断点恢复、幂等及来源清除。 |

独立进程证据：四流程桌面店1448、手机店1450共38份API快照。旧分析86/87为stale且原金额保留；Listing327/328和330/331已替代且来源stale，新329/332为approved/current。客服124/125为archived/current，version与reviewed_version均4；人工记录56/57为seller_reported/not_submitted。来源更新后的原低毛利事项393/399保留completed/stale和复检历史。

B1桌面shop1472/run712得到analysis88/todo68、listing344；手机shop1473/run713得到analysis89/todo69、listing347。两者succeeded、7步，两次verify均有实际record_id与not_submitted。新Listing批准后数据库任务来源仍current，首页只读派生stale/update_data=1，说明没有靠读取详情或写任务来修正首页。证据为readback-final.json/summary与final-b1-readback.json。

模型/邮件异常、预算不足及结果未知均使用原替身验证。历史基础版7次真实百炼及本人QQ两封邮件保持原证据和日期；本轮新增付费模型、真实邮件、平台写入均为0。

## 测试和准确提交

| 包 | 准确业务提交 | GitHub Actions实际结果 |
|---|---|---|
| P2-01 | 90cc92903f4d7828e1857ac6d84bf436fbbaa321 | [CI38046803979](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38046803979) success，880后端/128单元/78浏览器 |
| UAT-03/04 | 5216da4cb2728988d4c1424a155afcff70f5e5db | [CI38053971553](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38053971553) success，880后端/138单元/84浏览器 |
| UAT-02 | 69ba42a38ee95f31315c98c5f888de6a35a78e74 | [CI38055976730](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38055976730) success，880后端/158单元/89浏览器 |
| UAT-01与最终业务代码 | a84ffa3e88abc66ad45df3740591a206115ade15 | [CI38057461269](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38057461269) success，job114228754736：880后端/433.76秒、158单元/39文件、91浏览器/6.6分钟；全部静态构建通过 |

全部以完整head_sha比对，CI实际计数从对应job日志读取。包级明细：[P2-01](r2-fix-p2-01.md)、[UAT-03/04](r2-fix-uat-03-04.md)、[UAT-02](r2-fix-uat-02.md)、[UAT-01](r2-fix-uat-01.md)。起点870/128/78是历史基线，修复后最终本地为880/158/91。

命令统一通过`backend/.venv/Scripts/python.exe .local/r2-fixes/run.py`执行，日志均在.local/r2-fixes/：

| 检查 | 启动器后命令 | 实际结果/日志 |
|---|---|---|
| 完整后端 | `pytest -q` | 880 passed/455.81秒；20261010-213416-pytest-9e8a85.log |
| 后端静态 | `python -m ruff check app tests migrations scripts ../scripts`、同范围`ruff format --check`、`python -m mypy app` | 规则、258文件格式、176文件类型通过；20261010-213412-python-* |
| 前端单元 | `npm run test:unit` | 158 passed/39文件/9.25秒；20261010-215037-npm-d39545.log |
| 前端静态/构建 | `npm run lint`、`npm run type-check`、`npm run build` | 通过；20261010-215036-npm-f97246.log、20261010-214857-npm-7e1147.log、20261010-215214-npm-208556.log |
| 完整浏览器 | `npm run test:e2e` | 91 passed/6.4分钟，0重试；20261010-215325-npm-ff1418.log |
| 独立业务回读 | `python ../.local/r2-fixes/final_b1_readback.py`、`python ../.local/r2-fixes/final_readback.py final` | 两个B1结果组及38份四流程API回读通过；20261010-220026-python-83de41.log、20261010-220032-python-f024f5.log |

原失败`test_b1_inbox_reflects_changed_listing_before_opening_task`已修复：原先首页current与应有stale不符，现在首次读取即通过，并在最终880项中保留。包2首轮CI普通读取导航被拦的问题已修复并以准确5216da4完整CI复验；包3撤销等待/分阶段校验、包4折叠明细/账号准备的测试修正均保留业务断言，过程和失败日志见对应验收。沙箱Vite realpath EPERM通过原命令正常权限运行解决。原Starlette/httpx弃用及Node颜色提示保留，没有据此跳过测试。

本机只使用127.0.0.1:3313/soloops_r2_fixes_test，pytest与Playwright串行；API8001/预览5174由测试启动器管理。保护原3307/3308/3309、3311/3312、33312以及用户8002/5175。配置、原始日志及合成取证文件留忽略目录。全部本地测试和回读结束后，已停止本轮3313容器并保留持久卷与证据；日志20261010-220216-docker-0729bd.log。

## 迁移、数据与恢复

四个修复包没有新增表、迁移或第三方依赖；当前head d93f6b210ac4。应用回退不需要数据库降级，已有审批、分析、草稿和来源历史继续保存。分批导入仍使用原manifest协议，浏览器原件可由兼容Python工具重新产生分片恢复。已确认记录的撤销/覆盖仍经过版本、组外保护与事务，下载副本须由使用者管理。

原专项验收在3311源实例和3312新目标完成当前head恢复：67表COUNT/CHECKSUM一致、拒绝覆盖、临时恢复账号0、38份API快照完全相同。本轮只读核对备份SQL哈希、manifest与恢复文件67表校验相同，readback-source.json与readback-restored.json完全相同，没有重启或写入这两个实例。证据在.local/r2-final/restore-verification.json及对应快照；这属于原专项恢复证据，不能当作本轮新做的恢复或生产灾备验收。

含成本凭据、复检历史或客服人工证据的数据库受原降级门禁保护，不能强行删表/列。完整后端回归包含无记录降级/再升级、有记录拒绝及finally恢复head。实际部署升级前仍需核对目标与备份。

## 交付范围与后续条件

本轮使用合成数据、模型/通道替身及自动化浏览器。两份输入报告保持原样；“模拟卖家使用验收”没有独立真人参与。真实脱敏经营报表、独立真人任务观察和实际公网HTTPS/Cookie/入口限流/密钥日志/留存等仍需后续条件；它们不阻塞本轮约定代码交付，也没有被替身结果替代。

74项SO、32项原验收编号与本轮起点集合一致，foundation-backlog的74项及47项后续模块保持。本轮约定验收已完成，开发停止；后续按另行确认范围推进。
