# G-04：首次安装与实际进程恢复

验收日期：2026-10-09（Asia/Shanghai）。业务源码基线`8f6956fb15944015abe798b497a8657923dd6653`，唯一执行代码增量为本次`setup_local.py`配置保护修复；业务API、迁移和前端与该基线一致。对应B-01、B-10及B-12安装部分。

## 隔离边界与安装

从Git已提交源码导出新目录`.local/foundation-g04`，复制本次修正的初始化脚本。该副本独立生成随机配置，没有复制开发.env。Compose项目`soloops-foundation-g04`，独立持久卷`soloops-foundation-g04_mysql-data`；MySQL仅监听127.0.0.1:3309，数据库`soloops_foundation_g04_test`。API为8002，前端为5175。数据库账号仅用于该隔离容器；真实模型和邮件显式关闭。

实际执行现有`setup_local.py`；`uv sync --frozen --python 3.11`建立全新虚拟环境，安装47个锁定包（2.50秒）。MySQL迁移前经只读检查为0张表，随后`python -m alembic upgrade head`到`7e7851694067`、64张表。通过`app.cli create-user --password-stdin`从本地标准输入建立合成账号，口令未放命令参数。前端Node24.16.0执行`npm ci`安装293包、审计0漏洞；`npm run build`的类型检查与225模块生产构建通过，Vite构建1.23秒。

已有Docker与Python/Node工具链及包缓存继续使用；本次证明独立源码配置、虚拟环境、容器和空库初始化，不代表在全新操作系统上安装Docker等前置工具。

## 实际HTTP业务与金额

在运行的Uvicorn上通过原接口登录、保存经营资料、创建店铺、逐份上传映射预览和确认导入，使用`foundation_samples.py`同组动态合成资料。5批次/13原行：3商品、5订单、3库存、2消息，另存2份有出处及有效期的政策。

同店Amazon/USD确定性统计为购买量4、销售75、成本62、已知商品毛利13，金额按Decimal比较。保存1份分析、1份运营检查和5个候选；批准并完成其中1项；同SYN-CUP本地模板Listing获批准；同SYN-MIXED核验订单与政策后进入人工处理并存档；保存1份有来源的跨店经营摘要。Listing与客服的外部状态均为`not_submitted`。本次模型关闭，真实模型质量由G-05另验。

## 实际进程恢复与调度

每次停止前，用Get-NetTCPConnection和Win32_Process核对8002监听者、父进程、隔离venv路径及Uvicorn参数，再仅停止该API进程。未更改系统时间或数据库到期字段，未用测试替身或直接调用tick代替进程恢复。

1. 通过API创建定时运营计划，真实暂停后next_run_at为空；确认恢复后计划为active。下一期为2026-10-09 15:36:00 UTC（北京时间23:36），然后关闭API跨过该时刻。
2. 以scheduler=false启动新进程。原登录会话仍有效，13份业务响应完整匹配，统计金额一致；历史为空、active计划保留原到期时刻。随后保存经营摘要，待核对快照增加为14份。
3. 停止并以scheduler=true重启。启动轮询只恢复一期，状态waiting_approval，模型关闭、spent_usd为0。旧14份快照逐字典比较一致。
4. 通过API批准并推进该执行至succeeded。定时检查窗口与第一次手动窗口不同，低毛利形成新范围候选；待办总数为6，编号1至6。再次停止并启动API，执行仍为succeeded，14份业务响应、这6个编号和1条调度历史全部一致；跨后续轮询再查仍一致，未重复执行已批准动作。

调度历史保存触发时的waiting_approval，当前执行状态从其execution_id回读为succeeded；两者语义不同。最终库只读计数：1账号/1店铺、5导入、2运营检查、6待办、1分析、1批准Listing、1客服存档、1摘要、1定时计划/1周期/1Agent执行，外发记录0。

## 新副本前端与配置保护

对5175新副本运行Chromium1440×1000及390×844：登录、店铺选中、刷新、持久会话回读均通过，页面错误0、横溢0；手机截图已查看。新副本正常前端代理指向8002。

`.env`、`backend/.env`、`.local/test.env`三份原开发配置的SHA256在验收前后相同。数据库3307/3308和API8000未参与本轮初始化或启停。验收后关闭独立前端/API及该项目MySQL，持久卷和新副本保留供回查。

初始化修复的`test_local_setup.py`4项通过（1.01秒）：任一已有配置均在写入前阻断；首次生成开发/测试连接凭据一致且root口令独立，重复运行不修改原文件。最初沙箱临时目录无法创建，改用工作区忽略目录作为pytest basetemp后通过，未改测试要求。Ruff规则及223文件格式检查、mypy158个app文件通过。业务代码未变，因此继承基线业务回归；[8f6956f CI37950996694](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/37950996694)已核实Success，verify9分14秒、总时长9分18秒。

## 复现及证据位置

可提交的安装与调度步骤见[使用维护](foundation-user-guide.md)。本机执行辅助脚本在忽略目录`.local/g04_prepare.py`、`g04_bootstrap.py`、`g04_http.py`、`g04_control.ps1`、`g04_browser.mjs`、`g04_audit.py`，使用实际API及CLI；回读模式不清库。`.local/foundation-g04/.local`保存initial/bootstrap/http-state/final-audit、合成样本和截图。http-state含会话，account及配置含本地凭据，均不提交。复制源码副本及证据亦由.local整体忽略。

G-04通过；B-06本轮真实模型、B-07本人邮件仍待各自真实证据，基础版本保持实施中。
