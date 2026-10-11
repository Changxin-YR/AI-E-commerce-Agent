# 鸿蒙完整R2 · 集中验证记录

更新：2026-10-11。阶段：静态、单元、定向后端、CSV一致性与HAP编译。API22业务旅程尚未执行。机器可读摘要见 `harmony-validation.json`，功能覆盖见 `harmony-r2-coverage.md`。

| 检查 | 本次结果 | 证据 |
|---|---|---|
| Dart analyze | 无问题 | `.local/mobile-business/analyze-final.txt` |
| Flutter test --no-pub | 17 passed | `.local/mobile-business/flutter-final.txt` |
| Python/Dart CSV对照 | 12组清单、分片字节、拒绝条件一致 | `.local/mobile-business/csv-diff-3094f9cb/results.json` |
| 后端定向 | 97 passed / 64.18秒 | `.local/mobile-business/backend-final.txt` |
| 后端Ruff / mypy | 规则通过 / 180 app文件无类型问题 | 本机命令结果 |
| 迁移升级/回退/差异 | 纳入97项：Web会话保留、设备会话撤销、订单审阅存在时拒绝降级、Alembic check无差异 | test_mobile_auth / test_order_statement_reviews |
| SDK24 x64 HAP | BUILD SUCCESSFUL / 31.873秒，未签名debug | `.local/mobile-business/hap-build-final.txt` |
| API22当前业务 | 尚未运行 | 下一验证阶段 |

HAP：`apps/soloops_flutter/ohos/entry/build/default/outputs/default/entry-default-unsigned.hap`，103666758 bytes，SHA256 `32a7eb1c3ccca3207113f76d5f4c88a962b056c9dfcd95eec32f80b204f52c58`。此前M0 API22接受未签名调试安装；本次需实际安装/运行核验，不从编译结果推导设备兼容。

17项Flutter测试包括：9项金额/汇率、严格日期/IANA/DST、CSV单元；6项新版登录390×844与640×360/双倍字体/深色、费用时间反馈、返回与跨店深链、利润未知费用；2项原诊断壳布局回归。布局单测只代表覆盖的界面，全部业务页仍需设备观察。

97项后端限定 `test_mobile_auth.py`、`test_identity.py`、`test_order_statement_reviews.py`、`test_statement_reviews.py`、`test_order_reconciliation.py`。测试只连接独立合成库 `127.0.0.1:3315/soloops_harmony_r2_test`，容器 `soloops-harmony-r2-mysql`；服务未接入真实模型/邮件/平台。完整既有后端回归与移动业务旅程尚未完成。

首次Dart检查发现158项导入/括号风格提示，修复后清零；首次新增界面测试修正多滚动容器定位与输入后pump；后端测试准备修正撤销路由和SecretStr环境取值。最终结果以本页记录为准。保留Starlette/httpx弃用提示及ArkTS工具链弃用/异常处理提示，构建成功。

下一步：隔离API与合成卖家样本、模型和邮件替身 → API22安装 → 登录初始化/导入/巡检/AI B1/Listing/客服/财务/质量修订/计划外发完整旅程 → 断网和未知结果、冲突/清除/切店、系统文件保存分享、前后台/重启、横屏/深浅色/大字体。按实际失败继续修复，并更新证据。
