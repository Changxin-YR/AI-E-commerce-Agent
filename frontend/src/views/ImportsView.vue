<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { identityApi } from '@/api/identity'
import { importsApi } from '@/api/imports'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import type {
  BatchSummary,
  Corrections,
  ImportBatch,
  ImportCatalog,
  ImportKind,
  MappingTemplate,
  SourceChannel,
} from '@/types/imports'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import ImportMapping from '@/components/ImportMapping.vue'
import ImportRows from '@/components/ImportRows.vue'

const shops = ref<Shop[]>([])
const shopId = ref(0)
const catalog = ref<ImportCatalog | null>(null)
const templates = ref<MappingTemplate[]>([])
const history = ref<BatchSummary[]>([])
const batch = ref<ImportBatch | null>(null)
const mapping = ref<Record<string, string>>({})
const corrections = ref<Corrections>({})
const kind = ref<ImportKind>('products')
const templateFormat = ref('csv')
const channel = ref<SourceChannel>('generic')
const identity = ref('user_import')
const timezone = ref('Asia/Shanghai')
const exportedAt = ref('')
const file = ref<File | null>(null)
const fileKey = ref(0)
const busy = ref(false)
const error = ref('')
const success = ref('')
const dirty = ref(false)
const allowUpdates = ref(false)
const templateName = ref('')
const selectedTemplate = ref('')
const pendingAction = ref<'revoke' | 'clear' | null>(null)
const editable = computed(() => !!batch.value && ['draft', 'preview'].includes(batch.value.status))
const fields = computed(() => catalog.value?.[batch.value?.kind ?? kind.value] ?? [])
const suitableTemplates = computed(() =>
  templates.value.filter(
    (item) =>
      item.kind === batch.value?.kind && item.source_channel === batch.value?.source_channel,
  ),
)
const canCommit = computed(
  () =>
    batch.value?.status === 'preview' &&
    !dirty.value &&
    !batch.value.errors.length &&
    batch.value.error_rows === 0 &&
    (!batch.value.updated_rows || allowUpdates.value),
)
const statusLabels = {
  draft: '待映射',
  preview: '待确认',
  committed: '已导入',
  revoked: '已撤销',
  cleared: '已清除',
  expired: '已过期',
}

