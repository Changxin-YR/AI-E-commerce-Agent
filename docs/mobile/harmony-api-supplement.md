# 鸿蒙订单账单审阅接口补充

更新：2026-10-11。V1.3 的 H14 要求审阅保存与历史；已有 `POST /shops/{shop_id}/statements/orders/reconcile` 负责即时核对。本补充增加6个路由操作，原21功能标识/149条API引用继续作为R2追溯基线。

所有路径以下列前缀开始：`/api/shops/{shop_id}/order-statement-reviews`。复用当前用户与店铺权限、业务身份/渠道、原Decimal金额和UTC来源时间。

| 方法/后缀 | 作用 |
|---|---|
| POST `/preview` | 输入 scope、review_id（新建为空）、version（新建0）、conclusion，返回 snapshot 与 preview_hash |
| POST 根路径 | 在上述输入上增加 preview_hash、request_id UUID、confirm=true，保存或追加版本 |
| GET 根路径 | data_identity、channel、before 游标，返回 items 与 next_cursor |
| GET `/{review_id}` | 当前存档；可用 version 查询指定历史正文 |
| GET `/{review_id}/current` | 回读当前来源核对结果，同时保留历史存档 |
| POST `/{review_id}/{action}` | action 为 withdraw 或 clear；输入 version、request_id、confirm=true |

scope 使用原 OrderReconciliationScope，包含明确销售口径 sale_basis/basis_note；conclusion 包含 outcome（consistent、differences_recorded、pending）和必填 note。无可核对记录或存在待核对比较时，只能保存 pending；consistent 不得存在金额差异，differences_recorded 必须存在差异。

保存过程锁定用户/店铺，重新计算原核对服务、核对预览摘要与版本，保存不超过2MiB的证据和最多100个修订。相同请求UUID可回读已完成结果；更改输入必须使用新UUID。来源批次依赖沿用原审阅依赖表，来源撤销使存档过期，来源清除擦除各版本正文。已保存记录的当前重新核对不重写历史结论。

迁移 `b42e83f516c0` 接在移动会话迁移 `a31e72d405bf` 后，为 statement_reviews 增加 kind，既有行默认 fees，新订单审阅为 orders。费用审阅和订单审阅分别限制读取/分页/写入域，共享既有版本表与来源清理。存在订单审阅记录时拒绝降级删除 kind，保留数据和审计。

移动入口 `/order-reconciliation`，兼容 `/statements/order-reconciliation`，审阅ID query 为 review。界面以订单、账单、金额组成、差异原因和来源详情展示结果；预览与确认绑定同一份输入，未知写入保留原请求用于回读。
