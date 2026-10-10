# R2 A1-3 渠道字段预设验收

日期：2026-10-10。输入为自行编写的合成字段子集。状态：Shopify当前商品预设完成，订单预设条件延期；本地完整验收与目标提交CI通过。

## 基线、范围与依据

在A1-2代码`81ee5f6b14dd8121ce61c03a3b57e76b5b18d205`的[CI38022485965](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38022485965)回读completed/success后开始。本包代码`5b420abf67ab7a4ba7faf928773876e1f7f21ce3`的[CI38023850875](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38023850875)于2026-10-10 12:33 Asia/Shanghai核实completed/success，head_sha一致，verify及全部步骤通过。

| 渠道 / 报表 | 核实日期及字段 | 处理决定 |
|---|---|---|
| Shopify商品CSV当前字段 | 2026-10-10；URL handle、Title、SKU、Price、Cost per item；[官方说明](https://help.shopify.com/en/manual/products/import-export/using-csv) | 提供字段子集候选v1，URL handle用于识别，另外4列分别映射商品名/SKU/销售单价/单位成本 |
| Shopify订单CSV | 2026-10-10；[官方说明](https://help.shopify.com/en/manual/fulfillment/managing-orders/exporting-orders)存在多行订单空字段、整单退款且未列稳定订单行ID | 条件延期，需可验证行标识及行金额依据；保留通用映射 |
| Amazon订单报告 | 2026-10-10；[官方类型及字段](https://developer-docs.amazon/sp-api/docs/report-type-values-order)中GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL为TSV | 条件延期，需该类型的金额/状态语义证据，未取得实际脱敏样本 |

候选要求类型/渠道/区分大小写的完整5列签名一致；页面展示日期、官方链接、映射与限制。应用只更新映射草稿，复用既有preview/commit/revoke。币种人工确认，空白变体名称按来源补齐；未知金额保持未知。国际售价/比较价/商品描述不由本预设自动映射。预设停用或格式不符时继续手工映射，历史数据及个人模板保持。

主要变更：`services/import_presets.py`与导入schema/output、`ImportPresets.vue`与ImportsView、前后端测试、合成CSV及说明。无新依赖、数据库迁移、平台API或模型调用。

## 样本与实际业务结果

样本：`examples/imports/shopify-products-2026-10-10-synthetic.csv`，5列/2条商品源记录。

- 首次预览2条错误：金额缺币种，第3源行缺商品名；不能直接提交。
- 两行销售/成本币种补USD，第二个变体名补`Synthetic cup large`，预览后仍须关键字段语义确认。
- 保存后SKU为SYN-S/SYN-L，单价10.0000/12.5000、单位成本3.2500/4.5000。原名称空值、人工修正和规范化结果分别回读。
- 预设停用后历史行/映射相同，人工重导预览2条相同记录；撤销原批次后2个商品投影移除。
- 未知成本保持null；未映射Description中的公式仍拒绝。旧表头、错误渠道/类型和国际售价替代基础Price时不显示已核实预设。

## 检查记录

- 后端定向：`.venv/Scripts/python.exe -m pytest tests/test_import_presets.py tests/test_imports.py -q --tb=short --maxfail=1 --basetemp=../.local/pytest-r2-a13`，48 passed / 7.84秒。
- 前端：29文件103单元通过 / 4.60秒；lint、type-check及生产build通过。新增组件验证依据链接、主动点击、停用空态与纯文本渲染。
- 静态：Ruff规则/237文件格式通过，mypy165 app文件通过。
- 完整后端：`.venv/Scripts/python.exe -m pytest -q --tb=short --maxfail=1 --basetemp=../.local/pytest-r2-a13-full`，746 passed / 292.80秒；此后业务代码未改动。
- 浏览器：`npm run test:e2e`，65 passed / 3.0分钟；使用生产构建、8001/5174测试端口。新增1440/390px两场景覆盖预设依据、错误拦截、逐行补录、语义确认、保存、价格/成本核对、刷新和撤销；原四流程、旧入口及分组导入均通过。
- 已查看`frontend/test-results/r2-presets-1440.png`及`r2-presets-390.png`：依据、字段含义、补录步骤与按钮可读，横向溢出断言通过；截图/运行产物不提交。
- 首次默认沙箱连接MySQL出现WinError10013，Vitest缓存重命名出现EPERM；获正常权限后定向与单元均通过。测试中原“通用建议必定不同于预设”的假设不成立，改为核对原建议映射及停用后的持久值，业务匹配未改动。

## 数据保护与后续

所有数据库测试串行使用已断言的`127.0.0.1:3308/soloops_test`，真实模型、邮件和调度关闭。3307开发库及3309保留验收库未启动、迁移或测试。无新迁移；代码回退后额外候选响应消失，批次映射与业务来源继续沿用原协议。

本包仅证明官方字段语义核实及合成操作路径。真实卖家原始导出尚待验证；未证实的订单预设按R2条件延期，不阻塞通过目标CI后进入A2两种成本模式。
