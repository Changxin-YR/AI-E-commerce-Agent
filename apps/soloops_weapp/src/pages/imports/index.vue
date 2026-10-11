<template>
  <PageShell
    title="文件导入"
    subtitle="把业务数据，整理成依据"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="load"
  >
    <FactLine label="所属店铺" :value="shopName" />
    <text class="hint">
      数据截至文件导出时间，用于本地分析与草稿。请移除顾客姓名、地址、电话与邮箱。文件暂存 24 小时，确认后只保留映射字段及修正记录。
    </text>

    <text class="section-title">选择来源</text>
    <view v-for="field in sourceFields" :key="field.key" class="field">
      <text class="field__label">{{ field.label }}</text>
      <picker
        mode="selector"
        :range="field.options"
        range-key="label"
        :value="field.index"
        @change="setSource(field.key, field.options[Number(pickerValue($event))]?.key ?? '')"
      >
        <view class="field__picker">{{ field.options[field.index]?.label }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">文件时间使用的时区（IANA）</text>
      <input
        class="field__input"
        :value="timezone"
        :disabled="busy"
        @input="timezone = inputValue($event)"
      />
    </view>
    <view class="field">
      <text class="field__label">导出时间（可选，须含时区偏移）</text>
      <input
        class="field__input"
        :value="exportedAt"
        :disabled="busy"
        placeholder="2026-10-11T09:00:00+08:00"
        @input="exportedAt = inputValue($event)"
      />
    </view>
    <text class="hint">时间示例：2026-10-11T09:00:00+08:00</text>
    <text v-if="kind === 'statements'" class="hint">
      账单以 sale / refund / fee / payout 区分含义，金额填写正数；费用行须有凭据费用行编号与原始收费项名称。
    </text>

    <text class="section-title">单批次导入</text>
    <text class="hint">
      UTF-8 CSV 或单工作表 XLSX。单批最多 {{ catalog?.max_rows ?? 2000 }} 行、2 MiB、64 列；金额最多四位小数。不接受宏、公式及外部链接。
    </text>
    <view class="field">
      <text class="field__label">模板格式</text>
      <picker mode="selector" :range="templateFormats" range-key="label" :value="formatIndex" @change="setFormat($event)">
        <view class="field__picker">{{ templateFormats[formatIndex]?.label }}</view>
      </picker>
    </view>
    <view class="row">
      <ActionButton :label="`下载${labelOf(importKinds, kind)}模板`" :disabled="busy" @tap="downloadTemplate" />
      <ActionButton label="选择 CSV / XLSX" :disabled="busy" @tap="pickBatchFile" />
    </view>
    <FactLine v-if="selectedFile" label="已选文件" :value="`${selectedFile.name} · ${selectedFile.bytes.length} 字节`" />
    <ActionButton
      label="上传并查看映射"
      variant="primary"
      block
      :disabled="busy || selectedFile === null || catalog === null"
      @tap="upload"
    />

    <text class="section-title">大 CSV 分批导入</text>
    <text class="hint">
      最多 40 MiB、40000 条记录、20 片。按完整 CSV 记录拆分，逐片预览确认。组内全部分片完成后才具备完整来源；经营分析单次范围仍最多 10000 行。
    </text>
    <view class="row">
      <ActionButton label="选择原始 CSV，建立导入组" :disabled="busy || catalog === null" @tap="prepareGroupSource" />
      <ActionButton
        v-if="group === null"
        label="选择已有 manifest.json 清单"
        :disabled="busy"
        @tap="pickManifest"
      />
    </view>
    <text v-if="splitProgress" class="hint">
      已处理 {{ splitProgress.rows }} / {{ splitProgress.totalRows }} 条记录
    </text>

    <template v-if="activeManifest">
      <text class="section-title">来源与完整性</text>
      <FactLine label="原文件" :value="activeManifest.source_filename" />
      <FactLine label="SHA-256" :value="activeManifest.source_sha256" />
      <FactLine label="总记录 / 分片" :value="`${activeManifest.total_rows} / ${activeManifest.parts.length}`" />
      <template v-if="group">
        <FactLine label="状态" :value="groupStatusText" />
        <FactLine label="已提交片数" :value="`${group.committed_parts} / ${activeManifest.parts.length}`" />
        <FactLine label="已提交源记录" :value="`${group.committed_rows} / ${activeManifest.total_rows}`" />
        <FactLine label="去重 / 跨片重叠" :value="`${group.unique_rows} / ${group.overlap_rows}`" />
        <text v-if="group.complete !== true && group.status === 'active'" class="warn">
          汇总与完整性判断暂停，请补齐所有分片或撤销整组。
        </text>
      </template>
      <view class="row">
        <ActionButton label="保存分片清单" :disabled="busy" @tap="saveManifest" />
        <ActionButton
          v-if="group === null && activeManifest"
          label="按当前来源建立导入组"
          variant="primary"
          :disabled="busy"
          @tap="createGroup"
        />
        <ActionButton v-if="prepared !== null" label="释放本机文件" :disabled="busy" @tap="releasePrepared" />
      </view>

      <text class="section-title">逐片核对</text>
      <text class="hint">下方范围为原文件数据记录序号，不含表头；批次明细的源行号为分片内物理行号。</text>
      <view v-for="part in partRows" :key="part.filename" class="card">
        <text class="card__title">第 {{ part.index }} 片 · {{ part.filename }}</text>
        <text class="hint">原数据记录 {{ part.start }} — {{ part.end }} · {{ part.bytes }} 字节</text>
        <text v-if="part.batches.length === 0" class="hint">尚未上传</text>
        <ActionButton
          v-for="batch in part.batches"
          :key="batch.id"
          :label="`批次 #${batch.id} · ${labelOf(batchStatuses, batch.status)}`"
          :disabled="busy"
          @tap="openBatch(batch.id)"
        />
        <ActionButton
          v-if="group?.status === 'active' && prepared !== null"
          :label="`上传 / 恢复第 ${part.index} 片`"
          :disabled="busy"
          @tap="uploadPart(part.index - 1)"
        />
      </view>
      <template v-if="group?.status === 'active'">
        <ActionButton label="选择已有分片 CSV 并上传" :disabled="busy" @tap="selectPart" />
        <ActionButton label="撤销整个导入组" :disabled="busy" @tap="revokeGroup" />
      </template>
    </template>

    <text class="section-title">导入组</text>
    <view v-if="groups.length === 0 && !busy" class="card">
      <text class="hint">尚无导入组。</text>
    </view>
    <view v-for="item in groups" :key="item.id" class="card" @tap="openGroup(item.id)">
      <text class="card__title">#{{ item.id }} · {{ item.manifest.source_filename }}</text>
      <text class="hint">
        {{ groupText(item) }} · {{ item.committed_parts }} / {{ item.manifest.parts.length }} 片
      </text>
    </view>
    <ActionButton v-if="olderCursor !== null" label="加载更早的导入组" :disabled="busy" @tap="loadOlderGroups" />

    <text class="section-title">批次历史</text>
    <view v-if="history.length === 0 && !busy" class="card">
      <text class="hint">尚未导入文件。可以先下载一份模板。</text>
    </view>
    <view v-for="batch in history" :key="batch.id" class="card" @tap="openBatch(batch.id)">
      <text class="card__title">#{{ batch.id }} · {{ batch.filename }}</text>
      <text class="hint">
        {{ labelOf(batchStatuses, batch.status) }} · {{ labelOf(importKinds, batch.kind) }} ·
        {{ labelOf(importIdentities, batch.data_identity) }}
      </text>
      <text class="hint">{{ batch.total_rows }} 行 · {{ businessTimeText(batch.created_at ?? '', zone) }}</text>
    </view>

    <template v-if="batch">
      <text class="section-title">导入批次 #{{ batch.id }}</text>
      <ActionButton label="刷新批次" :disabled="busy" @tap="loadBatch(batch.id)" />
      <text class="card__title">{{ batch.filename }}</text>
      <FactLine label="状态" :value="labelOf(batchStatuses, batch.status)" />
      <FactLine
        label="来源"
        :value="`${labelOf(importKinds, batch.kind)} · ${labelOf(importChannels, batch.source_channel)} · ${labelOf(importIdentities, batch.data_identity)}`"
      />
      <FactLine label="归属店铺 / 批次版本" :value="`${batch.shop_id} / ${batch.version}`" />
      <FactLine v-if="batch.group_id !== null" label="导入组 / 分片" :value="`${batch.group_id} / ${batch.group_part}`" />
      <FactLine label="文件时区" :value="batch.timezone" />
      <FactLine label="来源导出时间" :value="batch.exported_at" :zone="batch.timezone || zone" />
      <FactLine
        label="源记录覆盖"
        :value="`${batch.coverage_start ?? '未知'} — ${batch.coverage_end ?? '未知'}`"
      />
      <FactLine label="暂存过期时间" :value="batch.expires_at" :zone="zone" />
      <FactLine label="币种" :value="(batch.currencies ?? []).length > 0 ? (batch.currencies ?? []).join(' / ') : '未知'" />
      <text class="hint">
        总计 {{ batch.total_rows }} · 有效 {{ batch.valid_rows }} · 错误 {{ batch.error_rows }}
      </text>
      <text class="hint">
        新增 {{ batch.new_rows }} · 更新 {{ batch.updated_rows }} · 相同 {{ batch.unchanged_rows }} · 重复 {{ batch.duplicate_rows ?? 0 }}
      </text>
      <text v-for="issue in batch.errors" :key="issue" class="warn">{{ issue }}</text>
      <text v-if="batch.suggested_kind !== batch.kind" class="warn">
        文件疑似 {{ labelOf(importKinds, batch.suggested_kind) }}，请核对所选报表类型。
      </text>

      <template v-if="editable">
        <text class="section-title">字段映射</text>
        <text class="hint">逐项核对源列与业务含义。金额保持原精度，缺失字段会在预览中提示。</text>
        <view v-for="preset in batch.presets" :key="preset.name" class="card">
          <text class="card__title">{{ preset.name }}</text>
          <text v-for="note in preset.notes" :key="note" class="hint">{{ note }}</text>
          <FactLine label="核验日期" :value="preset.verified_on" />
          <FactLine label="参考来源" :value="preset.reference_url" />
          <ActionButton label="使用候选映射" :disabled="busy" @tap="applyMapping(preset.mapping)" />
        </view>
        <view v-if="suitableTemplates.length > 0" class="field">
          <text class="field__label">使用个人模板</text>
          <picker mode="selector" :range="suitableTemplates" range-key="name" :value="0" @change="applyTemplate($event)">
            <view class="field__picker">选择个人模板</view>
          </picker>
        </view>
        <view v-for="field in fields" :key="field.key" class="field">
          <text class="field__label">{{ field.label }}{{ field.required ? ' *' : '' }}</text>
          <picker
            mode="selector"
            :range="columnOptions"
            range-key="label"
            :value="columnIndex(field.key)"
            @change="setMapping(field.key, columnOptions[Number(pickerValue($event))]?.key ?? '')"
          >
            <view class="field__picker">{{ columnLabel(field.key) }}</view>
          </picker>
          <text class="hint">{{ field.data_type }} · {{ field.help }}</text>
          <FactLine v-if="mapping[field.key]" label="原始示例" :value="batch.examples[mapping[field.key]]" />
          <text v-for="suggestion in suggestionsFor(field.key)" :key="suggestion.column" class="hint">
            {{ suggestion.confidence === 'exact' ? '标准字段匹配' : '别名候选，请核对口径' }}
          </text>
        </view>
        <view class="field">
          <text class="field__label">个人映射模板名称</text>
          <input
            class="field__input"
            :value="templateName"
            :disabled="busy"
            @input="templateName = inputValue($event)"
          />
        </view>
        <view class="row">
          <ActionButton label="保存映射模板" :disabled="busy" @tap="saveMapping" />
          <ActionButton
            :label="dirty ? '重新校验预览' : '校验并预览'"
            variant="primary"
            :disabled="busy"
            @tap="preview"
          />
        </view>
      </template>

      <text class="section-title">源行与转换结果</text>
      <view class="row" @tap="errorsOnly = !errorsOnly">
        <text class="chip" :class="{ 'chip--active': errorsOnly }">
          {{ errorsOnly ? '已开启' : '未开启' }} · 只看错误行
        </text>
      </view>
      <text v-if="filteredRows.length === 0" class="hint">当前筛选没有源行。</text>
      <view v-for="row in pagedRows" :key="row.row_number" class="card">
        <text class="card__title" @tap="toggleRow(row.row_number)">
          源行 {{ row.row_number }} · {{ labelOf(rowActions, row.action) }}
        </text>
        <text class="hint">{{ rowIdentifier(row) }}</text>
        <template v-if="expandedRow === row.row_number">
          <text v-for="issue in row.errors" :key="`${issue.field}:${issue.message}`" class="warn">
            {{ issue.field }}：{{ issue.message }}
          </text>
          <text v-for="warning in row.warnings" :key="warning" class="hint">{{ warning }}</text>
          <template v-for="field in fields" :key="field.key">
            <text class="card__title">{{ field.label }}</text>
            <FactLine label="源值" :value="row.raw[mapping[field.key]]" />
            <FactLine v-if="corrections[row.row_number]?.[field.key] !== undefined" label="修正值" :value="corrections[row.row_number]?.[field.key]" />
            <FactLine label="转换后" :value="row.normalized[field.key]" />
            <FactLine v-if="row.previous" label="当前旧值" :value="row.previous[field.key]" />
            <view class="divider" />
          </template>
          <template v-if="editable">
            <ActionButton
              v-if="editingRow !== row.row_number"
              label="修正此行"
              :disabled="busy"
              @tap="startEdit(row)"
            />
            <template v-else>
              <view v-for="field in fields" :key="`draft:${field.key}`" class="field">
                <text class="field__label">{{ field.label }}</text>
                <input
                  class="field__input"
                  :value="draft[field.key] ?? ''"
                  @input="draft = { ...draft, [field.key]: inputValue($event) }"
                />
              </view>
              <view class="row">
                <ActionButton label="保存修正" variant="primary" @tap="saveEdit(row)" />
                <ActionButton label="取消修正" @tap="editingRow = null" />
              </view>
            </template>
          </template>
        </template>
      </view>
      <view v-if="filteredRows.length > 0" class="row">
        <ActionButton label="上一页" :disabled="page === 0" @tap="page -= 1" />
        <text class="chip">第 {{ page + 1 }} / {{ totalPages }} 页</text>
        <ActionButton label="下一页" :disabled="page + 1 >= totalPages" @tap="page += 1" />
      </view>

      <template v-if="editable">
        <text class="section-title">核对后确认</text>
        <text v-if="dirty" class="warn">映射或修正值已变化，请重新预览后再确认。</text>
        <text v-if="batch.required_reviews.length > 0" class="hint">
          按原报表说明核对金额和稳定标识。整单退款不能直接当作行退款。
        </text>
        <view
          v-for="review in batch.required_reviews"
          :key="review.field"
          class="card"
          @tap="toggleReview(review.field)"
        >
          <text class="chip" :class="{ 'chip--active': reviewed.includes(review.field) }">
            {{ reviewed.includes(review.field) ? '已核对' : '未核对' }} · {{ review.column }} → {{ review.label }}
          </text>
          <text class="hint">{{ review.meaning }}</text>
        </view>
        <view v-if="batch.updated_rows !== 0" class="card" @tap="allowUpdates = !allowUpdates">
          <text class="chip" :class="{ 'chip--active': allowUpdates }">
            {{ allowUpdates ? '已允许' : '未允许' }} · 允许更新 {{ batch.updated_rows }} 条现有记录
          </text>
          <text class="hint">请在源行明细中比较转换后与当前旧值。</text>
        </view>
        <ActionButton
          label="确认导入"
          variant="primary"
          block
          :disabled="busy || !canCommit"
          @tap="commit"
        />
      </template>

      <view class="row">
        <ActionButton label="保存错误报告" :disabled="busy" @tap="exportErrors" />
        <ActionButton
          v-if="!['revoked', 'cleared', 'expired'].includes(batch.status)"
          label="撤销批次"
          :disabled="busy"
          @tap="withdraw('revoke')"
        />
        <ActionButton v-if="batch.status !== 'cleared'" label="清除批次" :disabled="busy" @tap="withdraw('clear')" />
      </view>
    </template>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 业务文件导入：选文件、映射预览、逐行纠错、分片 / 清单恢复。
 * 接口：
 *   GET  /api/imports/catalog
 *   GET  /api/imports/mappings                POST /api/imports/mappings
 *   GET  /api/shops/{shop_id}/imports         POST /api/shops/{shop_id}/imports
 *   GET  /api/imports/{batch_id}              POST /api/imports/{batch_id}/preview
 *   POST /api/imports/{batch_id}/commit       POST /api/imports/{batch_id}/revoke
 *   POST /api/imports/{batch_id}/clear        GET  /api/imports/{batch_id}/errors.csv
 *   GET  /api/shops/{shop_id}/import-groups   POST /api/shops/{shop_id}/import-groups
 *   GET  /api/import-groups/{group_id}        POST /api/import-groups/{group_id}/revoke
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import ActionButton from '../../ui/ActionButton.vue'
import { apiGet, apiPost, apiRequest, asObject } from '../../core/api'
import { businessTimeText } from '../../core/format'
import { pageQuery } from '../../core/links'
import { sha256Hex } from '../../core/digest'
import {
  decodeUtf8,
  sameManifest,
  splitCsv,
  validateManifest,
  type CsvManifest,
  type PreparedCsv,
} from '../../core/csv'
import {
  batchStatuses,
  importChannels,
  importIdentities,
  importKinds,
  labelOf,
  rowActions,
} from '../../core/labels'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

interface CatalogField {
  key: string
  label: string
  data_type: string
  help: string
  required: boolean
}

interface Catalog {
  products: CatalogField[]
  orders: CatalogField[]
  messages: CatalogField[]
  inventory: CatalogField[]
  statements: CatalogField[]
  max_bytes: number
  max_rows: number
}

interface BatchRow {
  row_number: number
  action: string
  errors: Array<{ field: string; message: string }>
  warnings: string[]
  raw: Record<string, string>
  normalized: Record<string, string>
  previous: Record<string, string> | null
}

interface ImportBatch {
  id: number
  filename: string
  status: string
  kind: string
  source_channel: string
  data_identity: string
  shop_id: number
  version: number
  group_id: number | null
  group_part: number | null
  timezone: string
  exported_at: string | null
  coverage_start: string | null
  coverage_end: string | null
  expires_at: string
  created_at?: string
  currencies: string[]
  total_rows: number
  valid_rows: number
  error_rows: number
  new_rows: number
  updated_rows: number
  unchanged_rows: number
  duplicate_rows: number | null
  errors: string[]
  suggested_kind: string
  headers: string[]
  examples: Record<string, string>
  mapping: Record<string, string>
  presets: Array<{ name: string; notes: string[]; verified_on: string; reference_url: string; mapping: Record<string, string> }>
  suggestions: Array<{ field: string; column: string; confidence: string }>
  required_reviews: Array<{ field: string; column: string; label: string; meaning: string }>
  rows: BatchRow[]
}

interface ImportGroup {
  id: number
  version: number
  status: string
  complete: boolean
  committed_parts: number
  committed_rows: number
  unique_rows: number
  overlap_rows: number
  manifest: CsvManifest
  options: Record<string, string>
  batches: Array<{ id: number; group_part: number; status: string }>
}

interface MappingTemplate {
  id: number
  name: string
  kind: string
  source_channel: string
  mapping: Record<string, string>
}

interface PickedFile {
  name: string
  bytes: Uint8Array
}

const templateFormats = [
  { key: 'csv', label: 'CSV' },
  { key: 'xlsx', label: 'Excel' },
]

const kind = ref('products')
const channel = ref('generic')
const identity = ref('user_import')
const timezone = ref(shopTimezone())
const exportedAt = ref('')
const format = ref('csv')
const catalog = ref<Catalog | null>(null)
const templates = ref<MappingTemplate[]>([])
const selectedFile = ref<PickedFile | null>(null)
const history = ref<ImportBatch[]>([])
const groups = ref<ImportGroup[]>([])
const olderCursor = ref<number | null>(null)
const batch = ref<ImportBatch | null>(null)
const mapping = ref<Record<string, string>>({})
const corrections = ref<Record<string, Record<string, string>>>({})
const reviewed = ref<string[]>([])
const templateName = ref('')
const dirty = ref(false)
const allowUpdates = ref(false)
const errorsOnly = ref(false)
const page = ref(0)
const expandedRow = ref<number | null>(null)
const editingRow = ref<number | null>(null)
const draft = ref<Record<string, string>>({})
const prepared = ref<PreparedCsv | null>(null)
const importedManifest = ref<CsvManifest | null>(null)
const group = ref<ImportGroup | null>(null)
const splitProgress = ref<{ rows: number; totalRows: number } | null>(null)
const busy = ref(false)
const error = ref('')
const successText = ref('')
const ready = ref(false)

const zone = computed(() => shopTimezone())
const shopName = computed(() => state.shops.find((shop) => shop.id === state.shopId)?.name ?? '未知')
const fields = computed<CatalogField[]>(() => {
  const value = catalog.value
  if (value === null || batch.value === null) return []
  return (value as unknown as Record<string, CatalogField[]>)[batch.value.kind] ?? []
})
const editable = computed(() => batch.value !== null && ['draft', 'preview'].includes(batch.value.status))
const suitableTemplates = computed(() => templates.value.filter(
  (item) => item.kind === batch.value?.kind && item.source_channel === batch.value?.source_channel,
))
const columnOptions = computed(() => [
  { key: '', label: '不映射' },
  ...(batch.value?.headers ?? []).map((header) => ({ key: header, label: header })),
])
const filteredRows = computed(() => {
  const rows = batch.value?.rows ?? []
  return errorsOnly.value ? rows.filter((row) => row.errors.length > 0) : rows
})
const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / 20)))
const pagedRows = computed(() => filteredRows.value.slice(page.value * 20, page.value * 20 + 20))
const canCommit = computed(() => {
  const current = batch.value
  if (current === null || current.status !== 'preview' || dirty.value) return false
  if (current.errors.length > 0 || current.error_rows !== 0) return false
  if (!current.required_reviews.every((review) => reviewed.value.includes(review.field))) return false
  return current.updated_rows === 0 || allowUpdates.value
})
const activeManifest = computed(() => group.value?.manifest ?? prepared.value?.manifest ?? importedManifest.value)
const groupStatusText = computed(() => {
  const current = group.value
  if (current === null) return '未建立'
  if (current.status === 'revoked') return '已整组撤销'
  return current.complete === true ? '分片全部完成' : '部分覆盖 / 数据不足'
})

