# G-06 本人邮件验收记录

结果：通过。2026-10-10完成QQ客户端授权码核验、本人验证码真实收件验证、经营摘要全文单次批准、SMTP接受、用户实际收件声明及重启持久回读。A-13/B-07及B-08邮件段通过。业务资料为G-04/G-05同组合成资料。

## 配置与迁移

09:01（本文时间均为Asia/Shanghai），用户完成本机客户端授权码填写后，使用生产QQMailProvider连接`smtp.qq.com:465`，验证TLS证书并完成SMTP AUTH。账号和授权码保存在被忽略的本机配置中。

使用保留G-04/G-05资料的3309独立验收库，依据店铺#2的归属和真实登录会话核对owner#1。迁移前导出一致性备份`foundation-qq-before-20261010-010136`，位于忽略的`.local/backups`；从`7e7851694067`升级至`92c7ea53bd10`。64张表记录数保持一致，除迁移表及本次增加列的两张邮件表外，其余表CHECKSUM全部一致。G-05费用账本文件哈希保持一致。

主代码运行的隔离API读取3309数据，关闭模型和调度。真实HTTP登录后，通道回读为`provider=qq_smtp`、`configured=true`、`status=disconnected`；收发地址与用户提供的本人QQ邮箱一致。

## 验证码真实提交与本人邮箱验证

向用户展示本人收发地址、主题「SoloOps 测试邮箱验证」及完整模板后，用户明确同意发送这1封。09:07:48通过生产受控API`/api/shops/2/outbound/channel/connect`提交一次，返回通道#1、`status=verifying`并保存SMTP接受关联标识。生产适配器仅在SMTP DATA最终250后返回accepted；随后只读API回查一致。

用户从本人QQ邮件取得8位数字，09:09:47通过生产API核验，通道#1变为active，保存verified_at并清空验证码哈希。验证码和真实邮箱地址不提交文档。

## 经营摘要批准、提交与收件

重新回读同店运营检查#4，来源状态current；经API生成经营摘要#1/version1。收发地址均为本人邮箱，主题「SoloOps 测试经营摘要 · 检查 #4」，[全文](foundation-mail-review.md)来自同组合成资料。实际地址、主题和正文完整展示后，用户明确回复「已核对，同意发送这 1 封摘要」。

09:12:48通过`/outbound/messages/1/approve`取得mode=once的审批#1；09:12:49调用`/send`一次。服务在网络发送前持久化授权消耗和提交标识，返回`status=accepted`、`provider_event=smtp_accepted`、version3，保存关联标识和稳定Message-ID。审批状态used、max_uses=1、used_count=1；随后实际GET与提交响应完全一致。地址、全文、来源版本及内容指纹均与获批预览相同。

用户确认「已在收件箱收到，地址和正文一致」，明确对应上述主题、09:12提交以及完整预览。09:15:25经`/outbound/messages/1/receipt`保存用户收件声明，可复查位置为本人QQ收件箱中的该主题邮件，按发送时间定位。`received_at`记录声明保存时间，不能当作精确投递时间。此次证据由SMTP接受结果和用户收件确认分别组成；未另行读取用户邮箱或核验邮件原文头。

本次真实提交总计2封：1封验证码、1封经营摘要。数据库只读核对为1个验证通道、1条经营摘要、1次已消耗审批，均无重试。SMTP关联标识和完整实际响应保存在本机忽略证据中。

## 重启与跨流程回读

收件声明保存后，关闭临时外发开关，实际停止并重新启动本次API进程；模型、外发和调度均关闭。原会话、经营摘要接受状态、全文、标识、收件声明和已使用一次的审批保持一致；通道可用状态按关闭配置显示not_configured，历史结果不变。

重启前后再次回读G-05的6个真实模型执行、分析历史、Listing历史和运营检查，9份快照与原结果完全一致。付费账本仍7次、目录估算0.0007750元、未知费用0，邮件验收未新增模型调用。结合既有贯通场景、G-04持久恢复和G-05真实四流程，B-08连续场景完成。

## 代码与证据

QQ功能提交`383ca25e9c7f7e6894b4a2a45fd156fac3ce4d6a`的[CI 38010808357](https://github.com/Changxin-YR/AI-E-commerce-Agent/actions/runs/38010808357)已核实completed/success。本阶段没有修改应用代码，沿用该提交的719项后端、98项前端单元和桌面/手机邮件验证。真实验证步骤见testing第三十四节。

忽略目录`.local/foundation-g06`保存migration、smtp-login、verification-result、mailbox-verified、summary-preview/approved/result/readback/receipt、database-audit以及before-restart/after-restart证据。账号、授权码、会话、真实邮箱地址与本机日志不提交。一次性辅助脚本不可作为重发或重新初始化入口。主开发3307库仍须在启用新版本前备份升级，不能沿用3309的账号/店铺绑定。
