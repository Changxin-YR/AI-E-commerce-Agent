# R2 C：工程收敛和本地交付门禁计划

B3准确提交8f03f3b的CI38041135924已核实成功，具备本包实施条件。只在合成3308和8001/5174实施，无生产配置变更、真实客户数据、外部付费/发送/写入。

F-08：现有SchedulesView已展示API运行依赖、30秒扫描、24小时补跑窗口、合并周期和暂停恢复语义。缺少不受未读筛选/分页影响的最近自动周期摘要。通过schedules/status新增latest_timer（仅当前owner/shop，排除manual，created_at/id倒序），UI显示最近自动周期保存时间、计划时刻/状态及合并起点。说明API关闭/主机休眠不执行、恢复只处理最近一期、超过窗口记missed；worker_enabled是配置状态，不是持续运行承诺。无新调度引擎、迁移或依赖。

F-09：A1已有parser/validation/catalog与import_groups分层；B1低毛利证据在margin_review，B2格式manual_delivery和组件ReviewedDelivery独立，B3客服交付与证据独立服务/组件。只对实际修改处保持小函数，记录其调用关系，不无故拆分原服务。

F-10：建立上线核对表，逐项列代码证据/合成验证与部署仍缺证据：HTTPS真实域名和代理未验证；Cookie Secure需生产配置与浏览器确认；登录账户锁有回归，IP/入口防护须部署核对；密钥只在忽略配置/SecretStr、验证错误不回显；数据范围及留存待用户经营政策，清除传播已测试；用户店铺隔离定向覆盖；历史备份恢复证据G03/G04有效但本轮新增结构恢复需部署前复验；生产host/origin/Cookie/数据库权限/外部开关未做真实验收。明确保持本地合成/脱敏演示，不提供公共运营就绪结论。

统一卖家旅程：扩展原foundation.spec.ts保留四流程、75/62/13及新成本后10、来源变化和重新登录断言；批准Listing后交付；客服编辑存档后独立审阅、复制下载和登记自报；来源修订后重新生成Listing并审批取得新交付。可加入新来源复检原低毛利事项（若数据仍异常明确保持），保存/回读同一ID。B1受控分支定向证据独立保留。

命令/证据：test_schedules和身份相关定向测试、前端受影响单元/静态构建、schedules和foundation桌面手机；准确提交完整CI。最终数74SO/32原验收/47长期模块核对。无新公开部署条件时C以本地范围完成，未来上线所需证据单独列清，不请求无关许可。

官方研究已于2026-10-10读取：FastAPI Lifespan/HTTPS (MIT) 与OWASP Session Management(CC BY-SA4)，只借鉴进程生命周期与SecureCookie/HTTPS关系，自行实现；B3完成后登记references。链接：
https://fastapi.tiangolo.com/advanced/events/
https://fastapi.tiangolo.com/deployment/https/
https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
