<template>
  <PageShell
    title="Listing 草稿"
    subtitle="从导入商品事实建立候选，审阅差异后批准本地版本。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load()"
  >
    <view class="field">
      <text class="field__label">查找 SKU / 商品名</text>
      <input
        class="field__input"
        :value="search"
        :disabled="busy"
        @input="search = inputValue($event)"
      />
    </view>
    <view class="row">
      <ActionButton label="搜索" :disabled="busy" @tap="refresh" />
      <ActionButton label="导入商品文件" :disabled="busy" @tap="openImports" />
    </view>

    <view v-if="products.length === 0 && !busy" class="card">
      <text class="hint">没有匹配商品。导入商品文件后，这里会显示可生成 Listing 的商品。</text>
    </view>
    <view v-for="product in products" :key="product.product_id" class="card" @tap="choose(product.product_id)">
      <text class="card__title">{{ product.sku }} · {{ product.name }}</text>
      <text class="hint">
        {{ labelOf(importIdentities, product.source?.data_identity) }} · 批次 #{{ product.source?.batch_id }}
      </text>
    </view>
    <view class="row">
      <ActionButton v-if="offset > 0" label="上一页" :disabled="busy" @tap="turn(-50)" />
      <ActionButton v-if="products.length === 50" label="下一页" :disabled="busy" @tap="turn(50)" />
    </view>

    <template v-if="workspace">
      <text class="section-title">当前商品</text>
      <FactLine label="SKU" :value="workspace.product.sku" />
      <FactLine label="商品名称" :value="workspace.product.name" />
      <FactLine label="完整参数" :value="workspace.product.facts" />
      <FactLine label="本地已批准版本" :value="workspace.active_id" />
      <view class="row">
        <ActionButton
          label="从商品事实生成草稿"
          variant="primary"
          :disabled="busy || dirty"
          @tap="generate"
        />
        <ActionButton label="生成 AI Listing 候选" :disabled="busy || dirty" @tap="openAgent" />
      </view>
      <ActionButton
        v-for="version in workspace.versions"
        :key="version.id"
        :label="`版本 ${version.number} · ${version.status}`"
        :disabled="busy"
        @tap="inspect(version.id)"
      />
    </template>

    <template v-if="selected">
      <text class="section-title">版本 #{{ selected.id }} · v{{ selected.number }}</text>
      <FactLine label="状态 / 来源" :value="`${selected.status} / ${labelOf(sourceLabels, selected.source_status)}`" />
      <FactLine label="生成方式" :value="labelOf(agentLabels, selected.engine)" />
      <FactLine label="创建 / 审批" :value="`${businessTimeText(selected.created_at, zone)} / ${businessTimeText(selected.decided_at, zone)}`" />
      <text class="hint">影响本店此 SKU 的本地文案，R1，外部费用 0。恢复可将有效历史文案另存待审版本。</text>

      <template v-if="snapshot">
        <text class="section-title">版本差异</text>
        <template v-for="field in comparisonFields" :key="field.key">
          <text class="card__title">
            {{ field.label }} · {{ snapshot.before?.[field.key] === snapshot.proposed?.[field.key] ? '保持原值' : '有变更' }}
          </text>
          <FactLine label="原值" :value="snapshot.before?.[field.key] ?? '无'" />
          <FactLine label="新值" :value="snapshot.proposed?.[field.key] ?? '无'" />
        </template>
        <FactLine label="缺失项" :value="words(snapshot.missing)" />
        <FactLine label="阻断项" :value="words(snapshot.blockers)" />

        <template v-if="live && workspace">
          <view class="field">
            <text class="field__label">拟议标题（1–240 字）</text>
            <input
              class="field__input"
              :value="title"
              :disabled="busy"
              @input="edited(inputValue($event), 'title')"
            />
          </view>
          <view class="field">
            <text class="field__label">拟议描述（不超过 4000 字）</text>
            <textarea
              class="field__input"
              :value="description"
              :disabled="busy"
              @input="edited(inputValue($event), 'description')"
            />
          </view>
          <text class="hint">标题保留完整商品名；描述可调整完整参数行顺序。新增事实须先补充导入来源。</text>
          <view class="row">
            <ActionButton
              :label="selected.status === 'draft' ? '保存修改为待审版本' : '另存待审版本 / 恢复历史文案'"
              :disabled="busy"
              @tap="revise"
            />
            <ActionButton v-if="dirty" label="放弃未保存修改" :disabled="busy" @tap="resetEdit" />
          </view>
        </template>

        <template v-if="selected.status === 'draft'">
          <view class="row" @tap="toggleConfirm">
            <text class="chip" :class="{ 'chip--active': confirmed }">
              {{ confirmed ? '已确认' : '未确认' }} · 已逐项核对来源真实性、文案差异和平台适用性
            </text>
          </view>
          <view class="row">
            <ActionButton
              label="批准本地生效"
              variant="primary"
              :disabled="!canApprove"
              @tap="decide('approve')"
            />
            <ActionButton label="拒绝版本" :disabled="busy || dirty || !live" @tap="decide('reject')" />
          </view>
        </template>

        <text class="section-title">交付与导出</text>
        <text class="hint">交付文件包含完整文案、版本和来源。每次操作前重新核对当前版本；外部状态保持未提交。</text>
        <view class="row">
          <ActionButton label="复制全文" :disabled="!canDeliver" @tap="deliver('copy')" />
          <ActionButton label="保存 CSV" :disabled="!canDeliver" @tap="deliver('save')" />
        </view>
        <text class="hint">CSV 使用服务端提供的公式防护标记；在电子表格中再次保存时请核对标记。</text>
      </template>
      <text v-else class="warn">相关来源已清除，版本正文已擦除。</text>

      <ActionButton label="回读当前版本与来源" :disabled="busy" @tap="load()" />
    </template>

    <text class="section-title">全部版本历史</text>
    <view v-if="history.length === 0 && !busy" class="card">
      <text class="hint">尚无 Listing 版本。</text>
    </view>
    <view v-for="version in history" :key="version.id" class="card" @tap="inspect(version.id)">
      <text class="card__title">#{{ version.id }} · {{ version.snapshot?.proposed?.title ?? '内容已清除' }}</text>
      <text class="hint">
        {{ version.status }} · {{ labelOf(sourceLabels, version.source_status) }} ·
        {{ businessTimeText(version.created_at, zone) }}
      </text>
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * Listing 草稿：编辑、批准、导出 / 保存 CSV。
 * 接口：
 *   GET  /api/shops/{shop_id}/listings/products
 *   GET  /api/shops/{shop_id}/listings/products/{product_id}
 *   GET  /api/shops/{shop_id}/listings/versions
 *   GET  /api/shops/{shop_id}/listings/versions/{listing_id}
 *   POST /api/shops/{shop_id}/listings/generate
 *   POST /api/shops/{shop_id}/listings/versions/{listing_id}/revise
 *   POST /api/shops/{shop_id}/listings/versions/{listing_id}/decision
 *   GET  /api/shops/{shop_id}/listings/versions/{listing_id}/delivery
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import ActionButton from '../../ui/ActionButton.vue'
import { apiGet, apiPost, asObject } from '../../core/api'
import { businessTimeText } from '../../core/format'
import { agentLabels, importIdentities, labelOf, sourceLabels } from '../../core/labels'
import { openPage, pageQuery, setPendingIntent, openTab } from '../../core/links'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

