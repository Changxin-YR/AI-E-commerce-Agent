<template>
  <PageShell
    title="商品本地修订"
    subtitle="在本地批量修订商品名称与参数事实；批准后写入本地商品数据，不推送到任何平台。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load"
  >
    <FactLine label="所属店铺" :value="shopName" />
    <FactLine label="业务时区" :value="zone" />

    <text class="section-title">范围与批量工具</text>
    <view class="field">
      <text class="field__label">数据身份</text>
      <picker mode="selector" :range="identityOptions" range-key="label" :value="identityIndex" @change="identity = identityOptions[Number(pickerValue($event))]?.key ?? 'user_import'">
        <view class="field__picker">{{ labelOf(importIdentities, identity) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">渠道</text>
      <picker mode="selector" :range="channelOptions" range-key="label" :value="channelIndex" @change="channel = channelOptions[Number(pickerValue($event))]?.key ?? 'generic'">
        <view class="field__picker">{{ labelOf(importChannels, channel) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">SKU 前缀（最多 120 字符）</text>
      <input class="field__input" :value="skuPrefix" :disabled="busy || locked" @input="skuPrefix = inputValue($event)" />
    </view>
    <view class="row">
      <ActionButton label="读取当前商品与来源" variant="primary" :disabled="busy || locked" @tap="loadCatalog" />
    </view>
    <FactLine label="来源修订" :value="catalog === null ? '尚未读取' : catalog.source_revision" />
    <FactLine label="已选择商品" :value="selectedCount" />
    <view class="field">
      <text class="field__label">批量名称前缀（留空表示不修改名称）</text>
      <input class="field__input" :value="batchNamePrefix" :disabled="busy || locked" @input="batchNamePrefix = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">批量追加参数（追加到参数事实末尾）</text>
      <input class="field__input" :value="batchFactsAppend" :disabled="busy || locked" @input="batchFactsAppend = inputValue($event)" />
    </view>
    <ActionButton label="将输入应用到已选商品表单" :disabled="busy || locked || selectedCount === 0" @tap="applyBatch" />

    <text class="section-title">商品差异编辑</text>
    <view v-if="drafts.length === 0 && !busy" class="card">
      <text class="hint">请先读取当前商品与来源，再选择要修订的商品。</text>
    </view>
    <view v-for="draft in pagedDrafts" :key="draft.productId" class="card">
      <text class="card__title" @tap="toggleDraft(draft.productId)">
        {{ draft.sku }} · {{ draft.selected ? '已选择' : '未选择' }}
      </text>
      <text class="chip" :class="{ 'chip--active': draft.selected }" @tap="toggleDraft(draft.productId)">
        {{ draft.selected ? '取消选择' : '选择此商品' }}
      </text>
      <view class="field">
        <text class="field__label">拟修订名称</text>
        <input class="field__input" :value="draft.name" :disabled="busy || locked" @input="setDraft(draft.productId, { name: inputValue($event) })" />
      </view>
      <view class="field">
        <text class="field__label">拟修订参数与事实</text>
        <input class="field__input" :value="draft.facts" :disabled="busy || locked" @input="setDraft(draft.productId, { facts: inputValue($event) })" />
      </view>
      <FactLine label="原名称" :value="draft.originalName" />
      <FactLine label="原参数" :value="draft.originalFacts" />
      <FactLine label="来源" :value="`${draft.sourceFilename} · 第 ${draft.sourceRowNumber} 行 · 批次 ${draft.sourceBatchId}`" />
    </view>
    <view v-if="drafts.length > 0" class="row">
      <ActionButton label="上一页" :disabled="busy || page === 0" @tap="page -= 1" />
      <text class="chip">第 {{ page + 1 }} / {{ totalPages }} 页 · 共 {{ drafts.length }} 个商品</text>
      <ActionButton label="下一页" :disabled="busy || page + 1 >= totalPages" @tap="page += 1" />
    </view>
    <view class="field">
      <text class="field__label">修订依据</text>
      <input class="field__input" :value="reason" :disabled="busy || locked" @input="reason = inputValue($event)" />
    </view>
    <view class="card" @tap="approved = !approved">
      <text class="chip" :class="{ 'chip--active': approved }">
        {{ approved ? '已核对' : '未核对' }} · 已核对全部商品的前后差异，批准应用到本地商品数据
      </text>
    </view>
    <ActionButton
      :label="pending ? '核对同次创建' : '创建修订差异预览'"
      variant="primary"
      block
      :disabled="busy || (!approved && !pending)"
      @tap="createEdit"
    />

    <template v-if="record !== null">
      <text class="section-title">修订差异与应用结果</text>
      <FactLine label="修订记录" :value="`#${record.id} · ${labelOf(editStatuses, record.status)} · v${record.version}`" />
      <FactLine label="当前有效商品数" :value="record.current_count" />
      <FactLine label="审批时间" :value="record.decided_at" :zone="zone" />
      <FactLine label="预览指纹" :value="record.preview_hash" />
      <view class="row">
        <ActionButton label="回读记录与当前状态" :disabled="busy" @tap="read(record.id)" />
      </view>
      <text v-if="uncertain" class="warn">请先回读记录，核对上次操作结果。</text>
      <template v-if="record.snapshot">
        <FactLine label="修订依据" :value="record.snapshot.reason" />
        <FactLine label="来源修订" :value="record.snapshot.source_revision" />
        <FactLine label="范围" :value="`${labelOf(importIdentities, record.snapshot.data_identity)} / ${labelOf(importChannels, record.snapshot.channel)}`" />
        <view v-for="item in record.snapshot.items ?? []" :key="item.product_id" class="card">
          <text class="card__title">{{ item.after.sku }} · {{ editResult(item.result) }}</text>
          <text class="hint">{{ item.message }}</text>
          <FactLine label="原名称" :value="item.before.name" />
          <FactLine label="新名称" :value="item.after.name" />
          <FactLine label="原参数" :value="item.before.facts" />
          <FactLine label="新参数" :value="item.after.facts" />
          <FactLine label="来源" :value="`${item.source.filename} · 第 ${item.source.row_number} 行 · 批次 ${item.source.batch_id}`" />
          <ActionButton label="查看来源导入批次" :disabled="busy" @tap="openPage('/pages/imports/index', { batch: `${item.source.batch_id}` })" />
        </view>
      </template>
      <view class="row">
        <ActionButton
          v-if="record.status === 'draft'"
          label="批准并应用本地修订"
          variant="primary"
          :disabled="busy || !approved"
          @tap="approve"
        />
        <ActionButton v-if="record.status === 'draft'" label="拒绝修订" :disabled="busy" @tap="control('reject')" />
        <ActionButton v-if="record.status === 'draft'" label="撤销本次修订" :disabled="busy" @tap="control('withdraw')" />
        <ActionButton v-if="record.status !== 'cleared'" label="清除差异正文" :disabled="busy" @tap="control('clear')" />
        <ActionButton
          v-if="record.output_batch_id !== null && record.output_batch_id !== undefined"
          label="查看应用批次与行结果"
          :disabled="busy"
          @tap="openPage('/pages/imports/index', { batch: `${record.output_batch_id}` })"
        />
      </view>
    </template>

    <text class="section-title">本地修订历史</text>
    <view class="row">
      <ActionButton label="刷新历史" :disabled="busy" @tap="load" />
    </view>
    <view v-if="history.length === 0 && !busy" class="card">
      <text class="hint">当前身份与渠道下暂无本地修订记录。</text>
    </view>
    <view v-for="item in history" :key="item.id" class="card">
      <text class="card__title">修订 #{{ item.id }} · {{ labelOf(editStatuses, item.status) }}</text>
      <text class="hint">
        v{{ item.version }} · {{ businessTimeText(item.created_at, zone) }} · 当前有效商品 {{ item.current_count }}
      </text>
      <ActionButton label="打开修订记录" :disabled="busy" @tap="read(item.id)" />
    </view>
    <ActionButton v-if="nextCursor !== null" label="加载更多修订" :disabled="busy" @tap="loadMore" />
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 商品本地修订：从商品质量预览读取当前商品与来源，批量选择名称/参数事实，
 * 生成差异预览，批准后应用到本地商品数据并回读结果；支持撤回、清除与批次深链。
 * 接口（来自 contracts/ui-contract.json 的 r2.product_edits，来源目录复用 r2.product_quality）：
 *   POST /api/shops/{shop_id}/product-quality/preview     （读取当前商品与来源修订）
 *   POST /api/shops/{shop_id}/product-edits
 *   GET  /api/shops/{shop_id}/product-edits
 *   GET  /api/shops/{shop_id}/product-edits/{edit_id}
 *   POST /api/shops/{shop_id}/product-edits/{edit_id}/approve
 *   POST /api/shops/{shop_id}/product-edits/{edit_id}/{action}   （reject / withdraw / clear）
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import ActionButton from '../../ui/ActionButton.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import { ApiError, apiGet, apiPost, asObject, asRows, newRequestId } from '../../core/api'
import { businessTimeText } from '../../core/format'
import { importChannels, importIdentities, labelOf } from '../../core/labels'
import { openPage, pageQuery } from '../../core/links'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

const editStatuses: Record<string, string> = {
  draft: '待审批',
  applied: '已应用',
  failed: '应用失败',
  rejected: '已拒绝',
  stale: '来源变化',
  revoked: '已撤销',
  cleared: '正文已清除',
}

const editResults: Record<string, string> = {
  pending: '等待审批',
  applied: '已应用',
  conflict: '与当前商品冲突',
  blocked: '已阻断',
}

interface SourceReference {
  batch_id: number
  row_id: number
  row_number: number
  filename: string
  imported_at: string
}

interface QualityProduct {
  product_id: number
  sku: string
  name: string
  facts: string
  source: SourceReference
}

interface Catalog {
  scope: { data_identity: string; channel?: string | null; sku_prefix: string }
  source_revision: number
  products: QualityProduct[]
}

interface ProductData {
  sku: string
  name: string
  facts: string
}

interface EditItem {
  product_id: number
  before: ProductData
  after: ProductData
  source: SourceReference
  result: string
  message: string
}

interface EditSnapshot {
  source_revision: number
  data_identity: string
  channel: string
  reason: string
  items: EditItem[]
}

interface EditSaved {
  id: number
  shop_id: number
  version: number
  status: string
  preview_hash: string
  snapshot: EditSnapshot | null
  output_batch_id?: number | null
  created_at: string
  decided_at?: string | null
  current_count: number
}

interface Draft {
  productId: number
  sku: string
  selected: boolean
  name: string
  facts: string
  originalName: string
  originalFacts: string
  sourceRowId: number
  sourceBatchId: number
  sourceRowNumber: number
  sourceFilename: string
}

const identity = ref('user_import')
const channel = ref('generic')
const skuPrefix = ref('')
const catalog = ref<Catalog | null>(null)
const drafts = ref<Draft[]>([])
const page = ref(0)
const batchNamePrefix = ref('')
const batchFactsAppend = ref('')
const reason = ref('')
const record = ref<EditSaved | null>(null)
const history = ref<EditSaved[]>([])
const nextCursor = ref<number | null>(null)
const approved = ref(false)
const pending = ref(false)
const pendingKey = ref<string | null>(null)
const uncertain = ref(false)
const busy = ref(false)
const error = ref('')
const successText = ref('')
const ready = ref(false)

const zone = computed(() => shopTimezone())
const shopName = computed(() => state.shops.find((shop) => shop.id === state.shopId)?.name ?? '未知')
const identityOptions = computed(() => Object.entries(importIdentities).map(([key, label]) => ({ key, label })))
const identityIndex = computed(() => Math.max(0, Object.keys(importIdentities).indexOf(identity.value)))
const channelOptions = computed(() => Object.entries(importChannels).map(([key, label]) => ({ key, label })))
const channelIndex = computed(() => Math.max(0, Object.keys(importChannels).indexOf(channel.value)))
const selectedCount = computed(() => drafts.value.filter((item) => item.selected).length)
const totalPages = computed(() => Math.max(1, Math.ceil(drafts.value.length / 10)))
const pagedDrafts = computed(() => drafts.value.slice(page.value * 10, page.value * 10 + 10))
/** 结果待确认时锁定目录与表单，避免差异与预览指纹不一致。 */
const locked = computed(() => pending.value)

function success(text: string): void {
  successText.value = text
  void Taro.showToast({ title: text, icon: 'none' })
}

/** 写操作：断线/超时提示“结果未知，请回读”，不推断成功。 */
async function writeAction(action: () => Promise<void>, done: string, hint: string): Promise<void> {
  let unknown = false
  const message = await perform(async () => {
    try {
      await action()
    } catch (caught) {
      unknown = caught instanceof ApiError && caught.kind === 'network_unknown'
      throw caught
    }
  })
  if (message === '') {
    success(done)
    return
  }
  error.value = message + (unknown ? ` 结果未知，请回读${hint}核对后再决定。` : '')
  if (unknown) uncertain.value = true
}

function editResult(result: string): string {
  return editResults[result] ?? result
}

function setDraft(productId: number, patch: Partial<Draft>): void {
  drafts.value = drafts.value.map((item) => (item.productId === productId ? { ...item, ...patch } : item))
}

function toggleDraft(productId: number): void {
  if (locked.value) return
  drafts.value = drafts.value.map((item) => (
    item.productId === productId ? { ...item, selected: !item.selected } : item
  ))
}

function applyBatch(): void {
  const prefix = batchNamePrefix.value
  const append = batchFactsAppend.value
  drafts.value = drafts.value.map((item) => {
    if (!item.selected) return item
    const name = prefix === '' ? item.name : `${prefix}${item.originalName}`
    const facts = append === '' ? item.facts : `${item.facts} ${append}`.trim()
    return { ...item, name, facts }
  })
  success('已把批量输入应用到已选商品表单，请逐项核对后再预览差异。')
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  // 从商品质量页等入口带入的预选范围先落到表单，再读取历史。
  const query = pageQuery()
  if (query.identity !== undefined && query.identity in importIdentities) identity.value = query.identity
  if (query.channel !== undefined && query.channel in importChannels) channel.value = query.channel
  await load()
  const editId = Number(query.edit ?? '')
  if (Number.isFinite(editId) && editId > 0) await read(editId)
})

async function load(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    const pageValue = asObject<{ items: EditSaved[]; next_cursor: number | null }>(
      await apiGet(shopPath('/product-edits'), {
        data_identity: identity.value,
        channel: channel.value,
      }),
    )
    history.value = asRows<EditSaved>(pageValue?.items)
    nextCursor.value = pageValue?.next_cursor ?? null
  })
  error.value = message
}

async function loadMore(): Promise<void> {
  const cursor = nextCursor.value
  if (cursor === null) return
  const message = await perform(async () => {
    const pageValue = asObject<{ items: EditSaved[]; next_cursor: number | null }>(
      await apiGet(shopPath('/product-edits'), {
        data_identity: identity.value,
        channel: channel.value,
        before: cursor,
      }),
    )
    const incoming = asRows<EditSaved>(pageValue?.items)
    history.value = [
      ...history.value,
      ...incoming.filter((item) => !history.value.some((old) => old.id === item.id)),
    ]
    nextCursor.value = pageValue?.next_cursor ?? null
  })
  error.value = message
}

async function loadCatalog(): Promise<void> {
  const message = await perform(async () => {
    if (skuPrefix.value.trim().length > 120) throw new Error('SKU 前缀最多 120 字符。')
    const value = asObject<Catalog>(
      await apiPost(shopPath('/product-quality/preview'), {
        data_identity: identity.value,
        channel: channel.value,
        sku_prefix: skuPrefix.value.trim(),
      }),
    )
    if (value === null) throw new Error('商品目录响应无法读取，请刷新重试。')
    catalog.value = value
    record.value = null
    approved.value = false
    page.value = 0
    // 重新读取目录代表新的修订意图：释放旧的幂等键与待确认状态。
    pending.value = false
    pendingKey.value = null
    uncertain.value = false
    const focus = Number(pageQuery().product ?? '')
    drafts.value = asRows<QualityProduct>(value.products).map((product) => ({
      productId: product.product_id,
      sku: product.sku,
      selected: Number.isFinite(focus) && focus > 0 ? product.product_id === focus : false,
      name: product.name,
      facts: product.facts,
      originalName: product.name,
      originalFacts: product.facts,
      sourceRowId: product.source.row_id,
      sourceBatchId: product.source.batch_id,
      sourceRowNumber: product.source.row_number,
      sourceFilename: product.source.filename,
    }))
  })
  if (message === '') success('已读取当前商品与来源，请选择要修订的商品。')
  else error.value = message
}

async function createEdit(): Promise<void> {
  if (pending.value && record.value !== null) {
    await read(record.value.id)
    return
  }
  const changes = drafts.value
    .filter((item) => item.selected)
    .map((item) => ({
      product_id: item.productId,
      expected_source_row_id: item.sourceRowId,
      name: item.name.trim(),
      facts: item.facts,
    }))
  if (changes.length === 0 || changes.length > 50) {
    error.value = '请选择 1–50 个有修改的商品。'
    return
  }
  const key = pendingKey.value ?? newRequestId()
  pendingKey.value = key
  await writeAction(async () => {
    if (reason.value.trim() === '') throw new Error('请填写修订依据。')
    for (const change of changes) {
      if (change.name === '') throw new Error('商品名称不能为空。')
      if (change.name.length > 240) throw new Error(`${change.name} 的名称最多 240 字符。`)
      if (change.facts.length > 2000) throw new Error(`商品 ${change.product_id} 的参数最多 2000 字符。`)
    }
    const value = asObject<EditSaved>(
      await apiPost(shopPath('/product-edits'), {
        data_identity: identity.value,
        channel: channel.value,
        reason: reason.value.trim(),
        changes,
        request_id: key,
      }),
    )
    if (value === null) throw new Error('创建响应无法读取，请到修订历史回读核对。')
    pending.value = false
    pendingKey.value = null
    record.value = value
    approved.value = false
    await load()
  }, '修订差异预览已创建，请核对前后差异后批准。', '修订历史')
}

async function read(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<EditSaved>(await apiGet(shopPath(`/product-edits/${id}`)))
    if (value === null) throw new Error('修订响应无法读取，请刷新重试。')
    record.value = value
    approved.value = false
    pending.value = false
    pendingKey.value = null
    uncertain.value = false
  })
  error.value = message
}

