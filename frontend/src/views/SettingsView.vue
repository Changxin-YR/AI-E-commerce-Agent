<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { identityApi } from '@/api/identity'
import { errorMessage } from '@/api/client'
import type { SellerProfile, Shop } from '@/types/identity'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import ProfileForm from '@/components/ProfileForm.vue'
import ShopForm from '@/components/ShopForm.vue'

const profile = ref<SellerProfile | null>(null)
const shops = ref<Shop[]>([])
const loading = ref(true)
const showShopForm = ref(false)
const error = ref('')
const notice = ref('')
const route = useRoute()
async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    ;[profile.value, shops.value] = await Promise.all([identityApi.profile(), identityApi.shops()])
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    loading.value = false
    if (!error.value && route.hash === '#shops') {
      await nextTick()
      document.getElementById('shops')?.scrollIntoView({ block: 'start' })
    }
  }
}
function onShopCreated(shop: Shop): void {
  shops.value.push(shop)
  showShopForm.value = false
  notice.value = `店铺“${shop.name}”已添加，当前使用文件模式。`
}
onMounted(load)
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>经营资料</h1>
      <p>让店铺、市场与数据口径各就其位。</p>
    </div>
    <span class="outline-label">工作空间设置</span>
  </div>
  <FeedbackBanner :message="error" /><FeedbackBanner :message="notice" kind="success" />
  <p v-if="loading" role="status">正在读取经营资料…</p>
  <button v-else-if="error" class="button secondary" @click="load">重新加载</button>
  <template v-else>
    <section class="settings-section">
      <div class="section-description">
        <span class="section-index">01 / PROFILE</span>
        <h2>经营档案</h2>
        <p>记录你的经营方向，可稍后完善。<br />币种与时区用于后续分析的默认口径。</p>
      </div>
      <div class="form-panel"><ProfileForm :profile="profile" @saved="profile = $event" /></div>
    </section>
    <section id="shops" class="settings-section" aria-labelledby="shops-heading">
      <div class="section-description">
        <span class="section-index">02 / STORES</span>
        <h2 id="shops-heading">店铺记录</h2>
        <p>每份业务数据归属到具体店铺。添加后点击该店铺的“导入文件”，核对模板并上传第一份资料。</p>
      </div>
      <div class="form-panel">
        <div class="section-title">
          <h3>
            我的店铺 <span class="count">{{ shops.length }}</span>
          </h3>
          <button v-if="!showShopForm" class="button secondary small" @click="showShopForm = true">
            添加店铺
          </button>
        </div>
        <ShopForm v-if="showShopForm" @created="onShopCreated" @cancel="showShopForm = false" />
        <div v-if="shops.length" class="shop-list">
          <article v-for="shop in shops" :key="shop.id" class="shop-row">
            <div class="shop-monogram" aria-hidden="true">{{ shop.name.slice(0, 1) }}</div>
            <div class="shop-details">
              <h4>{{ shop.name }}</h4>
              <p>{{ shop.code }} · {{ shop.market }} · {{ shop.currency }}</p>
              <small>{{ shop.timezone }}</small>
              <div>
                <RouterLink :to="{ path: '/imports', query: { shop: shop.id } }"
                  >导入文件</RouterLink
                >
              </div>
            </div>
            <span class="status-tag">文件模式</span>
          </article>
        </div>
        <div v-else-if="!showShopForm" class="empty-state">
          <h4>给第一份数据一个归属</h4>
          <p>添加一个店铺记录，之后按店铺导入和查看业务数据。</p>
        </div>
        <p class="panel-footnote">记录来源平台仅用于文件归类；平台连接与授权状态将单独验证。</p>
      </div>
    </section>
  </template>
</template>