interface ProductFacts {
  product_id: number
  sku: string
  name: string
  facts: string
  source: { data_identity: string; batch_id: number; row_id: number }
}

interface ListingSnapshot {
  product: ProductFacts
  before: { title?: string; description?: string }
  proposed: { title?: string; description?: string }
  missing: string[]
  blockers: string[]
}

interface ListingRecord {
  id: number
  number: number
  version: number
  status: string
  source_status: string
  engine: string
  created_at: string
  decided_at: string | null
  snapshot: ListingSnapshot | null
}

interface ProductWorkspace {
  product: ProductFacts
  active_id: number | null
  versions: ListingRecord[]
}

interface ListingDelivery {
  plain_text: string
  csv_text: string
  filename: string
}

const comparisonFields = [
  { key: 'title' as const, label: '标题' },
  { key: 'description' as const, label: '描述' },
]

const search = ref('')
const products = ref<ProductFacts[]>([])
const history = ref<ListingRecord[]>([])
const workspace = ref<ProductWorkspace | null>(null)
const selected = ref<ListingRecord | null>(null)
const offset = ref(0)
const title = ref('')
const description = ref('')
const confirmed = ref(false)
const busy = ref(false)
const error = ref('')
const ready = ref(false)

const zone = computed(() => shopTimezone())
const snapshot = computed(() => selected.value?.snapshot ?? null)
const live = computed(() => selected.value?.source_status === 'current')
const dirty = computed(
  () =>
    snapshot.value !== null &&
    (title.value !== (snapshot.value.proposed?.title ?? '') ||
      description.value !== (snapshot.value.proposed?.description ?? '')),
)
const canApprove = computed(
  () =>
    !busy.value &&
    !dirty.value &&
    live.value &&
    confirmed.value &&
    (snapshot.value?.blockers?.length ?? 0) === 0,
)
const canDeliver = computed(
  () => !busy.value && !dirty.value && live.value && selected.value?.status === 'approved',
)

