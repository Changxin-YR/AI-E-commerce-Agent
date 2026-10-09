# SoloOps 重点上下文

更新：2026-10-09。只维护稳定约定、当前成果、测试和接续起点。业务代码在 main；本分支不合并到 main。

## 用户目标与授权

- 持续完成冻结稿 docs/requirements/SoloOps-V1.0.md：先 23 个 P0 最小模块、四条 MVP 和 A-01—A-32 本地适用验收，再 P1/P2。全部 74 SO、32 验收行保留，计划不能称实现。
- 默认简体中文；Vue 3 + TypeScript / FastAPI Python / MySQL。接口→业务服务→repository，明确类型与小函数；Agent 只调用受控业务服务。
- 每功能先检索官方/GitHub 资料，更新 references（借鉴、许可证、适配）。完成前后端/测试/静态检查后更新 development、interview-guide、testing、功能/验收矩阵、questions；正常提交并推送 main 和 context-memory，禁止强推。
- 用户已授权上下文压力时创建新本地项目聊天接续。先落盘和推送，新聊天接手后旧聊天停止修改共享工作区。未经明确要求不启动子代理。
- 用户已提供模型凭据并授权本机接入；又明确批准仅向 https://dashscope.aliyuncs.com/compatible-mode/v1 鉴权和累计最高 ¥0.01 合成测试。已完成验证。后续正常任务仍须页面数据同意和预算；额外代理联网测试不能无限沿用一次性授权。
- 真实经营事实、历史成本/费用、本人测试发信账号与收件箱、项目许可证等见 docs/questions.md；独立开发继续，不反复询问未新增的问题。

## 当前提交与环境

- 仓库 https://github.com/Changxin-YR/AI-E-commerce-Agent.git 。main **517d49767ba734053a6420059a01124908cb2a42** 已推送，主题 feat: add grounded support model candidates and handoff。
- 当前 CI https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37878451567 最后观测 in_progress，接续先核对。上版百炼51c8701的CI37875677800和Listing cb6f119的CI37874275146均已success。
- 前版分析41c15fe的CI37844263020有前端断言失败：模型解释存在时隐藏本地 answer；已在 cb6f119 修复为常显，本地和云端通过。
- backend/.venv Python3.11，frontend/node_modules，Docker MySQL8.4开发3307/测试3308。迁移 head **86df84dc129a**，两库已升级/check；最近两切片无需新迁移。
- 当前本地API8000与前端5173已后台启动并健康200。客服切片后核实原进程并重启API，新启动PID28132、前端Node32612（须重新核实，不凭旧PID杀进程）。日志在忽略的 .local，API无热重载，代码/设置变更需重启。
- .env、backend/.env、.local/test.env、.local 回执和 .context-memory 都从 main 忽略。密钥、真实数据、日志不可打印/提交/写聊天或文档。API密钥已在 backend/.env，无需再索取或复制。
- pytest、Playwright、迁移回退会修改同一隔离 _test 库，必须串行。测试入口显式排除本机 .env、覆盖 provider/key/name/rates、模型与外发关闭；禁止替身测试继承本机真实凭据。
- Windows命令用 .venv/Scripts/python -m；MySQL/Node/Git写/联网常需 require_escalated。Vitest沙箱temp rename可EPERM，正常权限复验通过；本机连接在沙箱内可能ConnectError，允许环境中健康200。
- Firecrawl已确认402，使用官方网页/GitHub connector，不反复调用计费接口、不临时编写网页抓取脚本。
- GitHub CI通过 github_fetch REST读取并解析 structuredContent.content，只输出状态摘要，避免凭据/响应头。Windows服务器Start-Process要WindowStyle Hidden。

## 最新完成：MVP03 客服模型候选与人工接管

