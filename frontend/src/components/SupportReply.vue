<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { intentLabels, replyStatus, supportTime, type ReplyDraft } from '@/types/support'
import { sourceStatus } from '@/types/listings'
import SupportSource from './SupportSource.vue'
import { agentLabels } from '@/types/agent'
const props = defineProps<{ item: ReplyDraft; shopId: number; timezone: string; busy: boolean }>()
const emit = defineEmits<{
  edit: [text: string]
  action: [action: 'handoff' | 'archive' | 'reopen']
  dirty: [value: boolean]
}>()
const text = ref('')
const dirty = computed(() => text.value !== (props.item.snapshot?.reply ?? ''))
watch(
  () => [props.item.id, props.item.version],
  () => {
    text.value = props.item.snapshot?.reply ?? ''
  },
  { immediate: true },
)
watch(dirty, (value) => emit('dirty', value))
const editable = computed(
  () => props.item.source_status === 'current' && props.item.status !== 'archived',
)
</script>
<template>
  <section class="section-block support-reply" aria-label="客服草稿详情">
    <div class="section-heading">
      <h2>回复草稿 #{{ item.id }}</h2>
      <span class="outline-label">{{ replyStatus[item.status] }} · v{{ item.version }}</span>
    </div>
    <p>
      {{
        item.engine === 'manual'
          ? '人工编辑'
          : item.engine === 'local_rules'
            ? '本地规则模板'
            : (agentLabels[item.engine] ?? item.engine)
      }}
      · {{ sourceStatus[item.source_status] }} · 外部未提交
    </p>
    <p>
      更新于
      {{
        supportTime(item.updated_at, timezone)
      }}。存档只记录处理状态，退款及其他业务操作仍需单独处理。
    </p>
    <template v-if="item.snapshot">
      <div class="support-tags">
        <span v-for="intent in item.snapshot.intents" :key="intent" class="outline-label">{{
          intentLabels[intent]
        }}</span>
      </div>
      <div class="support-handoff">
        <h3>人工接管摘要</h3>
        <p>{{ item.snapshot.handoff_summary }}</p>
        <ul v-if="item.snapshot.model_facts?.length">
          <li v-for="fact in item.snapshot.model_facts" :key="fact">{{ fact }}</li>
        </ul>
        <ul v-if="item.snapshot.reasons.length">
          <li v-for="reason in item.snapshot.reasons" :key="reason">{{ reason }}</li>
        </ul>
        <p v-else>请人工核对原文、适用范围和回复内容后处理。</p>
      </div>
      <details>
        <summary>本次草稿依据</summary>
        <p class="preserve-text">{{ item.snapshot.message.body }}</p>
        <SupportSource :shop-id="shopId" :source="item.snapshot.message.source" />
        <div v-for="order in item.snapshot.orders" :key="order.source.row_id">
          <p>
            订单 {{ order.order_id }} / {{ order.line_id }} · {{ order.sku }} · {{ order.status }} ·
            文件履约状态 {{ order.fulfillment_status }}
          </p>
          <SupportSource :shop-id="shopId" :source="order.source" />
        </div>
        <div v-for="policy in item.snapshot.policies" :key="policy.id" class="support-policy-quote">
          <h3>{{ policy.data?.title }} · 本地 v{{ policy.number }}</h3>
          <p>出处 {{ policy.data?.source }} · 来源版本 {{ policy.data?.source_version }}</p>
          <p class="preserve-text">{{ policy.data?.text }}</p>
        </div>
      </details>
      <form class="listing-edit" @submit.prevent="emit('edit', text)">
        <div class="form-field">
          <label for="reply-body">回复正文（仅草稿）</label
          ><textarea
            id="reply-body"
            v-model="text"
            rows="8"
            maxlength="6000"
            :disabled="busy || !editable"
          />
        </div>
        <p v-if="dirty">有未保存修改，请先保存正文。</p>
        <button class="button secondary" :disabled="busy || !editable || !dirty || !text.trim()">
          保存修改
        </button>
      </form>
      <div class="button-row">
        <button
          class="button secondary"
          :disabled="busy || dirty || !editable || item.status === 'human_review'"
          @click="emit('action', 'handoff')"
        >
          标记需要人工
        </button>
        <button
          v-if="item.status !== 'archived'"
          class="button primary"
          :disabled="busy || dirty"
          @click="emit('action', 'archive')"
        >
          存档处理记录
        </button>
        <button
          v-else
          class="button secondary"
          :disabled="busy || item.source_status !== 'current'"
          @click="emit('action', 'reopen')"
        >
          重新打开并转人工
        </button>
      </div>
      <p v-if="item.source_status === 'stale'">
        依据已失效。请刷新消息与政策，重新核验后生成新草稿。
      </p>
    </template>
    <p v-else>关联来源已清除，正文和证据快照已擦除，保留编号、状态和时间记录。</p>
  </section>
</template>
