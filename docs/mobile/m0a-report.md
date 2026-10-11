# SoloOps R2 · M0-A 实际工程验收

核对日：2026-10-11。**三端最小目标编译均为 PASS；M0-A 整体验收仍为 BLOCKED。** 微信开发者工具启动页已实际加载，构建与静态契约已归档；当前微信主体/服务类目及完整域名规则核对仍受阻。OHOS 为未签名 HAP，设备与业务测试尚未执行。

## 1. 仓库与隔离

- 开始时本机 `main`、远端 `main`、本开发分支基线 SHA 均为 `0a49a37dcd7f1ccf0acc2c0a225bfdc8d8bee686`，已重新核对。
- 开发分支：`feat/soloops-mobile-m0a`，独立 worktree 位于原仓库 `.local/worktrees/mobile-m0a`。
- 原工作区未提交的 `docs/r2-final-special-acceptance.md`、`docs/uat/` 保留；原工作区仍在 `main`。
- 起步时重新查询的最新主分支 CI：[38058670333](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38058670333)，HEAD 为上述完整 SHA，结果 PASS。历史880/158/91数字不作为本次新跑的测试结果。
- 已读取 AGENTS、两版需求、foundation 三份文档、R2计划/进度/修复与部署门禁、功能矩阵，以及指定的后端入口/身份/中间件和 Web 路由。仓库无三端V1.2正式方案；用户提供的附件作为设计参考，执行授权仅为本次启动指令的 M0-A。
- SDK24 复核从干净提交 `ca82f9e592f8080a51c8da6dda5b897764376905` 开始；其 [分支 CI 38104616877](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38104616877) 为 PASS。
- 本次收尾起点为 `269faac6dedbaebdf413b9ff1b79cc7eb0aae715`；该 SHA 的 [CI 38105859947](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38105859947) 为 PASS。收尾时重新查询远端 main，仍为上述基线。仓库现为无空格物理目录，已修复 worktree 注册。
- 交付提交 SHA 用 `git rev-parse HEAD` 获取；此报告记录提交前事实，最终提交 SHA 和该 SHA 的分支 CI 由交付消息给出。CI 工作流只覆盖静态契约与小程序构建，不能代表 APK/HAP 的云端构建。

## 2. 实际环境与锁定版本

| 项目 | 实际值 |
|---|---|
| 系统 | Windows 11，10.0.26200.9457，x64；PowerShell |
| Python | 3.11.16，复用现有后端虚拟环境；静态 OpenAPI 不启动生命周期、不连接数据库 |
| Flutter OH | 官方 CPF `3.27.5-ohos-1.0.7`，SHA `6e545c2ce6ec9e303868dece5012d1d928890b57` |
| Dart / DevTools | 3.6.2 / 2.40.0 |
| Android | Temurin17.0.19+10，SDK35 / build-tools35.0.0，Gradle8.3，AGP8.1.0，Kotlin1.8.22 |
| OHOS 实际 | DevEco6.1.1.290，Hvigor6.24.3，OHPM6.1.2.285，SDK API24:default，构建时Node24.15.0 |
| OHOS 工程配置 | compile/target `6.1.1(24)`，compatible `5.0.0(12)`；实际SDK包6.1.1.125 |
| 小程序 | Node24.16.0 / npm11.13.0，Taro4.3.0，Vue3.5.43，TS5.9.3，Vite4.5.14 |
| 微信开发者工具 | 2.01.2510290，调试基础库3.17.4；实际启动页可见，automator 页面读取超时 |

SDK 源码从官方标签独立克隆并核对 SHA；Android/OHOS 都用该 SDK、同一 `lib/main.dart`。
引擎/HAR完整版本见 [`toolchain.lock.json`](../../apps/soloops_flutter/toolchain.lock.json)。
下载使用本机已有 `pub.flutter-io.cn` / `storage.flutter-io.cn` 镜像；锁文件记录来源及校验和。
发布说明明确 1.0.7 的引擎构建最低 API22、最低运行 API12。工程采用本机 SDK24，包内 module.json 实测 compileSdkVersion=6.1.1.125、targetAPIVersion=60101024；pack.info 的 target=24、compatible=12。此为编译与包元数据验证，最低运行版本尚未通过设备测试。

## 3. 分端结果

| 验证 | Android | OHOS | 微信小程序 |
|---|---|---|---|
| 目标编译 | PASS | PASS（未签名 HAP） | PASS |
| 端专属类型/静态检查 | PASS（Flutter analyze） | PASS（共享 Dart analyze，仅语言层） | PASS（vue-tsc） |
| IDE 项目加载 / 同步 | PASS | PASS（工程导入观察） | PASS（原生 UI 观察） |
| 模拟器运行 | NOT_TESTED | NOT_TESTED | PASS（仅 IDE 中最小启动页） |
| 真机运行 | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| 真实业务跨端一致性 | NOT_TESTED | NOT_TESTED | NOT_TESTED |

