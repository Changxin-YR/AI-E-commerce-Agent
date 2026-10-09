<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { feeRulesApi } from '@/api/feeRules'
import { errorMessage } from '@/api/client'
import { expenseCategories } from '@/types/expenses'
import {
  mappingStatuses,
  type FeeRuleContent,
  type FeeRuleDraft,
  type FeeRulePreview,
  type FeeRuleSaved,
  type FeeRuleWrite,
} from '@/types/feeRules'
import { supportTime } from '@/types/support'
import FeedbackBanner from './FeedbackBanner.vue'
import SupportSource from './SupportSource.vue'

const props = defineProps<{ shopId: number; scope: FeeRuleDraft['scope']; disabled: boolean }>()
const emit = defineEmits<{ changed: []; invalidated: []; busy: [value: boolean] }>()
const rows = ref<FeeRuleSaved[]>([])
const cursor = ref<number | null>(null)
const saved = ref<FeeRuleSaved | null>(null)
const editing = ref<{ id: number | null; version: number } | null>(null)
const content = reactive<FeeRuleContent>({ fee_name: '', category: 'platform', reason: '' })
const preview = ref<FeeRulePreview | null>(null)
const confirmed = ref(false)
const controlConfirmed = ref(false)
const controlAction = ref<'withdraw' | 'clear'>('withdraw')
const error = ref('')
const busy = ref(false)
const limit = ref(20)
const pending = ref<FeeRuleWrite | null>(null)
const pendingControl = ref<{
  id: number
  action: 'withdraw' | 'clear'
  body: { request_id: string; version: number; confirm: true }
} | null>(null)
let alive = true
let epoch = 0
function resetPreview(): void {
  preview.value = null
  confirmed.value = false
  limit.value = 20
}
watch(
  content,
  () => {
    epoch++
    resetPreview()
  },
  { deep: true, flush: 'sync' },
)
watch(controlAction, () => {
  controlConfirmed.value = false
})
function invalidate(): void {
  epoch++
  rows.value = []
  saved.value = null
  editing.value = null
  cursor.value = null
  resetPreview()
  controlConfirmed.value = false
  emit('invalidated')
}
async function action(work: (valid: () => boolean) => Promise<void>): Promise<void> {
  if (busy.value || props.disabled) return
  const current = epoch
  busy.value = true
  emit('busy', true)
  error.value = ''
  try {
    await work(() => alive && current === epoch)
  } catch (cause) {
    if (alive && current === epoch) error.value = errorMessage(cause)
  } finally {
    if (alive) {
      busy.value = false
      emit('busy', false)
    }
  }
}
async function refresh(): Promise<void> {
  if (busy.value || props.disabled) return
  invalidate()
  await action(async (valid) => {
    const response = await feeRulesApi.list(props.shopId, props.scope)
    if (!valid()) return
    rows.value = response.items
    cursor.value = response.next_cursor
  })
}
async function more(): Promise<void> {
  await action(async (valid) => {
    const response = await feeRulesApi.list(props.shopId, props.scope, cursor.value ?? undefined)
    if (valid()) {
      rows.value.push(...response.items)
      cursor.value = response.next_cursor
    }
  })
}
async function show(id: number): Promise<void> {
  await action(async (valid) => {
    saved.value = null
    rows.value = []
    cursor.value = null
    editing.value = null
    resetPreview()
    controlConfirmed.value = false
    const response = await feeRulesApi.get(props.shopId, id)
    if (valid()) {
      saved.value = response
      controlAction.value = response.status === 'withdrawn' ? 'clear' : 'withdraw'
    }
  })
}
function begin(rule: FeeRuleSaved | null): void {
  editing.value = { id: rule?.id ?? null, version: rule?.version ?? 0 }
  Object.assign(content, rule?.content ?? { fee_name: '', category: 'platform', reason: '' })
  pending.value = null
  resetPreview()
}
async function inspect(): Promise<void> {
  await action(async (valid) => {
    resetPreview()
    const response = await feeRulesApi.preview(props.shopId, {
      scope: { ...props.scope },
      rule_id: editing.value?.id ?? null,
      version: editing.value?.version ?? 0,
      content: { ...content },
    })
    if (valid()) preview.value = response
  })
}
async function save(retry = false): Promise<void> {
  if (!retry) {
    if (!preview.value || !confirmed.value) return
    pending.value = {
      scope: { ...props.scope },
      rule_id: editing.value?.id ?? null,
      version: editing.value?.version ?? 0,
      content: { ...content },
      request_id: crypto.randomUUID(),
      confirm: true,
      preview_hash: preview.value.preview_hash,
    }
  }
  const request = pending.value
  if (!request) return
  await action(async (valid) => {
    rows.value = []
    saved.value = null
    editing.value = null
    resetPreview()
    emit('invalidated')
    const response = await feeRulesApi.write(props.shopId, request)
    if (valid()) {
      saved.value = response
      pending.value = null
      emit('changed')
    }
  })
}
async function control(retry = false): Promise<void> {
  if (!retry) {
    if (!saved.value || !controlConfirmed.value) return
    pendingControl.value = {
      id: saved.value.id,
      action: controlAction.value,
      body: { request_id: crypto.randomUUID(), version: saved.value.version, confirm: true },
    }
  }
  const request = pendingControl.value
  if (!request) return
  await action(async (valid) => {
    rows.value = []
    saved.value = null
    editing.value = null
    resetPreview()
    controlConfirmed.value = false
    emit('invalidated')
    const response = await feeRulesApi.control(
      props.shopId,
      request.id,
      request.action,
      request.body,
    )
    if (valid()) {
      saved.value = response
      pendingControl.value = null
      controlAction.value = response.status === 'withdrawn' ? 'clear' : 'withdraw'
      emit('changed')
    }
  })
}
const statusLabels = { active: '有效', withdrawn: '已撤销', cleared: '已清除' }
const actions: Record<string, string> = {
  create: '创建',
  update: '修订',
  withdraw: '撤销',
  clear: '清除',
}
onMounted(() => window.addEventListener('focus', invalidate))
onUnmounted(() => {
  alive = false
  epoch++
  emit('busy', false)
  window.removeEventListener('focus', invalidate)
})
</script>
<template>
  <section class="form-panel section-block fee-rules" aria-label="收费映射规则">
    <h2>收费名称，统一分类。</h2>
    <p>
      人工规则按当前店铺、身份和渠道生效。收费名去首尾空白后区分大小写完整匹配，最多 200
      条有效规则。
    </p>
    <p>
      规则适用于此范围全部日期与币种，包括后来导入的账单；上方时间窗口仅限制差异预览。保存规则后仍需核对业务依据。
    </p>
    <FeedbackBanner :message="error" />
    <p v-if="busy" role="status">正在处理映射规则…</p>
    <fieldset :disabled="busy || disabled">
      <legend class="sr-only">规则管理</legend>
      <div class="form-actions">
        <button class="button secondary" @click="refresh">读取规则列表</button>
        <button class="button secondary" @click="begin(null)">新建映射规则</button>
        <button v-if="pending" class="button secondary" @click="save(true)">
          回查原规则保存请求
        </button>
        <button v-if="pendingControl" class="button secondary" @click="control(true)">
          回查原规则处理请求
        </button>
      </div>
      <ul v-if="rows.length">
        <li v-for="row in rows" :key="row.id">
          <button class="button secondary" @click="show(row.id)">
            规则 #{{ row.id }} · {{ row.content?.fee_name ?? '正文已清除' }} ·
            {{ statusLabels[row.status] }} · v{{ row.version }}
          </button>
        </li>
      </ul>
      <button v-if="cursor" class="button secondary" @click="more">更多规则</button>
      <article v-if="saved" class="section-block" aria-label="规则详情">
        <h3>规则 #{{ saved.id }} · {{ statusLabels[saved.status] }} · 版本 {{ saved.version }}</h3>
        <p v-if="saved.content">
          {{ saved.content.fee_name }} → {{ expenseCategories[saved.content.category] }} ·
          {{ saved.content.reason }}
        </p>
        <p v-else>收费名、类别及全部历史正文已清除。</p>
        <button v-if="saved.status === 'active'" class="button secondary" @click="begin(saved)">
          修订此规则
        </button>
        <details class="section-block">
          <summary>规则调整历史（{{ saved.history.length }}）</summary>
          <p v-for="item in saved.history" :key="item.version">
            v{{ item.version }} · {{ actions[item.action] }} ·
            {{ supportTime(item.created_at, scope.timezone) }}<br />{{
              item.content
                ? `${item.content.fee_name} → ${expenseCategories[item.content.category]} · ${item.content.reason}`
                : '无正文'
            }}
          </p>
        </details>
        <div v-if="saved.status !== 'cleared'" class="section-block">
          <label for="fee-rule-control">规则处理</label>
          <select id="fee-rule-control" v-model="controlAction">
            <option v-if="saved.status === 'active'" value="withdraw">撤销规则</option>
            <option value="clear">清除规则及全部历史正文</option>
          </select>
          <p>撤销后该规则停止参与所有窗口分类；清除同时擦除规则历史正文。原账单与人工费用保留。</p>
          <label class="check-label"
            ><input
              v-model="controlConfirmed"
              type="checkbox"
            />我确认处理此版本规则及上述影响</label
          >
          <button class="button secondary" :disabled="!controlConfirmed" @click="control()">
            确认处理规则
          </button>
        </div>
      </article>
      <form v-if="editing" class="section-block" @submit.prevent="inspect">
        <h3>{{ editing.id ? `修订规则 #${editing.id}` : '新建规则' }}</h3>
        <div class="form-grid">
          <div class="form-field">
            <label for="fee-rule-name">完整原始收费名</label
            ><input id="fee-rule-name" v-model="content.fee_name" maxlength="120" required />
          </div>
          <div class="form-field">
            <label for="fee-rule-category">统一费用类别</label
            ><select id="fee-rule-category" v-model="content.category">
              <option v-for="(label, key) in expenseCategories" :key="key" :value="key">
                {{ label }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label for="fee-rule-reason">本次规则依据与理由</label
            ><textarea
              id="fee-rule-reason"
              v-model="content.reason"
              maxlength="500"
              required
              rows="3"
            />
          </div>
        </div>
        <button class="button secondary">预览分类变化</button>
      </form>
      <section v-if="preview" class="section-block" aria-label="规则差异预览">
        <h3>分类变化预览</h3>
        <p>
          原规则：{{
            preview.previous
              ? `${preview.previous.fee_name} → ${expenseCategories[preview.previous.category]}`
              : '无'
          }}<br />拟保存：{{ preview.proposed.fee_name }} →
          {{ expenseCategories[preview.proposed.category] }}
        </p>
        <p>{{ preview.proposed.reason }}</p>
        <p>
          本次读取 {{ preview.statement_count }} 行账单，分类结果变化
          {{ preview.changes.length }} 行 · 来源版本
          {{ preview.source_revision }}。窗口外和后续账单也按当前规则读取。
        </p>
        <p v-if="!preview.changes.length">
          本窗口没有分类结果变化；规则仍会应用于同范围其它日期的匹配收费项。
        </p>
        <div
          v-for="item in preview.changes.slice(0, limit)"
          :key="item.statement_id"
          class="section-block"
        >
          <p>
            账单行 #{{ item.statement_id }} · {{ item.fee_name }}<br />{{
              mappingStatuses[item.before.status]
            }}
            {{ item.before.category ? expenseCategories[item.before.category] : '' }} →
            {{ mappingStatuses[item.after.status] }}
            {{ item.after.category ? expenseCategories[item.after.category] : '' }}
          </p>
          <SupportSource :shop-id="shopId" :source="item.source" />
        </div>
        <button v-if="limit < preview.changes.length" class="button secondary" @click="limit += 20">
          更多分类变化
        </button>
        <label class="check-label"
          ><input
            v-model="confirmed"
            type="checkbox"
          />我已核对差异，确认此规则适用于当前店铺、身份、渠道的全部日期与币种</label
        >
        <button class="button primary" :disabled="!confirmed" @click="save()">
          保存规则并回读
        </button>
      </section>
    </fieldset>
  </section>
</template>
<style scoped>
.fee-rules {
  overflow-wrap: anywhere;
}
fieldset {
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 12px;
  font: inherit;
  resize: vertical;
}
li {
  margin-top: 8px;
}
.check-label {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin: 18px 0;
}
.check-label input {
  flex: 0 0 auto;
  width: auto;
  margin-top: 4px;
}
</style>
