<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { identityApi } from '@/api/identity'
import { analyticsApi } from '@/api/analytics'
import { productQualityApi } from '@/api/productQuality'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import {
  qualityChannels,
  qualityStatus,
  type QualityScope,
  type QualityResult,
  type QualitySaved,
} from '@/types/productQuality'
import { supportTime } from '@/types/support'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import ProductQualityResult from '@/components/ProductQualityResult.vue'

const route = useRoute()
const shops = ref<Shop[]>([])
const shopId = ref(0)
const scope = reactive<QualityScope>({
  data_identity: 'user_import',
  channel: null,
  sku_prefix: '',
})
const result = ref<QualityResult | null>(null)
const saved = ref<QualitySaved | null>(null)
const history = ref<QualitySaved[]>([])
const cursor = ref<number | null>(null)
const busy = ref(false)
const error = ref('')
const success = ref('')
const confirmed = ref(false)
const confirmClear = ref(false)
let requestId = ''
let epoch = 0
let alive = true
let restoringScope = false
const timezone = computed(
  () => shops.value.find((s) => s.id === shopId.value)?.timezone ?? 'Asia/Shanghai',
)

function reset(): void {
  epoch++
  result.value = null
  saved.value = null
  confirmed.value = false
  confirmClear.value = false
  requestId = ''
  error.value = ''
  success.value = ''
}
watch(
  scope,
  () => {
    if (!restoringScope) reset()
  },
  { deep: true, flush: 'sync' },
)
watch(
  shopId,
  () => {
    reset()
    history.value = []
    cursor.value = null
  },
  { flush: 'sync' },
)

function acceptReport(response: QualitySaved): void {
  restoringScope = true
  Object.assign(scope, response.scope)
  restoringScope = false
  saved.value = response
  result.value = response.snapshot
}