微信页面显示 `SoloOps`、`M0-A · 微信小程序最小工程`、`查看环境信息`，路由 `pages/index/index`；完整构建后执行 IDE 编译，用户报告的 `summer-compiler miss dist/ js file` 热重载错误消失。此证据是本机原生 UI 观察，不是 automator 或业务 E2E。自动化 CLI 已退出0并开启端口，但两次读取页面仍超时，自动化通道为 BLOCKED。调试使用灰度基础库3.17.4，正式稳定库/真机兼容性另验。

Android 的 JVM21 提示已选择 JVM17；命令行 APK 使用 Temurin17，IDE 使用其本机 JBR17.0.14。IDE 原全局 Gradle cache 缺失 metadata.bin，现将 Android Studio 的 Gradle 用户主目录切换到本任务独立缓存；IDE 显示 BUILD SUCCESSFUL，日志确认同步结束。该设置保存在本机 IDE 配置，原全局缓存保留。OHOS 项目已在 DevEco 实际显示 AppScope、entry 与构建配置。用户打开的窗口保留12:19的安装/启动成功日志，设备选择显示API22；本轮未操作安装/运行，未验证模拟器上的页面与交互，正式设备验收仍为 NOT_TESTED。编译 SDK24 与所选模拟器 API 应分别记录。

Flutter 既有1项宿主 widget test PASS（启动页→环境信息→返回），不证明 Android/OHOS 设备运行。Taro 仅启动页和本地环境信息按钮，无业务接口调用。

## 4. 实际命令、退出码和日志

最新清单：[`m0a-closeout-evidence.json`](m0a-closeout-evidence.json)。命令 argv、工作目录、UTC 时间、退出码、日志及产物 SHA256 均来自实际执行；导出前重新校验哈希。所有下列日志位于本 worktree 的 `.local/mobile-m0a/`。

| 实际命令 | 退出码 | 状态 | 日志 |
|---|---:|---|---|
| `flutter build apk --debug --no-pub` | 0 | PASS | `20261011T042407Z-closeout-android-apk.log` |
| `hvigorw.bat assembleHap`（完整参数见下） | 0 | PASS | `20261011T042620Z-closeout-ohos-unsigned.log` |
| `npm run type-check` | 0 | PASS | `20261011T042732Z-closeout-weapp-types.log` |
| `npm run build:weapp` | 0 | PASS | `20261011T042743Z-closeout-weapp-build.log` |
| `cli.bat auto --project <weapp> --auto-port 9420` | 0 | PASS | `20261011T042406Z-closeout-weapp-auto.log` |
| `node scripts/mobile/check_weapp_load.cjs`（两次） | 1 | BLOCKED | `20261011T042438Z-closeout-weapp-load.log`、`20261011T044513Z-closeout-weapp-page.log` |
| `python scripts/validate_ui_contract.py` | 0 | PASS | `20261011T044838Z-closeout-ui-contract.log` |
| `python -m unittest discover -s scripts/mobile/tests -v` | 0 | PASS（15项） | `20261011T044828Z-closeout-tools-tests.log` |
| `python -m ruff check --config backend/pyproject.toml scripts/mobile scripts/validate_ui_contract.py` | 0 | PASS | `20261011T044840Z-closeout-python-lint.log` |
| `python -m ruff format --check --config backend/pyproject.toml scripts/mobile scripts/validate_ui_contract.py` | 0 | PASS | `20261011T044841Z-closeout-python-format.log` |

Android 与 OHOS 使用同一锁定 Flutter OH SDK / Dart 页面。Android 在 `apps/soloops_flutter` 构建，采用 `.local/gradle` 独立缓存；npm 在 `apps/soloops_weapp` 执行。本次 OHOS 直接在无空格仓库的 `apps/soloops_flutter/ohos` 构建，实际完整命令：

```powershell
$packageConfig = (Resolve-Path ../.dart_tool/package_config.json).Path
hvigorw.bat assembleHap -p product=default -p buildMode=debug --no-daemon -p FLUTTER_TARGET=lib/main.dart -p TARGET_PLATFORM=ohos-arm64 -p DART_OBFUSCATION=false -p TRACK_WIDGET_CREATION=true -p TREE_SHAKE_ICONS=false -p "PACKAGE_CONFIG=$packageConfig"
```

环境变量与 SDK 准备见 [Flutter README](../../apps/soloops_flutter/README.md)。证据 JSON 中路径相对仓库根目录；复现 Hvigor 时应如上解析 PACKAGE_CONFIG 的绝对路径。

历史清单保留：[初始构建](m0a-evidence.json)、[API22复核](m0a-sdk22-evidence.json)、[SDK24复核](m0a-sdk24-evidence.json)。其中 `flutter analyze --no-pub`、`flutter test --no-pub` 均退出0；`flutter build hap --debug --no-pub` 因签名检查退出1、BLOCKED；`npm audit --json` 退出1、FAIL。当前未改 Dart 页面或依赖锁，不把历史检查伪报为本次新跑结果。

原始日志及截图在本机忽略目录；提交可复核路径、摘要与哈希。原生 UI 观察单独见 [`m0a-ide-evidence.json`](m0a-ide-evidence.json)，不附造假的命令退出码。