/** 导入组状态文案：与 Flutter 端同一口径。 */
function groupText(item: ImportGroup): string {
  if (item.status === 'revoked') return '已整组撤销'
  return item.complete === true ? '分片全部完成' : '部分覆盖 / 数据不足'
}
const partRows = computed(() => {
  const manifest = activeManifest.value
  if (manifest === null) return []
  let start = 1
  return manifest.parts.map((part, index) => {
    const row = {
      index: index + 1,
      filename: part.filename,
      bytes: part.bytes,
      start,
      end: start + part.rows - 1,
      batches: (group.value?.batches ?? []).filter((item) => item.group_part === index + 1),
    }
    start += part.rows
    return row
  })
})

const sourceFields = computed(() => [
  { key: 'kind', label: '报表类型', options: optionsOf(importKinds), index: indexOf(importKinds, kind.value) },
  { key: 'channel', label: '来源渠道', options: optionsOf(importChannels), index: indexOf(importChannels, channel.value) },
  { key: 'identity', label: '数据身份', options: optionsOf(importIdentities), index: indexOf(importIdentities, identity.value) },
])
const formatIndex = computed(() => Math.max(0, templateFormats.findIndex((item) => item.key === format.value)))

function optionsOf(map: Record<string, string>): Array<{ key: string; label: string }> {
  return Object.entries(map).map(([key, label]) => ({ key, label }))
}

