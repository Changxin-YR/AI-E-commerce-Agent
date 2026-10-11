<template>
  <view class="evidence">
    <view class="evidence__head" @tap="toggle">
      <text class="evidence__title">{{ title }}</text>
      <text class="chip" :class="{ 'chip--active': expanded }">{{ expanded ? '收起' : '展开' }}来源证据</text>
    </view>
    <template v-if="expanded">
      <FactLine label="来源类型" :value="originText" />
      <FactLine label="来源批次" :value="source.batch_id" />
      <FactLine label="源行号" :value="source.row_number" />
      <FactLine label="来源文件" :value="source.filename" />
      <FactLine label="工作表" :value="source.sheet_name" />
      <FactLine label="数据身份" :value="identityText" />
      <FactLine label="来源导出时间" :value="source.exported_at" :zone="zone" />
      <FactLine label="导入时间" :value="source.imported_at" :zone="zone" />
      <FactLine label="证据引用" :value="evidenceRef" />
      <template v-if="detail !== null">
        <FactLine label="批次状态" :value="detail.batch_status" />
        <template v-for="section in sections" :key="section.key">
          <text class="section-title">{{ section.title }}</text>
          <view v-for="(value, key) in rowsOf(section.key)" :key="`${section.key}:${key}`">
            <FactLine :label="`${section.title} ${key}`" :value="value" />
          </view>
        </template>
      </template>
      <text v-if="hint !== ''" class="hint">{{ hint }}</text>
    </template>
  </view>
</template>

<script setup lang="ts">
/**
 * SourceEvidence：来源证据展开块。
 * 折叠时只显示文件名与源行号；展开后逐项列出来源类型、来源批次、源行号、
 * 工作表和证据引用等字段，缺失一律显示“未知”，不猜测来源。
 * 与 Flutter 端 ui/source_evidence.dart 的字段口径一致；
 * 来源批次的原始值与转换结果由父页面（GET /analytics/sources/{row_id}）回读后经 detail 传入，
 * 组件自身不发起请求，避免同一页面对同一来源重复读取。
 */
import { computed, ref } from 'vue'
import FactLine from './FactLine.vue'
import { UNKNOWN_TEXT, factText } from '../core/format'
import { importIdentities, labelOf } from '../core/labels'

const props = withDefaults(
  defineProps<{
    /** 后端 SourceReference（或结算页的裁剪版：仅有批次、源行号与文件名）。 */
    source: {
      origin?: unknown
      batch_id?: unknown
      row_id?: unknown
      row_number?: unknown
      filename?: unknown
      sheet_name?: unknown
      exported_at?: unknown
      imported_at?: unknown
      data_identity?: unknown
    }
    /** 业务时区（IANA），用于来源导出时间与导入时间的展示。 */
    zone?: string
    /** 可选补充说明，例如“同批次的原始值与转换结果由父页面回读”。 */
    hint?: string
    /** 可选的批次明细（GET /analytics/sources/{row_id} 的响应），由父页面回读后传入。 */
    detail?: {
      batch_status?: unknown
      raw?: Record<string, unknown>
      corrections?: Record<string, unknown>
      normalized?: Record<string, unknown>
    } | null
  }>(),
  { zone: 'UTC', hint: '', detail: null },
)

const sections = [
  { key: 'raw', title: '源值' },
  { key: 'corrections', title: '修正值' },
  { key: 'normalized', title: '转换后' },
] as const

function rowsOf(key: 'raw' | 'corrections' | 'normalized'): Record<string, unknown> {
  const section = props.detail?.[key]
  return section && typeof section === 'object' ? section : {}
}

/** 来源类型：后端目前只有文件导入；未命中的取值保留原值，不猜测语义。 */
const origins: Record<string, string> = {
  file_import: '业务文件导入',
}

const expanded = ref(false)

/** 缺失的源行号不拼进标题，避免出现“第 未知 行”。 */
const rowNumber = computed(() =>
  props.source.row_number === null || props.source.row_number === undefined
    ? ''
    : `${props.source.row_number}`,
)

const title = computed(() => {
  const filename = factText(props.source.filename)
  const row = rowNumber.value === '' ? '源行号未知' : `源行 ${rowNumber.value}`
  return `来源证据 · ${filename} · ${row}`
})

const originText = computed(() =>
  props.source.origin === null || props.source.origin === undefined || `${props.source.origin}`.trim() === ''
    ? UNKNOWN_TEXT
    : origins[`${props.source.origin}`] ?? `${props.source.origin}`,
)

const identityText = computed(() =>
  props.source.data_identity === null || props.source.data_identity === undefined
    ? UNKNOWN_TEXT
    : labelOf(importIdentities, props.source.data_identity),
)

/** 证据引用 = 批次 + 源行，供人工按同一来源回读核对。 */
const evidenceRef = computed(() => {
  if (props.source.batch_id === null || props.source.batch_id === undefined) return UNKNOWN_TEXT
  const batch = `批次 ${props.source.batch_id}`
  return rowNumber.value === '' ? batch : `${batch} · 源行 ${rowNumber.value}`
})

function toggle(): void {
  expanded.value = !expanded.value
}
</script>
