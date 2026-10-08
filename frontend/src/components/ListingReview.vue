<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { analyticsApi } from '@/api/analytics'
import { errorMessage } from '@/api/client'
import type { SourceDetail } from '@/types/analytics'
import {
  listingStatus,
  sourceStatus,
  type ListingContent,
  type ListingVersion,
} from '@/types/listings'
import FeedbackBanner from './FeedbackBanner.vue'
import FormField from './FormField.vue'

const props = defineProps<{
  item: ListingVersion
  busy: boolean
  timezone: string
  canRevise: boolean
}>()
const emit = defineEmits<{
  revise: [content: ListingContent]
  decide: [decision: 'approve' | 'reject', confirmed: boolean]
}>()
const content = reactive<ListingContent>({ title: '', description: '' })
const confirmed = ref(false)
const source = ref<SourceDetail | null>(null)
const sourceError = ref('')
const sourceBusy = ref(false)
watch(
  () => [props.item.id, props.item.version],
  () => {
    Object.assign(content, props.item.snapshot?.proposed ?? { title: '', description: '' })
    confirmed.value = false
    source.value = null
    sourceError.value = ''
  },
  { immediate: true },
)
watch(content, () => {
  confirmed.value = false
})
const dirty = computed(
  () =>
    content.title !== props.item.snapshot?.proposed.title ||
    content.description !== props.item.snapshot?.proposed.description,
)
const live = computed(() => props.item.source_status === 'current')
const engine = computed(
  () =>
    ({ local_template: '本地事实模板', manual: '人工编辑', test_double: '测试替身' })[
      props.item.engine
    ] ?? props.item.engine,
)
const time = (value: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    timeZone: props.timezone,
    dateStyle: 'medium',
    timeStyle: 'long',
  }).format(new Date(value))