function indexOf(map: Record<string, string>, key: string): number {
  const index = Object.keys(map).indexOf(key)
  return index < 0 ? 0 : index
}

function setSource(key: string, value: string): void {
  if (key === 'kind') kind.value = value
  if (key === 'channel') channel.value = value
  if (key === 'identity') identity.value = value
}

function setFormat(event: { detail: { value: string } }): void {
  format.value = templateFormats[Number(event.detail.value)]?.key ?? 'csv'
}

function options(): Record<string, string> {
  const exported = exportedAt.value.trim()
  if (exported !== '' && !/(Z|[+-]\d{2}:\d{2})$/.test(exported)) {
    throw new Error('导出时间须包含时区偏移，例如 2026-10-11T09:00:00+08:00。')
  }
  if (timezone.value.trim() === '') throw new Error('请填写文件时区。')
  const value: Record<string, string> = {
    kind: kind.value,
    source_channel: channel.value,
    data_identity: identity.value,
    timezone: timezone.value.trim(),
  }
  if (exported !== '') value.exported_at = exported
  return value
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const copy = new ArrayBuffer(bytes.length)
  new Uint8Array(copy).set(bytes)
  return copy
}

async function pickFile(extensions: string[]): Promise<PickedFile | null> {
  const result = await Taro.chooseMessageFile({ count: 1, type: 'file', extension: extensions })
  const file = result.tempFiles?.[0]
  if (!file) return null
  const data = Taro.getFileSystemManager().readFileSync(file.path)
  if (typeof data === 'string') {
    throw new Error('文件读取结果异常，请重新选择。')
  }
  return { name: file.name, bytes: new Uint8Array(data as ArrayBuffer) }
}

