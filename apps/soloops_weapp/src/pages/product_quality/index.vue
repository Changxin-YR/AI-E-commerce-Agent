<template>
  <PageShell
    title="商品质量检查"
    subtitle="按商品本地事实与成本依据检查缺失项；未检查项单独列出，不视为通过。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load"
  >
    <FactLine label="所属店铺" :value="shopName" />
    <FactLine label="业务时区" :value="zone" />

    <text class="section-title">检查范围</text>
    <view class="field">
      <text class="field__label">数据身份</text>
      <picker mode="selector" :range="identityOptions" range-key="label" :value="identityIndex" @change="identity = identityOptions[Number(pickerValue($event))]?.key ?? 'user_import'">
        <view class="field__picker">{{ labelOf(importIdentities, identity) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">渠道</text>
      <picker mode="selector" :range="channelOptions" range-key="label" :value="channelIndex" @change="channel = channelOptions[Number(pickerValue($event))]?.key ?? ''">
        <view class="field__picker">{{ channel === '' ? '全部渠道' : labelOf(importChannels, channel) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">SKU 前缀（最多 120 字符）</text>
      <input class="field__input" :value="skuPrefix" :disabled="busy || locked" @input="skuPrefix = inputValue($event)" />
    </view>
    <ActionButton label="检查当前商品" variant="primary" block :disabled="busy || locked" @tap="check" />

    <template v-if="saved !== null">
      <FactLine
        label="已存报告"
        :value="`#${saved.id} · ${saved.status === 'current' ? '当前有效' : saved.status === 'stale' ? '来源变化 · 待重查' : '正文已清除'}`"
      />
      <view class="row">
        <ActionButton label="回读存档状态" :disabled="busy" @tap="inspect(saved.id)" />
        <ActionButton label="清除报告正文" :disabled="busy" @tap="clearReport(saved.id)" />
      </view>
    </template>

    <template v-if="result !== null">
      <text class="section-title">质量报告</text>
      <FactLine label="检查时间" :value="result.checked_at" :zone="zone" />
      <FactLine label="规则版本" :value="result.rule_version" />
      <FactLine label="来源修订" :value="result.source_revision" />
      <FactLine label="检查商品 / 受影响商品" :value="`${result.product_count} / ${result.affected_products}`" />
      <FactLine label="缺失 / 待审问题" :value="`${result.missing_count} / ${result.review_count}`" />
      <FactLine label="预览指纹" :value="result.preview_hash" />

      <text class="section-title">检查覆盖</text>
      <view v-for="coverage in result.coverage ?? []" :key="coverage.code" class="card">
        <text class="card__title">{{ coverage.label }} · {{ coverage.status === 'checked' ? '已检查' : '未检查' }}</text>
        <text class="hint">{{ coverage.reason }}</text>
      </view>
      <text v-for="limit in result.limitations ?? []" :key="limit" class="warn">{{ limit }}</text>

      <text class="section-title">受影响商品与来源</text>
      <view v-for="product in result.products ?? []" :key="product.product_id" class="card">
        <text class="card__title">{{ product.sku }} · {{ product.name }}</text>
        <text class="hint">{{ (product.issues ?? []).length }} 项问题 · {{ labelOf(importChannels, product.channel) }}</text>
        <FactLine label="参数与事实" :value="product.facts" />
        <FactLine label="售价" :value="moneyText(product.price, product.currency)" />
        <FactLine label="采购成本" :value="moneyText(product.unit_cost, product.cost_currency)" />
        <FactLine
          label="相似 SKU"
          :value="(product.similar_skus ?? []).length === 0 ? '无' : `${(product.similar_skus ?? []).join('、')} · 共 ${product.similar_sku_count} 个`"
        />
        <SourceEvidence :source="product.source" :zone="zone" />
        <view v-for="issue in product.issues ?? []" :key="`${product.product_id}:${issue.code}:${issue.field}`" class="card">
          <text class="card__title">{{ issue.status === 'missing' ? '缺失' : '待审' }} · {{ issue.field }}</text>
          <text class="hint">{{ issue.reason }}</text>
          <text class="hint">建议：{{ issue.suggestion }}</text>
          <text class="hint">规则：{{ issue.code }}</text>
        </view>
        <view class="row">
          <ActionButton label="修订名称与参数" :disabled="busy" @tap="openPage('/pages/product_edits/index', { product: `${product.product_id}` })" />
          <ActionButton label="查看商品与文案" :disabled="busy" @tap="openPage('/pages/listings/index', { product: `${product.product_id}` })" />
        </view>
      </view>
      <view v-if="(result.products ?? []).length === 0" class="card">
        <text class="hint">当前范围没有受影响的商品记录。可放宽 SKU 前缀或调整范围后重试。</text>
      </view>

      <view class="card" @tap="confirmed = !confirmed">
        <text class="chip" :class="{ 'chip--active': confirmed }">
          {{ confirmed ? '已核对' : '未核对' }} · 已核对检查范围、规则结果与未检查项
        </text>
      </view>
      <ActionButton
        :label="pending ? '核对同次保存' : '保存质量报告'"
        variant="primary"
        block
        :disabled="busy || (!confirmed && !pending)"
        @tap="saveReport"
      />
    </template>

    <text class="section-title">质量报告历史</text>
    <view class="row">
      <ActionButton label="刷新历史" :disabled="busy" @tap="load" />
    </view>
    <view v-if="history.length === 0 && !busy" class="card">
      <text class="hint">当前身份与渠道下暂无质量报告。</text>
    </view>
    <view v-for="item in history" :key="item.id" class="card">
      <text class="card__title">报告 #{{ item.id }} · {{ reportStatus(item.status) }}</text>
      <text class="hint">
        {{ businessTimeText(item.created_at, zone) }} ·
        {{ labelOf(importIdentities, item.scope.data_identity) }} /
        {{ item.scope.channel === null || item.scope.channel === undefined ? '全部渠道' : labelOf(importChannels, item.scope.channel) }}
      </text>
      <text class="hint">SKU 前缀：{{ item.scope.sku_prefix === '' ? '未限定' : item.scope.sku_prefix }}</text>
      <view class="row">
        <ActionButton label="打开报告" :disabled="busy" @tap="inspect(item.id)" />
        <ActionButton label="清除报告正文" :disabled="busy || item.snapshot === null" @tap="clearReport(item.id)" />
      </view>
    </view>
    <ActionButton v-if="nextCursor !== null" label="加载更多" :disabled="busy" @tap="loadMore" />
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 商品质量检查：范围预览、持久报告、来源回读与清除。
 * 接口（均来自 contracts/ui-contract.json 的 r2.product_quality）：
 *   POST /api/shops/{shop_id}/product-quality/preview
 *   POST /api/shops/{shop_id}/product-quality/reports
 *   GET  /api/shops/{shop_id}/product-quality/reports
 *   GET  /api/shops/{shop_id}/product-quality/reports/{report_id}
 *   POST /api/shops/{shop_id}/product-quality/reports/{report_id}/clear
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import ActionButton from '../../ui/ActionButton.vue'
import SourceEvidence from '../../ui/SourceEvidence.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import { ApiError, apiGet, apiPost, asObject, asRows, newRequestId } from '../../core/api'
import { businessTimeText, moneyText } from '../../core/format'
import { importChannels, importIdentities, labelOf } from '../../core/labels'
import { openPage } from '../../core/links'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

const reportStatuses: Record<string, string> = {
  current: '当前有效',
  stale: '来源变化 · 待重查',
  cleared: '正文已清除',
}

interface SourceReference {
  batch_id: number
  row_id: number
  row_number: number
  filename: string
  imported_at: string
}

interface QualityScope {
  data_identity: string
  channel?: string | null
  sku_prefix: string
}

interface QualityIssue {
  code: string
  field: string
  status: string
  reason: string
  suggestion: string
}

interface QualityProduct {
  product_id: number
  sku: string
  name: string
  facts: string
  price?: string | null
  currency?: string | null
  unit_cost?: string | null
  cost_currency?: string | null
  channel: string
  source: SourceReference
  issues: QualityIssue[]
  similar_skus: string[]
  similar_sku_count: number
}

interface QualityCoverage {
  code: string
  label: string
  status: string
  reason: string
}

interface QualityResult {
  shop_id: number
  scope: QualityScope
  source_revision: number
  checked_at: string
  rule_version: string
  preview_hash: string
  product_count: number
  affected_products: number
  missing_count: number
  review_count: number
  coverage: QualityCoverage[]
  limitations: string[]
  products: QualityProduct[]
}

interface QualitySaved {
  id: number
  shop_id: number
  status: string
  created_at: string
  scope: QualityScope
  snapshot: QualityResult | null
}

const identity = ref('user_import')
const channel = ref('')
const skuPrefix = ref('')
const result = ref<QualityResult | null>(null)
const saved = ref<QualitySaved | null>(null)
const history = ref<QualitySaved[]>([])
const nextCursor = ref<number | null>(null)
const confirmed = ref(false)
const pending = ref(false)
const pendingKey = ref<string | null>(null)
const busy = ref(false)
const error = ref('')
const successText = ref('')
const ready = ref(false)

const zone = computed(() => shopTimezone())
const shopName = computed(() => state.shops.find((shop) => shop.id === state.shopId)?.name ?? '未知')
const identityOptions = computed(() => Object.entries(importIdentities).map(([key, label]) => ({ key, label })))
const identityIndex = computed(() => Math.max(0, Object.keys(importIdentities).indexOf(identity.value)))
const channelOptions = computed(() => [{ key: '', label: '全部渠道' }, ...Object.entries(importChannels).map(([key, label]) => ({ key, label }))])
const channelIndex = computed(() => Math.max(0, channelOptions.value.findIndex((item) => item.key === channel.value)))
/** 结果待确认时锁定范围，避免保存的指纹与当前输入不一致。 */
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
  error.value = unknown ? `${message} 结果未知，请回读${hint}核对后再决定。` : message
}

function reportStatus(status: string): string {
  return labelOf(reportStatuses, status)
}

function scopePayload(): QualityScope {
  if (skuPrefix.value.trim().length > 120) throw new Error('SKU 前缀最多 120 字符。')
  return {
    data_identity: identity.value,
    channel: channel.value === '' ? null : channel.value,
    sku_prefix: skuPrefix.value.trim(),
  }
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  await load()
})

async function load(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    const page = asObject<{ items: QualitySaved[]; next_cursor: number | null }>(
      await apiGet(shopPath('/product-quality/reports'), {
        data_identity: identity.value,
        channel: channel.value,
      }),
    )
    history.value = asRows<QualitySaved>(page?.items)
    nextCursor.value = page?.next_cursor ?? null
  })
  error.value = message
}

