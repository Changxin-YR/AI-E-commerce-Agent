<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Corrections, FieldDefinition, ImportRow } from '@/types/imports'

const props = defineProps<{
  rows: ImportRow[]
  fields: FieldDefinition[]
  editable: boolean
  corrections: Corrections
  disabled: boolean
}>()
const emit = defineEmits<{ correct: [row: number, field: string, value: string] }>()
const page = ref(1)
const errorsOnly = ref(false)
const filtered = computed(() => props.rows.filter((row) => !errorsOnly.value || row.errors.length))
const pages = computed(() => Math.max(1, Math.ceil(filtered.value.length / 20)))
const visible = computed(() => filtered.value.slice((page.value - 1) * 20, page.value * 20))
const actions = { new: '新增', update: '更新', unchanged: '相同记录', error: '需修正' }
watch([() => props.rows, errorsOnly], () => {
  page.value = 1
})
</script>
<template>
  <div class="section-title">
    <h3>源行与转换结果</h3>
    <label class="check-label"><input v-model="errorsOnly" type="checkbox" />只看错误行</label>
  </div>
  <p class="muted" v-if="!filtered.length">当前筛选没有记录。</p>
  <details
    v-for="row in visible"
    :key="row.row_number"
    class="source-row"
    :open="row.errors.length > 0 || undefined"
  >
    <summary>
      源行 {{ row.row_number }} ·
      {{
        row.normalized.message_id ||
        row.raw.message_id ||
        row.normalized.sku ||
        row.raw.sku ||
        '标识待补充'
      }}
      <span class="status-tag" :class="{ 'row-error': row.errors.length }">{{
        actions[row.action]
      }}</span>
    </summary>
    <ul v-if="row.errors.length" class="issue-list">
      <li v-for="(issue, i) in row.errors" :key="i">{{ issue.field }}：{{ issue.message }}</li>
    </ul>
    <p v-for="warning in row.warnings" :key="warning" class="row-warning">{{ warning }}</p>
    <div class="table-scroll" tabindex="0" aria-label="源行字段明细">
      <table>
        <thead>
          <tr>
            <th>字段</th>
            <th>源值</th>
            <th v-if="editable">修正值</th>
            <th>转换后</th>
            <th v-if="row.previous">当前旧值</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="field in fields" :key="field.key">
            <th scope="row">{{ field.label }}</th>
            <td>{{ row.raw[field.key] ?? '未映射' }}</td>
            <td v-if="editable">
              <input
                :aria-label="`源行 ${row.row_number} ${field.label} 修正值`"
                :disabled="disabled"
                :value="corrections[row.row_number]?.[field.key] ?? row.raw[field.key] ?? ''"
                maxlength="2000"
                @input="
                  emit(
                    'correct',
                    row.row_number,
                    field.key,
                    ($event.target as HTMLInputElement).value,
                  )
                "
              />
            </td>
            <td>{{ row.normalized[field.key] ?? '未知' }}</td>
            <td v-if="row.previous">{{ row.previous[field.key] ?? '未知' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </details>
  <div v-if="filtered.length" class="pagination">
    <button class="button secondary small" :disabled="page === 1" @click="page--">上一页</button>
    <span>{{ page }} / {{ pages }} · {{ filtered.length }} 行</span
    ><button class="button secondary small" :disabled="page >= pages" @click="page++">
      下一页
    </button>
  </div>
</template>