function success(text: string): void {
  successText.value = text
  void Taro.showToast({ title: text, icon: 'none' })
}

function toDisk(filename: string, data: string | Uint8Array): string {
  const path = `${Taro.env.USER_DATA_PATH}/${filename}`
  const fs = Taro.getFileSystemManager()
  if (typeof data === 'string') {
    fs.writeFileSync(path, data, 'utf8')
  } else {
    fs.writeFileSync(path, toArrayBuffer(data))
  }
  return path
}

async function saveToDisk(path: string, filename: string, fallbackText: string): Promise<void> {
  const saver = (Taro as unknown as { saveFileToDisk?: (options: { filePath: string }) => Promise<unknown> })
    .saveFileToDisk
  if (typeof saver === 'function') {
    await saver({ filePath: path })
    success('文件已保存。')
    return
  }
  await Taro.setClipboardData({ data: fallbackText })
  success(`当前客户端不支持直接保存 ${filename}，已复制文本到剪贴板，并写入小程序本地文件。`)
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  applyQuery()
  if (catalog.value === null) timezone.value = shopTimezone()
  await load()
})

/** 从库存 / Listing / 客服等入口带入的预选条件。 */
function applyQuery(): void {
  const query = pageQuery()
  if (query.kind && Object.keys(importKinds).includes(query.kind)) kind.value = query.kind
  if (query.identity && Object.keys(importIdentities).includes(query.identity)) identity.value = query.identity
  if (query.channel && Object.keys(importChannels).includes(query.channel)) channel.value = query.channel
  const batchId = Number(query.batch ?? '')
  if (Number.isFinite(batchId) && batchId > 0) void loadBatch(batchId)
}