- development二十三节、testing十八。support_model流程support_context→compose_support→support_candidate（审批）→verify，注册表共十一项；无新迁移，模型工厂和预算/租约复用。
- support_composition.py只接收意图ID、三个完整固定事实ID、已同意政策的匿名ID、offer_draft/handoff。模型意图与本地规则取并集，本地unknown与敏感条件不能删除。模型可补充语义意图；回复由中英文模板和完整、唯一、已确认FAQ原文组装。退款/物流/争议/地址取消/保修/未知语言/缺政策/冲突转人工。
- 政策池仍按本地意图主题及店铺/市场/渠道/身份/语言/有效期筛选，语义检索、自动语言检测、多轮和真实客服质量待继续，不称完整智能客服。
- Agent表单展示消息原文、所选政策全文和本地订单证据。目标与客服数据分开同意，support_context绑定消息源行、选定政策版本、人工核验的全部订单行集合。变更对象/政策/核验/范围/预算清空同意；组件请求epoch丢弃迟到回包，加载和错误时清空上下文。
- 请求只发目标、消息正文及标注语言、所选政策主题/全文/核对布尔值、三个固定事实与规则缺口。结构化订单号/SKU/行/文件名/政策出处留本地；原文若带个人信息或订单号会随正文发送，页面明确告知，不能宣传自动脱敏。
- _current_support在网络前/回包后/审批加载重建准备快照，save_candidate重验摘要。来源、订单集合、适用政策/冲突/有效期、经营规则变化阻断。最早政策截止写Agent valid_until。defer_commits保持owner/shop锁直到租约提交，不持锁联网。
- save_candidate去重含准备摘要/选择/供应商/失效世代；重复候选保留人工编辑/存档。草稿、依赖、审计和步骤同事务。依赖包含消息、已核验订单和全部已发送政策（包括模型未选中者）；来源/政策清除擦整稿和执行正文，在途回包只记已知费、不复活正文。
- SupportModelContext/SupportCandidatePreview桌面双栏手机单栏；SupportView精确消息深链→Agent→候选刷新回读→审批→准确草稿→编辑/存档。既有外部状态not_submitted，无退款/发信工具。
- 完整pytest **374 passed / 125.41s**（新客服32项），Ruff **145文件**，mypy **107app**；Vue lint/type/build通过，Vitest **15文件27项 / 2.74s**；Playwright定向2项13.3s、完整 **34项 / 1.5min**。已实际看桌面候选和手机存档截图，系统Temp soloops-support-{candidate,archived}-{desktop,mobile}.png不提交。74SO/32验收完整，27暂存文件敏感配置检查通过。
- 新测试使用现有导入语言枚举und；注册表断言随两项新技能更新为11。Windows沙箱MySQL10013/Vitest缓存EPERM在允许的普通执行环境复验通过。全部开发测试仅MockTransport/进程替身，无新增真实模型或邮件调用。

## 上一切片：百炼接入

- docs/development 第二十二节、testing 第十七迭代。configured_model 依据 Settings.model_provider 选择 openai_responses 或 dashscope_chat，默认示例关闭；服务端固定官方端点，不接受客户端任意URL。
- DashScopeChatModel 复用有界传输和业务契约，qwen3.7-flash / qwen3.7-flash-2026-07-15 已核对strictJSON支持。Chat消息/response_format严格schema/enable_thinking=false/max_completion_tokens，路由256、生成768，费用预留加官方10-token误差；无工具，最长30s、请求60KB/响应200KB，禁代理/重定向、无自动重试。
- prompt_tokens/completion_tokens映射共同用量；只接收唯一assistant文本且finish_reason=stop。拒答/截断/畸形候选有usage仍记费用；未知usage保留预留。事实ID、审批、来源和业务写权限全部沿用原服务。
- 本机模型已启用 qwen3.7-flash，公开状态configured。配置费率为0.24/0.96 USD每百万token：人民币全档最高目录价1.2/4.8乘保守预算约定1CNY=0.20USD，非实时汇率或实际账单。cost_note在UI和模型步骤配置快照显示。
- 官方鉴权GET /models 200；应用适配器真实合成路由103/11tokens、Listing203/51tokens，daily和完整事实覆盖通过。按<=32K目录档位0.2/0.8元每百万token估算合计¥0.0001108，总预算¥0.01，预留¥0.0030100。两次冒烟不等于完整质量评估；原始回执和拒绝重跑脚本仅在 .local。
- provider标签进入Agent同意文案、候选、历史版本，CandidateInput及Agent引擎白名单接受dashscope_chat。真实问数质量尚未单独验，客服/运营模型切片继续。
- 完整pytest **342 passed / 110.58s**；百炼新增19项，模型相关定向91。Ruff143文件、mypy106app；Vue lint/type/build；Vitest14文件24项；完整Playwright32项/1.2min全部通过。既有Starlette/httpx弃用提示仍在。
- main提交前检查本机密钥不在暂存diff，忽略路径无暂存。74SO/32验收完整。

## 上一切片：模型 Listing 候选

- development二十一节、testing十六。template=listing_model：product_context→compose_listing→listing_candidate（待审批）→verify；原listing事实模板保留。
- listing_composition.py为完整参数行建立ID。标题=完整商品名+最多3条完整参数，描述必须含全部去重参数一次；<=100行。模型只选择/排序事实ID及offer_draft/needs_review，未知/重复/遗漏/额外字段/长度越界阻断；check_content再验。
- 两项发送同意与expected_product_source_row_id绑定预览源行。对象/目标/范围/预算变化清空同意；服务核对owner/shop/identity/source。供应商仅见goal/name/facts，SKU/成本/文件名/旧版/订单不发送。
- 网络前和回包后校验来源、规则、租约、版本、本地生效Listing基线；保存时再核对。暂停/取消/来源变更丢弃正文但记已知费，清除后不恢复正文，未知费不能重发。显式恢复可能重新计费。
- Agent候选批准后ListingService.save_candidate保存draft，再在Listing页确认事实独立审批生效。去重包含来源/基线/内容/engine/失效世代；草稿/来源/步骤/审计同事务，verify回读。依赖当前商品及比较基线，清除任一依赖擦除全文。
- 九项内置技能，listing_candidate为R1受控服务。商品深链带shop/product与准确身份；候选双栏/手机单栏完整差异。上版pytest323、Vitest24、Playwright32及CI通过。

