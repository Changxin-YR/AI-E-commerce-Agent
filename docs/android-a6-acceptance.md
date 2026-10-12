# Android A6 验收记录

日期：2026-10-12，Asia/Shanghai。范围：安装与升级、签名发行构建与设备验证、APK 校验值、用户指南与部署状态。

**A6 完成（设备验收 3 项通过）。** 准确提交 `c7c31854ad171e0e2eb23f5069f3010356b38f84` 的 [CI 38204202976](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38204202976) 全部成功（lint、194 单元、类型检查、资源同步、Gradle debug 编译、release 资源门禁）。真实模型、邮件与平台写入保持关闭；没有向任何应用商店提交。

## 交付物

| 交付 | 位置 | 校验值 |
|---|---|---|
| 调试包（本机合成环境，`http://10.0.2.2:8011`） | `frontend/android/app/build/outputs/apk/debug/app-debug.apk` | 4,412,283 B · SHA256 `328445B8DCD9EB1EB06B39604ACEB472300BA81E777C8ED170627AC11A6D613D` |
| 发行包（已签名，构建时固定 HTTPS 服务地址） | `frontend/android/app/build/outputs/apk/release/app-release.apk` | 3,426,977 B · SHA256 `E91B03E23AC55A6B3562E3411FFF4E0C54959E596F15106973165239676873E9` |
| 上一个调试包（升级基线） | `.local/android/apk/app-debug-v1.apk`（本机忽略目录） | 4,412,287 B · SHA256 `04788A64C5082980B7818B1BE8F43F4B4767ADC7DC214FA6A2036DAB30A1A328` |
| 用户指南 | [android-user-guide.md](android-user-guide.md) | — |

版本元数据：`versionCode 2` / `versionName "1.0.1"`（`frontend/android/app/build.gradle`）。

## 安装与升级（`frontend/scripts/check-android-package.mjs`）

证据 `.local/android/evidence/device-a6-baseline.json`、`device-a6-upgrade.json`、`device-a6-release.json`，截图 `a6-upgrade.png`、`a6-release.png`。

| 阶段 | 结果 |
|---|---|
| `baseline`（干净安装 v1 + 登录） | **通过**。卸载后安装 `app-debug-v1.apk`（`versionCode 1` / `versionName 1.0`），启动落在登录页，合成账号 `android_seller` 登录成功进入工作台 |
| `upgrade`（v1 → v2 覆盖安装） | **通过**。`adb install -r` 安装 `versionCode 2` / `versionName 1.0.1`，安装后**无需重新登录**（`.android-toolbar` 直接可见），恢复路由 `/`，证明同签名升级保留会话与应用数据 |
| `release`（发行包干净安装） | **通过**。卸载调试包后安装签名发行包，版本一致（2 / 1.0.1），启动落在登录页且工具栏不可见（干净安装无会话，符合预期） |

安装脚本的行为：`baseline` 要求登录页并完成登录；`upgrade` 断言 `versionCode` 增大且会话保留；`release` 只做干净安装与登录页断言（不比较旧版本，因为安装前已卸载）。

## 签名与发行构建

- 本机签名材料（**不提交**）：`.local/android/keystore/soloops-release.jks`（PKCS12，RSA 4096，别名 `soloops-release`，有效期 3650 天）与 `.local/android/keystore/credentials.txt`；Gradle 读取被忽略的 `frontend/android/keystore.properties`（`frontend/android/.gitignore` 已加入该文件名，`*.jks`/`*.keystore` 原本已忽略）。
- 重新生成：`./scripts/make-release-key.ps1`（幂等；已存在则复用并重写属性文件）。属性文件必须**不带 BOM**写盘，否则 Java `Properties` 会把 BOM 并入首个键名，Gradle 报 `Cannot convert 'null' to File`——本轮已踩到并修正。
- 证书：DN `CN=SoloOps Android Release, OU=Local Build, O=SoloOps, L=Local, ST=Local, C=CN`；证书 SHA-256 `91E6DD8C5D64AF1C926D7248494301EDFD40FC5838A7009D76963CA885C51D52`；SHA-1 `B311669F57801BAB7B44D711CC924F54FFD84BAF`。`apksigner verify --print-certs` 通过。
- 发行构建流程：`VITE_SOLOOPS_API_ORIGIN=https://android-release.invalid npm run android:sync` → `gradle assembleRelease`。打包资源 `soloops-build.json` 为 `{"mode":"android"}`，满足既有 release 资源门禁；服务地址为保留的 HTTPS 占位域名，不是真实生产地址。
- 打包内容核对：发行资源包中可检索到 `android-release.invalid`，与本机测试地址（`10.0.2.2:8011`）分离；CI 的 `preReleaseBuild` 门禁在本轮未改动。

## 部署状态（如实记录）

- **未上架**：未向 Google Play、华为应用市场或任何渠道提交；没有创建商店条目、隐私表单或内容分级。
- **正式服务地址未定**：发行包当前指向占位域名；正式域名、HTTPS 证书与反向代理由用户决定后重新执行 `android:sync` + `assembleRelease`。
- **签名归属未定**：本机密钥仅用于本地发行预演；正式发布应由用户持有并备份密钥（丢失无法覆盖升级），或改用 Play App Signing 等托管方案。密钥与口令均在忽略目录，未进入版本库。
- **未做的发行端验证**：发行包与真实 HTTPS 服务的端到端登录未验证——本地合成后端是明文 HTTP，且不把测试 CA 打进正式包；该验证需要正式域名。发行包已在本机完成安装、启动与登录页渲染验证。

## 复现

1. `./scripts/make-release-key.ps1` 生成本机签名材料。
2. 调试包：`. ./scripts/android-env.ps1` → `npm run android:sync:local`（在 `frontend`）→ `gradle -p frontend/android assembleDebug`。
3. 发行包：`VITE_SOLOOPS_API_ORIGIN=https://<正式域名> npm run android:sync` → `gradle -p frontend/android assembleRelease` → `apksigner verify --print-certs`。
4. 设备验证：`SOLOOPS_PACKAGE_PHASE=baseline|upgrade|release` 配合 `SOLOOPS_APK=<apk 路径>` 运行 `node frontend/scripts/check-android-package.mjs`。
5. 用户使用说明见 [android-user-guide.md](android-user-guide.md)。
