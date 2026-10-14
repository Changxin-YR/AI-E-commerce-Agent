<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  text: string
  message: string
  active: boolean
  interrupted: boolean
}>()
const fields: Record<string, string> = {
  intent: '任务方向',
  branch_ids: '运营检查',
  check_ids: '核对建议',
  fact_ids: '统计依据',
  title_fact_ids: '标题依据',
  description_fact_ids: '描述依据',
  intent_ids: '消息诉求',
  policy_ids: '政策依据',
  next_action: '建议后续动作',
}
const labels: Record<string, string> = {
  daily: '今日运营',
  analysis: '经营分析',
  listing: '商品文案',
  support: '客服回复',
  summary: '销售汇总',
  sales: '销售排行',
  low_margin: '低毛利核对',
  blocked: '需要人工处理',
  unsupported: '超出支持范围',
  coverage: '核对数据覆盖范围',
  source_coverage: '核对文件与订单范围',
  order_review: '核对订单履约',
  low_inventory: '核对库存与补货',
  message_review: '核对回复进度',
  cost_basis: '核对采购成本',
  refund_basis: '核对折扣与退款',
  fees: '补充费用依据',
  identity: '核对客户与订单关联',
  tracking: '核对物流依据',
  permissions: '核对操作权限',
  finish: '完成本轮分析',
  offer_todo: '提交待办供审批',
  offer_tasks: '提交经营事项供审批',
  offer_draft: '提交草稿供审批',
  handoff: '交由人工处理',
}
const selections = computed(() => {
  const items: { key: string; label: string; value: string }[] = []
  // Only complete string values already received from the model become preview labels.
  // This does not validate the model's choices or authorize a business action.
  for (const match of props.text.matchAll(/"([a-z_]+)"\s*:\s*(\[[^\]]*\]?|"(?:\\.|[^"\\])*")/g)) {
    const field = match[1] ?? ''
    if (!fields[field]) continue
    for (const token of (match[2] ?? '').matchAll(/"((?:\\.|[^"\\])*)"/g)) {
      const raw = token[1] ?? ''
      let value: string
      try {
        value = JSON.parse(`"${raw}"`) as string
      } catch {
        continue
      }
      const key = `${field}:${value}`
      if (items.some((item) => item.key === key)) continue
      const numbered = /^(branch|fact|policy)_(\d+)$/.exec(value)
      const caption =
        labels[value] ??
        (numbered
          ? `${{ branch: '检查项', fact: '事实', policy: '政策' }[numbered[1] ?? ''] ?? '依据'} ${numbered[2]}`
          : value)
      items.push({ key, label: fields[field]!, value: caption })
    }
  }
  return items.slice(-8)
})
</script>

<template>
  <section class="agent-stream" aria-label="实时执行进度" :aria-busy="active">
    <p class="stream-status" role="status">{{ message }}</p>
    <p v-if="active && text">AI 正在生成 · 已收到 {{ text.length }} 个字符，内容待校验。</p>
    <p v-else-if="active">执行结果会实时更新，完成后可查看依据并处理待审批事项。</p>
    <p v-else-if="interrupted">请刷新执行记录核对结果，系统不会自动重发本次请求。</p>
    <div v-if="text" class="stream-content" aria-label="AI 生成预览">
      <strong>AI 当前选择 · 待校验</strong>
      <ul v-if="selections.length">
        <li v-for="item in selections" :key="item.key">
          <span>{{ item.label }}</span> {{ item.value }}
        </li>
      </ul>
      <pre v-else class="stream-fragment">{{ text.slice(-280) }}</pre>
    </div>
    <details v-if="text">
      <summary>{{ active ? '查看实时模型输出（待校验）' : '查看模型生成过程' }}</summary>
      <pre>{{ text }}</pre>
      <small>模型生成片段可能不完整，业务结果以执行记录中的校验结果为准。</small>
    </details>
  </section>
</template>

<style scoped>
.agent-stream {
  margin-top: 20px;
  padding: 18px 20px;
  border: 1px solid var(--line);
  border-left: 3px solid var(--green);
  border-radius: 12px;
  overflow-wrap: anywhere;
}
.agent-stream p {
  margin: 0 0 10px;
}
.stream-status {
  font-weight: 600;
}
.agent-stream summary {
  cursor: pointer;
}
.stream-content {
  margin: 14px 0;
}
.stream-content ul {
  margin: 10px 0;
  padding-left: 20px;
}
.stream-content li {
  padding: 4px 0;
}
.stream-content li span {
  color: var(--muted);
  margin-right: 8px;
}
.agent-stream pre {
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 12px;
}
</style>
