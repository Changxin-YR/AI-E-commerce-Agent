<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import type { PreparedImport, SplitProgress } from '@/lib/csvSplit'
import FeedbackBanner from './FeedbackBanner.vue'

defineProps<{ disabled: boolean }>()
const emit = defineEmits<{ prepared: [value: PreparedImport | null]; busy: [value: boolean] }>()
const working = ref(false)
const error = ref('')
const progress = ref<SplitProgress | null>(null)
const inputKey = ref(0)
let worker: Worker | undefined
function stop(): void {
  const wasWorking = working.value
  worker?.terminate()
  worker = undefined
  working.value = false
  if (wasWorking) emit('busy', false)
}
function cancel(): void {
  stop()
  progress.value = null
  inputKey.value++
  emit('prepared', null)
}
function choose(event: Event): void {
  const file = (event.target as HTMLInputElement).files?.[0]
  cancel()
  error.value = ''
  if (!file) return
  try {
    const active = new Worker(new URL('../workers/csvSplit.worker.ts', import.meta.url), {
      type: 'module',
    })
    worker = active
    working.value = true
    emit('busy', true)
    active.onmessage = (
      message: MessageEvent<{ progress?: SplitProgress; result?: PreparedImport; error?: string }>,
    ) => {
      if (worker !== active) return
      if (message.data.progress) progress.value = message.data.progress
      else {
        error.value = message.data.error ?? ''
        emit('prepared', message.data.result ?? null)
        stop()
      }
    }
    active.onerror = () => {
      error.value = '本机拆分未完成，请检查可用内存或联系管理员协助。'
      stop()
    }
    active.postMessage(file)
  } catch {
    error.value = '浏览器无法启动文件处理，请更新浏览器或联系管理员。'
    stop()
  }
}
onBeforeUnmount(stop)
</script>

<template>
  <div class="form-field">
    <label for="browser-csv">选择原始大报表 CSV（本机拆分／恢复）</label>
    <input
      :key="inputKey"
      id="browser-csv"
      type="file"
      accept=".csv"
      :disabled="disabled || working"
      @change="choose"
    />
    <small
      >UTF-8 CSV，最多40 MiB、40000条记录、20片。Excel请先将目标工作表另存为CSV
      UTF-8。原文件在本机检查，分片由你逐片上传和确认。</small
    >
    <p v-if="working" role="status">
      正在本机校验与拆分：{{ progress?.rows ?? 0 }}条记录，已解析{{
        progress ? Math.floor((progress.bytes / progress.totalBytes) * 100) : 0
      }}%。
    </p>
    <button v-if="working" class="button secondary" @click="cancel">取消本机拆分</button>
    <FeedbackBanner :message="error" />
  </div>
</template>