async function load(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    const [catalogValue, historyValue, groupValue, templateValue] = await Promise.all([
      apiGet<Catalog>('/api/imports/catalog'),
      apiGet<ImportBatch[]>(shopPath('/imports')),
      apiGet<ImportGroup[]>(shopPath('/import-groups')),
      apiGet<MappingTemplate[]>('/api/imports/mappings'),
    ])
    catalog.value = asObject<Catalog>(catalogValue)
    history.value = Array.isArray(historyValue) ? historyValue : []
    groups.value = Array.isArray(groupValue) ? groupValue : []
    templates.value = Array.isArray(templateValue) ? templateValue : []
    olderCursor.value = groups.value.length === 20 ? groups.value[groups.value.length - 1].id : null
  })
  error.value = message
}

async function loadOlderGroups(): Promise<void> {
  const cursor = olderCursor.value
  if (cursor === null) return
  const message = await perform(async () => {
    const result = await apiGet<ImportGroup[]>(shopPath('/import-groups'), { before: cursor })
    const incoming = Array.isArray(result) ? result : []
    groups.value = [
      ...groups.value,
      ...incoming.filter((item) => !groups.value.some((old) => old.id === item.id)),
    ]
    olderCursor.value = incoming.length === 20 ? incoming[incoming.length - 1].id : null
  })
  error.value = message
}

