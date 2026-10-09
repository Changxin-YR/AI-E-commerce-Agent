<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { identityApi } from '@/api/identity'
import { analyticsApi } from '@/api/analytics'
import { productQualityApi } from '@/api/productQuality'
import { productEditsApi } from '@/api/productEdits'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import type { SourceChannel } from '@/types/imports'
import type { QualityResult } from '@/types/productQuality'
import { qualityChannels } from '@/types/productQuality'
import {
  editStatuses,
  type EditAction,
  type EditCreate,
  type EditSaved,
} from '@/types/productEdits'
import { supportTime } from '@/types/support'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import ProductEditReview from '@/components/ProductEditReview.vue'

const route = useRoute()
const shops = ref<Shop[]>([])
const shopId = ref(0)
const scope = reactive({
  data_identity: 'user_import' as 'user_import' | 'synthetic',
  channel: 'generic' as SourceChannel,
  sku_prefix: '',
})
const catalog = ref<QualityResult | null>(null)
const fields = ref<Record<number, { selected: boolean; name: string; facts: string }>>({})
const reason = ref('')
const page = ref(0)
const prefix = ref('')
const appendFacts = ref('')
const saved = ref<EditSaved | null>(null)
const history = ref<EditSaved[]>([])
const cursor = ref<number | null>(null)
const error = ref('')
const busy = ref(false)
const pending = ref<EditCreate | null>(null)
let openId = 0
let epoch = 0
let alive = true
let restoring = false
const timezone = computed(
  () => shops.value.find((s) => s.id === shopId.value)?.timezone ?? 'Asia/Shanghai',
)
const visible = computed(
  () => catalog.value?.products.slice(page.value * 20, (page.value + 1) * 20) ?? [],
)
const selected = computed(() => Object.values(fields.value).filter((f) => f.selected).length)
const changes = computed(() =>
  (catalog.value?.products ?? []).flatMap((p) => {
    const f = fields.value[p.product_id]
    return f?.selected && (f.name !== p.name || f.facts !== p.facts)
      ? [
          {
            product_id: p.product_id,
            expected_source_row_id: p.source.row_id,
            name: f.name,
            facts: f.facts,
          },
        ]
      : []
  }),
)