async function loadMore(): Promise<void> {
  const cursor = nextCursor.value
  if (cursor === null) return
  const message = await perform(async () => {
    const page = asObject<{ items: QualitySaved[]; next_cursor: number | null }>(
      await apiGet(shopPath('/product-quality/reports'), {
        data_identity: identity.value,
        channel: channel.value,
        before: cursor,
      }),
    )
    const incoming = asRows<QualitySaved>(page?.items)
    history.value = [
      ...history.value,
      ...incoming.filter((item) => !history.value.some((old) => old.id === item.id)),
    ]
    nextCursor.value = page?.next_cursor ?? null
  })
  error.value = message
}

async function check(): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<QualityResult>(
      await apiPost(shopPath('/product-quality/preview'), scopePayload()),
    )
    if (value === null) throw new Error('检查响应无法读取，请刷新重试。')
    result.value = value
    saved.value = null
    confirmed.value = false
    // 新的检查结果代表新的保存意图：释放旧的幂等键与待确认状态。
    pending.value = false
    pendingKey.value = null
  })
  if (message === '') success('检查完成，请核对未检查项与受影响商品。')
  else error.value = message
}

async function saveReport(): Promise<void> {
  const current = result.value
  if (current === null) return
  if (pending.value && saved.value !== null) {
    await inspect(saved.value.id)
    return
  }
  const key = pendingKey.value ?? newRequestId()
  pendingKey.value = key
  await writeAction(async () => {
    const value = asObject<QualitySaved>(
      await apiPost(shopPath('/product-quality/reports'), {
        scope: current.scope,
        expected_revision: current.source_revision,
        expected_preview_hash: current.preview_hash,
        request_id: key,
        confirm: true,
      }),
    )
    if (value === null) throw new Error('保存响应无法读取，请到报告历史回读核对。')
    pending.value = false
    pendingKey.value = null
    saved.value = value
    await load()
  }, '质量报告已保存。', '报告历史')
}

async function inspect(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<QualitySaved>(await apiGet(shopPath(`/product-quality/reports/${id}`)))
    if (value === null) throw new Error('报告响应无法读取，请刷新重试。')
    saved.value = value
    result.value = value.snapshot
    channel.value = value.scope.channel ?? ''
    identity.value = value.scope.data_identity
    skuPrefix.value = value.scope.sku_prefix
    confirmed.value = false
    pending.value = false
    pendingKey.value = null
  })
  error.value = message
}

async function clearReport(id: number): Promise<void> {
  const modal = await Taro.showModal({
    title: '清除质量报告',
    content: '清除报告正文、SKU 前缀与来源依赖，无法恢复。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await writeAction(async () => {
    await apiPost(shopPath(`/product-quality/reports/${id}/clear`), { confirm: true })
    if (saved.value?.id === id) saved.value = null
    await load()
  }, '报告正文已清除。', '报告历史')
}
</script>