async function downloadTemplate(): Promise<void> {
  const message = await perform(async () => {
    const data = await apiRequest<ArrayBuffer>(`/api/imports/templates/${kind.value}`, {
      method: 'GET',
      query: { format: format.value },
      rawResponse: true,
    })
    const filename = `soloops-${kind.value}.${format.value}`
    const path = toDisk(filename, new Uint8Array(data))
    const saver = (Taro as unknown as { saveFileToDisk?: (options: { filePath: string }) => Promise<unknown> })
      .saveFileToDisk
    if (typeof saver === 'function') {
      await saver({ filePath: path })
      success('模板已保存。')
      return
    }
    success(`当前客户端不支持直接保存 ${filename}，已写入小程序本地文件。`)
  })
  error.value = message
}

async function pickBatchFile(): Promise<void> {
  const message = await perform(async () => {
    selectedFile.value = await pickFile(['csv', 'xlsx'])
  })
  error.value = message
}

async function upload(): Promise<void> {
  const file = selectedFile.value
  if (file === null || catalog.value === null) return
  if (file.bytes.length > (catalog.value.max_bytes ?? 2097152)) {
    error.value = '文件超过单批次上限，请使用“大 CSV 分批导入”；Excel 先将目标工作表另存为 CSV UTF-8。'
    return
  }
  const message = await perform(async () => {
    const result = asObject<ImportBatch>(
      await apiRequest<ImportBatch>(shopPath('/imports'), {
        method: 'POST',
        query: { ...options(), filename: file.name },
        bytes: toArrayBuffer(file.bytes),
        contentType: 'application/octet-stream',
      }),
    )
    selectedFile.value = null
    if (result === null) throw new Error('上传响应无法读取，请到批次历史核对结果。')
    await loadBatch(result.id)
    await load()
  })
  error.value = message
}

async function openBatch(id: number): Promise<void> {
  await loadBatch(id)
}

async function loadBatch(id: number): Promise<void> {
  const message = await perform(async () => {
    const value = asObject<ImportBatch>(await apiGet(`/api/imports/${id}`))
    if (value === null) throw new Error('批次响应无法读取，请刷新重试。')
    batch.value = value
    mapping.value = { ...(value.mapping ?? {}) }
    corrections.value = Object.fromEntries(
      value.rows.map((row) => [`${row.row_number}`, { ...((row as unknown as { corrections?: Record<string, string> }).corrections ?? {}) }]),
    )
    reviewed.value = []
    dirty.value = false
    allowUpdates.value = false
    page.value = 0
    expandedRow.value = null
    editingRow.value = null
  })
  error.value = message
}

function markDirty(): void {
  dirty.value = true
  reviewed.value = []
  allowUpdates.value = false
}

function applyMapping(candidate: Record<string, string>): void {
  const headers = batch.value?.headers ?? []
  mapping.value = Object.fromEntries(Object.entries(candidate).filter(([, column]) => headers.includes(column)))
  corrections.value = {}
  markDirty()
}

function applyTemplate(event: { detail: { value: string } }): void {
  const item = suitableTemplates.value[Number(event.detail.value)]
  if (item) applyMapping(item.mapping ?? {})
}

function columnIndex(fieldKey: string): number {
  const current = mapping.value[fieldKey] ?? ''
  const index = columnOptions.value.findIndex((option) => option.key === current)
  return index < 0 ? 0 : index
}

function columnLabel(fieldKey: string): string {
  const current = mapping.value[fieldKey] ?? ''
  return current === '' ? '不映射' : current
}

function setMapping(fieldKey: string, column: string): void {
  mapping.value = { ...mapping.value, [fieldKey]: column }
  corrections.value = {}
  markDirty()
}

