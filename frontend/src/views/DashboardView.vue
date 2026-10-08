<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { identityApi } from '@/api/identity'
import { errorMessage } from '@/api/client'
import type { Onboarding } from '@/types/identity'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import OperationsInbox from '@/components/OperationsInbox.vue'
import WorkInbox from '@/components/WorkInbox.vue'

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
      <h1>今日经营，从事实出发。</h1>
      <p>查看实际运行、审阅草稿与审批，接着处理你的经营事项。</p>
    </div>
    <span class="outline-label">SoloOps 工作台</span>
  </div>
  <FeedbackBanner :message="error" /><button v-if="error" class="button secondary" @click="load">
    重新加载
  </button>
  <p v-if="loading" role="status">正在读取工作空间…</p>
  <template v-else-if="status">
    <WorkInbox />
    <div id="operations"><OperationsInbox /></div>
    <details class="section-block" :open="!status.profile_complete">
      <summary>经营资料与首次使用引导</summary>
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
              <p>商品、订单行与单位采购成本，核对映射后导入。</p>
            </div>
            <RouterLink to="/imports" class="button secondary small">导入文件</RouterLink>
          </li>
        </ol>
      </section>
      <section class="data-note">
        <span class="note-symbol" aria-hidden="true">i</span>
        <div>
          <h3>当前为文件分析模式</h3>
          <p>
            分析以你提供的文件及其导出时间为准。已有商品或订单文件可前往经营分析，查看销售、已知毛利和来源；AI
            模型待配置，今日运营使用本地规则并保留检查记录。
          </p>
          <RouterLink to="/analytics" class="button secondary small">查看经营分析</RouterLink>
        </div>
      </section>
    </details>
  </template>
</template>
