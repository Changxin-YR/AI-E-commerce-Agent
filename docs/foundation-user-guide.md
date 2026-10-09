# SoloOps 基础版本使用与维护

当前版本正在按[发布验收](foundation-acceptance.md)执行验证。四条流程和所需条件见[规格](foundation-release.md)，以下路径持续与实际实现核对；只有验收记录中的实际通过结果作为交付证据。

## 安装与首次使用

环境：Python3.11、uv、Node.js24.16+（Windows）与Docker Desktop。按照[README本地启动](../README.md#本地启动)的setup_local.py生成本机配置、启动MySQL、安装锁定依赖、alembic升级、交互建账号与启动API/前端步骤。密钥仅填忽略配置；不要把密码写在命令参数、截图或共享日志中。初始化发现根.env、backend/.env或.local/test.env任一已存在时，会在写入前拒绝覆盖。

登录后先创建经营资料与店铺，再经导入页上传商品、订单、消息和库存。用[统一合成样本](../examples/foundation/README.md)可复现四流程；选择合成测试身份及每份文件标明的渠道，预览字段与错误行后确认。样本应有3商品、5订单行、3库存和2消息；Amazon/USD销售75、当前采购成本62、已知商品毛利13。业务文件可仅导入所需类型，缺数据时补充资料。

### 独立演练首次安装

已有工作库时，可在项目.local下用已提交源码建立全新副本。以下名称须尚未使用；不要在有业务配置的目录执行初始化或更改连接目标：

```powershell
git archive --format=zip --output=.local/foundation-install.zip HEAD
Expand-Archive -LiteralPath .local/foundation-install.zip -DestinationPath .local/foundation-install
cd .local/foundation-install
python scripts/setup_local.py
```

仅编辑新副本生成的配置：根.env中MYSQL_PORT设为3309；backend/.env中数据库URL的端口设为3309、库名设为soloops_foundation_install_test，保留随机口令；显式设置SOLOOPS_MODEL_ENABLED=false、SOLOOPS_OUTBOUND_ENABLED=false、SOLOOPS_SCHEDULER_ENABLED=true。若使用8002 API和5175前端，SOLOOPS_TRUSTED_ORIGINS设为JSON数组`["http://127.0.0.1:8002","http://127.0.0.1:5175"]`。

在新副本增加compose.install.yaml：

```yaml
services:
  mysql:
    environment:
      MYSQL_DATABASE: soloops_foundation_install_test
```

新终端清除先前导出的SOLOOPS配置变量，防止环境变量优先级覆盖新配置。确认3309、8002、5175空闲，再执行：

```powershell
docker compose -p soloops-foundation-install --env-file .env -f compose.yaml -f compose.install.yaml up -d --wait mysql
cd backend
uv sync --frozen --python 3.11
uv run alembic upgrade head
uv run python -m app.cli create-user foundation_owner
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8002 --no-access-log
```

另开终端进入新副本frontend，执行`npm ci`及`npm run build`。设置`$env:SOLOOPS_API_TARGET='http://127.0.0.1:8002'`后运行`npm run dev -- --port 5175`，打开127.0.0.1:5175，用新账号走经营资料→店铺→合成导入。项目名隔离容器、网络和卷；命令只启动新项目mysql，不启动固定3308端口的mysql-test。已有开发配置与数据库不参与演练。

### 关闭、重启和调度恢复

前台启动时，在API与前端各自终端按Ctrl+C关闭；先等待在途操作结束。只关闭API时，MySQL持久数据保留；重新执行相同启动命令后，原账号、会话和业务记录可回读。后台进程应先核实监听端口、程序路径及父子进程身份再停止，勿使用历史PID批量结束Python进程。

SOLOOPS_SCHEDULER_ENABLED=false关闭该API实例的自动调度，但已有计划与到期时刻保留。所有连接同一数据库的API实例均关闭调度后，才是整个库暂停自动检查。重新启用后，轮询每30秒检查一次；停机错过多期时只考虑最近一期，24小时恢复窗口内执行，窗口外记为missed。计划页“暂停”使计划next_run_at为空，“恢复”按当前配置计算下一次未来时刻；与单纯关闭API有不同语义。

定时运营生成待审批执行，继续审批前不会保存业务待办；真实模型与外发不由本地定时器调用。恢复后先回读通知、原执行和next_run_at，确认只新增一个周期。应用关闭后可在该副本根目录执行相同`docker compose -p ... --env-file ... -f ...`前缀加`stop mysql`；保持卷即可下次恢复。

## 四条日常流程

1. 今日运营：选择范围→检查及依据→审批候选→打开对象处理→记录核对结论→完成/延期/忽略或重开→再次检查。完成核对仅记录卖家的处理事实，外部履约和库存以实际渠道记录为准。
2. 经营问数：明确范围与问题→确认模型数据和预算→业务服务计算→展开公式与原行→审批保存→处理分析待办→补数据后重算并核对历史状态。
3. Listing：定位商品→核对事实与本次模型范围→生成、编辑和比较→保存待审版本→批准或拒绝→回读当前本地版本和历史→返回关联事项。平台发布独立于本地版本审批。
4. 客服：定位原消息→核验订单与政策→候选或人工接管→审阅编辑→保存草稿/人工处理结论→回读状态与依据。未发送草稿保留待发送；手动渠道处理需记录事实和凭据。R2经营报告测试邮件通过单独通道、本人邮箱验证和全文单次审批执行。

## 维护与故障恢复

每次升级前先等待在途操作结束，关闭全部API实例及其他数据库写入程序（API内的本地调度随进程停止），保持MySQL容器运行。然后在项目根目录备份，名称必须尚不存在：

```powershell
python scripts/database_backup.py backup --service mysql --name before-upgrade-20261009
docker compose --profile test up -d --wait mysql-test
python scripts/database_backup.py restore --name before-upgrade-20261009 --target soloops_restore_upgrade_20261009_test
```

输出位于`.local/backups/<name>/`，包含`backup.sql`和`manifest.json`。保存当前Git提交与配置版本；备份含业务正文、账号哈希和会话，应放在受控或加密存储中。它不包含被忽略的模型/邮件凭据，本机配置需另行安全保管。代码仓库不接收数据库备份。

工具使用现有容器的MySQL客户端，以InnoDB一致性事务导出并核对备份前后状态，备份期间不要迁移或修改表结构。恢复先验证SHA256，然后只在`mysql-test`创建新的`soloops_restore_<name>_test`库；已有库会拒绝覆盖。导入使用仅获该目标库权限的临时账号，完成或失败后移除账号，目标库保留供回读。结果核对全部表行数、数据校验值及迁移head；单次失败保留现场，修正后用新名称重试。

`mysql-test`采用tmpfs，容器停止或重建会丢失其测试和恢复库；SQL备份文件仍在本机。恢复副本用于升级前演练；切换正式库需另外核对连接配置、账号权限、调度和外发开关。本工具不自动切换业务库。

本轮已将完整桌面/手机贯通场景的合成测试库恢复到独立库，64张表校验一致，完成事项、分析、Listing、客服存档与经营摘要代表记录回读通过，见[B-12记录](foundation-acceptance.md)。服务重启后回读记录与调度历史，未知外发只安全回查。

网络失败时先刷新原记录核实状态；未知模型费用或未知邮件提交不自动重发。来源更新后重新核对与审批；撤销恢复来源不会自动复活旧确认。清除会擦除相关历史正文及依赖，按页面说明操作；保留必要审计状态。

本轮真实模型仅合成数据、人民币1元累计封顶。已完成7次真实调用、目录价估算0.0007750元、费用未知项0，四流程及缺证据/来源变化见[G-05证据](foundation-model-evidence.md)。实际扣款以供应商账单为准。尚未验收真实经营文件。

## 本人测试邮箱验收

当前待验B-07/A-13；已准备[经营摘要全文](foundation-mail-review.md)，来源为同组合成资料的已保存今日运营检查。配置前邮件通道保持关闭。

在本机忽略的backend/.env填写`SOLOOPS_OUTBOUND_API_KEY`、`SOLOOPS_OUTBOUND_SENDER`、`SOLOOPS_OUTBOUND_TEST_RECIPIENT`、已验证发件域的`SOLOOPS_OUTBOUND_DOMAIN_ID`，并将`SOLOOPS_OUTBOUND_OWNER_ID`及`SOLOOPS_OUTBOUND_SHOP_ID`绑定到此次本人合成测试店铺。不得将密钥写入聊天或提交仓库；本轮隔离验收店铺为3309独立库中的#2，账号ID须从该库登录会话核对，不能沿用其他库的编号。

配置就绪且确认使用该通道后才启用`SOLOOPS_OUTBOUND_ENABLED=true`并重启对应API。进入R2测试外发页，核对发件人和本人测试收件人；连接前单独确认验证码邮件，收到后在15分钟内输入8位验证码。若已经完成过同一有效通道验证，先回读状态。

随后选择当前有效的今日运营检查，生成摘要草稿。全文中的“检查记录数”表示该分支读取记录数，候选数量另列。核对实际地址、主题、完整正文及来源有效性后，取得本次摘要发送许可并批准一次，通过原提交按钮执行。保存真实提交回执，再记录本人邮箱实际收到的时间、主题和证据索引；供应商accepted状态与本人实际收件分别记录。若结果unknown，只回查原记录，不重新发送。结束后关闭测试外发开关。