function displayTime(value: string | null, zone = 'Asia/Shanghai'): string {
  if (!value) return '未知'
  const utcValue = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`
  return `${new Intl.DateTimeFormat('zh-CN', { dateStyle: 'short', timeStyle: 'medium', timeZone: zone }).format(new Date(utcValue))} (${zone})`
}
async function perform(action: () => Promise<void>): Promise<void> {
  busy.value = true
  error.value = ''
  success.value = ''
  try {
    await action()
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function loadHistory(): Promise<void> {
  history.value = shopId.value ? await importsApi.list(shopId.value) : []
}
function adopt(value: ImportBatch): void {
  batch.value = value
  mapping.value = { ...value.mapping }
  corrections.value = Object.fromEntries(
    value.rows.map((row) => [row.row_number, { ...row.corrections }]),
  )
  dirty.value = false
  allowUpdates.value = false
  pendingAction.value = null
}
async function initialize(): Promise<void> {
  await perform(async () => {
    const [loadedShops, loadedCatalog, loadedTemplates] = await Promise.all([
      identityApi.shops(),
      importsApi.catalog(),
      importsApi.mappings(),
    ])
    shops.value = loadedShops
    catalog.value = loadedCatalog
    templates.value = loadedTemplates
    if (loadedShops[0]) {
      shopId.value = loadedShops[0].id
      timezone.value = loadedShops[0].timezone
    }
    await loadHistory()
  })
}
async function changeShop(): Promise<void> {
  batch.value = null
  timezone.value = shops.value.find((shop) => shop.id === shopId.value)?.timezone ?? 'Asia/Shanghai'
  await perform(loadHistory)
}
function chooseFile(event: Event): void {
  file.value = (event.target as HTMLInputElement).files?.[0] ?? null
}
async function upload(): Promise<void> {
  await perform(async () => {
    if (!file.value) throw new Error('请选择文件')
    if (file.value.size > (catalog.value?.max_bytes ?? 2097152))
      throw new Error('文件不能超过 2 MiB')
    const options = {
      filename: file.value.name,
      kind: kind.value,
      source_channel: channel.value,
      data_identity: identity.value,
      timezone: timezone.value,
      ...(exportedAt.value ? { exported_at: exportedAt.value } : {}),
    }
    adopt(await importsApi.upload(shopId.value, file.value, options))
    file.value = null
    fileKey.value++
    await loadHistory()
  })
}
function changeMapping(field: string, column: string): void {
  mapping.value[field] = column
  corrections.value = {}
  dirty.value = true
  allowUpdates.value = false
}
function correct(row: number, field: string, value: string): void {
  corrections.value[row] = { ...corrections.value[row], [field]: value }
  dirty.value = true
  allowUpdates.value = false
}
async function preview(): Promise<void> {
  await perform(async () => {
    if (!batch.value) return
    adopt(
      await importsApi.preview(
        batch.value.id,
        batch.value.version,
        mapping.value,
        corrections.value,
      ),
    )
    await loadHistory()
  })
}
async function commit(): Promise<void> {
  await perform(async () => {
    if (!batch.value || !canCommit.value) return
    adopt(await importsApi.commit(batch.value.id, batch.value.version, allowUpdates.value))
    await loadHistory()
    success.value = '批次已导入。可展开源行核对，重复确认不会重复增加业务记录。'
  })
}
async function openBatch(id: number): Promise<void> {
  await perform(async () => {
    adopt(await importsApi.get(id))
  })
}
async function withdraw(): Promise<void> {
  await perform(async () => {
    if (!batch.value || !pendingAction.value) return
    adopt(await importsApi.withdraw(batch.value.id, batch.value.version, pendingAction.value))
    await loadHistory()
    success.value = '批次状态已更新；有效业务记录已按剩余批次重新确定。'
  })
}
function applyTemplate(): void {
  const selected = suitableTemplates.value.find(
    (item) => item.id === Number(selectedTemplate.value),
  )
  if (!selected || !batch.value) return
  mapping.value = Object.fromEntries(
    Object.entries(selected.mapping).filter(([, column]) => batch.value!.headers.includes(column)),
  )
  corrections.value = {}
  dirty.value = true
  allowUpdates.value = false
}
async function saveTemplate(): Promise<void> {
  await perform(async () => {
    if (!batch.value || !templateName.value.trim()) throw new Error('请填写映射模板名称')
    await importsApi.saveMapping({
      name: templateName.value.trim(),
      kind: batch.value.kind,
      source_channel: batch.value.source_channel,
      mapping: Object.fromEntries(Object.entries(mapping.value).filter(([, value]) => value)),
    })
    templates.value = await importsApi.mappings()
    success.value = '个人映射模板已保存；同名模板已更新。'
  })
}
onMounted(initialize)
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>把业务数据，整理成依据。</h1>
      <p>上传、核对、确认。每一行都能追溯到原始批次。</p>
    </div>
    <span class="outline-label">业务文件导入</span>
  </div>
  <FeedbackBanner :message="error" /><FeedbackBanner :message="success" kind="success" />
  <button v-if="error && !catalog" class="button secondary" @click="initialize">重新加载</button>
  <section class="data-note import-note">
    <span class="note-symbol" aria-hidden="true">i</span>
    <div>
      <h3>当前为文件分析模式</h3>
      <p>
        数据截至你导出的时间，用于本地业务分析与草稿。上传内容按资料处理。文件暂存用于映射，24
        小时后失效，后续访问时清理；确认后只保留映射字段及修正记录。请移除顾客姓名、地址、电话与邮箱。
      </p>
    </div>
  </section>
  <p v-if="busy" role="status" class="section-block">正在处理，请稍候…</p>
  <section v-if="catalog && !shops.length" class="form-panel section-block empty-state">
    <h2>先为文件选择一个归属</h2>
    <p>添加店铺记录后即可导入。</p>
    <RouterLink to="/settings" class="button primary">添加店铺</RouterLink>
  </section>
  <template v-if="catalog && shops.length">
    <section class="section-block form-panel">
      <div class="section-title">
        <h2>01 / 选择文件</h2>
        <div class="button-group">
          <select v-model="templateFormat" aria-label="模板格式" class="template-format">
            <option value="csv">CSV</option>
            <option value="xlsx">Excel</option>
          </select>
          <a
            class="button secondary small"
            :href="`/api/imports/templates/products?format=${templateFormat}`"
            >商品模板</a
          ><a
            class="button secondary small"
            :href="`/api/imports/templates/orders?format=${templateFormat}`"
            >订单模板</a
          ><a
            class="button secondary small"
            :href="`/api/imports/templates/messages?format=${templateFormat}`"
            >客服消息模板</a
          ><a
            class="button secondary small"
            :href="`/api/imports/templates/inventory?format=${templateFormat}`"
            >库存快照模板</a
          >
        </div>
      </div>
      <form @submit.prevent="upload">
        <div class="form-grid">
          <div class="form-field">
            <label for="import-shop">所属店铺</label
            ><select id="import-shop" v-model="shopId" :disabled="busy" @change="changeShop">
              <option v-for="shop in shops" :key="shop.id" :value="shop.id">
                {{ shop.name }} · {{ shop.code }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label for="import-kind">报表类型</label
            ><select id="import-kind" v-model="kind" :disabled="busy">
              <option value="products">通用商品文件</option>
              <option value="orders">通用订单行文件</option>
              <option value="messages">通用客服消息文件</option>
              <option value="inventory">通用库存快照文件</option>
            </select>
          </div>
          <div class="form-field">
            <label for="import-channel">来源渠道</label
            ><select id="import-channel" v-model="channel" :disabled="busy">
              <option value="generic">通用 / 自建表</option>
              <option value="shopify">Shopify 风格候选</option>
              <option value="amazon">Amazon 风格候选</option>
              <option value="other">其他来源</option></select
            ><small>平台别名仅为映射候选，尚无真实报表验证。</small>
          </div>
          <div class="form-field">
            <label for="import-identity">数据身份</label
            ><select id="import-identity" v-model="identity" :disabled="busy">
              <option value="user_import">用户导入文件</option>
              <option value="synthetic">合成测试数据</option>
            </select>
          </div>
          <div class="form-field">
            <label for="import-zone">文件时间使用的时区</label
            ><input
              id="import-zone"
              v-model="timezone"
              :disabled="busy"
              required
              maxlength="64"
            /><small>用于无时区偏移的日期时间，例如 Asia/Shanghai。</small>
          </div>
          <div class="form-field">
            <label for="import-exported">导出时间（可选）</label
            ><input
              id="import-exported"
              v-model="exportedAt"
              :disabled="busy"
              placeholder="2026-10-08T09:00:00+08:00"
            /><small>包含明确时区偏移；未知可留空。</small>
          </div>
          <div class="form-field wide">
            <label for="import-file">CSV / Excel 文件</label
            ><input
              :key="fileKey"
              id="import-file"
              type="file"
              accept=".csv,.xlsx"
              :disabled="busy"
              required
              @change="chooseFile"
            /><small
              >UTF-8 CSV 或单工作表 .xlsx，最多 2 MiB、2000 行、64
              列。金额最多四位小数；不接受宏、公式及外部链接。</small
            >
          </div>
        </div>
        <div class="form-actions">
          <span>上传后先核对映射，确认时才写入业务数据。</span
          ><button class="button primary" :disabled="busy || !file">上传并查看映射</button>
        </div>
      </form>
    </section>
    <section v-if="batch" class="section-block form-panel" aria-labelledby="batch-title">
      <div class="section-title">
        <h2 id="batch-title">批次 #{{ batch.id }} · {{ batch.filename }}</h2>
        <span class="status-tag" :class="{ complete: batch.status === 'committed' }">{{
          statusLabels[batch.status]
        }}</span>
      </div>
      <p class="muted">
        {{ batch.data_identity === 'synthetic' ? '合成测试数据' : '用户导入文件' }} ·
        {{ batch.source_channel }} · {{ batch.sheet_name }} ·
        {{
          { products: '商品', orders: '订单行', messages: '客服消息', inventory: '库存快照' }[
            batch.kind
          ]
        }}
      </p>
      <p class="muted">
        导入时间 {{ displayTime(batch.created_at, batch.timezone) }} · 导出时间
        {{ displayTime(batch.exported_at, batch.timezone) }}
      </p>
      <p class="muted" v-if="batch.coverage_start">
        数据时间范围 {{ displayTime(batch.coverage_start, batch.timezone) }} 至
        {{ displayTime(batch.coverage_end, batch.timezone) }}
      </p>
      <template v-if="editable">
        <h3 class="section-block">02 / 核对字段映射</h3>
        <p class="muted">
          识别候选：{{
            { products: '商品', orders: '订单行', messages: '客服消息', inventory: '库存快照' }[
              batch.suggested_kind
            ]
          }}。请核对已选报表类型；若不符，可重新上传并选择类型。
        </p>
        <div class="template-controls">
          <label for="saved-mapping">复用个人映射</label
          ><select
            id="saved-mapping"
            v-model="selectedTemplate"
            :disabled="busy"
            @change="applyTemplate"
          >
            <option value="">请选择</option>
            <option v-for="item in suitableTemplates" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select>
        </div>
        <ImportMapping
          :batch="batch"
          :fields="fields"
          :mapping="mapping"
          :disabled="busy"
          @change="changeMapping"
        />
        <div class="template-controls">
          <label for="template-name">保存为个人映射</label
          ><input
            id="template-name"
            v-model="templateName"
            placeholder="例如：店铺月报 v1"
            maxlength="80"
            :disabled="busy"
          /><button
            class="button secondary"
            :disabled="busy || !templateName"
            @click="saveTemplate"
          >
            保存映射
          </button>
        </div>
        <div class="form-actions">
          <span>修改映射或修正值后，请重新预览。</span
          ><button class="button primary" :disabled="busy" @click="preview">校验并预览</button>
        </div>
      </template>
      <template v-if="batch.rows.length">
        <div class="import-counts">
          <span
            >总计 <b>{{ batch.total_rows }}</b></span
          ><span
            >有效 <b>{{ batch.valid_rows }}</b></span
          ><span
            >错误 <b>{{ batch.error_rows }}</b></span
          ><span
            >新增 <b>{{ batch.new_rows }}</b></span
          ><span
            >更新 <b>{{ batch.updated_rows }}</b></span
          ><span
            >相同 <b>{{ batch.unchanged_rows }}</b></span
          >
        </div>
        <p class="muted">
          币种：{{
            batch.currencies.join('、') || '未知'
          }}。不同币种分别保留，不自动换算。未知费用不补零。
        </p>
        <FeedbackBanner v-for="message in batch.errors" :key="message" :message="message" />
        <a
          v-if="batch.error_rows"
          class="button secondary small"
          :href="`/api/imports/${batch.id}/errors.csv`"
          >下载错误行报告</a
        >
        <p v-if="dirty" class="row-warning" role="status">存在未预览的修改，确认导入已暂停。</p>
        <div class="section-block">
          <ImportRows
            :rows="batch.rows"
            :fields="fields"
            :editable="editable"
            :corrections="corrections"
            :disabled="busy"
            @correct="correct"
          />
        </div>
      </template>
      <div v-if="editable" class="form-actions">
        <label v-if="batch.updated_rows" class="check-label"
          ><input
            v-model="allowUpdates"
            type="checkbox"
            :disabled="busy || dirty"
          />已核对旧值与新值，允许更新 {{ batch.updated_rows }} 行</label
        ><span v-else>整批有效且完成预览后才能确认。</span
        ><button class="button primary" :disabled="busy || !canCommit" @click="commit">
          确认导入
        </button>
      </div>
      <div v-if="batch.status !== 'cleared'" class="form-actions">
        <span
          >撤销后恢复剩余有效来源，关联费用须重新核对，依赖本批的人工商品修订同步失效。清除还会擦除源行、依赖修订及费用的全部历史正文；保留必要状态和操作审计。</span
        >
        <div class="button-group">
          <button
            v-if="batch.status !== 'revoked' && batch.status !== 'expired'"
            class="button secondary"
            :disabled="busy"
            @click="pendingAction = 'revoke'"
          >
            {{ editable ? '取消此批次' : '撤销此批次' }}</button
          ><button class="button secondary" :disabled="busy" @click="pendingAction = 'clear'">
            清除源数据
          </button>
        </div>
      </div>
      <div v-if="pendingAction" class="action-confirm" role="region" aria-label="确认批次操作">
        <p>
          将{{
            pendingAction === 'clear'
              ? '清除此批次的源行与修正数据，清除后无法恢复'
              : '停止使用此批次，保留已提交的源行以便复核'
          }}。依赖本批的人工商品修订及费用依据将同步{{
            pendingAction === 'clear' ? '清除正文' : '失效'
          }}，后续分析需要使用最新数据重新计算。
        </p>
        <div class="button-group">
          <button class="button primary" :disabled="busy" @click="withdraw">
            确认{{ pendingAction === 'clear' ? '清除' : '撤销' }}</button
          ><button class="button secondary" :disabled="busy" @click="pendingAction = null">
            返回
          </button>
        </div>
      </div>
    </section>
    <section class="section-block">
      <div class="section-title">
        <h2>导入记录</h2>
        <span>当前店铺最近 100 批</span>
      </div>
      <p v-if="!history.length" class="muted">还没有导入记录。从一份文件开始。</p>
      <div v-for="item in history" :key="item.id" class="batch-history">
        <div>
          <h3>#{{ item.id }} · {{ item.filename }}</h3>
          <p class="muted">
            {{ item.data_identity === 'synthetic' ? '合成测试' : '用户导入' }} ·
            {{ item.origin === 'manual_edit' ? '人工修订' : '文件导入' }} · {{ item.total_rows }} 行
            · {{ statusLabels[item.status] }}
          </p>
        </div>
        <button class="button secondary small" :disabled="busy" @click="openBatch(item.id)">
          查看批次 #{{ item.id }}
        </button>
      </div>
    </section>
  </template>
</template>
