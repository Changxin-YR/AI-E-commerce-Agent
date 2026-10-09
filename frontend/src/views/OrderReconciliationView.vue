<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { identityApi } from '@/api/identity'
import { errorMessage } from '@/api/client'
import { orderReconciliationApi } from '@/api/orderReconciliation'
import type { Shop } from '@/types/identity'
import type { OrderReconciliation, OrderReconciliationScope } from '@/types/orderReconciliation'
import { qualityChannels } from '@/types/productQuality'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import OrderReconciliationResult from '@/components/OrderReconciliationResult.vue'

const route = useRoute()
const shops = ref<Shop[]>([])
const shopId = ref(0)
const scope = reactive<OrderReconciliationScope>({
  data_identity: 'user_import',
  channel: 'generic',
  timezone: 'UTC',
  start_at: `${new Date().toISOString().slice(0, 7)}-01T00:00:00Z`,
  end_at: new Date().toISOString(),
  sale_basis: 'unknown',
  basis_note: '',
})
const result = ref<OrderReconciliation | null>(null)
const busy = ref(false)
const loading = ref(false)
const error = ref('')
const canRead = computed(
  () =>
    shopId.value &&
    !loading.value &&
    !busy.value &&
    (scope.sale_basis === 'unknown' || scope.basis_note.trim()),
)
let epoch = 0
let initializeEpoch = 0
let alive = true
function invalidate(): void {
  epoch++
  busy.value = false
  result.value = null
  error.value = ''
}
function resetBasis(): void {
  scope.sale_basis = 'unknown'
  scope.basis_note = ''
}
watch(
  () => [
    shopId.value,
    scope.data_identity,
    scope.channel,
    scope.timezone,
    scope.start_at,
    scope.end_at,
  ],
  resetBasis,
  { flush: 'sync' },
)
watch(() => [shopId.value, ...Object.values(scope)], invalidate, { flush: 'sync' })
async function initialize(): Promise<void> {
  const current = ++initializeEpoch
  invalidate()
  resetBasis()
  loading.value = true
  try {
    const response = await identityApi.shops()
    if (!alive || current !== initializeEpoch) return
    shops.value = response
    shopId.value =
      response.find((s) => s.id === Number(route.query.shop))?.id ?? response[0]?.id ?? 0
    scope.timezone = response.find((s) => s.id === shopId.value)?.timezone ?? 'UTC'
    scope.data_identity = route.query.identity === 'synthetic' ? 'synthetic' : 'user_import'
    const channel = route.query.channel
    scope.channel =
      channel === 'shopify' || channel === 'amazon' || channel === 'other' ? channel : 'generic'
  } catch (cause) {
    if (alive && current === initializeEpoch) error.value = errorMessage(cause)
  } finally {
    if (alive && current === initializeEpoch) loading.value = false
  }
}
async function reconcile(): Promise<void> {
  if (!canRead.value) return
  invalidate()
  const current = epoch
  busy.value = true
  try {
    const response = await orderReconciliationApi.reconcile(shopId.value, { ...scope })
    if (alive && current === epoch) result.value = response
  } catch (cause) {
    if (alive && current === epoch) error.value = errorMessage(cause)
  } finally {
    if (alive && current === epoch) busy.value = false
  }
}
function focused(): void {
  invalidate()
  resetBasis()
}
watch(
  () => [route.query.shop, route.query.identity, route.query.channel],
  () => {
    void initialize()
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
      <h1>订单与账单，差异有据。</h1>
      <p>关联销售与退款来源，逐项查看金额差异及待补依据。</p>
    </div>
    <span class="outline-label">订单金额核对</span>
  </div>
  <section class="data-note">
    <span class="note-symbol" aria-hidden="true">i</span>
    <div>
      <h3>当前导入记录 · 只读核对</h3>
      <p>
        窗口选取候选，同订单号的窗口外记录作为关联依据。文件覆盖完整性未知；退款缺逐笔交易信息，保留待核。
      </p>
    </div>
  </section>
  <RouterLink :to="`/statements?shop=${shopId}`" class="button secondary"
    >返回账单与费用</RouterLink
  >
  <FeedbackBanner :message="error" />
  <button v-if="error && !shops.length" class="button secondary" @click="initialize">
    重新加载店铺
  </button>
  <p v-if="loading" role="status">正在读取店铺…</p>
  <p v-else-if="!shops.length">请先在<RouterLink to="/settings">经营资料</RouterLink>添加店铺。</p>
  <section v-if="shops.length" class="form-panel section-block">
    <form @submit.prevent="reconcile">
      <fieldset :disabled="loading">
        <legend>核对范围与金额口径</legend>
        <div class="form-grid">
          <div class="form-field">
            <label for="order-check-shop">所属店铺</label
            ><select id="order-check-shop" v-model="shopId">
              <option v-for="shop in shops" :key="shop.id" :value="shop.id">
                {{ shop.name }} · {{ shop.code }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label for="order-check-identity">数据身份</label
            ><select id="order-check-identity" v-model="scope.data_identity">
              <option value="user_import">用户实际记录</option>
              <option value="synthetic">合成测试数据</option>
            </select>
          </div>
          <div class="form-field">
            <label for="order-check-channel">来源渠道</label
            ><select id="order-check-channel" v-model="scope.channel">
              <option v-for="(label, key) in qualityChannels" :key="key" :value="key">
                {{ label }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label for="order-check-start">开始时间（含偏移）</label
            ><input id="order-check-start" v-model="scope.start_at" required />
          </div>
          <div class="form-field">
            <label for="order-check-end">结束时间（含偏移）</label
            ><input id="order-check-end" v-model="scope.end_at" required />
          </div>
          <div class="form-field">
            <label for="order-check-zone">核对显示时区（IANA）</label
            ><input id="order-check-zone" v-model="scope.timezone" required />
          </div>
        </div>
        <p>
          包含开始、不含结束，最多 366 天。窗口与关联查询各最多 1000 行订单及 1000 行销售/退款账单。
        </p>
        <div class="form-field section-block">
          <label for="order-check-basis">销售金额口径</label
          ><select id="order-check-basis" v-model="scope.sale_basis">
            <option value="unknown">尚未核实金额组成，仅查看待核依据</option>
            <option value="merchandise_after_discount">已核实两侧均为折后商品款（退款前）</option>
          </select>
        </div>
        <p>
          选择可比口径表示已核实本范围两侧金额均不含运费、税费和其他调整。来源格式混杂时请保留未知。
        </p>
        <div v-if="scope.sale_basis !== 'unknown'" class="form-field">
          <label for="order-check-note">两侧金额组成依据</label
          ><textarea
            id="order-check-note"
            v-model="scope.basis_note"
            required
            maxlength="500"
            rows="3"
            placeholder="填写原文件及列名、金额组成说明；不包含客户个人信息"
          />
        </div>
        <div class="form-actions section-block">
          <RouterLink
            :to="`/imports?shop=${shopId}&kind=orders&identity=${scope.data_identity}&channel=${scope.channel}`"
            class="button secondary"
            >查看或导入订单</RouterLink
          >
          <RouterLink
            :to="`/imports?shop=${shopId}&kind=statements&identity=${scope.data_identity}&channel=${scope.channel}`"
            class="button secondary"
            >查看或导入账单</RouterLink
          >
          <button class="button primary" :disabled="!canRead">读取销售与退款待核清单</button>
        </div>
      </fieldset>
    </form>
  </section>
  <p v-if="busy" role="status">正在读取当前订单与账单…</p>
  <OrderReconciliationResult v-if="result" :key="epoch" :result="result" :shop-id="shopId" />
  <p v-else-if="shops.length && !busy" class="section-block">
    选择范围后读取当前来源。修改范围或返回页面后，请重新核实口径并读取。
  </p>
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
