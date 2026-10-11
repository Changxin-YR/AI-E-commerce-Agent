<script setup lang="ts">
import { ref } from 'vue'
import type { SourceReference } from '../services/scope-types'
import { openLink } from '../services/navigation'
defineProps<{ sources: SourceReference[]; shopId: number }>()
const count = ref(5),
  error = ref('')
async function open(id: number, shop: number) {
  try {
    await openLink('/imports', { batch: String(id), shop: String(shop) })
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '无法打开依据'
  }
}
</script>
<template>
  <view
    ><text v-if="!sources.length" class="hint">未提供来源行。</text
    ><view
      v-for="source in sources.slice(0, count)"
      :key="`${source.batch_id}-${source.row_id}`"
      class="source"
      ><text class="hint"
        >{{ source.filename }} · {{ source.sheet_name }} · 第
        {{ source.row_number }} 行</text
      ><text class="hint"
        >{{ source.data_identity }} · 批次 #{{ source.batch_id }} · 来源行 #{{
          source.row_id
        }}
        · {{ source.origin || 'file_import' }}</text
      ><text class="hint"
        >导出 {{ source.exported_at || '未知' }} · 导入
        {{ source.imported_at }}</text
      ><button @tap="open(source.batch_id, shopId)">查看来源批次</button></view
    ><button v-if="sources.length > count" @tap="count += 10">
      更多来源（{{ sources.length }}）</button
    ><text v-if="error" class="error">{{ error }}</text></view
  >
</template>
<style scoped>
.source {
  border-top: 1rpx solid #dce7e0;
  margin-top: 16rpx;
  padding-top: 16rpx;
}
</style>
