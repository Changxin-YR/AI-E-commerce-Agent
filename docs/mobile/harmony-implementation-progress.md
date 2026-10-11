# 鸿蒙完整业务版 · 实时进度

更新：2026-10-11。工作区 `.local/worktrees/mobile-m0a`，分支 `feat/soloops-mobile-m0b`。当前目标：按V1.3连续完成R2全部业务功能，之后集中模拟器自查与联调。

## 最新用户决策

- 鸿蒙先做完整功能，API22模拟器运行即可；Android、微信只规划，当前不实现。
- 先全部实现再集中自查，不按M0/M1停工等待；真机/资质不作为开发条件。
- 上下文接近满时自主创建接续对话，持久记忆、同一计划、单写入工作区。
- 桌面与后台一次一个模拟器；本轮不运行Android。

## 已有工程基础

Android历史技术补齐已保存于016a1a5；鸿蒙M0本次新增26项断言和10项基础回归在最终HAP上通过。HAP SHA256 `fc6a6ceed0bcdc4d35229943b4ddc9769276aa782fdef708f757fec1f545c742`，API22。深色、1.3字体和横屏已实测。原始证据 `.local/mobile-m0b/20261011-ohos-acceptance/`，基础 `.local/mobile-m0b/20261011T082953Z-ohos-emulator/results.json`。当前不继续扩大M0测试。

业务实现前只有诊断页，没有任何已完成的移动业务流程。最新源码开始补齐会话、网络与业务基础；进度按下表逐项填写，不以骨架代表完成。

| 范围 | 实现状态 | 后续工作 |
|---|---|---|
| V1.3 主体方案和三端功能分工 | 已落盘 | 按清单连续实现 |
| 移动会话/系统桥接/网络 | 代码已实现，未集中验证 | `/mobile/auth/*`、Bearer、Asset凭据、文件选择/保存/分享；业务联调阶段再构建验证 |
| 五入口和业务导航 | 基础代码已实现 | 首页/待办读取、AI记录/消息读取、我的资料；继续补完整子路由和动作 |
| H01/H02 登录、经营档案、店铺 | 核心表单代码已实现，未端测 | 过期恢复/退出/全端退出、创建/切店/资料保存；初始化向导与冲突回读待补 |
| H03–H20 业务表单、操作和回读 | 待实现（少量列表基础） | 下一步直接实现H04导入，再核心流程与剩余R2页面 |
| 全量自查与API22运行 | 功能实现后执行 | 不提前逐项卡门槛 |

## 环境与保护

实际绝对工作区 `C:/Users/27363/Desktop/AIEcommerceAgent/.local/worktrees/mobile-m0a`，保存项目路径 `C:/Users/27363/Desktop/AI E-commerce Agent` 已过时；shell一律显式workdir，按现有方式require_escalated。

Python复用主仓库 `backend/.venv/Scripts/python.exe`；Flutter在本worktree `.local/toolchains/flutter-oh-api22`，PUB_CACHE `C:/Users/27363/Desktop/max/pub-cache`。SDK/构建见 `scripts/mobile/build_ohos_probe.ps1`。HDC为DevEco/sdk/default/openharmony/toolchains/hdc.exe，API22实例22。

本机 `ohos/build-profile.json5` 含签名配置、微信 `project.config.json` 含真实AppID：保留、不输出、不提交。密钥、日志、包、截图只保存在忽略目录。

模拟器在连续UI测试时发生guest低内存退出，Android当时已关闭；RAM曾临时3072MiB，目前已恢复原2048MiB。当前停止实例22。字体滑块已恢复1；浅色切换已发起，旋转锁尚待恢复ON，业务安装阶段顺手恢复。避免花时间扩大M0测试。CLI启动易挂在InitFeatureConfig，DevEco Device Manager启动22可靠。


## 接续必须直接做的工作

