# SoloOps R2 · M0-A 实际工程验收

核对日：2026-10-11。**M0-A 整体验收：BLOCKED。** 已交付可独立复核的 Android、小程序最小构建和静态契约；OHOS 工具链、小程序开发工具加载与部分资质核对仍受阻。本报告不表示三端整体完成。

## 1. 仓库与隔离

- 开始时本机 `main`、远端 `main`、本开发分支基线 SHA 均为 `0a49a37dcd7f1ccf0acc2c0a225bfdc8d8bee686`，已重新核对。
- 开发分支：`feat/soloops-mobile-m0a`，独立 worktree 位于原仓库 `.local/worktrees/mobile-m0a`。
- 原工作区未提交的 `docs/r2-final-special-acceptance.md`、`docs/uat/` 保留；原工作区仍在 `main`。
- 起步时重新查询的最新主分支 CI：[38058670333](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38058670333)，HEAD 为上述完整 SHA，结果 PASS。历史880/158/91数字不作为本次新跑的测试结果。
- 已读取 AGENTS、两版需求、foundation 三份文档、R2计划/进度/修复与部署门禁、功能矩阵，以及指定的后端入口/身份/中间件和 Web 路由。仓库无三端V1.2正式方案；用户提供的附件作为设计参考，执行授权仅为本次启动指令的 M0-A。
- 交付提交 SHA 用 `git rev-parse HEAD` 获取；此报告记录提交前事实，最终提交 SHA 和该 SHA 的分支 CI 由交付消息给出。CI 工作流只覆盖静态契约与小程序构建，不能代表 APK/HAP 的云端构建。

## 2. 实际环境与锁定版本

| 项目 | 实际值 |
|---|---|
| 系统 | Windows 11，10.0.26200.9457，x64；PowerShell |
| Python | 3.11.16，复用现有后端虚拟环境；静态 OpenAPI 不启动生命周期、不连接数据库 |
| Flutter OH | 官方 CPF `3.27.4+ohos-1.0.9`，SHA `cdb95e38dbc298aae697db043c14cdf29f584636` |
| Dart / DevTools | 3.6.2 / 2.40.0 |
| Android | Temurin17.0.19+10，SDK35 / build-tools35.0.0，Gradle8.3，AGP8.1.0，Kotlin1.8.22 |
| OHOS 实际 | DevEco6.1.1.290，Hvigor6.24.3，OHPM6.1.2.285，SDK API24:default，构建时Node24.15.0 |
| OHOS 发布版要求 | DevEco / Command Line Tools26.0.0 Release，compile/target SDK26.0.0，compatible5.0.5(17) |
| 小程序 | Node24.16.0 / npm11.13.0，Taro4.3.0，Vue3.5.43，TS5.9.3，Vite4.5.14 |
| 微信开发者工具 | 已安装2.01.2510290；CLI实际尝试加载返回缓存错误 |

SDK 源码从官方标签独立克隆并核对 SHA；Android/OHOS 都用该 SDK、同一 `lib/main.dart`。
引擎/HAR完整版本见 [`toolchain.lock.json`](../../apps/soloops_flutter/toolchain.lock.json)。
下载使用本机已有 `pub.flutter-io.cn` / `storage.flutter-io.cn` 镜像；锁文件记录来源及校验和。
doctor 退出码0仍提示许可证及自定义分支信息，且其 OHOS 检测没有识别 SDK26 配套问题，不能据 doctor 绿项宣称 HAP 成功。

## 3. 分端结果

| 验证 | Android | OHOS | 微信小程序 |
|---|---|---|---|
| 目标编译 | PASS | BLOCKED | PASS |
| 端专属类型/静态检查 | PASS（Flutter analyze） | PASS（共享 Dart analyze，仅语言层） | PASS（vue-tsc） |
| IDE 项目加载 | NOT_TESTED | NOT_TESTED | FAIL |
| 模拟器运行 | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| 真机运行 | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| 真实业务跨端一致性 | NOT_TESTED | NOT_TESTED | NOT_TESTED |

