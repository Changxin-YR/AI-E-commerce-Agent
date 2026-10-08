<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { identityApi } from '@/api/identity'
import { errorMessage } from '@/api/client'
import type { Onboarding } from '@/types/identity'
import FeedbackBanner from '@/components/FeedbackBanner.vue'

const status = ref<Onboarding | null>(null)
const error = ref('')
const loading = ref(true)
async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    status.value = await identityApi.onboarding()
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>把经营的第一步，准备好。</h1>
      <p>先建立经营资料，让后续数据有明确的店铺、币种和时区。</p>
    </div>
    <span class="outline-label">开始使用 SoloOps</span>
  </div>
  <FeedbackBanner :message="error" /><button v-if="error" class="button secondary" @click="load">
    重新加载
  </button>
  <p v-if="loading" role="status">正在读取工作空间…</p>
  <template v-else-if="status">
    <section class="welcome-panel">
      <div>
        <h2>你的经营工作空间</h2>
        <p>从一份商品资料或订单文件开始。每份数据都有来源，每一步操作都能核对。</p>
        <RouterLink class="button primary" to="/settings">{{
          status.profile_complete ? '管理经营资料' : '完善经营资料'
        }}</RouterLink>
      </div>
      <div class="welcome-index" aria-hidden="true">SO<span>START WITH FACTS</span></div>
    </section>
    <section class="section-block" aria-labelledby="preparation">
      <div class="section-title">
        <h2 id="preparation">开始前的准备</h2>
        <span>逐步完善，随时可改</span>
      </div>
      <ol class="setup-list">
        <li>
          <span class="step-index">01</span>
          <div>
            <h3>建立经营档案</h3>
            <p>目标市场、经营类目、默认币种和时区。</p>
          </div>
          <span class="status-tag" :class="{ complete: status.profile_complete }">{{
            status.profile_complete ? '已完成' : '待完善'
          }}</span>
        </li>
        <li>
          <span class="step-index">02</span>
          <div>
            <h3>添加店铺记录</h3>
            <p>用于归属导入数据，按店铺分别管理。</p>
          </div>
          <span class="status-tag" :class="{ complete: status.shop_count > 0 }">{{
            status.shop_count > 0 ? `${status.shop_count} 个店铺` : '待添加'
          }}</span>
        </li>
        <li>
          <span class="step-index">03</span>
          <div>
            <h3>准备业务文件</h3>
            <p>商品、订单行、成本和可选库存；导入向导正在开发。</p>
          </div>
          <span class="status-tag">待开放</span>
        </li>
      </ol>
    </section>
    <section class="data-note">
      <span class="note-symbol" aria-hidden="true">i</span>
      <div>
        <h3>当前为文件分析模式</h3>
        <p>后续分析以你提供的文件及其导出时间为准。当前尚未导入业务数据，也尚未运行 AI 巡检。</p>
      </div>
    </section>
  </template>
</template>
