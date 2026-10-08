<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ShopOverview } from '@/types/overview'
import type { AnalysisResult, SourceDetail, SourceReference } from '@/types/analytics'
import { analyticsApi } from '@/api/analytics'
import { errorMessage } from '@/api/client'
import AnalysisEvidence from './AnalysisEvidence.vue'
import FeedbackBanner from './FeedbackBanner.vue'

const props = defineProps<{ shop: ShopOverview; timezone: string }>()
const evidence = ref<AnalysisResult | null>(null)
const source = ref<SourceDetail | null>(null)
const error = ref('')
const busy = ref(false)
const sourcePage = ref(0)
const stockCount = ref(20)
const messageCount = ref(20)
const sources = computed(() =>
  props.shop.sources.slice(sourcePage.value * 20, (sourcePage.value + 1) * 20),
)
const time = (value: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    timeZone: props.timezone,
    dateStyle: 'short',
    timeStyle: 'long',
  }).format(new Date(value))
const amount = (value: string | null) => value ?? '未知 / 不完整'
const exportedCoverage = computed(() => {
  const refs = props.shop.sources
  if (!refs.length) return '未获取来源'
  const values = refs.flatMap((r) => (r.exported_at ? [r.exported_at] : [])).sort()
  const range = values.length ? `${time(values[0]!)} 至 ${time(values[values.length - 1]!)}` : '未知'
  return `${range}${values.length < refs.length ? '；含导出时间未知的来源' : ''}`
})
watch(
  () => props.shop,
  () => {
    evidence.value = null
    source.value = null
    sourcePage.value = 0
    error.value = ''
  },
)
async function inspect(ref: SourceReference): Promise<void> {
  busy.value = true
  error.value = ''
  source.value = null
  const shop = props.shop
  try {
    const loaded = await analyticsApi.source(shop.shop_id, ref.row_id)
    if (shop === props.shop) source.value = loaded
  } catch (cause) {
    if (shop === props.shop) error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <article class="section-block overview-shop" :aria-label="shop.shop_name">
    <div class="section-title">
      <h3>{{ shop.shop_name }}</h3>
      <span class="outline-label"
        >{{ shop.platform }} · {{ shop.market }} · 来源 v{{ shop.source_revision }}</span
      >
    </div>
    <p>店铺 #{{ shop.shop_id }} · 市场为经营资料登记值。所有下列数量限已导入覆盖范围。</p>
    <p>来源导出截至范围：{{ exportedCoverage }}。详情见下方全部来源。</p>
    <section
      v-for="group in shop.currencies"
      :key="group.currency"
      class="currency-detail"
      :aria-label="`${shop.shop_name} ${group.currency}`"
    >
      <h4>{{ group.currency }} / 订单与商品</h4>
      <dl class="overview-values">
        <div>
          <dt>净销售额</dt>
          <dd>{{ amount(group.current.analysis.summary.sales) }}</dd>
          <small>对比期 {{ amount(group.comparison.analysis.summary.sales) }}</small>
        </div>
        <div>
          <dt>已观察支付订单</dt>
          <dd>{{ group.current.orders ?? '未知' }}</dd>
          <small>对比期 {{ group.comparison.orders ?? '未知' }} · 同店同币种去重</small>
        </div>
        <div>
          <dt>行退款额</dt>
          <dd>{{ amount(group.current.refunds) }}</dd>
          <small
            >已知子集 {{ group.current.known_refunds }} ·
            {{ group.current.refund_known_lines }} 行</small
          >
        </div>
        <div>
          <dt>已知商品毛利</dt>
          <dd>{{ amount(group.current.analysis.summary.gross_profit) }}</dd>
          <small
            >已知子集 {{ group.current.analysis.summary.known_gross_subtotal }} ·
            净利润未结算</small
          >
        </div>
      </dl>
      <p>
        销售差额 {{ amount(group.sales_change) }} · 变化率
        {{
          group.sales_change_percent === null
            ? '未知（对比缺失或基数非正）'
            : `${group.sales_change_percent}%`
        }}
      </p>
      <p>
        待发货订单 {{ group.current.pending_orders ?? '未知 / 不完整' }} ·
        {{ group.current.unknown_fulfillment_lines }} 行履约状态未知；已发现
        {{ group.current.pending_sources.length }} 行未履约或部分履约。
      </p>
      <p>
        购买数量前五 SKU：{{
          group.current.top_skus.join('、') || '未获取'
        }}。原购买量不扣退货件数。
      </p>
      <p>
        低已知毛利 SKU：{{
          group.current.analysis.ranking_available
            ? group.current.analysis.candidates.join('、') || '此口径未命中'
            : '数据不足，待核对'
        }}。
      </p>
      <details>
        <summary>公式与缺口</summary>
        <p>{{ group.current.analysis.formula }}</p>
        <p>{{ group.current.analysis.cost_basis }}</p>
        <p v-for="warning in group.current.analysis.warnings" :key="warning">{{ warning }}</p>
        <p>未归集：{{ group.current.analysis.fee_gaps.join('、') }}</p>
      </details>
      <div class="button-row">
        <button class="button secondary small" @click="evidence = group.current.analysis">
          查看本期 {{ group.currency }} 订单依据</button
        ><button class="button secondary small" @click="evidence = group.comparison.analysis">
          查看对比期 {{ group.currency }} 依据
        </button>
      </div>
    </section>
    <AnalysisEvidence v-if="evidence" :result="evidence" :shop-id="shop.shop_id" />
    <details class="analysis-line">
      <summary>
        当前库存 · 已知低库存 {{ shop.inventory_low ?? '未知' }} · 未知快照
        {{ shop.inventory_unknown }}
      </summary>
      <p>按当前快照时效独立核验，不表示所选日期的历史库存。未导入库存时不能推断为零。</p>
      <p v-if="!shop.inventory.length">
        未获取库存。<RouterLink to="/imports">导入库存快照</RouterLink>
      </p>
      <div v-for="item in shop.inventory.slice(0, stockCount)" :key="item.id" class="analysis-line">
        <p>
          {{ item.sku }} · {{ item.channel }} · 来源可售 {{ item.available }} / 阈值
          {{ item.safety_threshold }}
        </p>
        <p>{{ item.reason }} · {{ time(item.snapshot_at) }}</p>
        <button class="button secondary small" :disabled="busy" @click="inspect(item.source)">
          查看库存来源 · 行 {{ item.source.row_number }}
        </button>
      </div>
      <button
        v-if="shop.inventory.length > stockCount"
        class="button secondary small"
        @click="stockCount += 20"
      >
        再显示 20 条快照
      </button>
    </details>
    <details class="analysis-line">
      <summary>区间客户消息 · {{ shop.message_count ?? '未知 / 未获取' }}</summary>
      <p>回复状态未知，以下消息须到客服工作台核对。</p>
      <div
        v-for="message in shop.messages.slice(0, messageCount)"
        :key="message.source.row_id"
        class="analysis-line"
      >
        <p>{{ message.channel }} · {{ message.message_id }} · {{ time(message.sent_at) }}</p>
        <button class="button secondary small" :disabled="busy" @click="inspect(message.source)">
          查看消息来源 · 行 {{ message.source.row_number }}
        </button>
      </div>
      <button
        v-if="shop.messages.length > messageCount"
        class="button secondary small"
        @click="messageCount += 20"
      >
        再显示 20 条消息</button
      ><RouterLink to="/support">打开客服工作台</RouterLink>
    </details>
    <details class="analysis-line">
      <summary>
        当时未结待办 · {{ shop.tasks.length }}{{ shop.tasks_has_more ? '+' : '' }} 条
      </summary>
      <p>仅回顾生成摘要时已有记录，打开工作台重新核验来源、规则与当前状态。</p>
      <p v-for="task in shop.tasks" :key="task.id">
        #{{ task.id }} · {{ task.kind }} · {{ task.status }}
      </p>
      <RouterLink to="/">打开工作台查看待办</RouterLink>
    </details>
    <details class="analysis-line">
      <summary>全部来源与数据截至 · {{ shop.sources.length }} 行</summary>
      <p v-if="!shop.sources.length">未获取可用来源；空窗口不等于零经营活动。</p>
      <div v-for="ref in sources" :key="ref.row_id" class="analysis-line">
        <p>{{ ref.filename }} · 批次 #{{ ref.batch_id }} · 行 {{ ref.row_number }}</p>
        <p>
          导出截至：{{
            ref.exported_at ? time(ref.exported_at) : '未知（不以导入时间替代）'
          }}；导入：{{ time(ref.imported_at) }}
        </p>
        <button class="button secondary small" :disabled="busy" @click="inspect(ref)">
          查看原始行 #{{ ref.row_id }}
        </button>
      </div>
      <div v-if="shop.sources.length > 20" class="pagination">
        <button class="button secondary small" :disabled="sourcePage === 0" @click="sourcePage--">
          上一页来源</button
        ><span>{{ sourcePage + 1 }}</span
        ><button
          class="button secondary small"
          :disabled="(sourcePage + 1) * 20 >= shop.sources.length"
          @click="sourcePage++"
        >
          下一页来源
        </button>
      </div>
    </details>
    <FeedbackBanner :message="error" />
    <section v-if="source" class="source-detail" aria-label="总览来源原始值">
      <h4>
        {{ source.reference.filename }} · 批次 #{{ source.reference.batch_id }} · 行
        {{ source.reference.row_number }}
      </h4>
      <p>{{ source.batch_status }} · {{ source.reference.data_identity }}</p>
      <p>原始单元格</p>
      <pre>{{ JSON.stringify(source.raw, null, 2) }}</pre>
      <p>人工修正</p>
      <pre>{{ JSON.stringify(source.corrections, null, 2) }}</pre>
      <p>规范化值</p>
      <pre>{{ JSON.stringify(source.normalized, null, 2) }}</pre>
    </section>
  </article>
</template>
<style scoped>
.overview-shop {
  overflow-wrap: anywhere;
}
.currency-detail {
  padding: 20px 0;
  border-bottom: 1px solid var(--line);
}
.overview-values {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.overview-values div {
  padding: 14px;
  background: var(--surface, #f5f6f0);
  border-radius: 6px;
}
dd {
  margin: 8px 0;
  font-size: 21px;
  font-weight: 600;
}
small {
  color: var(--muted);
}
.button-row {
  margin-top: 14px;
}
p {
  line-height: 1.7;
}
@media (max-width: 760px) {
  .overview-values {
    grid-template-columns: 1fr;
  }
}
</style>
