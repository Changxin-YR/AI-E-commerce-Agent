# 鸿蒙完整R2 · 集中验证记录

更新：2026-10-11。API22集中业务验收进行中。机器可读摘要见 `harmony-validation.json`，源码覆盖见 `harmony-r2-coverage.md`。

| 检查 | 结果 | 本机证据（.local/mobile-business/） |
|---|---|---|
| Dart analyze | 无问题 | analyze-form-fix.txt |
| Flutter test --no-pub | 21 passed | flutter-form-fix.txt |
| Python/Dart CSV对照 | 12组清单与分片字节一致 | csv-diff-3094f9cb/results.json |
| 后端全量 | 890 passed / 529.36秒 | backend-full.txt、backend-full.xml |
| 本地夹具隔离 | 5 passed | fixture-tests.txt |
| 后端Ruff / mypy | 规则通过 / 180 app文件无类型问题 | 前轮本机命令结果 |
| 迁移 | head b42e83f516c0；升级/回退/差异检查已覆盖 | 后端定向97项与全量回归 |
| SDK24 x64 HAP | BUILD SUCCESSFUL / 25.873秒 | hap-build-form-fix.txt |
| API22手机 | 安装、启动、会话恢复及部分业务通过 | device/布局与下面各项证据 |

本轮固定安装包 `.local/mobile-business/accepted-form-fix.hap`，103688494 bytes，SHA256 `94fa230e202ac1829bd207b3bc6e11ed230b44f70311a2ef1c3c874dd518f1ac`；未签名debug x64，SDK24编译/API22运行。构建源输出仍为 `apps/soloops_flutter/ohos/entry/build/default/outputs/default/entry-default-unsigned.hap`。安装前校验固定副本，避免IDE后续构建覆盖。

## 已完成的真实设备操作

- 合成账号登录、保存经营资料、创建店铺918。模拟器重启并覆盖安装后保留会话与店铺，见 `device/recovered-launch.json`。
- 系统DocumentSave保存商品CSV模板；系统选择器授权读取Download/浏览器中的本轮合成CSV/XLSX。
- 商品批次1181新增3条；相同商品XLSX批次1182相同3条、无重复新增。
- 纠错批次1183：缺少name → 编辑SyntheticFixedCup → 返回提示取消后输入保留 → 重新预览有效1/错误0 → 确认新增1。数据库回读名称和corrections一致，见 `device/correction-committed.json`、`correction-db.json`。
- 订单批次1184新增3条，覆盖带时区日期和部分退款，见 `device/orders-committed.json`。

## 端测发现与修复

1. 行修正基线采用late初始化，首次保存时才读取已修改控制器，导致差异为空。在initState捕获初始值，并按映射列读取原值；新增离开保护，2项回归覆盖取消返回、别名列和显式空修正。
2. 长表单滚出ListView视口后，内部Form被销毁导致上传无响应；外层Form的离屏字段也会注销并跳过必填校验。两种情况先以widget测试复现。PageBody对Form祖先或直接Form子项使用完整滚动布局，普通数据列表保留按需渲染；2项回归均通过，API22长距离滚动复验通过（批次1186上传）。
3. IDE后续默认构建覆盖HAP曾引起Flutter ArkTS模块ReferenceError。使用锁定构建脚本重新构建、覆盖安装后恢复；固定副本供后续安装。诊断仅存本机日志。

## 隔离环境与待验边界

测试库仅 `127.0.0.1:3315/soloops_harmony_r2_test`（容器soloops-harmony-r2-mysql，tmpfs）；API夹具 `scripts/mobile/business_fixture.py` 仅绑定 `127.0.0.1:18080` 并限制专用库。模型和邮件使用本地替身，实际模型费用、真实邮件与平台写入均为0。全量pytest会清表，不与设备业务验收并行。

后续继续库存/客服/账单导入、巡检待办复检、AI/B1双审批及暂停取消、Listing交付、客服政策审阅、分析/财务/规则/质量/定时/替身外发；补齐未知结果重试、冲突/来源清除/切店、系统分享消费时机、前后台/重启、横屏/深浅色/大字体。当前部分设备证据不代表全部业务通过；其他设备类型仍未验证。

库存1185新增3条、客服消息1186新增2条；六个批次均committed且error_rows为0，见journey-db.json。巡检184生成195–197三个候选；195完成审批、复检、完成核对，version4。复检保持等待新有效库存来源，未误标业务解决。B1执行256因商品generic与订单amazon渠道不匹配被正确阻断；移动选择范围改进与双审批仍在继续。