function words(value: unknown): string {
  return Array.isArray(value) && value.length > 0 ? value.join('、') : '无'
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  await load(true)
})

async function listAll(): Promise<void> {
  const [productRows, versionRows] = await Promise.all([
    apiGet<ProductFacts[]>(shopPath('/listings/products'), {
      q: search.value.trim(),
      offset: offset.value,
    }),
    apiGet<ListingRecord[]>(shopPath('/listings/versions')),
  ])
  products.value = Array.isArray(productRows) ? productRows : []
  history.value = Array.isArray(versionRows) ? versionRows : []
}

function accept(record: ListingRecord): void {
  selected.value = record
  confirmed.value = false
  title.value = record.snapshot?.proposed?.title ?? ''
  description.value = record.snapshot?.proposed?.description ?? ''
}

async function load(initial = false): Promise<void> {
  if (!ready.value) return
  // 从工作台 / Agent 带入的定位参数只处理一次。
  const query = initial ? pageQuery() : {}
  const wantedListing = Number(query.listing ?? '')
  const wantedProduct = Number(query.product ?? '')
  const message = await perform(async () => {
    await listAll()
    if (Number.isFinite(wantedListing) && wantedListing > 0) {
      await readSelected(wantedListing)
      return
    }
    if (Number.isFinite(wantedProduct) && wantedProduct > 0) {
      workspace.value = asObject<ProductWorkspace>(
        await apiGet(shopPath(`/listings/products/${wantedProduct}`)),
      )
      selected.value = null
      return
    }
    const wanted = initial ? null : selected.value?.id ?? null
    if (wanted !== null) {
      await readSelected(wanted)
    }
  })
  error.value = message
}

async function readSelected(id: number): Promise<void> {
  const record = asObject<ListingRecord>(await apiGet(shopPath(`/listings/versions/${id}`)))
  if (record === null) return
  accept(record)
  workspace.value = null
  const productId = record.snapshot?.product?.product_id
  if (record.source_status === 'current' && productId !== undefined) {
    workspace.value = asObject<ProductWorkspace>(
      await apiGet(shopPath(`/listings/products/${productId}`)),
    )
  }
}

async function choose(productId: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<ProductWorkspace>(
      await apiGet(shopPath(`/listings/products/${productId}`)),
    )
    workspace.value = value
    selected.value = null
  })
  error.value = message
}

async function inspect(id: number): Promise<void> {
  const message = await perform(() => readSelected(id))
  error.value = message
}

async function refresh(): Promise<void> {
  offset.value = 0
  await load()
}

function turn(delta: number): void {
  offset.value = Math.max(0, offset.value + delta)
  void load()
}

function edited(value: string, field: 'title' | 'description'): void {
  if (field === 'title') title.value = value
  else description.value = value
  confirmed.value = false
}

function resetEdit(): void {
  if (selected.value !== null) accept(selected.value)
}

function toggleConfirm(): void {
  if (busy.value || dirty.value || !live.value) return
  confirmed.value = !confirmed.value
}

