<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { importsApi } from '@/api/imports'
import { errorMessage } from '@/api/client'
import type { ImportBatch, ImportGroup, ImportManifest } from '@/types/imports'
import FeedbackBanner from './FeedbackBanner.vue'
import BrowserImportSource from './BrowserImportSource.vue'
import { sameManifest, type PreparedImport } from '@/lib/csvSplit'

const props = defineProps<{
  shopId: number
  options: Record<string, string>
  refresh: number
  disabled: boolean
}>()
const emit = defineEmits<{ batch: [value: ImportBatch]; changed: []; busy: [value: boolean] }>()
const groups = ref<ImportGroup[]>([])
const selectedId = ref(0)
const olderCursor = ref<number | undefined>()
const manifest = ref<ImportManifest | null>(null)
const file = ref<File | null>(null)
const error = ref('')
const working = ref(false)
const confirmRevoke = ref(false)
const prepared = shallowRef<PreparedImport | null>(null)
const sourceKey = ref(0)
const activity = ref('')
const selected = computed(() => groups.value.find((group) => group.id === selectedId.value))
const readyFiles = computed(() =>
  prepared.value && selected.value && sameManifest(prepared.value.manifest, selected.value.manifest)
    ? prepared.value.files
    : [],
)
function acceptPrepared(value: PreparedImport | null): void {
  prepared.value = null
  if (!selected.value) manifest.value = null
  if (!value) return
  error.value = ''
  if (selected.value && !sameManifest(value.manifest, selected.value.manifest)) {
    error.value =
      '原文件与当前组的文件名、指纹或分片清单不一致。请选择建组时的原文件；来源有变化时须重新建组。'
    return
  }
  prepared.value = value
  manifest.value = value.manifest
}
function releaseSource(): void {
  prepared.value = null
  manifest.value = null
  sourceKey.value++
}
function newGroup(): void {
  selectedId.value = 0
  releaseSource()
}
function recordStart(index: number): number {
  return (
    1 +
    (selected.value?.manifest.parts.slice(0, index).reduce((total, part) => total + part.rows, 0) ??
      0)
  )
}
const status = (group: ImportGroup) =>
  group.status === 'revoked' ? '已整组撤销' : group.complete ? '分片全部完成' : '部分覆盖／数据不足'
let loadSequence = 0
async function reload(): Promise<void> {
  const sequence = ++loadSequence
  const shop = props.shopId
  const result = shop ? await importsApi.groups(shop) : []
  if (shop !== props.shopId || sequence !== loadSequence) return
  olderCursor.value = result.length === 20 ? result[result.length - 1]?.id : undefined
  if (selectedId.value && !result.some((item) => item.id === selectedId.value)) {
    const selectedGroup = await importsApi.group(selectedId.value)
    if (shop !== props.shopId || sequence !== loadSequence) return
    if (selectedGroup.shop_id === shop) result.push(selectedGroup)
  }
  groups.value = result
}
async function older(): Promise<void> {
  await perform(async () => {
    const result = await importsApi.groups(props.shopId, olderCursor.value)
    olderCursor.value = result.length === 20 ? result[result.length - 1]?.id : undefined
    groups.value = [
      ...groups.value,
      ...result.filter((item) => !groups.value.some((loaded) => loaded.id === item.id)),
    ]
  })
}
async function perform(action: () => Promise<void>): Promise<void> {
  working.value = true
  emit('busy', true)
  error.value = ''
  try {
    await action()
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    working.value = false
    emit('busy', false)
  }
}
async function readManifest(event: Event): Promise<void> {
  newGroup()
  manifest.value = null
  const value = (event.target as HTMLInputElement).files?.[0]
  if (!value) return
  await perform(async () => {
    if (value.size > 65536) throw new Error('清单最多 64 KiB，请使用拆分工具生成的 manifest.json')
    const parsed = JSON.parse(await value.text()) as ImportManifest
    if (
      parsed.format !== 'soloops-split-v1' ||
      !Array.isArray(parsed.parts) ||
      !parsed.parts.length
    )
      throw new Error('清单格式不正确')
    manifest.value = parsed
  })
}
async function create(): Promise<void> {
  await perform(async () => {
    if (!manifest.value) return
    const group = await importsApi.createGroup(props.shopId, {
      options: { ...props.options, filename: manifest.value.source_filename },
      manifest: manifest.value,
    })
    selectedId.value = group.id
    await reload()
    emit('changed')
  })
}
async function uploadPart(): Promise<void> {
  if (file.value) await uploadFile(file.value)
}
async function uploadFile(value: File): Promise<void> {
  await perform(async () => {
    const group = selected.value
    if (!group) return
    const part = group.manifest.parts.findIndex((item) => item.filename === value.name)
    if (part < 0) throw new Error('文件名不在当前组清单中，请选择原分片')
    if (value.size > 2097152) throw new Error('分片不能超过 2 MiB')
    activity.value = `正在上传第${part + 1}/${group.manifest.parts.length}片；等待服务端确认。`
    const options = Object.fromEntries(
      Object.entries(group.options)
        .filter(([, value]) => value != null)
        .map(([key, value]) => [key, String(value)]),
    )
    emit(
      'batch',
      await importsApi.upload(props.shopId, value, {
        ...options,
        filename: value.name,
        group_id: String(group.id),
        group_part: String(part + 1),
      }),
    )
    await reload()
    emit('changed')
  })
  activity.value = ''
  if (error.value)
    error.value += ' 请重试同一片；若服务端已收到，会回到原批次。已确认的其他片保留。'
}
async function uploadPrepared(index: number): Promise<void> {
  const value = readyFiles.value[index]
  if (value) await uploadFile(value)
}
async function openBatch(id: number): Promise<void> {
  await perform(async () => {
    emit('batch', await importsApi.get(id))
  })
}
async function revoke(): Promise<void> {
  activity.value = '正在整组撤销并核对剩余来源，记录较多时需要等待；完成前请勿重复操作。'
  await perform(async () => {
    if (!selected.value) return
    await importsApi.revokeGroup(selected.value.id, selected.value.version)
    confirmRevoke.value = false
    await reload()
    emit('changed')
  })
  activity.value = ''
}
watch(
  () => props.shopId,
  () => {
    releaseSource()
    selectedId.value = 0
    file.value = null
    confirmRevoke.value = false
  },
)
watch(
  [() => props.shopId, () => props.refresh],
  () => {
    void reload().catch((cause) => {
      error.value = errorMessage(cause)
    })
  },
  { immediate: true },
)
watch(selectedId, () => {
  confirmRevoke.value = false
  file.value = null
})
</script>

