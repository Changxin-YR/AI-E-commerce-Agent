# SoloOps M0 Android 技术验收补齐

日期：2026-10-11。分支 `feat/soloops-mobile-m0b`，本轮起点 `c4758a937e780b24c8920be01e53de13808b80db`。

**Android 模拟器技术验收 PASS；全部 M0 尚未完成。** 26 项新增端上断言、16 项基础运行记录通过。下一端为鸿蒙，随后微信；继续停在 M0 范围。用户要求全部使用模拟器，小程序资质暂缓。

## 环境与产物

复用 `.local/worktrees/mobile-m0a`。Flutter OH `3.27.5-ohos-1.0.7` / `6e545c2ce6ec9e303868dece5012d1d928890b57`、宿主 Dart3.6.2、Android 引擎 Dart3.6.1；JDK17、SDK35、AGP8.1.0、Gradle8.3。目标为 `emulator-5580` / KnowFlow_API34 / Android14 / API34 / x86_64。

- APK：`apps/soloops_flutter/build/app/outputs/flutter-apk/app-debug.apk`，101,534,556 bytes。
- SHA256：`1483dba9d188cd512dd54ed1c866b2eac2c2367f7ef61013332434c1177c8b71`。
- [完整证据清单](m0-android-closure-evidence.json)：实际 argv、时间、退出码、设备结果、文件路径及 SHA256。所有选入的新增端测在当前 APK 安装完成之后执行。
- 起点准确 SHA CI：[38118986499](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38118986499)，completed / success。交付提交的准确 SHA/CI 在交付消息及后续交接中记录。

## 实现与端上结果

| 项目 | 状态 | 实际断言 |
|---|---|---|
| 安全存储 | PASS | Android Keystore AES-256/GCM；写读、覆盖、密文篡改拒绝、密钥缺失拒绝、删除、进程终止后读回和清除 |
| 密钥与备份策略 | PASS | key.encoded=null；密文在 noBackupFilesDir；应用禁用备份；原子落盘；失败显式返回而不转明文 |
| 硬件安全 | NOT_TESTED | 当前模拟器 KeyInfo 报告 hardwareBacked=false / securityLevel=0；不作为真机 TEE/StrongBox 证明 |
| 非敏感缓存 | PASS | 原生 SharedPreferences 合成 scope A/B 隔离、清理、跨进程持久化；未保存会话凭据 |
| 文件选择/URI | PASS | 系统 ACTION_OPEN_DOCUMENT；26字节合成文本的 content URI、文件名、text/plain、内容和SHA256；取消、未授权URI拒绝、2MiB+1文件拒绝 |
| 上传 | PASS | 选中文件哈希与夹具回读一致、2MiB边界成功、超限客户端拒绝、503失败、传输中取消、后续恢复 |
| 下载 | PASS | 64KiB分块写 .part，131072字节逐字节核对后重命名；超限、503、取消均清理部分文件 |
| 网络补充 | PASS | 响应超时中止、跨域重定向不跟随；本机固定TLS证书，仅debug信任 |
| 分享 | PASS | 仅暴露m0-share子目录的FileProvider、系统面板显示synthetic.txt，按返回取消、撤销授权并删除文件；超限分享被拒绝 |
| 渠道接收 | NOT_TESTED | 未选择渠道或接收人，面板/回调不作为外发确认 |
| 外链分发 | PASS | ACTION_VIEW已进入Chrome，返回后恢复应用 |
| 浏览器页面加载 | NOT_TESTED | Chrome停在首次使用页；下一步可由用户完成浏览器初始化后复验。本地自签名HTTPS页面不绕过证书提示 |
| 国际化日期 | PASS | 固定UTC样例2026-10-10T16:30Z，Asia/Shanghai跨日结果，zh_CN与en_US格式均核对；不是全时区业务实现 |
| 基础回归 | PASS | 16项记录：启动、导航、返回、前后台、深色、横屏、1.3倍字体、基础系统诊断和无未捕获异常；设置恢复到执行前值 |