async function generate(): Promise<void> {
  const current = workspace.value
  if (current === null || busy.value || dirty.value) return
  const message = await perform(async () => {
    const record = asObject<ListingRecord>(
      await apiPost(shopPath('/listings/generate'), {
        product_id: current.product.product_id,
        expected_source_row_id: current.product.source.row_id,
        expected_active_id: current.active_id,
      }),
    )
    if (record !== null) accept(record)
    await listAll()
  })
  error.value = message
}

async function revise(): Promise<void> {
  const record = selected.value
  if (record === null || workspace.value === null || busy.value) return
  if (title.value.trim() === '' || title.value.length > 240 || description.value.length > 4000) {
    error.value = '标题须为 1–240 字，描述不超过 4000 字。'
    return
  }
  const message = await perform(async () => {
    const next = asObject<ListingRecord>(
      await apiPost(shopPath(`/listings/versions/${record.id}/revise`), {
        expected_version: record.version,
        expected_active_id: workspace.value?.active_id ?? null,
        content: { title: title.value, description: description.value },
      }),
    )
    if (next !== null) accept(next)
    await listAll()
  })
  error.value = message
  if (message === '') void Taro.showToast({ title: '待审版本已保存。', icon: 'none' })
}

async function decide(decision: 'approve' | 'reject'): Promise<void> {
  const record = selected.value
  if (record === null || busy.value) return
  if (dirty.value || (decision === 'approve' && !confirmed.value)) {
    error.value = '请先保存文案并核对当前版本。'
    return
  }
  const modal = await Taro.showModal({
    title: decision === 'approve' ? '批准本地生效' : '拒绝版本',
    content:
      decision === 'approve'
        ? '批准仅在本地生效，不代表已向外部平台提交或发布。'
        : '拒绝后版本历史保留，可另外保存历史文案为待审版本。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  const message = await perform(async () => {
    const next = asObject<ListingRecord>(
      await apiPost(shopPath(`/listings/versions/${record.id}/decision`), {
        expected_version: record.version,
        decision,
        facts_confirmed: confirmed.value,
      }),
    )
    if (next !== null) accept(next)
    await listAll()
  })
  error.value = message
  if (message === '') {
    void Taro.showToast({
      title: decision === 'approve' ? '此版本已在本地生效。' : '版本已拒绝，历史保留。',
      icon: 'none',
    })
  }
}

async function deliver(action: 'copy' | 'save'): Promise<void> {
  const record = selected.value
  if (record === null || !canDeliver.value) return
  const message = await perform(async () => {
    const artifact = asObject<ListingDelivery>(
      await apiGet(shopPath(`/listings/versions/${record.id}/delivery`), {
        expected_version: record.version,
      }),
    )
    if (artifact === null) throw new Error('交付内容无法读取，请刷新后重试。')
    if (action === 'copy') {
      await Taro.setClipboardData({ data: artifact.plain_text })
      success('完整文案、版本与来源已复制，请在原渠道核对后使用。')
      return
    }
    const path = `${Taro.env.USER_DATA_PATH}/${artifact.filename}`
    const fs = Taro.getFileSystemManager()
    fs.writeFileSync(path, artifact.csv_text, 'utf8')
    const saver = (Taro as unknown as { saveFileToDisk?: (options: { filePath: string }) => Promise<unknown> })
      .saveFileToDisk
    if (typeof saver === 'function') {
      await saver({ filePath: path })
      success('通用 CSV 已保存。')
      return
    }
    // 小程序仅在部分客户端支持保存到磁盘；其余环境回退为复制 CSV 文本并明确说明。
    await Taro.setClipboardData({ data: artifact.csv_text })
    success('当前客户端不支持直接保存文件，已把 CSV 文本复制到剪贴板，并写入小程序本地文件。')
  })
  error.value = message
}

const successText = ref('')

function success(text: string): void {
  successText.value = text
  void Taro.showToast({ title: text, icon: 'none' })
}

function openImports(): void {
  openPage('/pages/imports/index', { kind: 'products' })
}

function openAgent(): void {
  const current = workspace.value
  if (current === null) return
  setPendingIntent('/pages/agent/index', {
    mode: 'listing_model',
    product: `${current.product.product_id}`,
    identity: current.product.source?.data_identity ?? '',
  })
  openTab('/pages/agent/index')
}
</script>
