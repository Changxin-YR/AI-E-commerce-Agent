<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import Taro from '@tarojs/taro'
import { account } from '../services/session'
import { safeFilename, type ManualDelivery } from '../services/delivery-policy'
const props = defineProps<{
  contextKey: string
  allowed: boolean
  disabled: boolean
  loadArtifact: () => Promise<ManualDelivery>
}>()
const artifact = ref<ManualDelivery>(),
  busy = ref(false),
  error = ref(''),
  notice = ref('')
let epoch = 0
watch(
  () => [
    props.contextKey,
    props.allowed,
    props.disabled,
    account.shopId,
    account.session?.session_id,
  ],
  () => {
    epoch++
    artifact.value = undefined
    error.value = ''
    notice.value = ''
  },
  { flush: 'sync' },
)
onBeforeUnmount(() => {
  epoch++
  artifact.value = undefined
})
async function deliver(mode: 'preview' | 'copy' | 'csv') {
  if (busy.value || props.disabled || !props.allowed) return
  const token = epoch
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const value = await props.loadArtifact()
    if (token !== epoch || !props.allowed || props.disabled) return
    artifact.value = value
    if (mode === 'copy') {
      await Taro.setClipboardData({ data: value.plain_text })
      notice.value = '已复制当前核验内容，请人工粘贴并核对；外部未提交。'
    } else if (mode === 'csv') {
      const fs = Taro.getFileSystemManager()
      const filePath = `${Taro.env.USER_DATA_PATH}/soloops-delivery-${Date.now()}.csv`
      try {
        fs.writeFileSync(filePath, value.csv_text, 'utf8')
        await Taro.shareFileMessage({
          filePath,
          fileName: safeFilename(value.filename),
        })
        notice.value = '已完成文件分享操作；平台发布和收件情况仍需人工核对。'
      } finally {
        try {
          fs.unlinkSync(filePath)
        } catch {
          /* File may already be removed by the runtime. */
        }
      }
    }
  } catch (cause) {
    if (token === epoch) {
      artifact.value = undefined
      error.value =
        cause instanceof Error ? cause.message : '复制或分享未完成，请重试。'
    }
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <view class="card"
    ><text class="label">当前版本交付</text
    ><text class="hint"
      >每次复制或导出均重新核验版本和来源，并携带店铺、来源、缺项与外部未提交标识。</text
    ><button :disabled="disabled || busy || !allowed" @tap="deliver('preview')">
      核验并查看交付全文</button
    ><text v-if="artifact" class="prose">{{ artifact.plain_text }}</text
    ><text v-if="artifact" class="hint">核验时间 {{ artifact.checked_at }}</text
    ><button :disabled="disabled || busy || !allowed" @tap="deliver('copy')">
      核验并复制全文</button
    ><button :disabled="disabled || busy || !allowed" @tap="deliver('csv')">
      核验并导出 / 分享 CSV</button
    ><text v-if="error" class="error">{{ error }}</text
    ><text v-if="notice" class="hint">{{ notice }}</text></view
  >
</template>
<style scoped>
.prose {
  display: block;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