Android 原生通道仅在 debug 响应，Shared Dart 页面负责检查和传输。平台桥接只提供系统能力，未接正式认证、业务上传或数据库。

## 实际命令与日志

从本工作区根目录执行，脚本内指定相应应用 cwd；本机工具绝对路径在导出时映射为工具名。构建时 JAVA_HOME=JDK17、ANDROID_HOME=SDK目录、GRADLE_USER_HOME=`.local/gradle`；Flutter SDK 使用上面的锁定提交。

| 命令 | 退出码 | 结果 / 日志 |
|---|---:|---|
| `flutter build apk --debug --no-pub --dart-define-from-file=../../.local/mobile-m0b/tls/dart-defines.json` | 0 | PASS，`20261011T065810Z-closure-android-build.log` |
| `adb -s emulator-5580 install -r apps/soloops_flutter/build/app/outputs/flutter-apk/app-debug.apk` | 0 | PASS，`20261011T065902Z-closure-android-install.log` |
| `python scripts/mobile/check_android_closure.py --adb <adb> --serial emulator-5580 --stage <stage>` | 0 | PASS；storage、pick-cancel、pick-small、pick-large、transfer、share、external各自独立证据目录 |
| `python scripts/mobile/check_android_emulator.py --adb <adb> --serial emulator-5580` | 0 | PASS，`20261011T070137Z-closure-android-basic.log` |
| `flutter analyze --no-pub` | 0 | PASS，`20261011T065903Z-closure-analyze.log` |
| `flutter test --no-pub` | 0 | PASS，2项，`20261011T065914Z-closure-widget-tests.log` |
| `python -m unittest discover -s scripts/mobile/tests -v` | 0 | PASS，20项，最新日志在证据清单 |
| `python -m ruff check --config scripts/mobile/ruff.toml scripts/mobile scripts/validate_ui_contract.py` | 0 | PASS，最新日志在证据清单 |
| `python -m ruff format --check --config scripts/mobile/ruff.toml scripts/mobile scripts/validate_ui_contract.py` | 0 | PASS，最新日志在证据清单 |

原始日志、截图、XML与证书位于忽略目录 `.local/mobile-m0b/`。本次重启存储的PID由8704变为8840；两个进程日志分别保留在 `20261011T065906Z-closure-storage/`。最终传输记录为 `20261011T070507Z-closure-transfer/`；最终分享截图在 `20261011T070353Z-closure-share/`，已查看确认系统面板与文件名。基础显示回归目录为 `20261011T070137Z-emulator-5580/`。

`runtime_fixture.py` 只监听127.0.0.1:18443。新增 `/_m0c/` 合成端点限定标记头、方法和实际2MiB计数，不保存文件；原业务写路由仍403、数据库仍被禁止。预期取消上传以ClientDisconnect处理，最新夹具日志没有未处理异常。历史首次构建的BuildConfig错误及早期取消日志保留在忽略目录，最终结论来自修复后真实执行。

## 依赖、范围与剩余工作

新增SDK flutter_localizations、锁定intl0.19.0（BSD-3-Clause，声明已保存）及显式androidx.core:core:1.13.1（Apache-2.0，Maven POM已核对）。原R2后端、Web业务、数据库迁移、权限审批与静态契约未修改。两份本机文件 `ohos/build-profile.json5`、微信 `project.config.json` 保留且排除提交。

鸿蒙仍需实现系统安全存储/安全失败策略、缓存、文件选择/分享等必要ArkTS桥接，并在API22 x64模拟器验证共享Dart。微信仍需补客户端安全策略、网络/文件能力、工具兼容和依赖审计。物理设备、硬件密钥证明、正式业务E2E与生产发布均未通过本次Android技术验收获得许可。下一阶段仍为M0技术补齐。