function clearEditor(): void {
  catalog.value = null
  fields.value = {}
  reason.value = ''
  prefix.value = ''
  appendFacts.value = ''
  page.value = 0
}
function reset(): void {
  epoch++
  clearEditor()
  saved.value = null
  pending.value = null
  openId = 0
  error.value = ''
}
watch(
  scope,
  () => {
    if (!restoring) reset()
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

async function action(work: (valid: () => boolean) => Promise<void>): Promise<void> {
  if (busy.value || !shopId.value) return
  busy.value = true
  error.value = ''
  const current = epoch
  const valid = () => alive && epoch === current
  try {
    await work(valid)
  } catch (cause) {
    if (valid()) error.value = errorMessage(cause)
  } finally {
    if (alive) busy.value = false
  }
}
function accept(edit: EditSaved): void {
  if (edit.snapshot) {
    restoring = true
    scope.data_identity = edit.snapshot.data_identity
    scope.channel = edit.snapshot.channel
    scope.sku_prefix = ''
    restoring = false
  }
  saved.value = edit
  openId = edit.id
}
async function loadHistory(valid: () => boolean, more = false): Promise<void> {
  const result = await productEditsApi.list(
    shopId.value,
    more ? (cursor.value ?? undefined) : undefined,
  )
  if (valid()) {
    history.value = more ? [...history.value, ...result.items] : result.items
    cursor.value = result.next_cursor
  }
}
async function load(): Promise<void> {
  if (busy.value) return
  reset()
  await action(async (valid) => {
    const result = await productQualityApi.preview(shopId.value, { ...scope })
    if (!valid()) return
    catalog.value = result
    fields.value = Object.fromEntries(
      result.products.map((p) => [p.product_id, { selected: false, name: p.name, facts: p.facts }]),
    )
    await loadHistory(valid)
  })
}
function applyToSelected(): void {
  for (const field of Object.values(fields.value)) {
    if (!field.selected) continue
    field.name = prefix.value + field.name
    if (appendFacts.value) field.facts = [field.facts, appendFacts.value].filter(Boolean).join('\n')
  }
  prefix.value = ''
  appendFacts.value = ''
}
async function create(retry = false): Promise<void> {
  if (busy.value) return
  if (!retry) {
    if (!changes.value.length || changes.value.length > 50 || !reason.value.trim()) return
    const invalid = changes.value.find(
      (c) => !c.name.trim() || c.name.length > 240 || c.facts.length > 2000,
    )
    if (invalid) {
      const sku = catalog.value?.products.find((p) => p.product_id === invalid.product_id)?.sku
      error.value = `请修正商品 ${sku}：名称须为 1—240 字符，参数最多 2000 字符。`
      return
    }
    pending.value = {
      data_identity: scope.data_identity,
      channel: scope.channel,
      reason: reason.value,
      changes: changes.value.map((c) => ({ ...c })),
      request_id: crypto.randomUUID(),
    }
  }
  const data = pending.value
  if (!data) return
  await action(async (valid) => {
    clearEditor()
    saved.value = null
    const result = await productEditsApi.create(shopId.value, data)
    if (!valid()) return
    accept(result)
    pending.value = null
    await loadHistory(valid)
  })
}
async function show(id: number): Promise<void> {
  await action(async (valid) => {
    clearEditor()
    pending.value = null
    saved.value = null
    openId = id
    const result = await productEditsApi.get(shopId.value, id)
    if (valid()) accept(result)
  })
}
async function refresh(): Promise<void> {
  await action(async (valid) => {
    const prior = catalog.value
    const editor = fields.value
    const oldReason = reason.value
    clearEditor()
    saved.value = null
    history.value = []
    if (openId) {
      const result = await productEditsApi.get(shopId.value, openId)
      if (!valid()) return
      accept(result)
    } else if (prior) {
      const revision = await analyticsApi.revision(shopId.value)
      if (!valid()) return
      if (revision === prior.source_revision) {
        catalog.value = prior
        fields.value = editor
        reason.value = oldReason
      } else error.value = '来源已变化，请重新加载商品后修订。'
    }
    await loadHistory(valid)
  })
}
async function decide(kind: EditAction): Promise<void> {
  const edit = saved.value
  if (!edit) return
  await action(async (valid) => {
    saved.value = null
    clearEditor()
    pending.value = null
    const result = await productEditsApi.decide(edit, kind)
    if (!valid()) return
    accept(result)
    await loadHistory(valid)
  })
}
function focused(): void {
  if (!busy.value && shopId.value) void refresh()
}
onMounted(async () => {
  try {
    const result = await identityApi.shops()
    if (!alive) return
    shops.value = result
    shopId.value = result.find((s) => s.id === Number(route.query.shop))?.id ?? result[0]?.id ?? 0
    await refresh()
    const id = Number(route.query.edit)
    if (Number.isSafeInteger(id) && id > 0) await show(id)
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
      <h1>商品修订，核对后生效。</h1>
      <p>选择商品、编写名称与参数，保存差异草稿后逐项审批。</p>
    </div>
    <RouterLink class="button secondary" :to="`/product-quality?shop=${shopId}`"
      >商品质量检查</RouterLink
    >
  </div>
  <FeedbackBanner :message="error" />
  <section class="data-note">
    <span class="note-symbol" aria-hidden="true">i</span>
    <div>
      <h3>本地商品资料</h3>
      <p>
        每批最多 50
        个商品；人工修订保留原始导入与事实依据。金额、库存、素材和外部平台保持各自原有状态。
      </p>
    </div>
  </section>
  <section v-if="shops.length" class="form-panel section-block">
    <form @submit.prevent="load">
      <fieldset :disabled="busy">
        <legend>选择修订范围</legend>
        <div class="form-grid">
          <div class="form-field">
            <label for="edit-shop">所属店铺</label
            ><select id="edit-shop" v-model="shopId" @change="refresh">
              <option v-for="shop in shops" :key="shop.id" :value="shop.id">
                {{ shop.name }} · {{ shop.code }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label for="edit-identity">数据身份</label
            ><select id="edit-identity" v-model="scope.data_identity">
              <option value="user_import">用户导入文件</option>
              <option value="synthetic">合成测试数据</option>
            </select>
          </div>
          <div class="form-field">
            <label for="edit-channel">来源渠道</label
            ><select id="edit-channel" v-model="scope.channel">
              <option v-for="(label, value) in qualityChannels" :key="value" :value="value">
                {{ label }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label for="edit-prefix">SKU 前缀（可选）</label
            ><input id="edit-prefix" v-model="scope.sku_prefix" maxlength="120" /><small
              >区分大小写，每次最多加载 1000 个商品。</small
            >
          </div>
        </div>
        <div class="form-actions">
          <span>加载将重置未保存编辑。</span><button class="button primary">加载当前商品</button>
        </div>
      </fieldset>
    </form>
  </section>
  <p v-if="busy" role="status">正在核对商品与修订…</p>
  <section v-if="!shops.length && !busy" class="form-panel section-block">
    <h2>先添加店铺记录</h2>
    <RouterLink to="/settings">经营资料</RouterLink>
  </section>
  <section v-if="catalog" class="form-panel section-block" aria-label="编写商品修订">
    <h2>选择与编辑</h2>
    <p>
      已加载 {{ catalog.product_count }} 个商品 · 已选 {{ selected }} 个 · 有改动
      {{ changes.length }} 个。仅保存有改动的选中商品。
    </p>
    <p v-if="!catalog.products.length">此范围暂无商品，请导入资料或调整范围。</p>
    <form v-else @submit.prevent="create()">
      <fieldset :disabled="busy">
        <details>
          <summary>为选中商品填写相同改动</summary>
          <div class="form-grid">
            <div class="form-field">
              <label for="edit-name-prefix">名称前缀</label
              ><input id="edit-name-prefix" v-model="prefix" maxlength="240" />
            </div>
            <div class="form-field">
              <label for="edit-append">追加参数（每行一项）</label
              ><textarea
                id="edit-append"
                v-model="appendFacts"
                maxlength="2000"
                rows="3"
              ></textarea>
            </div>
          </div>
          <button
            type="button"
            class="button secondary"
            :disabled="!selected || (!prefix && !appendFacts)"
            @click="applyToSelected"
          >
            填入选中商品
          </button>
          <p>填入后请逐项核对；名称最多 240 字符，参数最多 2000 字符。</p>
        </details>
        <article
          v-for="product in visible"
          :key="product.product_id"
          class="editor-item"
          :aria-label="`编辑 ${product.sku}`"
        >
          <label class="check-label"
            ><input
              v-model="fields[product.product_id]!.selected"
              type="checkbox"
              :disabled="!fields[product.product_id]!.selected && selected >= 50"
            />选择 {{ product.sku }} · {{ product.name }}</label
          >
          <div v-if="fields[product.product_id]!.selected" class="form-grid">
            <div class="form-field">
              <label :for="`edit-name-${product.product_id}`">商品 {{ product.sku }} 名称</label
              ><input
                :id="`edit-name-${product.product_id}`"
                v-model="fields[product.product_id]!.name"
                maxlength="240"
                required
              />
            </div>
            <div class="form-field">
              <label :for="`edit-facts-${product.product_id}`">商品 {{ product.sku }} 参数</label
              ><textarea
                :id="`edit-facts-${product.product_id}`"
                v-model="fields[product.product_id]!.facts"
                maxlength="2000"
                rows="4"
              ></textarea>
            </div>
          </div>
        </article>
        <div class="form-actions">
          <button type="button" class="button secondary" :disabled="page === 0" @click="page--">
            上一页</button
          ><span>第 {{ page + 1 }} 页，共 {{ Math.ceil(catalog.product_count / 20) }} 页</span
          ><button
            type="button"
            class="button secondary"
            :disabled="(page + 1) * 20 >= catalog.product_count"
            @click="page++"
          >
            下一页
          </button>
        </div>
        <div class="form-field">
          <label for="edit-reason">修订依据</label
          ><textarea
            id="edit-reason"
            v-model="reason"
            maxlength="500"
            required
            rows="3"
            placeholder="填写核对过的规格、资料出处或纠错原因"
          ></textarea>
        </div>
        <div class="form-actions">
          <span>保存后展示完整新旧差异，审批前主档不变。</span
          ><button
            class="button primary"
            :disabled="!changes.length || changes.length > 50 || !reason.trim()"
          >
            保存修订草稿
          </button>
        </div>
      </fieldset>
    </form>
  </section>
  <section v-if="pending && !busy" class="form-panel section-block">
    <p>上次保存结果尚未确认，可用同一请求标识回查。</p>
    <button class="button secondary" @click="create(true)">回查上次保存请求</button>
  </section>
  <ProductEditReview
    v-if="saved"
    :key="`${saved.id}-${saved.version}`"
    :edit="saved"
    :busy="busy"
    @decide="decide"
  />
  <section v-if="shopId" class="form-panel section-block" aria-label="修订历史">
    <div class="section-title">
      <h2>本店修订记录</h2>
      <button class="button secondary" :disabled="busy" @click="refresh">刷新修订与来源</button>
    </div>
    <p v-if="!history.length">此店暂无修订记录。</p>
    <article v-for="edit in history" :key="edit.id" class="history-row">
      <div>
        <strong>#{{ edit.id }} · {{ editStatuses[edit.status] }}</strong>
        <p>{{ supportTime(edit.created_at, timezone) }}</p>
      </div>
      <button class="button secondary" :disabled="busy" @click="show(edit.id)">
        查看修订 #{{ edit.id }}
      </button>
    </article>
    <button
      v-if="cursor"
      class="button secondary"
      :disabled="busy"
      @click="action((valid) => loadHistory(valid, true))"
    >
      加载更早修订
    </button>
  </section>
</template>
<style scoped>
fieldset {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.editor-item {
  border-top: 1px solid var(--line);
  padding: 1rem 0;
  overflow-wrap: anywhere;
}
.history-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  border-top: 1px solid var(--line);
  padding: 1rem 0;
}
textarea {
  resize: vertical;
}
@media (max-width: 640px) {
  .page-heading,
  .history-row,
  .section-title {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
