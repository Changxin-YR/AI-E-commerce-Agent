# Android 开发接续入口

更新时间：2026-10-12，Asia/Shanghai。GitHub 仓库 `Changxin-YR/AI-E-commerce-Agent`，分支 `android/capacitor-m0`。
本地独立目录：`C:/Users/27363/Desktop/AI E-commerce Agent/soloops-android`。只写本副本；同级 UI、微信、鸿蒙由其他聊天维护。

## 当前进度与下一步

- A0/A1/A2/A3/A4/A5 已完成。A3 设备验收 7 项通过：导入链路 4 项（真实字节上传、2001 行两片拆分、强停恢复、指纹拒绝/跨片去重/销售额 4000.0000）与今日运营、经营问数两条 MVP；详细证据见 [A3 验收](android-a3-acceptance.md)。
- A4 设备验收 9 项通过：Listing MVP（候选 → 节点批准 → 本地生效版本 #7；另一版本 #8 拒绝）与客服 MVP（AI 候选 → 草稿 → 保存修改 → 存档 #2）、政策过期（#3 当前有效 / #4 已过期）、执行 #12 拒绝、#13 取消（保留 3 步）、#14 暂停→恢复→强停重启后批准为 `succeeded`、运营事项未保存备注保护；见 [A4 验收](android-a4-acceptance.md)。
- A5 设备验收完成：**19 个业务入口逐项真实结果（20 项模块检查）**与 **5 种显示/字号配置 41 项适配检查**全部通过（小屏 360×582、平板 1067×1556、横屏 866×364、系统字号 1.3 下标题 23→29.9px，均无横向溢出）；本机无真机，真机适配未覆盖；见 [A5 验收](android-a5-acceptance.md)。
- A3 同时修复一个真实缺陷：`accept=".csv"` 使原生选择器把 CSV 文件置灰（`typ=text/csv` 与 MediaProvider `text/comma-separated-values` 不匹配）。两个 CSV 入口改为显式多 MIME 拼写，单元 192 → 194，设备复验通过。
- 本轮 debug APK SHA256 `A1931F93F817DE710CC6CD51925741D4C340D72B3F65B9E58BADAB45B813E91D`（A4/A5 未改应用代码，APK 不变；A6 将更新 versionCode/versionName 并重建）。
- **首个动作**：先 `git fetch` 核对本轮提交与准确 SHA 的 `Verify Android foundation` CI 成功，再进入 **A6**：安装升级（同签名 `install -r` 保留会话）、签名发行构建与设备验证、APK 校验值、用户指南与部署状态。74 SO、32 验收与 47 长期模块范围保持。
- 正式签名与生产服务地址尚未确定：本机签名材料放在忽略目录 `.local/android/keystore/`，`scripts/make-release-key.ps1` 可重新生成；上架账号与正式域名仍需用户决定。
- 当前仅专属 API 34 模拟器；真机与其他尺寸归 A5，正式签名/服务地址归 A6。

## A4 收尾记录（2026-10-12）

- 设备脚本：`check-android-listing-support.mjs`（Listing/客服 MVP + 政策过期 4 项）、`check-android-agent-lifecycle.mjs`（拒绝/取消/暂停恢复/重启恢复/未保存保护 5 项）；共享 `android-device.mjs` 本轮新增 `call`/`seedImport`/`createShop`/`open` 并回归 A3 脚本（3 项通过，店铺 #19）。
- 关键回读：`listings/versions` #7 `approved` / #8 `rejected`；政策 #3 当前有效、#4 已过期；客服草稿 #2 `archived`；`agent_executions` #12 `rejected`、#13 `cancelled`（3 步保留）、#14 `ready → paused → waiting_approval → succeeded`；`operation_tasks` 备注保存成功。
- 设备操作要点：应用会按店铺恢复上次的表单模式（记录恢复），因此设备脚本必须在选完店铺/身份后再设执行流程；Listing 与客服都从业务页的入口链接进入任务台；客服页未保存正文由页面自身守卫生效（文案「正文或人工记录尚未保存…」），不弹壳层确认框。
- 真实模型、邮件与平台写入保持 0；模型仅 `listing-model-e2e-*`、`support-model-e2e-*`、`question-e2e-*` 等前缀店铺使用本地确定性替身。
- 未覆盖：执行记录没有“过期”状态（`valid_until` 只是来源有效期提示），过期以客服政策有效期验收；任务侧“请求处理中禁止离页”由单元测试覆盖（本地替身毫秒级完成，设备无法稳定复现）。

