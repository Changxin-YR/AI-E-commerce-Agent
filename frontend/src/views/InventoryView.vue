<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { identityApi } from '@/api/identity'
import { inventoryApi } from '@/api/inventory'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import type { InventoryResult, InventoryScope } from '@/types/inventory'
import { supportTime } from '@/types/support'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import SourceEvidence from '@/components/SupportSource.vue'

const shops = ref<Shop[]>([])
const shopId = ref(0)
const scope = reactive<InventoryScope>({
  data_identity: 'user_import',
  channel: 'generic',
  max_age_hours: 24,
  search: '',
  offset: 0,
})
const result = ref<InventoryResult | null>(null)
const error = ref('')
const busy = ref(false)
const timezone = computed(
  () => shops.value.find((s) => s.id === shopId.value)?.timezone ?? 'Asia/Shanghai',
)
const labels = { low: '低于安全阈值', above_threshold: '未低于安全阈值', unknown: '当前库存未知' }

async function load(offset = 0): Promise<void> {
  if (busy.value || !shopId.value) return
  busy.value = true
  error.value = ''
  result.value = null
  scope.offset = offset
  try {
    result.value = await inventoryApi.list(shopId.value, { ...scope })
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
function refresh(): void {
  void load(scope.offset)
}
onMounted(async () => {
  window.addEventListener('focus', refresh)
  try {
    shops.value = await identityApi.shops()
    shopId.value = shops.value[0]?.id ?? 0
    await load()
  } catch (cause) {
    error.value = errorMessage(cause)
  }
})
onUnmounted(() => window.removeEventListener('focus', refresh))
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>库存判断，从快照出发。</h1>
      <p>核对可售数量、快照时间和你设定的安全阈值。</p>
    </div>
    <RouterLink class="button primary" to="/imports">导入库存快照</RouterLink>
  </div>
  <FeedbackBanner :message="error" />
  <section class="data-note">
    <span class="note-symbol" aria-hidden="true">i</span>
    <div>
      <h3>库存是可选数据</h3>
      <p>
        没有快照的 SKU 库存未知，仍可使用经营分析、Listing
        和客服。各渠道分别核对，订单不会自动扣减本地快照。
      </p>
    </div>
  </section>
  <section v-if="shops.length" class="form-panel section-block">
    <form @submit.prevent="load()">
      <fieldset :disabled="busy" class="inventory-filters">
        <legend>库存查询范围</legend>
        <div class="form-grid">
          <div class="form-field">
            <label for="stock-shop">所属店铺</label
            ><select id="stock-shop" v-model="shopId" @change="load()">
              <option v-for="shop in shops" :key="shop.id" :value="shop.id">
                {{ shop.name }} · {{ shop.code }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label for="stock-identity">数据身份</label
            ><select id="stock-identity" v-model="scope.data_identity" @change="load()">
              <option value="user_import">用户导入文件</option>
              <option value="synthetic">合成测试数据</option>
            </select>
          </div>
          <div class="form-field">
            <label for="stock-channel">来源渠道</label
            ><select id="stock-channel" v-model="scope.channel" @change="load()">
              <option value="generic">通用 / 自建表</option>
              <option value="shopify">Shopify</option>
              <option value="amazon">Amazon</option>
              <option value="other">其他来源</option>
            </select>
          </div>
          <div class="form-field">
            <label for="stock-age">快照有效时长（小时）</label
            ><input
              id="stock-age"
              v-model.number="scope.max_age_hours"
              type="number"
              min="1"
              max="720"
              required
            /><small>查询规则，默认 24 小时；请按来源更新频率调整后刷新。</small>
          </div>
          <div class="form-field">
            <label for="stock-search">搜索 SKU</label
            ><input id="stock-search" v-model="scope.search" maxlength="120" />
          </div>
        </div>
        <div class="form-actions">
          <span>安全阈值来自已确认的导入行；修改阈值请重新导入并核对差异。</span
          ><button class="button primary">刷新库存</button>
        </div>
      </fieldset>
    </form>
  </section>
  <p v-if="busy" role="status">正在核对快照…</p>
  <section v-if="!shops.length && !busy" class="form-panel section-block empty-state">
    <h2>先添加店铺记录</h2>
    <RouterLink to="/settings" class="button secondary">经营资料</RouterLink>
  </section>
  <section v-if="result" class="section-block" aria-label="库存核对结果">
    <div class="section-title">
      <h2>已导入快照</h2>
      <span>来源版本 {{ result.source_revision }}</span>
    </div>
    <p class="muted">
      核对时间 {{ supportTime(result.checked_at, timezone) }} · 本次时效
      {{ result.scope.max_age_hours }} 小时
    </p>
    <p class="muted">{{ result.note }}</p>
    <div v-if="!result.items.length" class="form-panel empty-state">
      <h3>库存未知 / 未检查</h3>
      <p>此范围没有可用快照。请检查店铺、渠道和数据身份，或导入库存文件。</p>
    </div>
    <article
      v-for="item in result.items"
      :key="item.id"
      class="form-panel section-block inventory-item"
    >
      <div class="section-title">
        <h3>{{ item.sku }}</h3>
        <span class="status-tag" :class="{ complete: item.status === 'above_threshold' }">{{
          labels[item.status]
        }}</span>
      </div>
      <p>
        <strong>快照可售 {{ item.available }}</strong> · 安全阈值 {{ item.safety_threshold }}
      </p>
      <p>{{ item.reason }}</p>
      <p class="muted">
        快照时间 {{ supportTime(item.snapshot_at, timezone) }} · 有效至
        {{ supportTime(item.valid_until, timezone) }}
      </p>
      <SourceEvidence
        :key="`${result.source_revision}-${item.source.row_id}`"
        :shop-id="shopId"
        :source="item.source"
      />
    </article>
    <div class="form-actions">
      <button
        class="button secondary"
        :disabled="busy || scope.offset === 0"
        @click="load(Math.max(0, scope.offset - 50))"
      >
        上一页</button
      ><span>每页最多 50 条</span
      ><button
        class="button secondary"
        :disabled="busy || !result.has_more"
        @click="load(scope.offset + 50)"
      >
        下一页
      </button>
    </div>
  </section>
</template>

<style scoped>
.inventory-filters {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.inventory-item {
  overflow-wrap: anywhere;
}
@media (max-width: 640px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .inventory-item .section-title {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.75rem;
  }
}
</style>
