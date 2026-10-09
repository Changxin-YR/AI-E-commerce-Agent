<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { analyticsApi } from '@/api/analytics'
import { errorMessage } from '@/api/client'
import type { AnalysisResult, SourceDetail, SourceReference } from '@/types/analytics'
import FeedbackBanner from './FeedbackBanner.vue'

const props = defineProps<{ result: AnalysisResult; shopId: number }>()
const page = ref(0)
const source = ref<SourceDetail | null>(null)
const error = ref('')
const busy = ref(false)
const rows = computed(() => props.result.lines.slice(page.value * 20, (page.value + 1) * 20))
watch(
  () => props.result,
  () => {
    page.value = 0
    source.value = null
    error.value = ''
  },
)
const time = (value: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    timeZone: props.result.scope.timezone,
    dateStyle: 'medium',
    timeStyle: 'long',
  }).format(new Date(value))
async function inspect(ref: SourceReference): Promise<void> {
  busy.value = true
  error.value = ''
  source.value = null
  const result = props.result
  try {
    const detail = await analyticsApi.source(props.shopId, ref.row_id)
    if (result === props.result) source.value = detail
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <section class="section-block analysis-evidence">
    <h2>订单行与来源</h2>
    <p>订单渠道：{{ result.scope.channel ?? '全部渠道' }}；商品成本取此店铺同身份的当前主档。</p>
    <p>共 {{ result.lines.length }} 行；取消、未付款、测试和其他币种的行显示排除原因。</p>
    <details v-for="line in rows" :key="line.source.row_id" class="analysis-line">
      <summary>
        {{ line.order_id }} / {{ line.line_id }} · {{ line.sku }} ·
        {{ line.included ? '计入' : '排除' }} · {{ line.status }}
      </summary>
      <p>
        {{ time(line.ordered_at) }} · {{ line.quantity }} 件 × {{ line.unit_price }}
        {{ line.currency }}
      </p>
      <p>
        行折扣 {{ line.discount ?? '未知' }} · 行退款 {{ line.refund ?? '未知' }} · 净销售额
        {{ line.sales ?? '未知 / 未计入' }}
      </p>
      <p>
        估算采购成本 {{ line.cost ?? '未知 / 未计入' }} · 已知毛利
        {{ line.gross_profit ?? '未知 / 未计入' }}
      </p>
      <p v-for="gap in line.gaps" :key="gap">{{ gap }}</p>
      <div class="button-row">
        <button class="button secondary small" :disabled="busy" @click="inspect(line.source)">
          订单来源 · 批次 {{ line.source.batch_id }} · 行 {{ line.source.row_number }}
        </button>
        <button
          v-if="line.cost_source"
          class="button secondary small"
          :disabled="busy"
          @click="inspect(line.cost_source)"
        >
          成本来源 · 批次 {{ line.cost_source.batch_id }} · 行 {{ line.cost_source.row_number }}
        </button>
      </div>
    </details>
    <div v-if="result.lines.length > 20" class="pagination">
      <button class="button secondary small" :disabled="page === 0" @click="page--">上一页</button>
      <span>{{ page + 1 }} / {{ Math.ceil(result.lines.length / 20) }}</span>
      <button
        class="button secondary small"
        :disabled="(page + 1) * 20 >= result.lines.length"
        @click="page++"
      >
        下一页
      </button>
    </div>
    <FeedbackBanner :message="error" />
    <section v-if="source" class="source-detail" aria-label="来源原始值">
      <h3>来源原始值 · {{ source.reference.filename }}</h3>
      <p>
        批次 {{ source.reference.batch_id }} · {{ source.reference.sheet_name || 'CSV' }} · 源行
        {{ source.reference.row_number }} · {{ source.batch_status }}
      </p>
      <p>
        导出时间：{{
          source.reference.exported_at
            ? time(source.reference.exported_at)
            : '未知（不能推断数据截至时间）'
        }}
      </p>
      <p>
        导入时间：{{ time(source.reference.imported_at) }} ·
        {{ source.reference.data_identity === 'synthetic' ? '合成测试数据' : '用户导入数据' }}
      </p>
      <h4>原始单元格</h4>
      <pre>{{ JSON.stringify(source.raw, null, 2) }}</pre>
      <h4>人工修正</h4>
      <pre>{{ JSON.stringify(source.corrections, null, 2) }}</pre>
      <h4>规范化值</h4>
      <pre>{{ JSON.stringify(source.normalized, null, 2) }}</pre>
    </section>
  </section>
</template>
