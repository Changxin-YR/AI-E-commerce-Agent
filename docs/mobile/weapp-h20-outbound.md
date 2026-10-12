# 微信 H20：受控测试外发（W10）

更新：2026-10-12。范围：`docs/requirements/SoloOps-Mobile-V1.3.md` H20、`contracts/ui-contract.json` 的 `r2.outbound`（14 个动作）、SO-031/SO-067。

## 页面与动作

原生 `pages/outbound`（`/outbound`）单页覆盖全部 14 个动作，动作与后端路由一一对应：

| 分组 | 动作 | 实现要点 |
|---|---|---|
| 通道状态 | `GET /shops/{id}/outbound/channel` | 展示 provider、`configured`、状态标签、发件/收件地址与验证邮件主题和模板 |
| 通道连接 | `POST /channel/connect`、`/channel/{channel_id}/verify`、`/channel/{channel_id}/revoke` | 连接前强制勾选知情确认并二次弹窗；8 位数字验证码先本地校验；撤销前二次确认并核对通道 ID 未变化 |
| 待审摘要 | `GET/POST /messages` | 关联当前有效运营检查（`operations/runs` 且 `source_status=current`）；QQ SMTP 可改收件地址，地址先本地校验 |
| 正文 | `PATCH /messages/{id}` | 主题单行 1–200 字、全文 1–12000 字；保存使原审批失效；未保存时阻止切换对象并启用返回提醒 |
| 审批 | `POST /messages/{id}/approve`、`/approvals/{approval_id}/revoke`、`/reject` | 单次批准 10 分钟内有效、预授权 1–24 小时限 1 次；同意后单次批准在同一动作内接着 `send`；拒绝与撤销均二次确认 |
| 提交 | `POST /messages/{id}/send` | 按有效授权提交 1 次，提交前弹窗重申不可撤回 |
| 回查与收件 | `POST /messages/{id}/reconcile`、`/receipt` | 只读回查（可选 UUID）；人工收件证据 5–500 字并勾选声明，明确人工声明不改变服务器状态 |

## 状态门禁

客户端镜像服务端门禁（`services/outbound-policy.ts` 的 `mailActions`），与服务端 `OutboundService` 保持一致：

- `edit`/`reject`：仅 `draft` 且来源 `current` 且未提交。
- `approve`：在可编辑基础上要求通道 `active`。
- `send`：要求存在 `active` 审批授权；来源非 `current` 或已提交一律不提供。
- `reconcile`：已提交且非 `sending` 且正文未清除。
- `receipt`：`accepted`，或 QQ SMTP 的 `unknown`，且正文未清除。
- 未知写入结果保留“先回读”提示，不自动重发、不更换请求标识。

## 隔离替身与费用说明

本地与 CI 不触达真实通道：真实付费模型、邮件与平台写入沿用隔离替身，页面文案明确通道接受/报告送达不等于实际收件，费用由用户套餐与配额决定。

## 离线验证（2026-10-12）

- `npm run type-check` 退出 0；`npm test` 含新增 `outbound-policy` 7 项；`npm run build:weapp` 退出 0，产物含 `dist/pages/outbound/index.js`。
- `git diff --check` 无输出；静态契约校验 PASS。
- 未执行微信开发者工具交互、真实后端数据库旅程与任何真实邮件发送；这些与 H11–H19 一起在集中验收阶段执行。