async function action(work: (valid: () => boolean) => Promise<void>): Promise<void> {
  if (busy.value || !shopId.value) return
  busy.value = true
  error.value = ''
  success.value = ''
  const current = epoch
  const valid = () => alive && current === epoch
  try {
    await work(valid)
  } catch (cause) {
    if (valid()) {
      error.value = errorMessage(cause)
      confirmed.value = false
    }
  } finally {
    if (alive) busy.value = false
  }
}
async function loadHistory(valid: () => boolean, more = false): Promise<void> {
  const page = await productQualityApi.list(
    shopId.value,
    more ? (cursor.value ?? undefined) : undefined,
  )
  if (valid()) {
    history.value = more ? [...history.value, ...page.items] : page.items
    cursor.value = page.next_cursor
  }
}
async function run(): Promise<void> {
  if (busy.value) return
  reset()
  await action(async (valid) => {
    const loaded = await productQualityApi.preview(shopId.value, { ...scope })
    if (!valid()) return
    result.value = loaded
    requestId = crypto.randomUUID()
    await loadHistory(valid)
  })
}
async function save(): Promise<void> {
  if (!result.value || !confirmed.value || saved.value) return
  const preview = result.value
  await action(async (valid) => {
    // Hide the old preview while revalidating; failures must not keep erased source text visible.
    result.value = null
    confirmed.value = false
    const response = await productQualityApi.save(preview, requestId)
    if (!valid()) return
    acceptReport(response)
    success.value = '检查报告已保存，可从本店历史报告回读。'
    await loadHistory(valid)
  })
}
async function show(id: number): Promise<void> {
  await action(async (valid) => {
    result.value = null
    saved.value = null
    confirmed.value = false
    confirmClear.value = false
    const response = await productQualityApi.get(shopId.value, id)
    if (valid()) {
      acceptReport(response)
    }
  })
}
async function refresh(): Promise<void> {
  await action(async (valid) => {
    const prior = result.value
    const record = saved.value
    result.value = null
    saved.value = null
    history.value = []
    confirmed.value = false
    confirmClear.value = false
    if (record) {
      const response = await productQualityApi.get(shopId.value, record.id)
      if (!valid()) return
      acceptReport(response)
    } else if (prior) {
      const revision = await analyticsApi.revision(shopId.value)
      if (!valid()) return
      if (revision === prior.source_revision) result.value = prior
      else error.value = '来源已变化，请重新检查。'
    }
    await loadHistory(valid)
  })
}
async function clear(): Promise<void> {
  if (!saved.value || !confirmClear.value) return
  const id = saved.value.id
  await action(async (valid) => {
    result.value = null
    confirmClear.value = false
    const response = await productQualityApi.clear(shopId.value, id)
    if (!valid()) return
    acceptReport(response)
    success.value = '报告正文、SKU 前缀与来源依赖已清除。'
    await loadHistory(valid)
  })
}
function focused(): void {
  if (!busy.value) void refresh()
}
onMounted(async () => {
  try {
    const loaded = await identityApi.shops()
    if (!alive) return
    shops.value = loaded
    const linked = Number(route.query.shop)
    shopId.value = loaded.some((s) => s.id === linked) ? linked : (loaded[0]?.id ?? 0)
    await action((valid) => loadHistory(valid))
    const report = Number(route.query.report)
    if (Number.isSafeInteger(report) && report > 0) await show(report)
  } catch (cause) {
    if (alive) error.value = errorMessage(cause)
  }
  if (alive) window.addEventListener('focus', focused)
})
onUnmounted(() => {
  alive = false
  epoch++
  window.removeEventListener('focus', focused)
})
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>商品资料，逐项核对。</h1>
      <p>从已导入的名称、参数与金额出发，保留每个核对项的依据。</p>
    </div>
    <RouterLink class="button secondary" to="/imports">导入或修订商品</RouterLink>
  </div>
  <FeedbackBanner :message="error" /><FeedbackBanner :message="success" kind="success" />
  <section class="data-note">
    <span class="note-symbol" aria-hidden="true">i</span>
    <div>
      <h3>本地商品检查</h3>
      <p>
        检查后可保存报告。修改商品请补充源文件并在导入预览中核对差异；品牌、编码、图片和平台刊登要求仍需另外核验。
      </p>
    </div>
  </section>
  <section v-if="shops.length" class="form-panel section-block">
    <form @submit.prevent="run">
      <fieldset :disabled="busy" class="quality-fields">
        <legend>商品检查范围</legend>
        <div class="form-grid">
          <div class="form-field">
            <label for="quality-shop">所属店铺</label
            ><select id="quality-shop" v-model="shopId" @change="refresh">
              <option v-for="shop in shops" :key="shop.id" :value="shop.id">
                {{ shop.name }} · {{ shop.code }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label for="quality-identity">数据身份</label
            ><select id="quality-identity" v-model="scope.data_identity">
              <option value="user_import">用户导入文件</option>
              <option value="synthetic">合成测试数据</option>
            </select>
          </div>
          <div class="form-field">
            <label for="quality-channel">来源渠道</label
            ><select id="quality-channel" v-model="scope.channel">
              <option :value="null">全部导入渠道</option>
              <option v-for="(label, value) in qualityChannels" :key="value" :value="value">
                {{ label }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label for="quality-prefix">SKU 前缀（可选）</label
            ><input id="quality-prefix" v-model="scope.sku_prefix" maxlength="120" /><small
              >按原始 SKU 前缀筛选，区分大小写；每次最多 1000 个商品。</small
            >
          </div>
        </div>
        <div class="form-actions">
          <span>仅检查当前导入主档。</span><button class="button primary">检查商品信息</button>
        </div>
      </fieldset>
    </form>
  </section>
  <p v-if="busy" role="status">正在核对商品与来源…</p>
  <section v-if="!shops.length && !busy" class="form-panel section-block empty-state">
    <h2>先添加店铺记录</h2>
    <RouterLink class="button secondary" to="/settings">经营资料</RouterLink>
  </section>
  <section v-if="saved" class="form-panel section-block" aria-label="报告存档状态">
    <h2>质量报告 #{{ saved.id }}</h2>
    <p role="status">{{ qualityStatus[saved.status] }}</p>
    <p v-if="saved.status === 'stale'">以下为当时的检查记录，不能代表当前商品资料。请重新检查。</p>
    <RouterLink :to="`/product-quality?shop=${saved.shop_id}&report=${saved.id}`"
      >报告固定链接</RouterLink
    >
  </section>
  <ProductQualityResult
    v-if="result"
    :key="`${saved?.id ?? 'preview'}-${result.preview_hash}`"
    :result="result"
    :timezone="timezone"
  />
  <section v-if="result && !saved" class="form-panel section-block">
    <label class="quality-confirm"
      ><input
        v-model="confirmed"
        type="checkbox"
        :disabled="busy"
      />我已查看范围与未检查项，确认保存本次本地检查报告</label
    >
    <div class="form-actions">
      <span>保存时重新核验全部来源。</span
      ><button class="button primary" :disabled="busy || !confirmed" @click="save">
        保存检查报告
      </button>
    </div>
  </section>
  <section v-if="saved && saved.status !== 'cleared'" class="form-panel section-block">
    <label class="quality-confirm"
      ><input
        v-model="confirmClear"
        type="checkbox"
        :disabled="busy"
      />确认清除这份报告正文与来源依赖</label
    ><button class="button secondary" :disabled="busy || !confirmClear" @click="clear">
      清除报告正文
    </button>
  </section>
  <section v-if="shopId" class="form-panel section-block" aria-label="质量报告历史">
    <div class="section-title">
      <h2>本店历史报告</h2>
      <button class="button secondary" :disabled="busy" @click="refresh">刷新报告与来源</button>
    </div>
    <p v-if="!history.length">此店暂无已保存的检查报告。</p>
    <article v-for="item in history" :key="item.id" class="history-row">
      <div>
        <strong>#{{ item.id }} · {{ qualityStatus[item.status] }}</strong>
        <p>
          {{ supportTime(item.created_at, timezone) }} ·
          {{ item.scope.data_identity === 'synthetic' ? '合成测试数据' : '用户导入文件' }} ·
          {{ item.scope.channel ? qualityChannels[item.scope.channel] : '全部导入渠道' }}
        </p>
      </div>
      <button class="button secondary" :disabled="busy" @click="show(item.id)">
        查看报告 #{{ item.id }}
      </button>
    </article>
    <button
      v-if="cursor"
      class="button secondary"
      :disabled="busy"
      @click="action((valid) => loadHistory(valid, true))"
    >
      加载更早报告
    </button>
  </section>
</template>

<style scoped>
.quality-fields {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.quality-confirm {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  margin-bottom: 1rem;
}
.quality-confirm input {
  width: auto;
  margin-top: 0.25rem;
}
.history-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border-top: 1px solid var(--line);
  padding: 1rem 0;
  overflow-wrap: anywhere;
}
@media (max-width: 640px) {
  .page-heading,
  .history-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
