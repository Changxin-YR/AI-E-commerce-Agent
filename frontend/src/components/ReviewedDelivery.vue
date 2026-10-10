<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { errorMessage } from '@/api/client'
import type { ManualDelivery } from '@/types/manualDelivery'
import FeedbackBanner from './FeedbackBanner.vue'

const props = defineProps<{
  contextKey: string
  allowed: boolean
  disabled: boolean
  loadArtifact: () => Promise<ManualDelivery>
}>()
const busy = ref(false)
const error = ref('')
const notice = ref('')
const fallback = ref('')
let epoch = 0
function reset(): void {
  epoch++
  busy.value = false
  error.value = notice.value = fallback.value = ''
}
watch(() => [props.contextKey, props.allowed, props.disabled], reset, { flush: 'sync' })
onBeforeUnmount(reset)

async function deliver(action: 'copy' | 'download'): Promise<void> {
  if (busy.value || props.disabled || !props.allowed) return
  reset()
  const request = epoch
  busy.value = true
  try {
    const artifact = await props.loadArtifact()
    if (request !== epoch) return
    if (action === 'copy') {
      try {
        await navigator.clipboard.writeText(artifact.plain_text)
        if (request === epoch) notice.value = '已复制通用草稿；请在原渠道人工核对并操作。'
      } catch {
        if (request !== epoch) return
        fallback.value = artifact.plain_text
        notice.value = '浏览器未允许复制。请选中下方全文，手动复制。'
      }
    } else {
      const url = URL.createObjectURL(
        new Blob([artifact.csv_text], { type: 'text/csv;charset=utf-8' }),
      )
      const link = document.createElement('a')
      link.href = url
      link.download = artifact.filename
      document.body.append(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      notice.value = '已准备通用 CSV 下载，请核对下载文件。'
    }
  } catch (cause) {
    if (request === epoch) error.value = errorMessage(cause)
  } finally {
    if (request === epoch) busy.value = false
  }
}
</script>

<template>
  <section class="manual-delivery source-detail" aria-label="人工使用草稿">
    <h3>人工使用草稿</h3>
    <p>包含完整文案、版本和来源，供你在原渠道核对后使用。外部状态保持未提交。</p>
    <p v-if="!allowed" class="muted">仅当前已批准且来源有效的版本可复制或下载。</p>
    <p v-else-if="disabled" class="muted">请先完成当前操作；有修改时须保存并审批新版本。</p>
    <div class="button-row">
      <button
        class="button secondary"
        :disabled="!allowed || disabled || busy"
        @click="deliver('copy')"
      >
        复制通用草稿
      </button>
      <button
        class="button secondary"
        :disabled="!allowed || disabled || busy"
        @click="deliver('download')"
      >
        下载通用 CSV
      </button>
    </div>
    <p v-if="busy" role="status">正在核对版本与来源…</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <FeedbackBanner :message="error" />
    <label v-if="fallback" class="manual-copy">
      手动复制全文
      <textarea
        :value="fallback"
        readonly
        rows="10"
        @focus="($event.target as HTMLTextAreaElement).select()"
      />
    </label>
    <p class="muted">
      CSV
      为通用核对格式。单元格前置单引号用于公式防护，纯文本保留原文；用电子表格再次保存时请重新核对防护标记。
    </p>
  </section>
</template>

<style scoped>
.manual-delivery {
  display: grid;
  gap: 0.75rem;
  margin-block: 1.25rem;
}
.manual-delivery p {
  margin: 0;
  overflow-wrap: anywhere;
}
.manual-copy {
  display: grid;
  gap: 0.5rem;
}
textarea {
  width: 100%;
  min-width: 0;
}
</style>
