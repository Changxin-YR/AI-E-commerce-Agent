# M0-A 关键插件兼容性矩阵

核对日：2026-10-11。基线为 Flutter OH `3.27.4+ohos-1.0.9` / Dart 3.6.2。
来源声明只说明候选支持；下表验收状态区分静态检查、宿主测试、设备测试。
本次工程仅引入 Flutter SDK 与开发测试依赖，候选插件尚未集成。

| 能力 | Android 候选与依据 | OHOS 候选与依据 | 本次原型实测 / 状态 | 替代或后续验证 |
|---|---|---|---|---|
| HTTPS 请求 | Dart 3.6.2 `HttpClient` [S1] | 同 SDK `dart:io`，引擎适配待端上验证 | Android/OHOS 网络运行均 NOT_TESTED | 有效证书、错误证书、超时/断网、请求取消；必要时 ArkTS HTTP 通道，保持证书校验 |
| Cookie / Bearer 请求 | `HttpClientRequest.cookies/headers` [S1] | 同 Dart API；Cookie jar 需统一管理 | 两端 NOT_TESTED；未调用后端 | 请求头能力不等于服务端支持 Bearer。现有 R2 是 Cookie+CSRF，移动认证另期实现 |
| 安全存储 | `flutter_secure_storage` 9.2.4，Android KeyStore [S2] | CPF tag `9.2.4-ohos-1.0.0`，子包 `flutter_secure_storage_ohos` 1.2.2 [S3] | Android NOT_TESTED；OHOS 凭据存储静态审查 FAIL；端上均 NOT_TESTED | 该实现将 RSA 私钥编码后放入 preferences，不能据包名认定满足硬件密钥保护。优先评估 ArkTS Asset / HUKS 不可导出密钥加密存储；验证重启、卸载、备份与注销清除 |
| 文件选择 | `file_picker` 8.0.6，manifest 声明 Android [S4] | 旧 OH 子包1.0.1要求 Dart <3，和3.6.2冲突；新版 `file_picker_ohos` 10.3.8 声明 Dart >=3.4，但官方映射3.35 [S4] | 旧 OH 候选约束检查 FAIL；新版及两端选择器 NOT_TESTED | 评估官方3.27对应的10.2.0适配或 ArkTS DocumentViewPicker；需固定完整提交并构建，不用版本范围强行绕过 |
| 文件读取 / 上传 | Dart File/Stream + HttpClient 3.6.2 [S1] | 同 API + picker 返回 URI 的平台处理 | 两端 NOT_TESTED | 不假设 content URI 是磁盘路径。ArkTS 打开 URI 后有界分块桥接；沿用服务端原导入引擎，不能整文件跨 channel 无限拷贝 |
| 剪贴板 | Flutter `Clipboard`，随固定 SDK [S5] | 固定 SDK services/platform channel | 两端 NOT_TESTED | 用合成文本核对读写、隐私提示和返回值；必要时 ArkTS pasteboard。复制成功不是外部发布 |
| 下载 / 分享 | HttpClient 下载 + `share_plus` 10.1.1 [S6] | CPF share_plus10.1.1 OH 适配；SDK>=3.3，Flutter>=3.19 [S6] | 两端 NOT_TESTED | 校验保存目录/文件名/MIME、取消/拒绝权限/资源释放；分享面板关闭或 success 不代表渠道确认 |
| 本地缓存 | `shared_preferences`2.3.2，SDK^3.4 [S7] | CPF同版本 + OH子包2.3.1 [S7] | 两端 NOT_TESTED | 仅存非敏感设置；账号/店铺隔离、过期与清除。其嵌套 Git 分支依赖也需 pin，不能只锁外层 ref |
| 页面导航 | Flutter Navigator / MaterialPageRoute，固定 SDK | 同 Dart 页面源码 | 宿主机1项 widget test PASS；Android/OHOS 设备均 NOT_TESTED | 后续验证系统返回、手势、深链和记录恢复；当前只启动页→环境页→返回 |
| 应用生命周期 | WidgetsBindingObserver，固定 SDK | 同 Dart 观察器 | 两端编译中的源代码已存在；事件运行均 NOT_TESTED | 前后台/重建/进程终止；不能用 resumed 自动重发副作用，必要时补 ArkTS 通道 |

Android 最小壳编译 PASS；OHOS 壳编译 BLOCKED（SDK 26 / 现有 API 24 工具不匹配）。
以上插件的设备运行结果不能从壳编译推导。业务 E2E 为 NOT_TESTED。

## 固定来源与静态证据

- S1：[Dart HttpClient API](https://api.dart.dev/dart-io/HttpClient-class.html)。实际项目运行时固定 Dart 3.6.2；在线 API 页版本可能较新，后续以锁定 SDK 编译与端测为准。
- S2：[flutter_secure_storage 9.2.4](https://pub.dev/packages/flutter_secure_storage/versions/9.2.4)，BSD-3-Clause。
- S3：[CPF secure storage](https://atomgit.com/CPF-Flutter/fluttertpc_flutter_secure_storage)，tag `9.2.4-ohos-1.0.0`，commit `ecc4257040163da3c4dd64d4fced5d4d24676a53`。已读 `README.OpenHarmony_CN.md`、两个 pubspec 与 `flutter_secure_storage_ohos/ohos/src/main/ets/components/plugin/ciphers/RSACipher18Implementation.ets:76`。源码 `createRSAKeysIfNeeded` 将 `priKey.getEncoded()` Base64 后写 preferences；这是静态发现，不是设备攻击测试。
- S4：[CPF file picker](https://atomgit.com/CPF-Flutter/fluttertpc_file_picker)，旧 tag `8.0.6_ohos_1.0.1` / `49c94285da95fe93920da899562bfc4fa2080574`，已读根和 `ohos/pubspec.yaml`；新版 tag `10.3.8-ohos-1.0.0` / `1a38f43d7c2e976c2add2c057da79223a0913f84`，已读 manifest 和 OH README。MIT，版本兼容与 API 支持仍需分开判断。
- S5：[Flutter Clipboard](https://api.flutter.dev/flutter/services/Clipboard-class.html)，BSD-3-Clause；版本跟随 SDK SHA。
- S6：[CPF plus plugins](https://atomgit.com/CPF-Flutter/flutter_plus_plugins)，`br_share_plus-v10.1.1_ohos` 核对时 SHA `55de300a8627c55cd45ac86e6a26bcae8e0ca4cf`。读取 `packages/share_plus/share_plus/pubspec.yaml` 与 OH README；BSD-3-Clause，维护者历史实测 Flutter3.22，不能当本次3.27证据。
- S7：[CPF flutter packages](https://atomgit.com/CPF-Flutter/flutter_packages)，`br_shared_preferences-v2.3.2_ohos` 核对时 SHA `f924a51ea2da823204b73e06e938e0db98a3a5f6`。用 `git show HEAD:packages/shared_preferences/.../pubspec.yaml` 核对两包；上游 BSD-3-Clause，OH 子包还含 Apache-2.0 文件头，集成时保留对应声明。

候选插件优先走适配插件。安全存储和文件 URI 是明确的 ArkTS 通道评估点；平台通道只承担系统能力，不复制 Dart 业务规则。本阶段未新增 Bearer、刷新 Token 或上传业务引擎。