## 已有业务基础与不变量

- development各节涵盖账号/经营空间、CSV/XLSX映射纠错模板与批次、确定性经营分析、Listing版本、客服政策与模板、库存快照、今日运营、持久Agent、新品利润、经营规则、R1授权、R2测试外发、跨店总览、统一驾驶舱。
- 所有资源owner/shop约束；用户→店铺→来源→派生锁序，锁后当前读+populate_existing避免RR旧快照；Decimal/Numeric金额，UTC持久化、显式IANA显示。来源恢复不自动复活旧审批，清除正文和派生依赖。
- 导入键：商品shop+SKU，订单shop+order+line，消息shop+channel+message_id，库存shop+channel+SKU；source_row_id与批次版本决定当前投影，撤销不复活已撤销祖先。
- 分析时间窗[start,end)最长366天，最多10000行，按当前同身份同币种采购成本估历史毛利。未知不补零，不宣称净利润，不跨币种排名。订单统计全店所选身份，渠道只绑定经营规则。
- question流程question_plan→metrics→explain_analysis→analysis_todo→verify。事实目录coverage/totals/fees+最多20匿名SKU，不发送订单号/SKU/文件名；模型只选择fact_ids/check_ids/next_action，服务再验，金额和句子本地渲染，coverage/fees强制保留。正常两次模型调用，各自预算预留。
- offer_todo需要审批，AnalyticsService.save_and_create_todo同事务保存和去重；已完成待办不因重跑归零。完成/重开有expected_version，clear擦解释及正文。test_analysis_model.py和桌面/手机E2E验证。
- 客服订单号不证明身份，关联必须人工核验全部当前源行；政策按同店/渠道/身份/语言/市场/主题/UTC有效区间筛选。退款/冲突/无可信物流/未知语言转人工。草稿存档不表示已发送，政策和来源清除擦整稿，policy_epoch防复活。
- 库存只读有时效快照及显式阈值，缺失为unknown，各渠道不擅自合并，不从订单推算库存。
- 今日运营四类候选：待核履约、有效低库存、消息需回复核对、完整已知成本低毛利。缺物流/广告/平台数据标未检查，不以导入时间伪装导出时间。单项10000行/最多500候选，超限整体拒绝。
- 运营去重绑定范围/规则/相关口径/来源集合，重跑保留处理状态。来源状态与处理状态独立，过期禁止批准；源清除擦snapshot/note/due/审计详情。
- R1预授权绑定预览范围/规则/来源/次数/有效期，调用受控服务前再核验，支持撤销/消耗记录；无通用扩大权限。
- R2 Resend默认关闭，绑定本人发件/测试收件箱、域验证+邮箱验证码；单次审批或限一次预授权。每摘要至多提交一次，未知只读回查；收件声明另存，真实通道仍待凭据/授权，绝不可伪造送达。
- 跨店总览按owner和选中店铺有界锁、按币种分组、显式时区日历比较，保存源依赖，缺费用/过期/无导出时间明确标记。所有摘要为本地存档。
- 统一驾驶舱十种业务表UNION ALL元数据，owner约束、稳定keyset、只读无执行，未知优先；深链精确打开原审批详情。前端请求epoch丢弃迟到回包，失败清旧数据；原服务继续决定权限。

## 下一步

1. 核对517d497的CI37878451567，失败则先修复。读取AGENTS、冻结稿和矩阵、development运营/Agent/模型相关节。日常开发服务已运行；不要在不检查进程和来源的情况下杀端口。
2. 继续P0 **MVP01运营模型解释**。先官方资料/references，复用generate、费用/租约/来源与经营规则门禁、当前provider工厂。确定性检查保持全部数据分支/缺失，模型仅编排受控事实与核对建议。明确将发送的数据范围和授权，保存内部候选复用OperationsService审批/去重/回读；不得获得外发/退款/发货权限。做完桌面手机、文档与测试，再回审23个P0最小模块和32本地适用验收，推进剩余缺口/P1/P2。
3. 真实模型已配置，但后续自动化开发使用MockTransport/替身；不要把本次两次合成请求当作真实客服质量或许可发送客户数据。额外费用与敏感业务数据仍按任务明确授权处理，先完成独立本地实现。
4. 每切片完成测试和文档，再提交/推送main与重点context-memory。保持74SO/32验收，P0整体仍未完成；完整本地适用项结束后推进P1/P2。