async function approve(): Promise<void> {
  const current = record.value
  if (current === null) return
  const modal = await Taro.showModal({
    title: '批准并应用本地修订',
    content: `将按预览指纹写入本地商品数据，来源修订 ${current.snapshot?.source_revision ?? '未知'}。不会推送到任何平台。`,
    confirmText: '批准',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<EditSaved>(
      await apiPost(shopPath(`/product-edits/${current.id}/approve`), {
        version: current.version,
        expected_preview_hash: current.preview_hash,
        confirm: true,
      }),
    )
    if (value === null) throw new Error('批准响应无法读取，请回读修订记录核对。')
    record.value = value
    await load()
  }, '本地修订已应用，请核对当前有效商品数与应用批次。', '修订记录')
}

async function control(action: 'reject' | 'withdraw' | 'clear'): Promise<void> {
  const current = record.value
  if (current === null) return
  const titles: Record<string, string> = {
    reject: '拒绝修订',
    withdraw: '撤销本地修订',
    clear: '清除修订正文',
  }
  const modal = await Taro.showModal({
    title: titles[action],
    content: action === 'clear'
      ? '清除差异正文与依据；已生效修订还会清除对应导入批次并回退其当前商品影响，无法恢复已清除正文。'
      : `按当前版本处理修订 #${current.id}，完成后回读结果。`,
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    const value = asObject<EditSaved>(
      await apiPost(shopPath(`/product-edits/${current.id}/${action}`), {
        version: current.version,
        confirm: true,
      }),
    )
    if (value !== null) record.value = value
    await load()
  }, '修订状态已更新。', '修订历史')
}
</script>
