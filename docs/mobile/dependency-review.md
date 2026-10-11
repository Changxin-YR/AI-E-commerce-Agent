# M0-A 依赖与许可证审查

核对日期：2026-10-11。此页审查新客户端；原 Web 和后端依赖未改。

## 版本和配置

- Flutter SDK 采用 CPF 官方发布 tag 和完整 SHA；来源与 Android/OH 工具版本见 `apps/soloops_flutter/toolchain.lock.json`。`pubspec.lock` 已提交，当前仅 Flutter、flutter_test 与 flutter_lints5.0.0；插件矩阵候选尚未加入工程。
- Taro 各直接包统一4.3.0，Vue3.5.43，TypeScript5.9.3，Vite4.5.14。根据已安装 `@tarojs/vite-runner` 和框架插件 manifest 的 Vite4 peer 约束选插件Vue4.6.2/JSX3.1.0。没有使用忽略 peer 冲突的安装参数。
- Node24.16.0、npm11.13.0；lockfile 固定完整依赖及 integrity。CI 使用 `npm ci`，同时进行类型检查和微信目标编译。
- Flutter 平台模板含开发签名示例和 OH 模板测试文件；它们不构成已签名发布或已运行设备测试。提交内容不包含发布证书、密钥、真实 AppID、API URL 或客户资料；微信导入生成的本机 AppID 配置保留在工作区并排除提交。
- `dist`、`build`、SDK、原始日志、依赖缓存、`local.properties`、微信私有配置和签名文件均受忽略规则保护。工程只有启动页和环境说明，无业务 API 请求。

## 安全审计

最终 `npm audit --json` 退出码1：**FAIL**。审计计数是受影响依赖节点，不是42个独立漏洞：

| 严重度 | 节点数 |
|---|---:|
| low | 1 |
| moderate | 12 |
| high | 25 |
| critical | 4 |
| 合计 | 42 |

已在兼容范围内更新 Vue3.5.43、Babel core7.29.7、PostCSS8.5.29，并重新通过类型检查和编译。
仍需处理的代表问题：

- Taro components 引用的 Swiper 依赖链被标为 critical，参见[维护者公告](https://github.com/advisories/GHSA-hmx5-qpq5-p643)。当前小程序启动壳不使用 Swiper，但本次没有完成最终包可达性和利用条件分析，不能据此豁免。
- 模板下载依赖链的 decompress/归档处理存在路径穿越等公告；本次只构建本地受控源码，没有调用 Taro 在线模板下载。最终原始审计详见证据清单。
- Vite4 及相关开发服务器依赖有文件访问等漏洞；不向外暴露开发服务器。正式发布前必须评估维护者修复、兼容构建器升级或有测试支撑的定向补丁。
- 审计建议部分会将 Taro 降至1.x/3.x或将Vite升至8.x，不满足冻结技术栈或 peer 约束。预览修复没有给出可直接应用的兼容更新；本阶段保留 FAIL，不执行强制变更。

**生产发布准入：BLOCKED。** 最小构建 PASS 与安全审计 FAIL 分开记录。后续仅合成资料的工程/设备验证可分端安排；业务数据接入和发布需先处理可达漏洞与凭据存储问题。

## 许可证

静态许可证清单核对：PASS（不是法律审计或发布许可）。

- Flutter SDK 根 LICENSE 和 LICENSE_KHZG 均为三条款 BSD 类型声明，模板来源通知完整保留在 `apps/soloops_flutter/licenses/`。
- Taro/Vue/Vite 为 MIT；TypeScript 为 Apache-2.0。Taro 模板参考的完整 MIT 声明保留在 `apps/soloops_weapp/licenses/TARO-LICENSE`。页面代码自行实现。
- npm lock 元数据涵盖 MIT、ISC、BSD、Apache、0BSD、CC0、BlueOak、Python-2.0 等声明；另有 CC-BY-4.0 数据依赖，最终分发需要保留对应归属说明。
- lock 唯一没有单值 `license` 字段的是 `svg-tags@1.0.0`；已读取安装包 `licenses` 数组和 LICENSE，均为 MIT。没有将缺字段默认为无许可证。
- 插件矩阵中的第三方候选另有 BSD-3-Clause/MIT/Apache 文件头；尚未引入或分发，后续集成须核对所固定提交和传递依赖。

当前仅提交源码、锁文件与声明。应用商店发布、第三方完整通知包及许可证义务复核为 NOT_TESTED。

API22复核：当前Flutter OH固定3.27.5-ohos-1.0.7，Dart版本和pubspec.lock不变。`miniprogram-automator@0.12.1`（MIT）仅安装在被忽略的`.local/weapp-tools`，不进入小程序依赖或产物；它仅检查本地启动页，本次连接BLOCKED。

SDK24复核：沿用已锁定Flutter OH 1.0.7与Dart依赖，新增本机无空格构建脚本。HAP包内编译SDK为6.1.1.125、target24；编译PASS但上游ArkTS仍有弃用/异常处理/NAPI告警。未签名包不构成安装或发布验收。证据工具超时回归PASS，未引入新的应用运行时依赖。

本次收尾沿用上述依赖锁，未新增应用依赖；Android APK、SDK24 原目录未签名 HAP、微信目标重新编译 PASS。微信启动页的原生 UI 观察 PASS，automator 通道仍超时 BLOCKED，二者分别归档。证据导出工具增加 Hvigor 参数内绝对路径的规范化与拒绝外部私有路径的回归测试，合计15项工具/契约测试 PASS。
