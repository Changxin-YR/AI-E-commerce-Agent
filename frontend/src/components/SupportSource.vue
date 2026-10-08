<script setup lang="ts">
import { ref, watch } from 'vue'
import { analyticsApi } from '@/api/analytics'
import { errorMessage } from '@/api/client'
import type { SourceDetail, SourceReference } from '@/types/analytics'
import FeedbackBanner from './FeedbackBanner.vue'

const props = defineProps<{ shopId: number; source: SourceReference }>()
const detail = ref<SourceDetail | null>(null)
const error = ref('')
const busy = ref(false)
watch(
  () => [props.shopId, props.source.row_id],
  () => {
    detail.value = null
    error.value = ''
  },
)
async function inspect(): Promise<void> {
  const row = props.source.row_id
  const shop = props.shopId
  error.value = ''
  busy.value = true
  try {
    const result = await analyticsApi.source(shop, row)
    if (shop === props.shopId && row === props.source.row_id) detail.value = result
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <details class="support-source">
    <summary>
      来源：{{ source.filename }} · 批次 {{ source.batch_id }} · 第 {{ source.row_number }} 行
    </summary>
    <p>
      {{ source.data_identity === 'synthetic' ? '合成测试数据' : '用户导入数据' }} · 导出时间
      {{ source.exported_at ?? '未知' }}（UTC）
    </p>
    <button class="button secondary" :disabled="busy" @click="inspect">查看来源原始行</button>
    <FeedbackBanner :message="error" />
    <div v-if="detail" role="region" aria-label="来源原始值">
      <p>批次状态：{{ detail.batch_status }}</p>
      <dl>
        <template v-for="(value, key) in detail.raw" :key="key"
          ><dt>{{ key }}</dt>
          <dd class="preserve-text">{{ value }}</dd></template
        >
      </dl>
      <details>
        <summary>规范化值</summary>
        <pre>{{ JSON.stringify(detail.normalized, null, 2) }}</pre>
      </details>
    </div>
  </details>
</template>
