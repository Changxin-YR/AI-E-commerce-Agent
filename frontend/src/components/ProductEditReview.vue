<script setup lang="ts">
import { ref, watch } from 'vue'
import type { EditAction, EditSaved } from '@/types/productEdits'
import { editStatuses } from '@/types/productEdits'
import { qualityChannels } from '@/types/productQuality'
import SupportSource from './SupportSource.vue'

const props = defineProps<{ edit: EditSaved; busy: boolean }>()
const emit = defineEmits<{ decide: [action: EditAction] }>()
const confirmed = ref(false)
const control = ref<'reject' | 'withdraw' | 'clear'>('clear')
const controlConfirmed = ref(false)
watch(
  () => [props.edit.id, props.edit.version, props.edit.preview_hash, props.busy],
  () => {
    confirmed.value = false
    controlConfirmed.value = false
  },
)
watch(control, () => {
  controlConfirmed.value = false
})
</script>
<template>
  <section class="form-panel section-block" aria-label="修订差异与审批">
    <div class="section-title">
      <h2>修订 #{{ edit.id }}</h2>
      <strong role="status">{{ editStatuses[edit.status] }}</strong>
    </div>
    <RouterLink :to="`/product-edits?shop=${edit.shop_id}&edit=${edit.id}`"
      >修订固定链接</RouterLink
    >
    <p v-if="edit.status === 'applied'">
      本批已执行 {{ edit.snapshot?.items.length }} 项，当前
      {{ edit.current_count }} 项仍为主档来源。后续导入或修订可能覆盖历史结果。
    </p>
    <p v-if="['failed', 'stale'].includes(edit.status)">请重新加载当前商品，核对后建立新草稿。</p>
    <template v-if="edit.snapshot">
      <p>
        {{ edit.snapshot.data_identity === 'synthetic' ? '合成测试数据' : '用户导入数据' }} ·
        {{ qualityChannels[edit.snapshot.channel] }}
      </p>
      <p class="preserve-text">修订依据：{{ edit.snapshot.reason }}</p>
      <p>
        仅修改本地商品名称与参数，金额沿用来源；平台尚未同步。店铺数据版本变化或任一项冲突则整批停止，需重新建立草稿。
      </p>
      <article
        v-for="item in edit.snapshot.items"
        :key="item.product_id"
        class="edit-item"
        :aria-label="`修订 ${item.before.sku}`"
      >
        <h3>
          {{ item.before.sku }} <span class="muted">· {{ item.message }}</span>
        </h3>
        <div class="edit-diff">
          <div>
            <h4>修改前</h4>
            <p class="preserve-text">{{ item.before.name }}</p>
            <pre>{{ item.before.facts || '参数为空' }}</pre>
          </div>
          <div>
            <h4>修改后</h4>
            <p class="preserve-text">{{ item.after.name }}</p>
            <pre>{{ item.after.facts || '参数为空' }}</pre>
          </div>
        </div>
        <SupportSource :shop-id="edit.shop_id" :source="item.source" />
      </article>
      <div v-if="edit.status === 'draft'" class="edit-approval">
        <label class="check-label"
          ><input
            v-model="confirmed"
            type="checkbox"
            :disabled="busy"
          />我已逐项核对差异与事实依据，批准本批本地生效</label
        >
        <button
          class="button primary"
          :disabled="busy || !confirmed"
          @click="emit('decide', 'approve')"
        >
          批准本地生效
        </button>
      </div>
      <details class="edit-control">
        <summary>拒绝、撤销与清除</summary>
        <p>
          撤销按仍有效的历史来源恢复主档；依赖本批的后续人工修订同步失效。清除会擦除本批及依赖修订正文，并恢复可用来源；文件独立版本保留。
        </p>
        <label for="edit-control">处理方式</label>
        <select id="edit-control" v-model="control" :disabled="busy">
          <option value="clear">清除修订正文</option>
          <option v-if="edit.status === 'draft'" value="reject">拒绝草稿</option>
          <option v-if="edit.status === 'applied'" value="withdraw">撤销本地修订</option>
        </select>
        <label class="check-label"
          ><input
            v-model="controlConfirmed"
            type="checkbox"
            :disabled="busy"
          />确认执行所选处理及其依赖影响</label
        >
        <button
          class="button secondary"
          :disabled="busy || !controlConfirmed"
          @click="emit('decide', control)"
        >
          执行所选处理
        </button>
      </details>
    </template>
  </section>
</template>
<style scoped>
.edit-item {
  border-top: 1px solid var(--line);
  margin-top: 1.25rem;
  padding-top: 1rem;
  overflow-wrap: anywhere;
}
.edit-diff {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.edit-diff > div {
  min-width: 0;
  background: var(--surface-soft, #f5f5f2);
  padding: 1rem;
  border-radius: 8px;
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: inherit;
}
.edit-approval,
.edit-control {
  margin-top: 1.5rem;
}
.check-label {
  margin: 1rem 0;
}
@media (max-width: 640px) {
  .edit-diff {
    grid-template-columns: 1fr;
  }
  .section-title {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