1. 先读本账本、`docs/requirements/SoloOps-Mobile-V1.3.md`、当前AGENTS。原V1.2参考已入库，无需再次查Downloads，也不要重读整个M0日志。不得再次问用户是否进入M1。
2. 当前代码没有业务构建/测试结果：按用户“先全部实现后集中自查”执行，只做过源文件格式化。H01/H02源代码和基础列表不等于全功能完成。不要把历史M0结果算给当前业务包。
3. 立即实现导入：读取 `frontend/src/views/ImportsView.vue`、`components/ImportMapping.vue`、`ImportRows.vue`、`ImportSemanticsReview.vue`、`ImportGroups.vue` 与 `frontend/src/api/imports.ts` / `types/imports.ts`。Flutter新建 `features/imports/`，真实调用原上传/预览/提交/撤销/清除和分组接口。鸿蒙可直接原字节上传，本轮无需微信multipart。
4. 然后完整实现首页/待办动作、Agent/B1、Listing、客服，再V1.3其余页面。`RecordListPage`只有读取列表，必须替换/扩展为完整业务模块；工作台卡片也尚无详情深链与动作。不允许用通用JSON编辑器或空页面冒充业务功能。
5. 使用现有Web API模块、types、页面组件逐项移植交互与合法payload；服务端业务判断复用。已有OpenAPI契约覆盖149条引用；最后更新移动覆盖矩阵。
6. 业务全覆盖后再构建HAP、静态和定向后端检查、启动隔离MySQL/API/合成样本，在API22模拟器集中运行卖家旅程，修复缺点后与用户联调。Android/微信本轮不构建不启动。可用已有后端E2E配置/种子模式，不打印本机env秘密，不对原业务库直接跑迁移。

## 本次业务代码位置与设计

- `backend/app/api/routes/mobile_auth.py`：移动login/session/logout/logout-all。Bearer不透明随机值，复用会话表hash；账号持久锁定+进程内IP20次/分钟限制；绝对到期沿用session_hours。新路由无Cookie。
- `backend/app/services/auth.py`：设备client_type、session_id、issued/last_used、单设备/全端吊销。沿用用户行锁与索引删除；密码重置原逻辑自动删除同表全端会话。
- `backend/app/api/dependencies.py` / middleware：拒绝Cookie+Bearer混用；合法设备Bearer进入原业务层；Web Cookie仍需CSRF与来源校验。Web `/auth/session`、logout拒绝Bearer。后续集中验证认证兼容与并发。
- `backend/migrations/versions/a31e72d405bf_mobile_sessions.py`：接d93f6b210ac4的加列迁移，尚未对任何库执行。降级先使设备token失效，再删除移动字段。
- `lib/core/api_client.dart`：Dart HttpClient、45秒请求截止、8MiB响应界限、原字节分块上传、拒绝跟随重定向、401重登、generation防迟到响应、写入未知不自动重放。HTTPS；debug仅回环地址可HTTP。debug回环HTTPS可使用现有M0证书。
- `lib/core/app_state.dart`：账号与店铺状态、Asset恢复/保存、logout、UUID。`device_bridge.dart`连接 `soloops/device`。
- `ohos/.../DeviceBridge.ets`：正式Asset会话alias与M0合成alias分开；preferences仅地址和店铺；csv/xlsx选择<=40MiB、保存、分享。API22桥接需在集中构建时确认ArkTS类型与UTD。share dismiss当前删除临时文件，联调需核对实际消费时机。
- `lib/product_app.dart`：绿色中性主题、深浅色、五入口；`main()`已改为ProductApp，旧SoloOpsApp诊断组件保留给历史测试。后续新增业务测试不能只跑旧诊断widget测试。
- `lib/features/account_pages.dart`：登录、资料编辑、店铺创建、单设备/全端退出；`workbench_page.dart`读取工作台/AI/客服列表。表单/列表已有代码但尚未构建或端测。
- `lib/ui/common.dart`：共用输入、反馈、确认、店铺选择组件。

## 本地资源状态

鸿蒙22已停止，Android未运行；RAM配置已恢复2048MiB。旧M0 HTTPS夹具PID16356/44528已停止，HDC映射为空。DevEco可以保持打开但没有本轮模拟器常驻。下次业务模拟器启动时可顺手确认浅色、字体滑块1、旋转锁ON。工具CLI冷启动曾无窗口挂起，优先已有DevEco Device Manager的22实例。

## 持续交接约定

本次以进度提交保存开发中源码，完整业务/模拟器自查未开始。接续不得先花时间追旧CI或M0显示遗留；按V1.3继续代码实现。提交SHA由新对话启动消息给出，不能把父提交当当前SHA。工作区只由接续对话写入，旧对话交接后停止。
