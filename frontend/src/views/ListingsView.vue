<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { linkedId, linkedShop, revealRecord } from '@/composables/deepLink'
import { identityApi } from '@/api/identity'
import { listingsApi } from '@/api/listings'
import { errorMessage } from '@/api/client'
import {
  listingStatus,
  sourceStatus,
  type ListingContent,
  type ListingVersion,
  type ProductFacts,
  type ProductWorkspace,
} from '@/types/listings'
import type { Shop } from '@/types/identity'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import ListingReview from '@/components/ListingReview.vue'

const shops = ref<Shop[]>([])
const route = useRoute()
const shopId = ref(0)
const products = ref<ProductFacts[]>([])
const history = ref<ListingVersion[]>([])
const workspace = ref<ProductWorkspace | null>(null)
const selected = ref<ListingVersion | null>(null)
const query = ref('')
const offset = ref(0)
const busy = ref(false)
const error = ref('')
const success = ref('')
const timezone = computed(
  () => shops.value.find((s) => s.id === shopId.value)?.timezone ?? 'Asia/Shanghai',
)
async function action(work: () => Promise<void>): Promise<void> {
  if (busy.value) return
  busy.value = true
  error.value = ''
  success.value = ''
  try {
    await work()
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function loadHistory(): Promise<void> {
  history.value = await listingsApi.history(shopId.value)
}
async function selectShop(): Promise<void> {
  workspace.value = null
  selected.value = null
  products.value = []
  history.value = []
  offset.value = 0
  if (!shopId.value) return
  await action(async () => {
    products.value = await listingsApi.products(shopId.value, query.value, 0)
    await loadHistory()
  })
}
async function search(page = 0): Promise<void> {
  await action(async () => {
    products.value = await listingsApi.products(shopId.value, query.value, page)
    offset.value = page
  })
}
async function choose(product: ProductFacts): Promise<void> {
  await action(async () => {
    workspace.value = await listingsApi.workspace(shopId.value, product.product_id)
    selected.value = null
  })
}
async function show(item: Pick<ListingVersion, 'id'>): Promise<void> {
  await action(async () => {
    selected.value = await listingsApi.get(shopId.value, item.id)
    workspace.value = null
    if (selected.value.snapshot && selected.value.source_status === 'current')
      workspace.value = await listingsApi.workspace(
        shopId.value,
        selected.value.snapshot.product.product_id,
      )
  })
}
async function refresh(): Promise<void> {
  if (!shopId.value) return
  await action(async () => {
    await loadHistory()
    if (selected.value) selected.value = await listingsApi.get(shopId.value, selected.value.id)
    products.value = await listingsApi.products(shopId.value, query.value, offset.value)
    const productId = workspace.value?.product.product_id
    workspace.value = null
    if (productId && (!selected.value || selected.value.source_status === 'current'))
      workspace.value = await listingsApi.workspace(shopId.value, productId)
  })
}
async function updateResult(item: ListingVersion, message: string): Promise<void> {
  selected.value = item
  if (item.snapshot)
    workspace.value = await listingsApi.workspace(shopId.value, item.snapshot.product.product_id)
  await loadHistory()
  success.value = message
}
async function generate(): Promise<void> {
  if (!workspace.value) return
  await action(async () =>
    updateResult(
      await listingsApi.generate(shopId.value, workspace.value!),
      '已保存候选版本，请核对事实与差异。相同来源和基线会复用已有候选。',
    ),
  )
}
async function revise(content: ListingContent): Promise<void> {
  if (!selected.value || !workspace.value) return
  await action(async () =>
    updateResult(
      await listingsApi.revise(shopId.value, selected.value!, workspace.value!.active_id, content),
      '新待审版本已保存，批准前保留当前生效版本。',
    ),
  )
}
async function decide(decision: 'approve' | 'reject', confirmed: boolean): Promise<void> {
  if (!selected.value) return
  await action(async () =>
    updateResult(
      await listingsApi.decide(shopId.value, selected.value!, decision, confirmed),
      decision === 'approve' ? '此版本已在本地生效。' : '已拒绝此版本，保留草稿与审批记录。',
    ),
  )
}
function onFocus(): void {
  if (!busy.value) void refresh()
}
onMounted(async () => {
  window.addEventListener('focus', onFocus)
  await action(async () => {
    shops.value = await identityApi.shops()
  })
  try {
    shopId.value = linkedShop(shops.value, route.query.shop)
    await selectShop()
    const id = linkedId(route.query.listing)
    if (id) {
      await show({ id })
      await revealRecord('linked-listing')
    }
  } catch (cause) {
    error.value = errorMessage(cause)
  }
})
onUnmounted(() => window.removeEventListener('focus', onFocus))
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>让商品文案，每一句有据可查。</h1>
      <p>从导入商品事实建立候选，核对差异后由你批准本地版本。</p>
    </div>
    <span class="outline-label">Listing · 本地审批</span>
  </div>
  <FeedbackBanner
    message="生成方式：本地事实模板。当前使用商品原文，AI 模型尚未接入；平台发布未接入。"
    kind="info"
  />
  <FeedbackBanner :message="error" /><FeedbackBanner :message="success" kind="success" />
  <section class="section-block">
    <div class="form-grid">
      <div class="form-field">
        <label for="listing-shop">Listing 店铺</label
        ><select id="listing-shop" v-model="shopId" :disabled="busy" @change="selectShop">
          <option v-for="shop in shops" :key="shop.id" :value="shop.id">
            {{ shop.name }} · {{ shop.code }}
          </option>
        </select>
      </div>
    </div>
    <p v-if="!shops.length">
      先在<RouterLink to="/settings">经营资料</RouterLink>中添加店铺，再导入商品。
    </p>
    <form v-if="shopId" class="listing-search" @submit.prevent="search()">
      <div class="form-field">
        <label for="listing-query">查找 SKU / 商品名</label
        ><input id="listing-query" v-model="query" maxlength="120" :disabled="busy" />
      </div>
      <button class="button secondary" :disabled="busy">查找商品</button>
    </form>
    <div v-if="products.length" class="listing-products">
      <button
        v-for="product in products"
        :key="product.product_id"
        class="listing-product"
        :class="{ chosen: workspace?.product.product_id === product.product_id }"
        :disabled="busy"
        @click="choose(product)"
      >
        <strong>{{ product.sku }} · {{ product.name }}</strong
        ><span
          >{{ product.source.data_identity === 'synthetic' ? '合成测试数据' : '用户导入数据' }} ·
          批次 {{ product.source.batch_id }}</span
        >
      </button>
    </div>
    <p v-else-if="shopId && !busy" class="empty-state">
      没有匹配的商品。<RouterLink to="/imports">导入商品文件</RouterLink
      >后即可准备草稿；订单为可选数据。
    </p>
    <div v-if="offset || products.length === 50" class="button-row">
      <button
        class="button secondary small"
        :disabled="busy || !offset"
        @click="search(offset - 50)"
      >
        上一页</button
      ><span>第 {{ offset / 50 + 1 }} 页 · 每页最多 50 件</span
      ><button
        class="button secondary small"
        :disabled="busy || products.length < 50"
        @click="search(offset + 50)"
      >
        下一页
      </button>
    </div>
  </section>
  <section v-if="workspace" class="section-block" aria-label="当前商品">
    <h2>{{ workspace.product.sku }} · {{ workspace.product.name }}</h2>
    <p>
      最近批准版本：{{ workspace.active_id ? `#${workspace.active_id}` : '尚无已批准版本' }} · 店铺
      #{{ shopId }}
    </p>
    <p v-if="workspace.active_version">
      {{
        workspace.active_version.source_status === 'current'
          ? '本地已生效'
          : sourceStatus[workspace.active_version.source_status]
      }}
      · {{ workspace.active_version.snapshot?.proposed.title }}
    </p>
    <p class="preserve-text">商品参数：{{ workspace.product.facts || '未提供；仅商品名可核对' }}</p>
    <button class="button primary" :disabled="busy" @click="generate">从商品事实生成草稿</button>
  </section>
  <ListingReview
    id="linked-listing"
    v-if="selected"
    :item="selected"
    :busy="busy"
    :timezone="timezone"
    :can-revise="!!workspace"
    @revise="revise"
    @decide="decide"
  />
  <section v-if="shopId" class="section-block" aria-label="Listing 版本记录">
    <div class="section-title">
      <h2>版本与审批记录</h2>
      <button class="button secondary small" :disabled="busy" @click="refresh">刷新版本记录</button>
    </div>
    <p class="muted">当前店铺最近 50 条版本。来源失效后重新生成；历史审批状态保留。</p>
    <p v-if="!history.length">尚无草稿。选择上方商品，建立第一个候选版本。</p>
    <button
      v-for="item in history"
      :key="item.id"
      class="listing-history"
      :disabled="busy"
      @click="show(item)"
    >
      <strong
        >查看版本 #{{ item.id }} · {{ item.snapshot?.product.sku ?? '内容已清除' }} · v{{
          item.number
        }}</strong
      ><span>{{ listingStatus[item.status] }} · {{ sourceStatus[item.source_status] }}</span>
    </button>
  </section>
</template>
