<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import Taro, { useDidShow, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { chooseFile, exportFile, uploadFile } from '../../services/files'
import { prepareImport, type PreparedImport } from '../../services/prepare-import'
import { sameManifest } from '../../services/csv-split'
import type { ImportBatch, ImportCatalog, ImportKind, BatchSummary, MappingTemplate, Corrections, ImportGroup } from '../../services/import-types'

const kinds: ImportKind[] = ['products', 'orders', 'messages', 'inventory', 'statements']
const labels = ['商品', '订单行', '客服消息', '库存快照', '渠道账单']
const channels = ['generic', 'shopify', 'amazon', 'other']
const kindIndex = ref(0), channelIndex = ref(0), identityIndex = ref(0), timezone = ref('Asia/Shanghai'), exportedAt = ref('')
const busy = ref(false), error = ref(''), notice = ref(''), catalog = ref<ImportCatalog>(), templates = ref<MappingTemplate[]>([]), history = ref<BatchSummary[]>([])
const batch = ref<ImportBatch>(), mapping = ref<Record<string, string>>({}), corrections = ref<Corrections>({}), dirty = ref(false), reviewed = ref<string[]>([]), allowUpdates = ref(false), templateName = ref('')
const rowPage = ref(0), errorsOnly = ref(false), groups = ref<ImportGroup[]>([]), selectedGroup = ref<ImportGroup>(), olderCursor = ref<number>()
const prepared = shallowRef<PreparedImport>(), progress = ref('')
const fields = computed(() => catalog.value?.[batch.value?.kind || kinds[kindIndex.value]!] || [])
const editable = computed(() => !!batch.value && ['draft', 'preview'].includes(batch.value.status))
const rows = computed(() => (batch.value?.rows || []).filter(row => !errorsOnly.value || row.errors.length))
const visibleRows = computed(() => rows.value.slice(rowPage.value * 10, rowPage.value * 10 + 10))
const matchingTemplates = computed(() => templates.value.filter(item => item.kind === batch.value?.kind && item.source_channel === batch.value?.source_channel))
const canCommit = computed(() => batch.value?.status === 'preview' && !dirty.value && !batch.value.errors.length && !batch.value.error_rows && (!batch.value.updated_rows || allowUpdates.value) && (batch.value.required_reviews || []).every(item => reviewed.value.includes(item.field)))
const options = () => ({ kind: kinds[kindIndex.value]!, source_channel: channels[channelIndex.value]!, data_identity: identityIndex.value ? 'synthetic' : 'user_import', timezone: timezone.value, ...(exportedAt.value ? { exported_at: exportedAt.value } : {}) })
const statusLabels: Record<string, string> = { draft: '待映射', preview: '待确认', committed: '已导入', revoked: '已撤销', cleared: '已清除', expired: '已过期' }
function eventValue(event: unknown): unknown { return (event as { detail: { value: unknown } }).detail.value }
function release() { prepared.value?.dispose(); prepared.value = undefined }
function reset() { batch.value = undefined; history.value = []; groups.value = []; selectedGroup.value = undefined; release(); error.value = ''; notice.value = '' }
watch(() => [account.shopId, account.session?.session_id], reset)
let alive = true
useUnload(() => { alive = false; release() })
function changed() { dirty.value = true; reviewed.value = []; allowUpdates.value = false }
function adopt(value: ImportBatch) {
  if (value.shop_id !== account.shopId) throw new Error('批次不属于当前店铺。')
  batch.value = value; mapping.value = { ...value.mapping }; corrections.value = Object.fromEntries(value.rows.filter(row => Object.keys(row.corrections).length).map(row => [row.row_number, { ...row.corrections }]))
  dirty.value = false; reviewed.value = []; allowUpdates.value = false; rowPage.value = 0
}
async function perform(action: () => Promise<void>) {
  if (busy.value) return
  if (!account.session || !account.shopId) { error.value = '请返回工作台登录并选择店铺。'; return }
  busy.value = true; error.value = ''; notice.value = ''
  try { await action() } catch (cause) { error.value = cause instanceof Error ? cause.message : '操作未完成。请刷新记录核对结果后再操作。' } finally { busy.value = false; progress.value = '' }
}
async function refresh() {
  const [batches, list] = await Promise.all([api.request<BatchSummary[]>(`/shops/${account.shopId}/imports`), api.request<ImportGroup[]>(`/shops/${account.shopId}/import-groups`)])
  history.value = batches; groups.value = list; olderCursor.value = list.length === 20 ? list[list.length - 1]?.id : undefined
  if (selectedGroup.value) selectedGroup.value = await api.request<ImportGroup>(`/import-groups/${selectedGroup.value.id}`)
}
async function initialize() { await perform(async () => { const [c, t] = await Promise.all([api.request<ImportCatalog>('/imports/catalog'), api.request<MappingTemplate[]>('/imports/mappings')]); catalog.value = c; templates.value = t; timezone.value = account.shops.find(s => s.id === account.shopId)?.timezone || 'Asia/Shanghai'; await refresh() }) }
useDidShow(() => { void initialize() })
async function upload() { await perform(async () => { const shop = account.shopId, settings = options(), session = account.session; const file = await chooseFile(); if (shop !== account.shopId || session !== account.session) return; adopt(await uploadFile<ImportBatch>(shop, file, settings)); await refresh() }) }
async function openBatch(id: number) { await perform(async () => { adopt(await api.request<ImportBatch>(`/imports/${id}`)) }) }
function mapField(key: string, index: number) { mapping.value[key] = batch.value?.headers[index - 1] || ''; changed() }
function correct(row: number, field: string, value: string) { corrections.value[row] = { ...corrections.value[row], [field]: value }; changed() }
async function preview() { await perform(async () => { if (!batch.value) return; adopt(await api.request<ImportBatch>(`/imports/${batch.value.id}/preview`, 'POST', { version: batch.value.version, mapping: Object.fromEntries(Object.entries(mapping.value).filter(([, v]) => v)), corrections: corrections.value })) }) }
async function commit() { await perform(async () => { if (!batch.value || !canCommit.value) return; const id = batch.value.id; await api.request(`/imports/${id}/commit`, 'POST', { version: batch.value.version, allow_updates: allowUpdates.value, reviewed_fields: reviewed.value }); adopt(await api.request<ImportBatch>(`/imports/${id}`)); await refresh(); notice.value = '已回读导入结果。' }) }
async function withdraw(action: 'revoke' | 'clear') { await perform(async () => {
  if (!batch.value) return
  const { id, version } = batch.value
  const answer = await Taro.showModal({ title: action === 'clear' ? '清除源数据' : '撤销批次', content: action === 'clear' ? '清除源行、修订和关联费用历史正文后无法恢复，依赖结果将失效。确认继续？' : '停止使用此批来源，关联修订和费用依据失效，分析需要重新计算。确认继续？' })
  if (!answer.confirm || batch.value?.id !== id || !account.session) return
  await api.request(`/imports/${id}/${action}`, 'POST', { version }); adopt(await api.request<ImportBatch>(`/imports/${id}`)); await refresh()
}) }
async function saveTemplate() { await perform(async () => { if (!batch.value) return; await api.request('/imports/mappings', 'POST', { name: templateName.value.trim(), kind: batch.value.kind, source_channel: batch.value.source_channel, mapping: Object.fromEntries(Object.entries(mapping.value).filter(([, v]) => v)) }); templates.value = await api.request<MappingTemplate[]>('/imports/mappings'); notice.value = '个人映射已保存。' }) }
function applyMapping(value: Record<string, string>) { mapping.value = Object.fromEntries(Object.entries(value).filter(([, v]) => batch.value?.headers.includes(v))); corrections.value = {}; changed() }
async function prepare() { await perform(async () => { release(); const shop = account.shopId, session = account.session, selected = selectedGroup.value?.id; const file = await chooseFile(); const result = await prepareImport(file, rows => { progress.value = `已解析 ${rows} 条逻辑记录` }); if (!alive || shop !== account.shopId || session !== account.session) { result.dispose(); return } if (selected && selectedGroup.value && !sameManifest(result.manifest, selectedGroup.value.manifest)) { result.dispose(); throw new Error('原文件指纹或分片清单与当前导入组不一致。') } prepared.value = result; notice.value = `已准备 ${result.manifest.parts.length} 片，请核对数据身份后建组。` }) }
async function createGroup() { await perform(async () => { if (!prepared.value) return; selectedGroup.value = await api.request<ImportGroup>(`/shops/${account.shopId}/import-groups`, 'POST', { options: { ...options(), filename: prepared.value.manifest.source_filename }, manifest: prepared.value.manifest }); await refresh() }) }
async function selectGroup(group: ImportGroup) { await perform(async () => { release(); selectedGroup.value = await api.request<ImportGroup>(`/import-groups/${group.id}`) }) }
async function uploadPart(index: number) { await perform(async () => { const group = selectedGroup.value, source = prepared.value; if (!group || !source || !sameManifest(group.manifest, source.manifest)) throw new Error('请重新选择建组时的原始 CSV。'); const settings = Object.fromEntries(Object.entries(group.options).filter(([, v]) => v != null)) as Record<string, string | number>; adopt(await uploadFile<ImportBatch>(account.shopId, source.files[index]!, { ...settings, group_id: group.id, group_part: index + 1 })); await refresh() }) }
async function revokeGroup() { await perform(async () => { const group = selectedGroup.value; if (!group) return; const answer = await Taro.showModal({ title: '撤销整组', content: '停止使用整组所有分片，依赖分析及修订失效。确认继续？' }); if (!answer.confirm || selectedGroup.value?.id !== group.id) return; await api.request(`/import-groups/${group.id}/revoke`, 'POST', { version: group.version }); await refresh(); if (batch.value?.group_id === group.id) adopt(await api.request<ImportBatch>(`/imports/${batch.value.id}`)) }) }
async function older() { await perform(async () => { const list = await api.request<ImportGroup[]>(`/shops/${account.shopId}/import-groups?before=${olderCursor.value}`); groups.value.push(...list.filter(item => !groups.value.some(g => g.id === item.id))); olderCursor.value = list.length === 20 ? list[list.length - 1]?.id : undefined }) }
function download(path: string, name: string) { void perform(() => exportFile(path, name)) }
</script>

<template>
  <view class="screen">
    <view class="hero"><text class="eyebrow">业务文件导入</text><text class="title">把数据整理成依据</text><text class="muted">{{ account.shops.find(s => s.id === account.shopId)?.name || '请先选择店铺' }} · 上传、核对、确认</text></view>
    <view v-if="error" class="error">{{ error }}<text class="hint">写入断线时结果可能未知，请刷新批次或导入组后核对，勿重复提交。</text></view>
    <text v-if="notice" class="hint">{{ notice }}</text><text v-if="busy" class="hint">{{ progress || '正在处理…' }}</text>
    <button :disabled="busy" @tap="initialize">刷新记录</button>
    <view class="card">
      <text class="section-title">01 / 文件与数据身份</text><text class="hint">CSV UTF-8 或单表 XLSX，每批 2 MiB / 2000 行。暂存 24 小时；请移除顾客姓名、地址、电话及邮箱。</text>
      <text class="label">报表类型</text><picker :range="labels" :value="kindIndex" :disabled="busy" @change="kindIndex = Number($event.detail.value)"><view class="select">{{ labels[kindIndex] }}</view></picker>
      <text class="label">来源渠道</text><picker :range="channels" :value="channelIndex" :disabled="busy" @change="channelIndex = Number($event.detail.value)"><view class="select">{{ channels[channelIndex] }}</view></picker>
      <text class="label">数据身份</text><picker :range="['用户导入文件', '合成测试数据']" :value="identityIndex" :disabled="busy" @change="identityIndex = Number($event.detail.value)"><view class="select">{{ identityIndex ? '合成测试数据' : '用户导入文件' }}</view></picker>
      <text class="label">文件时区</text><input v-model="timezone" :disabled="busy" placeholder="Asia/Shanghai" />
      <text class="label">导出时间（可选，含时区）</text><input v-model="exportedAt" :disabled="busy" placeholder="2026-10-11T12:00:00+08:00" />
      <button :disabled="busy" @tap="download(`/imports/templates/${kinds[kindIndex]}?format=csv`, `soloops-${kinds[kindIndex]}.csv`)">获取 CSV 模板</button>
      <button :disabled="busy" @tap="download(`/imports/templates/${kinds[kindIndex]}?format=xlsx`, `soloops-${kinds[kindIndex]}.xlsx`)">获取 Excel 模板</button>
      <button class="primary" :disabled="busy || !account.shopId" @tap="upload">从聊天选择文件并上传</button>
    </view>
    <view class="card">
      <text class="section-title">大 CSV 分批导入</text><text class="hint">最多 40 MiB / 40000 条逻辑记录 / 20 片。每片独立预览、确认；部分完成表示来源覆盖不足。</text>
      <text v-if="selectedGroup" class="label">当前组 #{{ selectedGroup.id }} · {{ selectedGroup.status }} · {{ selectedGroup.options.data_identity }}</text>
      <button :disabled="busy" @tap="selectedGroup = undefined; release()">开始新的导入组</button>
      <button :disabled="busy" @tap="prepare">选择原始 CSV 并校验分片</button>
      <text v-if="prepared" class="hint">{{ prepared.manifest.source_filename }} · {{ prepared.manifest.total_rows }} 行 / {{ prepared.manifest.parts.length }} 片</text>
      <button v-if="prepared && !selectedGroup" class="primary" :disabled="busy" @tap="createGroup">按上方身份与类型创建导入组</button>
      <template v-if="selectedGroup">
        <text class="hint">已提交 {{ selectedGroup.committed_parts }} 片 / {{ selectedGroup.committed_rows }} 行；唯一 {{ selectedGroup.unique_rows }} 行，重叠 {{ selectedGroup.overlap_rows }} 行。{{ selectedGroup.complete ? '全部分片已完成' : '部分覆盖 / 数据不足' }}</text>
        <view v-for="(part, index) in selectedGroup.manifest.parts" :key="part.filename" class="record">
          <text>{{ index + 1 }}. {{ part.filename }} · {{ part.rows }} 行</text>
          <template v-if="selectedGroup.batches.find(b => b.group_part === index + 1)"><text class="hint">{{ statusLabels[selectedGroup.batches.find(b => b.group_part === index + 1)!.status] }}</text><button :disabled="busy" @tap="openBatch(selectedGroup.batches.find(b => b.group_part === index + 1)!.id)">查看并审阅此片</button></template>
          <button v-if="!selectedGroup.batches.some(b => b.group_part === index + 1 &amp;&amp; ['draft', 'preview', 'committed'].includes(b.status))" :disabled="busy || !prepared || selectedGroup.status !== 'active'" @tap="uploadPart(index)">上传此片</button>
        </view>
        <button v-if="selectedGroup.status === 'active'" class="danger" :disabled="busy" @tap="revokeGroup">撤销整组</button>
      </template>
      <view v-for="group in groups" :key="group.id" class="record"><text>#{{ group.id }} · {{ group.manifest.source_filename }} · {{ group.status }} · {{ group.committed_parts }}/{{ group.manifest.parts.length }} 片</text><button :disabled="busy" @tap="selectGroup(group)">查看导入组</button></view>
      <button v-if="olderCursor" :disabled="busy" @tap="older">更早的导入组</button>
    </view>
    <view v-if="batch" class="card">
      <text class="section-title">批次 #{{ batch.id }} · {{ statusLabels[batch.status] || batch.status }}</text><text class="muted">{{ batch.filename }} · {{ batch.kind }} · {{ batch.data_identity }} · {{ batch.source_channel }}</text><text class="hint">版本 {{ batch.version }} · 文件时区 {{ batch.timezone }} · 导出 {{ batch.exported_at || '未知' }} · 币种 {{ batch.currencies.join('、') || '未知' }}</text>
      <text class="hint">覆盖 {{ batch.coverage_start || '未知' }} 至 {{ batch.coverage_end || '未知' }}；服务端原始时间保留时区。</text>
      <template v-if="editable">
        <text class="label">02 / 核对字段映射</text><text class="hint">识别候选 {{ batch.suggested_kind }}。候选不一致请重新选择报表类型上传。</text>
        <button v-for="preset in batch.presets" :key="preset.id" :disabled="busy" @tap="applyMapping(preset.mapping)">候选映射：{{ preset.name }}</button>
        <text v-for="preset in batch.presets" :key="`${preset.id}-notes`" class="hint">{{ preset.notes.join('；') }}</text>
        <button v-for="item in matchingTemplates" :key="item.id" :disabled="busy" @tap="applyMapping(item.mapping)">使用映射：{{ item.name }}</button>
        <view v-for="field in fields" :key="field.key"><text class="label">{{ field.label }}{{ field.required ? ' *' : '' }}</text><picker :range="['不映射', ...batch.headers]" :value="batch.headers.indexOf(mapping[field.key] || '') + 1" :disabled="busy" @change="mapField(field.key, Number($event.detail.value))"><view class="select">{{ mapping[field.key] || '不映射' }}</view></picker><text class="hint">{{ field.help }} · 示例 {{ batch.examples[mapping[field.key] || ''] || '空' }}</text></view>
        <input v-model="templateName" :disabled="busy" placeholder="个人映射模板名称" :maxlength="80" /><button :disabled="busy || !templateName.trim()" @tap="saveTemplate">保存个人映射</button>
        <button class="primary" :disabled="busy" @tap="preview">校验并预览</button>
      </template>
      <text class="label">总计 {{ batch.total_rows }} · 有效 {{ batch.valid_rows }} · 错误 {{ batch.error_rows }}</text><text class="hint">新增 {{ batch.new_rows }} · 更新 {{ batch.updated_rows }} · 相同 {{ batch.unchanged_rows }} · 重复 {{ batch.duplicate_rows || 0 }}</text>
      <text v-for="message in batch.errors" :key="message" class="error">{{ message }}</text>
      <button v-if="batch.error_rows || batch.errors.length" :disabled="busy" @tap="download(`/imports/${batch.id}/errors.csv`, `import-${batch.id}-errors.csv`)">导出错误报告</button>
      <view class="row"><text>只看错误行</text><switch :checked="errorsOnly" :disabled="busy" @change="errorsOnly = Boolean(eventValue($event)); rowPage = 0" /></view>
      <view v-for="row in visibleRows" :key="row.row_number" class="record">
        <text class="label">源行 {{ row.row_number }} · {{ row.action }}</text><text v-for="issue in row.errors" :key="`${issue.field}-${issue.message}`" class="danger">{{ issue.field }}：{{ issue.message }}</text><text v-for="warning in row.warnings" :key="warning" class="hint">{{ warning }}</text>
        <view v-for="field in fields" :key="field.key"><text class="hint">{{ field.label }} · 原始 {{ row.raw[mapping[field.key] || ''] ?? '空' }} · 规范值 {{ row.normalized[field.key] ?? '未知' }}</text><text v-if="row.previous" class="hint">旧值 {{ row.previous[field.key] ?? '未知' }} → 新值 {{ row.normalized[field.key] ?? '未知' }}</text><input v-if="editable" :value="corrections[row.row_number]?.[field.key] ?? row.corrections[field.key] ?? row.normalized[field.key] ?? ''" :disabled="busy" :maxlength="2000" @input="correct(row.row_number, field.key, String(eventValue($event)))" /></view>
      </view>
      <view class="row"><button :disabled="busy || rowPage === 0" @tap="rowPage--">上一页</button><text>{{ rowPage + 1 }} / {{ Math.max(1, Math.ceil(rows.length / 10)) }}</text><button :disabled="busy || (rowPage + 1) * 10 >= rows.length" @tap="rowPage++">下一页</button></view>
      <template v-if="editable && batch.status === 'preview'">
        <text v-if="dirty" class="error">修改尚未预览，请重新校验。</text>
        <checkbox-group @change="reviewed = $event.detail.value"><label v-for="review in batch.required_reviews" :key="review.field" class="label"><checkbox :value="review.field" :checked="reviewed.includes(review.field)" :disabled="busy || dirty" />{{ review.label }}：{{ review.column }} → {{ review.meaning }}</label></checkbox-group>
        <view v-if="batch.updated_rows" class="row"><text>已核对差异，允许更新 {{ batch.updated_rows }} 行</text><switch :checked="allowUpdates" :disabled="busy || dirty" @change="allowUpdates = Boolean(eventValue($event))" /></view>
        <button class="primary" :disabled="busy || !canCommit" @tap="commit">确认导入并回读</button>
      </template>
      <button v-if="['draft', 'preview', 'committed'].includes(batch.status)" class="danger" :disabled="busy" @tap="withdraw('revoke')">撤销此批次</button><button v-if="batch.status !== 'cleared'" class="danger" :disabled="busy" @tap="withdraw('clear')">清除源数据</button>
    </view>
    <view class="card"><text class="section-title">最近 100 个批次</text><text v-if="!history.length" class="muted">暂无导入记录</text><view v-for="item in history" :key="item.id" class="record"><text>#{{ item.id }} · {{ item.filename }}</text><text class="hint">{{ item.data_identity }} · {{ item.total_rows }} 行 · {{ statusLabels[item.status] || item.status }}</text><button :disabled="busy" @tap="openBatch(item.id)">查看批次</button></view></view>
  </view>
</template>
<style scoped>.record { border-top: 1rpx solid #dce7e0; padding: 24rpx 0; margin-top: 16rpx; }</style>


