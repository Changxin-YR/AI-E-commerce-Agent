<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { leavePrompt, leaveBlocked, finishLeaving } from '@/composables/useLeaveProtection'
import {
  connectionNotice,
  checkingConnection,
  checkConnection,
} from '@/composables/useAndroidShell'
const dialog = ref<HTMLDialogElement>()
watch(leavePrompt, async (open) => {
  await nextTick()
  if (open) dialog.value?.showModal()
  else dialog.value?.close()
})
</script>
<template>
  <aside v-if="connectionNotice" class="connection-notice" role="status">
    <span>{{ connectionNotice }}</span>
    <button class="button secondary" :disabled="checkingConnection" @click="checkConnection()">
      {{ checkingConnection ? '检查中…' : '检查连接' }}
    </button>
    <button class="button secondary" aria-label="关闭连接提示" @click="connectionNotice = ''">
      关闭
    </button>
  </aside>
  <dialog
    ref="dialog"
    class="leave-dialog"
    aria-labelledby="leave-title"
    @cancel.prevent="finishLeaving(false)"
  >
    <h2 id="leave-title">{{ leaveBlocked ? '请先完成当前操作' : '离开当前编辑？' }}</h2>
    <p v-if="leaveBlocked">请等待正在进行的请求结束，或先在页面保存、放弃当前编辑，再离开。</p>
    <p v-else>当前内容尚未保存。继续编辑可保留输入，离开会放弃这些修改。</p>
    <div class="button-group">
      <button class="button primary" autofocus @click="finishLeaving(false)">继续编辑</button>
      <button v-if="!leaveBlocked" class="button secondary" @click="finishLeaving(true)">
        放弃并离开
      </button>
    </div>
  </dialog>
</template>