<template>
  <section class="section-block form-panel import-groups" aria-label="大报表分批导入">
    <h2>大报表分批导入</h2>
    <p>
      先在上方确认店铺、类型、渠道、数据身份与时区，再选择原文件。拆分完成后建组，逐片上传并在下方核对、确认。
    </p>
    <p class="data-note">
      导入组最多40000行。经营分析、今日运营和总览的单次范围最多10000行，部分账单／商品核对最多1000行。请按明确日期或业务范围导出与查询；单日仍超限时，当前不能生成完整该日汇总。
    </p>
    <BrowserImportSource
      :key="`${shopId}-${sourceKey}`"
      :disabled="disabled || working"
      @prepared="acceptPrepared"
      @busy="emit('busy', $event)"
    />
    <p v-if="prepared" role="status">
      本机文件已就绪：{{ prepared.manifest.total_rows }}个源记录，{{
        prepared.files.length
      }}片。未确认导入的记录尚未生效。
    </p>
    <button
      v-if="prepared"
      class="button secondary"
      :disabled="disabled || working"
      @click="releaseSource"
    >
      结束本次本机处理
    </button>
    <p>
      刷新或结束本机处理会释放本机文件，已保存的导入组仍保留。恢复时选择下方原组和同一原文件；不再导入时，请确认撤销整组。
    </p>
    <details>
      <summary>查看本地拆分步骤</summary>
      <p>在项目的 backend 目录运行以下命令，将路径换成自己的文件和一个尚不存在的输出目录：</p>
      <code>.venv\Scripts\python.exe -m scripts.split_import "报表.csv" "拆分结果"</code>
      <p>
        最多 40 MiB、40000 行、20 个分片。工具保留完整 CSV 记录，生成每片最多 2000 行、2 MiB
        的文件及 manifest.json。先移除无关客户资料。
      </p>
      <p>
        先在上方选择店铺、类型、渠道、数据身份与时区，再读取清单建组。逐片上传后，在下方核对映射、纠错并确认导入；刷新可继续原组。源记录按清单顺序连续分段，分片中的源行号为该片内部行号。
      </p>
    </details>
    <FeedbackBanner :message="error" />
    <p v-if="activity" role="status">{{ activity }}</p>
    <div class="form-field">
      <label for="group-manifest">拆分清单 manifest.json</label>
      <input
        id="group-manifest"
        type="file"
        accept=".json"
        :disabled="disabled || working"
        @change="readManifest"
      />
    </div>
    <p v-if="manifest">
      {{ manifest.source_filename }} · {{ manifest.total_rows }} 个源记录 ·
      {{ manifest.parts.length }} 片
    </p>
    <button
      v-if="!selectedId"
      class="button secondary"
      :disabled="!manifest || disabled || working"
      @click="create"
    >
      按当前来源建立导入组
    </button>
    <button v-else class="button secondary" :disabled="disabled || working" @click="newGroup">
      准备新的导入组
    </button>
    <div v-if="groups.length" class="form-field">
      <label for="import-group">继续导入组</label>
      <select id="import-group" v-model="selectedId" :disabled="disabled || working">
        <option :value="0">选择导入组</option>
        <option v-for="group in groups" :key="group.id" :value="group.id">
          #{{ group.id }} {{ group.manifest.source_filename }} · {{ status(group) }}
        </option>
      </select>
    </div>
    <button
      v-if="olderCursor"
      class="button secondary"
      :disabled="disabled || working"
      @click="older"
    >
      加载更早的导入组
    </button>
    <div v-if="selected">
      <p class="data-note" data-testid="group-coverage">
        {{ status(selected) }} · 已提交 {{ selected.committed_parts }}/{{
          selected.manifest.parts.length
        }}
        片；源记录 {{ selected.committed_rows }}/{{ selected.manifest.total_rows }}；去重后
        {{ selected.unique_rows }}；跨片重叠 {{ selected.overlap_rows }}。
      </p>
      <progress
        :value="selected.committed_rows"
        :max="selected.manifest.total_rows"
        aria-label="导入确认进度"
      />
      <details>
        <summary>查看来源与完整性</summary>
        <p>
          原文件：{{ selected.manifest.source_filename }}；SHA-256：{{
            selected.manifest.source_sha256
          }}
        </p>
        <p>
          下方范围是原文件的数据记录序号，不含表头。多行字段算一条记录；批次明细的源行号为分片内物理行号。分片统一编码，指纹与原文件分别核验。
        </p>
      </details>
      <p>
        {{ selected.options.kind }} · {{ selected.options.source_channel }} ·
        {{ selected.options.data_identity }} · {{ selected.options.timezone }}
      </p>
      <p v-if="!selected.complete && selected.status === 'active'">
        汇总与完整性判断暂停。请补齐所有分片，或撤销整组。
      </p>
      <ol class="part-list">
        <li v-for="(part, index) in selected.manifest.parts" :key="part.filename">
          {{ part.filename }} · {{ part.rows }} 行 · 原数据记录{{ recordStart(index) }}–{{
            recordStart(index) + part.rows - 1
          }}
          <small> · {{ part.bytes }}字节</small>
          <span v-if="!selected.batches.some((batch) => batch.group_part === index + 1)"
            >尚未上传</span
          >
          <button
            v-if="readyFiles[index] && selected.status === 'active'"
            class="button secondary small"
            :disabled="disabled || working"
            @click="uploadPrepared(index)"
          >
            上传／恢复第 {{ index + 1 }} 片
          </button>
          <template
            v-for="batch in selected.batches.filter((item) => item.group_part === index + 1)"
            :key="batch.id"
          >
            <span>{{
              batch.status === 'committed'
                ? '已提交'
                : batch.status === 'revoked'
                  ? '已撤销，可重传'
                  : batch.status === 'expired'
                    ? '已过期，请重传'
                    : batch.status === 'cleared'
                      ? '已清除，可重传'
                      : '待核对确认'
            }}</span>
            <button
              class="button secondary small"
              :disabled="disabled || working"
              @click="openBatch(batch.id)"
            >
              打开第 {{ index + 1 }} 片
            </button>
          </template>
        </li>
      </ol>
      <template v-if="selected.status === 'active'">
        <label for="group-part">选择原分片 CSV</label>
        <input
          :key="selectedId"
          id="group-part"
          type="file"
          accept=".csv"
          :disabled="disabled || working"
          @change="file = ($event.target as HTMLInputElement).files?.[0] ?? null"
        />
        <div class="button-group">
          <button
            class="button primary"
            :disabled="!file || disabled || working"
            @click="uploadPart"
          >
            上传此分片并核对
          </button>
          <button
            class="button secondary"
            :disabled="disabled || working"
            @click="confirmRevoke = true"
          >
            撤销整组
          </button>
        </div>
        <div v-if="confirmRevoke" class="data-note">
          <p>将撤销本组所有分片及其衍生来源，按现有批次规则恢复其他有效版本。组外独立记录保留。</p>
          <button class="button secondary" :disabled="disabled || working" @click="revoke">
            确认撤销整组
          </button>
          <button
            class="button secondary"
            :disabled="disabled || working"
            @click="confirmRevoke = false"
          >
            继续保留
          </button>
        </div>
      </template>
    </div>
  </section>
</template>

<style scoped>
.import-groups {
  overflow-wrap: anywhere;
}
.import-groups input,
.import-groups select {
  max-width: 100%;
  min-width: 0;
}
.import-groups progress {
  width: 100%;
}
.import-groups code {
  display: block;
  white-space: pre-wrap;
}
.part-list {
  padding-left: 1.4rem;
}
.part-list li {
  margin-block: 0.6rem;
}
.part-list span {
  margin-inline: 0.6rem;
}
</style>