Flutter 另有 **1 项宿主 widget test PASS**：启动页→环境信息→返回。它不证明 Android/OHOS 设备运行。
Taro 仅启动页和本地环境信息折叠按钮，没有伪造业务测试。

## 4. 实际命令、退出码和日志

下表路径相对独立 worktree 根目录。`flutter` 均指 `.local/toolchains/flutter-oh/bin/flutter.bat`；
Flutter 命令在 `apps/soloops_flutter` 执行，npm 命令在 `apps/soloops_weapp` 执行，Python 命令在根目录执行。
完整 argv、UTC起止时间、所有日志和产物的 SHA256 均见 [`m0a-evidence.json`](m0a-evidence.json)。

| 实际命令 | 退出码 | 验收 | 日志 `.local/mobile-m0a/` 下文件 |
|---|---:|---|---|
| `flutter build apk --debug --no-pub` | 0 | PASS | `20261011T013254Z-android-final-apk.log` |
| `flutter build hap --debug --no-pub` | 1 | BLOCKED | `20261011T012758Z-ohos-hap.log` |
| `flutter analyze --no-pub` | 0 | PASS | `20261011T012942Z-flutter-analyze.log` |
| `flutter test --no-pub` | 0 | PASS | `20261011T013008Z-flutter-widget-test.log` |
| `npm run type-check` | 0 | PASS | `20261011T013154Z-weapp-final-type-check.log` |
| `npm run build:weapp` | 0 | PASS | `20261011T013200Z-weapp-final-build.log` |
| `npm audit --json` | 1 | FAIL | `20261011T013220Z-weapp-final-audit.log` |
| 微信官方 `cli.bat open --project <本工程>` | 0 | FAIL | `20261011T013244Z-weapp-devtools-open.log` |
| `python scripts/validate_ui_contract.py` | 0 | PASS | `20261011T014203Z-ui-contract.log` |
| `python -m unittest discover -s scripts/mobile/tests -v` | 0 | PASS，12项 | `20261011T014206Z-ui-contract-tests.log` |
| `python -m ruff check --config backend/pyproject.toml scripts/mobile scripts/validate_ui_contract.py` | 0 | PASS | `20261011T014202Z-python-lint.log` |
| `python -m ruff format --check --config backend/pyproject.toml scripts/mobile scripts/validate_ui_contract.py` | 0 | PASS | `20261011T014203Z-python-format.log` |

编译和检查经 `scripts/mobile/run_evidence.py` 记录实际退出码。原始开发日志按仓库约定留在本机忽略目录；提交可复核的相对路径、命令与哈希，不提交本机配置。`export_evidence.py` 导出前重新核对日志与产物哈希；验收状态由实际语义决定，不按退出码机械判定。

## 5. 产物

- APK：`apps/soloops_flutter/build/app/outputs/flutter-apk/app-debug.apk`，86,763,598 bytes。
  SHA256：`8705feac7d87f53a9926b4e50e8ad9b0a6ce1ffd914c33c9ade3edbbab0f1aa8`。
- 小程序：`apps/soloops_weapp/dist/`，15个实际文件，逐文件哈希在证据 JSON；含 `app.js/app.json`、页面 JS/JSON/WXML、Taro runtime。
- 小程序本地打包：`.local/mobile-m0a/soloops-weapp-dist.zip`，69,161 bytes。
  SHA256：`9e8b9b110827f77339e73783f12225adfdd46a139e4ee3ecb300126d8581bbf0`。
- HAP：没有生成。预期目录 `apps/soloops_flutter/ohos/entry/build/default/outputs/default/` 不作为成功产物。
- GitHub 分支 CI 会独立生成 `soloops-weapp-dist` artifact；云端压缩包和本地 zip 不要求字节相同。

## 6. 插件、资质与契约