function suggestionsFor(fieldKey: string): Array<{ column: string; confidence: string }> {
  const column = mapping.value[fieldKey] ?? ''
  return (batch.value?.suggestions ?? []).filter(
    (item) => item.field === fieldKey && item.column === column,
  )
}

async function preview(): Promise<void> {
  const current = batch.value
  if (current === null) return
  const message = await perform(async () => {
    const result = asObject<ImportBatch>(
      await apiPost(`/api/imports/${current.id}/preview`, {
        version: current.version,
        mapping: mapping.value,
        corrections: corrections.value,
      }),
    )
    if (result === null) throw new Error('预览响应无法读取，请刷新后重试。')
    batch.value = result
    mapping.value = { ...(result.mapping ?? {}) }
    dirty.value = false
    reviewed.value = []
    allowUpdates.value = false
    page.value = 0
  })
  if (message === '') {
    success('预览已更新，请核对结果和关键字段含义。')
  } else {
    error.value = message
  }
}

async function saveMapping(): Promise<void> {
  const current = batch.value
  if (current === null) return
  if (templateName.value.trim() === '') {
    error.value = '请填写模板名称。'
    return
  }
  const message = await perform(async () => {
    await apiPost('/api/imports/mappings', {
      name: templateName.value.trim(),
      kind: current.kind,
      source_channel: current.source_channel,
      mapping: Object.fromEntries(Object.entries(mapping.value).filter(([, value]) => value !== '')),
    })
    templates.value = await apiGet('/api/imports/mappings')
  })
  error.value = message
  if (message === '') success('个人映射模板已保存；每次导入仍须核对字段含义。')
}

function toggleRow(rowNumber: number): void {
  expandedRow.value = expandedRow.value === rowNumber ? null : rowNumber
}

function rowIdentifier(row: BatchRow): string {
  return row.normalized.message_id ?? row.normalized.sku ?? row.normalized.order_id ?? '标识待补充'
}

function startEdit(row: BatchRow): void {
  const current = corrections.value[row.row_number] ?? {}
  const next: Record<string, string> = {}
  for (const field of fields.value) {
    next[field.key] = current[field.key] ?? row.raw[mapping.value[field.key]] ?? ''
  }
  draft.value = next
  editingRow.value = row.row_number
}

function saveEdit(row: BatchRow): void {
  const current = { ...(corrections.value[row.row_number] ?? {}) }
  const original: Record<string, string> = {}
  for (const field of fields.value) {
    original[field.key] = current[field.key] ?? row.raw[mapping.value[field.key]] ?? ''
  }
  for (const [key, value] of Object.entries(draft.value)) {
    if (value !== original[key]) current[key] = value
  }
  corrections.value = { ...corrections.value, [`${row.row_number}`]: current }
  editingRow.value = null
  markDirty()
}

function toggleReview(field: string): void {
  if (busy.value || dirty.value) return
  reviewed.value = reviewed.value.includes(field)
    ? reviewed.value.filter((item) => item !== field)
    : [...reviewed.value, field]
}