async function inspect(): Promise<void> {
  const item = props.item
  if (!item.snapshot) return
  sourceBusy.value = true
  sourceError.value = ''
  try {
    const detail = await analyticsApi.source(item.shop_id, item.snapshot.product.source.row_id)
    if (props.item.id === item.id && props.item.version === item.version) source.value = detail
  } catch (cause) {
    sourceError.value = errorMessage(cause)
  } finally {
    sourceBusy.value = false
  }
}
</script>
<template>
  <section class="section-block listing-review" aria-label="Listing 审批详情">
    <div class="section-title">
      <div>
        <p class="eyebrow">REVIEW / VERSION {{ item.number }}</p>
        <h2>版本 {{ item.number }} · {{ listingStatus[item.status] }}</h2>
      </div>
      <span class="status-badge">{{ sourceStatus[item.source_status] }}</span>
    </div>
    <p>{{ time(item.created_at) }} · {{ engine }} · R1 内部可恢复写入</p>
    <p>执行渠道：本地保存 · 外部状态：未提交</p>
    <FeedbackBanner v-if="!live" :message="sourceStatus[item.source_status]" />
    <template v-if="item.snapshot">
      <p>
        影响对象：店铺 #{{ item.shop_id }} / SKU {{ item.snapshot.product.sku }}；仅更新本地 Listing
        文案。
      </p>
      <p>预计外部费用：0；恢复方式：将仍有有效来源的历史文案另存为待审版本，批准后生效。</p>
      <p>
        数据身份：{{
          item.snapshot.product.source.data_identity === 'synthetic'
            ? '合成测试数据'
            : '用户导入数据'
        }}
      </p>
      <div class="listing-diff">
        <section aria-label="修改前">
          <h3>
            修改前 ·
            {{ item.base_version_id ? `本地版本 #${item.base_version_id}` : '导入商品原文' }}
          </h3>
          <strong>{{ item.snapshot.before.title }}</strong>
          <p class="preserve-text">{{ item.snapshot.before.description || '未提供描述' }}</p>
        </section>
        <section aria-label="拟议版本">
          <h3>
            拟议版本 ·
            {{
              item.snapshot.before.title === item.snapshot.proposed.title &&
              item.snapshot.before.description === item.snapshot.proposed.description
                ? '与原文相同'
                : '有文字变化'
            }}
          </h3>
          <strong>{{ item.snapshot.proposed.title }}</strong>
          <p class="preserve-text">{{ item.snapshot.proposed.description || '未提供描述' }}</p>
        </section>
      </div>
      <details class="source-detail">
        <summary>事实依据与检查结果</summary>
        <p>商品名：{{ item.snapshot.product.name }}</p>
        <p class="preserve-text">商品参数：{{ item.snapshot.product.facts || '缺失' }}</p>
        <p>规则范围：核对完整原文片段；真实性、适用性与平台合规仍需人工核对。</p>
        <p v-for="gap in item.snapshot.missing" :key="gap">{{ gap }}</p>
        <p v-for="block in item.snapshot.blockers" :key="block" class="feedback error">
          {{ block }}
        </p>
        <p v-if="!item.snapshot.blockers.length">原文覆盖检查通过。</p>
        <button class="button secondary small" :disabled="busy || sourceBusy" @click="inspect">
          查看来源原始行 · 批次 {{ item.snapshot.product.source.batch_id }} · 行
          {{ item.snapshot.product.source.row_number }}
        </button>
      </details>
      <FeedbackBanner :message="sourceError" />
      <section v-if="source" aria-label="来源原始值" class="source-detail">
        <h3>
          {{ source.reference.filename }} · {{ source.reference.sheet_name || 'CSV' }} · 行
          {{ source.reference.row_number }}
        </h3>
        <p>
          导入时间：{{ time(source.reference.imported_at) }}；导出时间：{{
            source.reference.exported_at ? time(source.reference.exported_at) : '未提供'
          }}
        </p>
        <h4>原始值</h4>
        <pre>{{ JSON.stringify(source.raw, null, 2) }}</pre>
        <h4>修正值</h4>
        <pre>{{ JSON.stringify(source.corrections, null, 2) }}</pre>
        <h4>规范值</h4>
        <pre>{{ JSON.stringify(source.normalized, null, 2) }}</pre>
      </section>
      <form
        v-if="live && canRevise"
        class="listing-edit"
        @submit.prevent="emit('revise', { ...content })"
      >
        <h3>{{ item.status === 'draft' ? '修改草稿' : '另存为待审版本 / 恢复历史文案' }}</h3>
        <p class="muted">
          支持选用和调整完整参数行的顺序。标题保留完整商品名，可用「 ·
          」连接参数行；新增事实请先在导入中补充来源。
        </p>
        <FormField label="拟议标题" for-id="listing-title"
          ><input
            id="listing-title"
            v-model="content.title"
            required
            maxlength="240"
            :disabled="busy"
        /></FormField>
        <FormField label="拟议描述" for-id="listing-description">
          <textarea
            id="listing-description"
            v-model="content.description"
            rows="5"
            maxlength="4000"
            :disabled="busy"
          ></textarea>
        </FormField>
        <button class="button secondary" :disabled="busy || (!dirty && item.status === 'draft')">
          保存为新待审版本
        </button>
        <p v-if="dirty" role="status">有未保存的修改。请先保存新版本，再核对并审批。</p>
      </form>
      <div v-if="item.status === 'draft' && live" class="listing-decision">
        <label class="check-label"
          ><input
            v-model="confirmed"
            type="checkbox"
            :disabled="busy || dirty"
          />我已逐项核对商品事实、差异与影响范围</label
        >
        <div class="button-row">
          <button
            class="button primary"
            :disabled="busy || dirty || !confirmed || !!item.snapshot.blockers.length"
            @click="emit('decide', 'approve', confirmed)"
          >
            批准并在本地生效
          </button>
          <button
            class="button secondary"
            :disabled="busy || dirty"
            @click="emit('decide', 'reject', false)"
          >
            拒绝此版本
          </button>
        </div>
      </div>
      <p v-if="item.decided_at">审批时间：{{ time(item.decided_at) }} · 操作人：当前店铺拥有者</p>
    </template>
    <p v-else>来源内容与派生文案已清除；保留版本编号、处理状态和时间以供审计。</p>
  </section>
</template>