## 5. 当前编译产物

- APK：`apps/soloops_flutter/build/app/outputs/flutter-apk/app-debug.apk`，86,743,929 bytes。
  SHA256：`050e3a3fb8efd78a39a0fb86861c147ae6c8e3020b6c949c93f6533b66ec29d2`。
- HAP：`apps/soloops_flutter/ohos/entry/build/default/outputs/default/entry-default-unsigned.hap`，93,929,716 bytes。
  SHA256：`57bed61d412a61804c9ac901a9b1b8bc22858da199d889fc30cd28a0af3b0867`。
  本次使用 Hvigor 原生输出路径；历史快照脚本的 `build/ohos/hap/` 包和旧 zip 不作为本次产物。
- 小程序：`apps/soloops_weapp/dist/`，15个实际文件，各文件哈希见最新清单；包括 app.js/app.json、页面 JS/JSON/WXML 和 Taro runtime。构建目录含本机导入配置，保留本机；分支 CI 从占位配置独立生成 `soloops-weapp-dist` artifact。

## 6. 插件、资质与契约

- [插件矩阵](plugin-matrix.md)：网络、Cookie/Bearer、存储、文件选择、读取上传、剪贴板、下载分享、缓存、导航和生命周期均有版本/来源/实测/替代项。OH 文件选择旧候选版本约束 FAIL，OH 凭据存储候选静态安全审查 FAIL；未经设备验证的能力 NOT_TESTED。
- [微信资质](weapp-compliance.md)：备案原则、接入商区域要求、request/uploadFile 域名配置入口取得官方依据；现行主体与类目、完整 HTTPS/域名细则仍 BLOCKED。已有本机 AppID，主体类型和后台资质 NOT_TESTED；未推断个人主体必然可或不可发布。
- [UI契约](ui-contract.md) / `contracts/ui-contract.json`：首页、待办、AI、客服、我的五入口；21功能（19业务路由+登录+B1）、149现有 API 引用。校验结构、ID唯一、路由覆盖、静态 OpenAPI 字段/动作、写入门禁和风险语义。
- `not_submitted` 不表示外部发布，`seller_reported` 不等于渠道确认，`stale` 要求重核来源；候选不等于执行、审批不等于外部成功；B1 保留两处独立审批。Flutter/Taro 业务实现 NOT_TESTED；12项契约变异测试属于静态检查。
- [依赖与许可证](dependency-review.md)：许可证静态检查 PASS；npm 安全审计 FAIL（1 low、12 moderate、25 high、4 critical 依赖节点），生产发布 BLOCKED。当前依赖锁未变。

## 7. 问题和恢复步骤

| 项目 | 状态 | 结果 / 可执行下一步 |
|---|---|---|
| 同源 Dart 的 APK / SDK24 未签名 HAP | PASS | 实际重新编译，日志和哈希已归档 |
| OHPM / Hvigor 路径 | PASS | 无空格物理仓库中直接构建成功；SDK自动迁移的两份配置归位 rawfile，内容不变 |
| Android IDE 同步 | PASS | JBR17.0.14 与独立 Gradle 用户缓存配置生效，界面 BUILD SUCCESSFUL，日志确认同步完成 |
| 微信 IDE 启动页与热重载报错 | PASS | 等待完整 dist 后执行 IDE 完整编译，页面显示且缺文件错误消失 |
| 微信 automator 通道 | BLOCKED | 连接/页面读取55秒超时；原生 UI 启动证据独立有效。后续检查工具和自动化协议兼容性 |
| Flutter包装命令签名检查 | BLOCKED | 按后续运行目标核对调试签名、架构和 API；未签名构建已 PASS，现有 IDE 启动日志不替代设备验收 |
| Taro 安全审计 | FAIL | 后续评估兼容修复版及漏洞可达性；接真实业务/发布前处理 |
| 官方当前微信规则及账号材料 | BLOCKED | 官方完整类目/网络文档读取受限；需允许渠道与账号后台确认主体、类目、HTTPS/域名细则 |
| 移动设备 / 插件 / 真实业务行为 | NOT_TESTED | 后续获授权阶段以合成资料逐端验收 |

## 8. 准入判断

本次交付两个工程、三个端目录，Android/OHOS 共用 Dart；新增工程、工具、契约与文档，原后端/Web 业务代码、迁移、身份审批与 R2 计算逻辑无变更。74个SO、32项原验收和47项长期模块范围保持。

- Android：编译前置 PASS；可在新指令下安排 M0-B 合成资料设备验证。
- OHOS：未签名编译前置 PASS；M0-B 需要本机调试签名及设备运行验证。
- 微信小程序：编译和 IDE 最小启动页 PASS；后续补稳定基础库/真机、主体类目、域名和依赖安全条件。
- M0-A 整体放行：BLOCKED（资质核对未闭合）；生产发布：BLOCKED。技术构建通过支持分端建议，不等于后续阶段已授权。本轮停止在 M0-A。