async function commit(): Promise<void> {
  const current = batch.value
  if (current === null || !canCommit.value) return
  const modal = await Taro.showModal({
    title: '确认导入',
    content: `本次新增 ${current.new_rows} 行，更新 ${current.updated_rows} 行。确认后写入当前店铺业务记录。`,
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  const message = await perform(async () => {
    const result = asObject<ImportBatch>(
      await apiPost(`/api/imports/${current.id}/commit`, {
        version: current.version,
        allow_updates: allowUpdates.value,
        reviewed_fields: reviewed.value,
      }),
    )
    if (result !== null) await loadBatch(result.id)
  })
  if (message === '') success('批次已导入，可继续核对源行与转换结果。')
  else error.value = message
}

async function withdraw(action: 'revoke' | 'clear'): Promise<void> {
  const current = batch.value
  if (current === null) return
  const clear = action === 'clear'
  const modal = await Taro.showModal({
    title: clear ? '清除批次' : '撤销批次',
    content: clear
      ? '将撤销本批次影响并清除源行资料；操作后无法恢复本批次的原始明细。'
      : '将撤销本批次及其衍生来源，按剩余有效批次恢复业务版本。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  const message = await perform(async () => {
    const result = asObject<ImportBatch>(
      await apiPost(`/api/imports/${current.id}/${action}`, { version: current.version }),
    )
    if (result !== null) await loadBatch(result.id)
  })
  if (message === '') success('批次状态已更新，业务记录已按剩余来源重新确定。')
  else error.value = message
}

async function exportErrors(): Promise<void> {
  const current = batch.value
  if (current === null) return
  const message = await perform(async () => {
    const data = await apiRequest<ArrayBuffer>(`/api/imports/${current.id}/errors.csv`, {
      method: 'GET',
      rawResponse: true,
    })
    const bytes = new Uint8Array(data)
    const filename = `import-${current.id}-errors.csv`
    const path = toDisk(filename, bytes)
    await saveToDisk(path, filename, decodeUtf8(bytes))
  })
  error.value = message
}

async function prepareGroupSource(): Promise<void> {
  const message = await perform(async () => {
    const file = await pickFile(['csv'])
    if (file === null) return
    splitProgress.value = { rows: 0, totalRows: file.bytes.length }
    try {
      const result = splitCsv(file.name, file.bytes)
      if (group.value !== null && !sameManifest(result.manifest, group.value.manifest)) {
        throw new Error('原文件的名称、指纹或分片与当前组不一致。请选择建组时的原文件。')
      }
      prepared.value = result
      importedManifest.value = null
      success(`本机文件已就绪：${result.manifest.total_rows} 条记录，${result.parts.length} 片。`)
    } finally {
      splitProgress.value = null
    }
  })
  if (message !== '') error.value = message
}

async function pickManifest(): Promise<void> {
  const message = await perform(async () => {
    const file = await pickFile(['json'])
    if (file === null) return
    if (file.bytes.length > 65536) throw new Error('分片清单不能超过 64 KiB。')
    const value = validateManifest(JSON.parse(decodeUtf8(file.bytes)))
    prepared.value = null
    importedManifest.value = value
    success('清单已读取，请核对来源并建组，再选择对应分片。相同清单与来源可回读已建组。')
  })
  if (message !== '') error.value = message
}

function releasePrepared(): void {
  prepared.value = null
  success('已释放本机文件；服务端记录仍保留。')
}

async function saveManifest(): Promise<void> {
  const manifest = activeManifest.value
  if (manifest === null) return
  const message = await perform(async () => {
    const path = toDisk('manifest.json', JSON.stringify(manifest, null, 2))
    await saveToDisk(path, 'manifest.json', JSON.stringify(manifest, null, 2))
  })
  error.value = message
}

async function createGroup(): Promise<void> {
  const manifest = prepared.value?.manifest ?? importedManifest.value
  if (manifest === null) return
  const message = await perform(async () => {
    // 后端要求 options.filename 与清单的 source_filename 一致。
    const value = asObject<ImportGroup>(
      await apiPost(shopPath('/import-groups'), {
        options: { ...options(), filename: manifest.source_filename },
        manifest,
      }),
    )
    group.value = value
    await load()
  })
  if (message === '') success('导入组已建立，请逐片上传、预览并确认。')
  else error.value = message
}

async function openGroup(id: number): Promise<void> {
  const message = await perform(async () => {
    group.value = asObject<ImportGroup>(await apiGet(`/api/import-groups/${id}`))
  })
  error.value = message
}

async function uploadPart(index: number): Promise<void> {
  const current = group.value
  const source = prepared.value
  if (current === null || source === null) return
  const part = current.manifest.parts[index]
  const bytes = source.parts[index]
  if (part === undefined || bytes === undefined) return
  if (bytes.length !== part.bytes || sha256Hex(bytes) !== part.sha256) {
    error.value = '此分片字节或指纹与清单不一致，请使用原分片。'
    return
  }
  const message = await perform(async () => {
    const sourceOptions = Object.fromEntries(
      Object.entries(current.options ?? {}).filter(([, value]) => value !== null && value !== undefined && `${value}` !== ''),
    )
    const created = asObject<ImportBatch>(
      await apiRequest<ImportBatch>(shopPath('/imports'), {
        method: 'POST',
        query: { ...sourceOptions, filename: part.filename, group_id: current.id, group_part: index + 1 },
        bytes: toArrayBuffer(bytes),
        contentType: 'application/octet-stream',
      }),
    )
    group.value = asObject<ImportGroup>(await apiGet(`/api/import-groups/${current.id}`))
    if (created !== null) await loadBatch(created.id)
    group.value = asObject<ImportGroup>(await apiGet(`/api/import-groups/${current.id}`))
  })
  error.value = message
}

function sha256Of(bytes: Uint8Array): string {
  return sha256Hex(bytes)
}

async function selectPart(): Promise<void> {
  const current = group.value
  if (current === null) return
  let index = -1
  let bytes: Uint8Array | null = null
  const message = await perform(async () => {
    const file = await pickFile(['csv'])
    if (file === null) return
    index = current.manifest.parts.findIndex((part) => part.filename === file.name)
    if (index < 0) throw new Error('文件名不在当前清单中，请选择原分片。')
    bytes = file.bytes
  })
  if (message !== '') {
    error.value = message
    return
  }
  if (bytes === null || index < 0) return
  const part = current.manifest.parts[index]
  const selected = bytes as Uint8Array
  if (part === undefined || selected.length !== part.bytes || sha256Of(selected) !== part.sha256) {
    error.value = '此分片字节或指纹与清单不一致，请使用原分片。'
    return
  }
  const upload = await perform(async () => {
    const sourceOptions = Object.fromEntries(
      Object.entries(current.options ?? {}).filter(([, value]) => value !== null && value !== undefined && `${value}` !== ''),
    )
    const created = asObject<ImportBatch>(
      await apiRequest<ImportBatch>(shopPath('/imports'), {
        method: 'POST',
        query: { ...sourceOptions, filename: part.filename, group_id: current.id, group_part: index + 1 },
        bytes: toArrayBuffer(selected),
        contentType: 'application/octet-stream',
      }),
    )
    group.value = asObject<ImportGroup>(await apiGet(`/api/import-groups/${current.id}`))
    if (created !== null) await loadBatch(created.id)
  })
  error.value = upload
}

async function revokeGroup(): Promise<void> {
  const current = group.value
  if (current === null) return
  const modal = await Taro.showModal({
    title: '撤销整个导入组',
    content: '将撤销本组所有分片及其衍生来源，按剩余有效批次恢复其他版本。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  const message = await perform(async () => {
    const value = asObject<ImportGroup>(
      await apiPost(`/api/import-groups/${current.id}/revoke`, { version: current.version }),
    )
    if (value !== null) group.value = value
    prepared.value = null
    await load()
  })
  if (message === '') success('整组已撤销。')
  else error.value = message
}
</script>