- [`plugin-matrix.md`](plugin-matrix.md)：逐项核对网络、Cookie/Bearer请求、存储、选文件、读取上传、剪贴板、下载分享、缓存、导航、生命周期；版本、固定提交、来源声明、实测结果和 ArkTS 替代方向分别记录。旧 OH 文件选择版本约束 FAIL，OH 凭据存储候选静态安全审查 FAIL；其余未经设备验证的能力为 NOT_TESTED。
- [`weapp-compliance.md`](weapp-compliance.md)：已核实备案原则及接入商区域要求；微信现行主体/类目、域名细则因官方页读取受阻，状态 BLOCKED，账号后台资质为 NOT_TESTED。未断言个人主体必然可或不可发布。
- [`ui-contract.md`](ui-contract.md)、`contracts/ui-contract.json`：五入口：首页、待办、AI、客服、我的；21个功能映射（19业务路由+登录+B1）、149个现有 API 引用。静态校验结构、ID唯一、路由覆盖、真实 OpenAPI 请求/展示字段、动作枚举、写入门禁和核心风险语义。
- 契约明确 `not_submitted`、`seller_reported`、`stale`、候选、审批及外部成功之间的区别，保留 B1 两个独立审批节点。Flutter/Taro业务实现状态均 NOT_TESTED，业务路由留空。12项校验器变异测试不称为跨端业务测试。
- [`dependency-review.md`](dependency-review.md)：兼容补丁已更新并重编译；npm审计仍 FAIL（1 low、12 moderate、25 high、4 critical）。许可证静态检查 PASS，生产发布条件 BLOCKED。

## 7. 问题与可执行恢复步骤

| 问题 | 状态 | 处理 / 下一步 |
|---|---|---|
| 原全局 Gradle cache 缺失 scripts metadata，首次 APK 构建失败 | PASS | 本任务改用独立 `.local/gradle`，最终命令成功并生成实际 APK；保留首次失败原日志 |
| Windows SDK clone 长路径 | PASS | 仅对任务 SDK clone 配置 `core.longpaths` 并恢复该新克隆的缺失模板；固定 SDK 工作区已核对干净 |
| HAP Hvigor `00306042 Specification Limit Violation` | BLOCKED | 旧工具不能识别发行版 `targetSdkVersion: "26.0.0"`。准备配套 DevEco/CLI及SDK26，显式 `compileSdkVersion`/`targetSdkVersion`26后用同一 Dart 重跑；不把降低版本号当兼容证明。后续再处理必要的本地签名条件 |
| 微信 IDE cache `EEXIST` / code10 | FAIL | CLI进程虽退出0，正文明确 openProject 失败；未宣称加载成功。开发者确认没有需保留的 IDE 工作后处理工具缓存/重启，再加载本工程；本次未清理用户全局缓存 |
| Taro依赖安全审计 | FAIL | 详见依赖审查，后续验证修复版或定向补丁，不强制跨大版本替换 peer 依赖 |
| 官方微信当前规则读取 | BLOCKED | 当前工具站点策略阻止文档读取；后续由允许的官方渠道及账号后台确认类目、主体和域名配置 |
| 设备/网络业务/权限与插件实际行为 | NOT_TESTED | 由后续获授权阶段使用合成数据验证；当前编译和静态检查不能替代 |

## 8. 交付范围及下一阶段准入

本阶段新增两个客户端工程、三个端目录、固定工具链/依赖、契约及定向 CI；未改 `backend/` 或 `frontend/` 业务代码，数据库迁移/数据、身份审批机制和原 R2 计算逻辑均无变更。
原74个SO、32项验收与47个长期模块范围保留。此次工程成果不计作五大移动业务页面实现。

- Android：编译前置 PASS，可在新指令下申请 M0-B 合成数据设备验证；凭据存储/插件能力仍须单独验收。
- 微信小程序：编译前置 PASS；先修复 IDE 项目加载并处理后续所需安全/账号前置条件，再安排 M0-B。
- OHOS：BLOCKED，先配套 SDK26 并补 M0-A HAP 编译证据；不阻止其他端未来分端推进。
- 全端 M0-A 整体放行：BLOCKED。生产发布：BLOCKED。本轮止于 M0-A，未进入 M0-B、M1、M2、M3 或 M4。
