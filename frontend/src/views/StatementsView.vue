<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { identityApi } from '@/api/identity'
import { statementsApi } from '@/api/statements'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import { qualityChannels } from '@/types/productQuality'
import type { StatementReconciliation } from '@/types/statements'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import StatementResult from '@/components/StatementResult.vue'
import FeeRules from '@/components/FeeRules.vue'
import StatementReviews from '@/components/StatementReviews.vue'
import { statementReviewsApi } from '@/api/statementReviews'

const route = useRoute()
const shops = ref<Shop[]>([])
const shopId = ref(0)
const scope = reactive<StatementReconciliation['scope']>({
  data_identity: 'user_import',
  channel: 'generic',
  timezone: 'UTC',
  start_at: `${new Date().toISOString().slice(0, 7)}-01T00:00:00Z`,
  end_at: new Date().toISOString(),
})
const result = ref<StatementReconciliation | null>(null)
const error = ref('')
const busy = ref(false)
const ruleBusy = ref(false)
const reviewBusy = ref(false)
const reviewFreshness = ref(0)
const ready = ref(false)
const initialReview = ref<number | undefined>()
const importLink = computed(
  () =>
    `/imports?shop=${shopId.value}&kind=statements&identity=${scope.data_identity}&channel=${scope.channel}`,
)
let epoch = 0
let initializeEpoch = 0
let alive = true
function invalidate(): void {
  epoch++
  result.value = null
}
watch(
  () => [shopId.value, ...Object.values(scope)],
  () => {
    invalidate()
    initialReview.value = undefined
  },
  { flush: 'sync' },
)
async function initialize(): Promise<void> {
  const initializing = ++initializeEpoch
  busy.value = true
  ready.value = false
  error.value = ''
  try {
    const response = await identityApi.shops()
    if (!alive || initializing !== initializeEpoch) return
    shops.value = response
    shopId.value =
      response.find((s) => s.id === Number(route.query.shop))?.id ?? response[0]?.id ?? 0
    scope.timezone = response.find((s) => s.id === shopId.value)?.timezone ?? 'UTC'
    initialReview.value = undefined
    const reviewId = Number(route.query.review)
    if (shopId.value && Number.isSafeInteger(reviewId) && reviewId > 0) {
      const record = await statementReviewsApi.get(shopId.value, reviewId)
      if (!alive || initializing !== initializeEpoch) return
      if (record.snapshot) Object.assign(scope, record.snapshot.result.scope)
      else Object.assign(scope, { data_identity: record.data_identity, channel: record.channel })
      initialReview.value = reviewId
    }
  } catch (cause) {
    if (alive && initializing === initializeEpoch) error.value = errorMessage(cause)
  } finally {
    if (alive && initializing === initializeEpoch) {
      busy.value = false
      ready.value = true
    }
  }
}
async function reconcile(): Promise<void> {
  if (!shopId.value || busy.value) return
  invalidate()
  const current = epoch
  const request = { ...scope }
  busy.value = true
  error.value = ''
  try {
    const response = await statementsApi.reconcile(shopId.value, request)
    if (alive && current === epoch) result.value = response
  } catch (cause) {
    if (alive && current === epoch) error.value = errorMessage(cause)
  } finally {
    if (alive) busy.value = false
  }
}
function focused(): void {
  // Hide a previous read after changes in another tab, including while a request is in flight.
  invalidate()
}
function rulesInvalidated(): void {
  invalidate()
  reviewFreshness.value++
}
watch(
  () => [route.query.shop, route.query.review],
  () => {
    if (alive) void initialize()
  },
)
onMounted(() => {
  void initialize()
  window.addEventListener('focus', focused)
})
onUnmounted(() => {
  alive = false
  initializeEpoch++
  invalidate()
  window.removeEventListener('focus', focused)
})
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>账单与费用，逐行核对。</h1>
      <p>从原始账单到人工凭据，保留每一处差异的依据。</p>
    </div>
    <span class="outline-label">渠道账单</span>
  </div>
  <section class="data-note">
    <span class="note-symbol" aria-hidden="true">i</span>
    <div>
      <h3>文件账单 · 回款到账待核</h3>
      <p>销售款、退款、费用和平台记载回款分开合计。文件覆盖及费用完整性未知，无法确定净利润。</p>
    </div>
  </section>
  <FeedbackBanner :message="error" />
  <button v-if="error && !shops.length" class="button secondary" @click="initialize">
    重新加载店铺
  </button>
  <p v-if="busy" role="status">正在读取账单与费用…</p>
  <p v-if="!busy && !shops.length">
    请先在<RouterLink to="/settings">经营资料</RouterLink>添加店铺。
  </p>
  <section v-if="shops.length" class="form-panel section-block">
    <form @submit.prevent="reconcile">
      <fieldset :disabled="busy || ruleBusy || reviewBusy">
        <legend>核对范围</legend>
        <div class="form-grid">
          <div class="form-field">
            <label for="statement-shop">所属店铺</label
            ><select id="statement-shop" v-model="shopId">
              <option v-for="shop in shops" :key="shop.id" :value="shop.id">
                {{ shop.name }} · {{ shop.code }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label for="statement-identity">数据身份</label
            ><select id="statement-identity" v-model="scope.data_identity">
              <option value="user_import">用户实际记录</option>
              <option value="synthetic">合成测试数据</option>
            </select>
          </div>
          <div class="form-field">
            <label for="statement-channel">来源渠道</label
            ><select id="statement-channel" v-model="scope.channel">
              <option v-for="(label, key) in qualityChannels" :key="key" :value="key">
                {{ label }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label for="statement-start">开始时间（含偏移）</label
            ><input id="statement-start" v-model="scope.start_at" required />
          </div>
          <div class="form-field">
            <label for="statement-end">结束时间（含偏移）</label
            ><input id="statement-end" v-model="scope.end_at" required />
          </div>
          <div class="form-field">
            <label for="statement-zone">核对显示时区（IANA）</label
            ><input id="statement-zone" v-model="scope.timezone" required />
          </div>
        </div>
        <p>包含开始、不含结束，最多 366 天、1000 行账单及 1000 笔费用；两侧按各自发生时间筛选。</p>
        <div class="form-actions">
          <RouterLink :to="importLink" class="button secondary">导入或查看账单批次</RouterLink
          ><button class="button primary">读取并核对</button>
        </div>
      </fieldset>
    </form>
  </section>
  <FeeRules
    v-if="shopId"
    :key="[shopId, ...Object.values(scope)].join('|')"
    :shop-id="shopId"
    :scope="scope"
    :disabled="busy || reviewBusy"
    @busy="ruleBusy = $event"
    @invalidated="rulesInvalidated"
    @changed="reconcile"
  />
  <StatementResult v-if="result" :result="result" :shop-id="shopId" />
  <p v-else-if="shops.length && !busy" class="section-block">
    选择范围后读取当前记录。数据修订、页面切换或返回后，请重新核对。
  </p>
  <StatementReviews
    v-if="shopId && ready"
    :key="[shopId, ...Object.values(scope)].join('|')"
    :shop-id="shopId"
    :scope="scope"
    :disabled="busy || ruleBusy"
    :freshness="reviewFreshness"
    :initial-id="initialReview"
    @busy="reviewBusy = $event"
    @invalidated="invalidate"
  />
</template>
<style scoped>
fieldset {
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}
legend {
  font-weight: 600;
  margin-bottom: 16px;
}
</style>
