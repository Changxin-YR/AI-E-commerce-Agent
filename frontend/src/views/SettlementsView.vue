<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { identityApi } from '@/api/identity'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import { qualityChannels } from '@/types/productQuality'
import type { SettlementSnapshot } from '@/types/settlements'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import SettlementRecords from '@/components/SettlementRecords.vue'
import { settlementsApi } from '@/api/settlements'

const route = useRoute()
const shops = ref<Shop[]>([])
const shopId = ref(0)
const scope = reactive<SettlementSnapshot['scope']>({
  data_identity: 'user_import',
  channel: 'generic',
  timezone: 'UTC',
  start_at: `${new Date().toISOString().slice(0, 7)}-01T00:00:00Z`,
  end_at: new Date().toISOString(),
})
const error = ref('')
const busy = ref(false)
const settlementBusy = ref(false)
const ready = ref(false)
const initialSettlement = ref<number | undefined>()
const importLink = computed(
  () =>
    `/imports?shop=${shopId.value}&kind=statements&identity=${scope.data_identity}&channel=${scope.channel}`,
)
let initializeEpoch = 0
let alive = true
watch(
  () => [shopId.value, ...Object.values(scope)],
  () => {
    initialSettlement.value = undefined
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
    initialSettlement.value = undefined
    const settlementId = Number(route.query.settlement)
    if (shopId.value && Number.isSafeInteger(settlementId) && settlementId > 0) {
      const record = await settlementsApi.get(shopId.value, settlementId)
      if (!alive || initializing !== initializeEpoch) return
      if (record.snapshot) Object.assign(scope, record.snapshot.scope)
      else Object.assign(scope, { data_identity: record.data_identity, channel: record.channel })
      initialSettlement.value = settlementId
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
watch(
  () => [route.query.shop, route.query.settlement],
  () => {
    if (alive) void initialize()
  },
)
onMounted(() => {
  void initialize()
})
onUnmounted(() => {
  alive = false
  initializeEpoch++
})
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>结算周期，回款有据。</h1>
      <p>按原账单登记周期，逐笔回读平台记录与卖家到账声明。</p>
    </div>
    <span class="outline-label">结算与回款</span>
  </div>
  <section class="data-note">
    <span class="note-symbol" aria-hidden="true">i</span>
    <div>
      <h3>平台记载与人工到账，分别保留依据</h3>
      <p>一对一同币种才计算差额，人工登记需核验原始凭据。银行证据、文件覆盖和结算余额仍待核。</p>
    </div>
  </section>
  <FeedbackBanner :message="error" />
  <button v-if="error && !shops.length" class="button secondary" @click="initialize">
    重新加载店铺
  </button>
  <p v-if="busy" role="status">正在读取结算范围…</p>
  <p v-if="!busy && !shops.length">
    请先在<RouterLink to="/settings">经营资料</RouterLink>添加店铺。
  </p>
  <section v-if="shops.length" class="form-panel section-block">
    <form @submit.prevent>
      <fieldset :disabled="busy || settlementBusy">
        <legend>新建登记范围</legend>
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
            <label for="statement-start">周期开始（含偏移）</label
            ><input id="statement-start" v-model="scope.start_at" required />
          </div>
          <div class="form-field">
            <label for="statement-end">周期结束（含偏移）</label
            ><input id="statement-end" v-model="scope.end_at" required />
          </div>
          <div class="form-field">
            <label for="statement-zone">周期显示时区（IANA）</label
            ><input id="statement-zone" v-model="scope.timezone" required />
          </div>
        </div>
        <p>
          周期包含开始、不含结束，最多 366 天。每份登记最多 1000 行原账单、50
          笔人工到账凭据；回款及到账日期可在周期之外。
        </p>
        <div class="form-actions">
          <RouterLink :to="importLink" class="button secondary">导入或查看账单批次</RouterLink
          ><RouterLink to="/statements" class="button secondary">账单与费用核对</RouterLink>
        </div>
      </fieldset>
    </form>
  </section>
  <SettlementRecords
    v-if="shopId && ready"
    :key="[shopId, ...Object.values(scope)].join('|')"
    :shop-id="shopId"
    :scope="scope"
    :disabled="busy"
    :initial-id="initialSettlement"
    @busy="settlementBusy = $event"
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