## A5 收尾记录（2026-10-12）

- 设备脚本：`check-android-modules.mjs`（19 个入口逐项结果，20/20 通过）、`check-android-adaptation.mjs`（5 种显示/字号配置 × 8 入口，41/41 通过）。证据 `.local/android/evidence/device-a5-modules.json`、`device-a5-adaptation.json`，截图 `a5-*.png`。
- 设备操作要点：店铺选择器在页面加载后才挂载，脚本按 option 的 `value`（店铺 id）轮询选择；合成来源需在选店后再切「合成测试数据」，因为换店会重置范围；部分入口的选择器是隐藏的下拉（如 `#message-identity`），脚本跳过不可见控件；有记录写入的页面可能在离页后把路由推回，脚本用 `ensureRoute` 复核；利润试算表单的「试算名称」是必填，缺它会被浏览器原生校验拦住、不会发出请求。
- 关键结果：Listing 本地模板在设备上生成版本（0→1）；库存快照命中 `A5-SKU`；利润试算结果区（售价 20 / 采购 18 / 合成依据）；商品质量检查结果区；订单金额待核清单；经营分析净销售额 `60.0000`；经营总览净销售额；费用/修订/账单/结算/规则/外发/定时入口与空状态。
- 适配：默认 412×842、小屏 360×582、平板 1067×1556、横屏 866×364、系统字号 1.3（标题 23px→29.9px）全部无横向溢出；脚本 finally 恢复 `wm size`/`wm density`/`font_scale`/`user_rotation`。
- 未覆盖：本机没有 Android 真机（厂商 ROM、刘海、手势导航、真实网络未测）；账单/结算/费用/修订在合成店铺下无来源数据，只记录入口与空状态。

## A3 收尾记录（2026-10-12）

- 设备脚本：`frontend/scripts/android-device.mjs`（共用连接/登录/导航/API/截图）、`check-android-imports.mjs`（导入链路 4 项）、`check-android-mvps.mjs`（今日运营与经营问数 3 项）。证据 `.local/android/evidence/device-imports.json`、`device-mvps.json`，截图 `a3-*.png`、`mvp-*.png`，日志 `a3-imports-run2.log`、`a3-mvps-run4.log`。
- 关键回读：导入组 #1（`active`/`complete=1`）两片 2000+1 行、去重后 2000/跨片重叠 1；今日运营 `operation_runs` #3（`current`，`source_revision` 3）产生 2 个候选，批准后 `operation_tasks` #5 `low_inventory` `open` v2（备注已存），`low_margin` #6 仍 `pending_approval`；经营问数 `agent_executions` #1 `question` `succeeded`、`model_status=test_double`、`spent_usd=0.002000`、`reserved_usd=0`。
- 真实模型、邮件与平台写入保持 0；模型仅 `question-e2e-*` 前缀店铺使用 `backend/scripts/e2e_analysis.py` 的本地确定性替身。
- 未覆盖：`ImportGroups` 的「选择原分片 CSV」仅单元验证属性；浏览器模型 E2E 本轮未启动（终端未加载 `_test` 库环境）。

## 本轮执行注意

