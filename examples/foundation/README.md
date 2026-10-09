# 基础版本统一合成样本

在项目根目录运行：

```powershell
python scripts/foundation_samples.py --output .local/foundation-samples-20261009
```

目录必须不存在。生成器只创建明确标记的合成文件，不读取或修改用户文件；默认以当前UTC提前5分钟为锚点，也可用`--as-of 2026-10-09T12:00:00+00:00`复现固定时刻。过几天重新验收时新建另一个目录，按manifest中的窗口和政策有效期操作，旧样本自然过期。

建立单独合成店铺（USD、Asia/Shanghai），按manifest的`files`顺序导入，全部选择“合成测试数据”，渠道逐文件对应：商品generic，主订单amazon，缺成本和EUR边界订单shopify，库存与消息amazon。预览确认后应有3商品、5订单行、3库存、2消息。另有3份政策在manifest中，可从客服政策页录入并核对来源。

主流程选择amazon/USD及manifest时间窗：销售75、当前成本62、已知商品毛利13、购买数量4；SYN-CUP为低毛利、低库存及客户咨询共同商品。EUR订单属于shopify渠道，在全部渠道USD统计中排除。全部渠道USD销售87，因shopify缺成本，完整成本及毛利未知；混合币种也会暂停完整毛利排行。库存SYN-BOX已过期，不能当作有效低库存。今日检查形成5个候选：履约核对1、低库存1、消息2、低毛利1。

`orders-duplicate-synthetic.csv`用于验证同批业务键重复的错误预览，不应确认导入。重复上传已确认的原文件不会增加当前投影行数。`products-revised-synthetic.csv`将SYN-CUP成本改为19，明确确认覆盖后主范围成本65、毛利10，旧分析/审批应提示来源变化。

客户SYN-FAQ可依据faq政策形成待审草稿；SYN-MIXED同时提出物流与退款，必须转人工且不能确认退款或未知物流。草稿、存档和真实发送分别验收。四流程共用此样本，真实模型也仅使用这些合成资料；真实邮件另需本人通道及本次许可。

完整连续浏览器场景及本轮实际结果见`docs/foundation-acceptance.md`。预期值是验收输入，不表示已执行通过。
