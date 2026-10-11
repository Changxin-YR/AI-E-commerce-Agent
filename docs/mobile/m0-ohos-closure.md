# SoloOps M0 鸿蒙技术验收补齐

日期：2026-10-11。分支 `feat/soloops-mobile-m0b`，本轮起点 `016a1a5319cd9da8471c55af2dc37b2047e872e0`。

鸿蒙 API22 x64 模拟器新增26项技术断言及10项基础回归PASS，深色、1.3倍字体与横屏已观察通过。本文冻结已执行M0诊断包事实；后续源码已转入V1.3完整业务实现，开发状态见 `harmony-implementation-progress.md`。

## 环境与产物

Flutter OH `3.27.5-ohos-1.0.7` / `6e545c2ce6ec9e303868dece5012d1d928890b57`，Dart3.6.2；DevEco6.1.1.290、SDK24 6.1.1.125、Hvigor6.24.3。复用 API22 实例 `22`，HDC `127.0.0.1:5555`。

- HAP：`apps/soloops_flutter/ohos/entry/build/default/outputs/default/entry-default-unsigned.hap`，100,644,160 bytes。
- SHA256：`fc6a6ceed0bcdc4d35229943b4ddc9769276aa782fdef708f757fec1f545c742`。
- 最终构建日志：`.local/mobile-m0b/20261011T082322Z-closure-ohos-build.log`。
- 最终安装日志：`.local/mobile-m0b/20261011T082351Z-closure-ohos-install.log`，含 `install bundle successfully`。
- 运行证据目录：`.local/mobile-m0b/20261011-ohos-acceptance/`；进程重启由 PID7342 变为 PID7422。每次日志独立存档并记录当前 HAP 哈希和采集时间。

单模拟器运行：执行鸿蒙时 Android 模拟器关闭；切换平台先停止上一台，确认进程退出后再启动目标实例。测试结束关闭模拟器并保留实例数据。

## 实现与端上结果

| 能力 | 状态 | 证据范围 |
|---|---|---|
| 安全存储 | PASS | 原生 Asset 服务写读、覆盖、删除；进程重启读回和清理；仅接受合成值 |
| Asset 策略 | PASS | 查询真实 ATTRIBUTES，验证 DEVICE_UNLOCKED、SYNC_TYPE=NEVER、IS_PERSISTENT=false，属性查询不返回 SECRET；错误向上返回 |
| 安全失败路径 | PASS | 空 SECRET 更新由系统返回401，原值保留；不存在 alias 返回 NOT_FOUND；删除后读回为空 |
| 硬件保护 / 卸载效果 | NOT_TESTED | 模拟器没有证明真机 TEE/硬件加密；卸载策略只查询属性，未执行卸载重装 |
| 非敏感缓存 | PASS | preferences 合成 A/B scope 隔离、覆盖与清理，跨进程持久化；值限定为诊断设置 |
| 文件选择 | PASS | DocumentViewPicker，取消、26字节合成文件、文件名、text/plain、file://docs URI、内容和SHA256；2MiB+1文件拒绝 |
| URI 桥接校验 | PASS | 桥接只读当前选择器返回的 URI，操作后清空；未选 URI 在打开前被 DOCUMENT_NOT_SELECTED 拒绝 |
| OS URI 撤权 | NOT_TESTED | 当前文件创建/授权样本不能建立有效的系统撤权拒绝证据；桥接校验结果不等价于 OS 授权隔离 |
| 合成上传 / 下载 | PASS | 共享 Dart 64KiB分块；2MiB边界、超限拒绝、503、取消、恢复；下载内容核对及部分文件清理 |
| 网络边界 | PASS | 响应超时、重定向不跟随；仅本机合成夹具 |
| 分享 | PASS | ShareKit 系统面板实际显示合成文件和26B；返回取消、文件清理、超限拒绝 |
| 渠道交付 | NOT_TESTED | 本次仅验证系统面板与取消，不选择接收渠道 |
| 外链分发 | PASS | openLink 进入系统浏览器，浏览器显示本机自签名证书警告，取消后返回 |
| 浏览器页面加载 | NOT_TESTED | 停在证书校验提示，未绕过 |
| 日期格式 | PASS | 固定 UTC 跨日样例及 zh_CN/en_US 格式；不构成完整业务时区实现 |

ArkTS 通道仅在 DEBUG 响应，负责系统能力；Dart 页面、传输和校验继续与 Android 共享。文件读取在分配前检查大小，64KiB分块且总计最多2MiB+1，异常路径关闭文件。正式认证和业务导入不在本次原型范围。

## 可复现检查

在工作区根目录执行，PUB_CACHE 指向本机已有缓存，SDK 提交必须匹配 toolchain.lock.json。TLS 夹具复用忽略目录证书；仅 debug HAP 信任该证书。

```powershell
pwsh -NoProfile -File scripts/mobile/build_ohos_probe.ps1
hdc -t 127.0.0.1:5555 install -r apps/soloops_flutter/ohos/entry/build/default/outputs/default/entry-default-unsigned.hap
python scripts/mobile/check_ohos_closure.py --hdc <hdc> --session .local/mobile-m0b/<session> start
python scripts/mobile/check_ohos_closure.py --hdc <hdc> --session .local/mobile-m0b/<session> tap "M0 技术验收"
python scripts/mobile/check_ohos_closure.py --hdc <hdc> --session .local/mobile-m0b/<session> logs
```

按诊断按钮执行存储准备、结束/重启进程后读回、取消和选择大小文件、传输、分享取消/清理、外链返回。系统文件选择器使用 Download 下的 `soloops-m0-small.txt` / `soloops-m0-large.txt`。首次可通过“保存合成选择器样本”生成。

Flutter analyze、2项widget、24项Python工具/契约测试及ruff检查通过。证据导出器拒绝空安装日志、含失败的安装日志、安装前采集和不同 HAP 哈希；只将安装后的26项PASS合入正式清单。HDC返回0本身不作为安装成功。

## 依赖与准入

AssetStoreKit、CoreFileKit、ArkData、CryptoArchitectureKit、ShareKit 均来自固定 DevEco SDK；无新增第三方运行时包。参考官方 API 后自行实现通道，来源记录见 docs/references.md。原后端、Web业务、数据库及权限审批无改动；本机签名与真实AppID配置排除提交。

生产发布 BLOCKED；真机、硬件安全、正式业务认证与渠道接收仍需后续验收。用户已调整为鸿蒙完整R2业务优先，依V1.3继续实现。


显示配置使用 `auto_rotation_restricted` 与 app profile `fontSizeScale=followSystem`，实测1.3、portrait 377.1×816及landscape 816×377.1，页面可滚动。最终浅色复核未完成。模拟器guest内存曾低于500MiB并退出；测试时仅鸿蒙运行，RAM临时3072MiB后恢复2048MiB。当前设备已关闭，设置恢复遗留见实时进度。运行与显示证据见 `m0-ohos-closure-evidence.json`；这些结果只覆盖上述HAP，不代表后续业务代码已验证。