- Windows沙箱导致Vitest临时文件rename EPERM，正常本机权限重跑192项通过。必须加载scripts/android-env.ps1后构建，否则缺少VITE_SOLOOPS_API_ORIGIN。
- 模拟器启动另将ANDROID_HOME和ANDROID_SDK_ROOT指向原有AppData/Local/Android/Sdk，构建则重新加载android-env.ps1使用副本SDK。
- gh未在PATH，GitHub匿名REST受到限流；内置网页工具可读 `https://api.github.com/repos/Changxin-YR/AI-E-commerce-Agent/actions/runs?head_sha=<完整SHA>&per_page=1`。
- 单元maxWorkers=2。设备脚本依次执行，共用 ADB 9223 端口，避免冲突。检查命令各自退出码：PowerShell 把 adb push 的 stderr 当错误记录，`node … | Tee-Object` 之后 pwsh 可能返回 1，须以脚本自身输出的 results 与退出码为准。
- 大报表入口曾被原生选择器置灰：根因是 `accept=".csv"` 与 MediaProvider 的 `text/comma-separated-values` 不匹配；排查用 `dumpsys activity activities`、`content query --uri content://media/external/file`、`uiautomator dump`。
- 模拟器网络若为 `PARTIAL_CONNECTIVITY`，壳层会显示「网络已断开」而 API 可用；干净提示需 `settings put global captive_portal_mode 0` 与 `captive_portal_detection_enabled 0` 后重开 Wi-Fi。
- 页面商店列表在应用内新建店铺后不会自动刷新；脚本先 `page.reload()` 再选择新店铺。

## 可复用本机环境

- Java `D:/Javajdk`；SDK `.local/android/sdk`；Gradle `.local/android/tools/gradle-8.14.3`；环境脚本只设置当前进程，并设置 `VITE_SOLOOPS_API_ORIGIN=http://10.0.2.2:8011`。
- AVD `.local/android/avd/SoloOps_A1.avd`，API34 / Pixel6 / x86_64 / WHPX；模拟器和镜像复用原SDK。当前后台运行，ADB5037需正常本机访问权限。
- 独立 Docker project `soloops-android-a1`，MySQL8.4，端口3311，schema `soloops_android_test`，专属卷。配置 `.local/android/mysql.env`、`.local/android/backend.env`。
- FastAPI后台监听 `127.0.0.1:8011`，启动入口 `scripts/start_android_backend.py`，模型/邮件/调度明确关闭。停止前按端口和父进程命令行核对归属，勿使用旧PID。
- 合成账号 `android_seller` / `Android-Synthetic-2026!`。本轮结束时设备处于已登录的工作台/导入页，未主动退出登录。
- 证据 `.local/android/evidence/`：`device-shell.json`（A2 壳 29 组）、`device-auth.json`（A1 认证 7 组）、`device-imports.json`（A3 导入 4 项）、`device-mvps.json`（A3 MVP 3 项），以及 `a2-*`/`a3-*`/`mvp-*` 截图与 `a3-imports-run2.log`、`a3-mvps-run4.log`；单元/构建日志 `unit-a2.log`、`sync-a3.log`、`build-a3.log`。本机文件被 Git 忽略，可用已提交脚本复现。
- 本轮安装的 APK SHA256 `A1931F93F817DE710CC6CD51925741D4C340D72B3F65B9E58BADAB45B813E91D`（`frontend/android/app/build/outputs/apk/debug/app-debug.apk`）。本轮结束时 MySQL 容器、8011 后端与专属 AVD 均在运行；如已停机，按 `docs/android-local-testing.md` 启停，停止前先核对端口与进程归属。

## 授权和协作约定

用户已授权持续开发、推送本安卓分支并运行CI；无需重复确认。仅合成数据/替身，新的真实付费模型、邮件、平台写入须另获明确授权。只允许一个开发聊天写本安卓副本。
用户授权上下文接近上限时先落盘/推送，再新建聊天接续；旧聊天从新聊天接手起停止写入。此次因切换账号提前保存检查点，新账号可从本文直接恢复。

## 本次GitHub检查点

A3 收尾提交 `eaed69ce3a517b3a8702bbd236e611597d69d809`（含此前本地未推送的 `cbba852`）已推送，[CI 38191429012](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38191429012) 全部成功（3m3s：lint、194 单元、类型检查、资源同步、Gradle `assembleDebug`、release 资源门禁）。A2 期已核对：应用代码 `b70e783` 的 CI 38141560687 Success、测试提交 `6ecbd86` 的 CI [38143266315](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38143266315) Success（2m56s）。下一聊天先 `git fetch` 核对该尖端未变（或取更新 SHA）再进入 A4。
