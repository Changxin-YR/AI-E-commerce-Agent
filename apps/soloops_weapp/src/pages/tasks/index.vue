<template>
  <PageShell
    title="待办事项"
    subtitle="审批、复检与完成核对都在本地留痕，外部状态保持未提交。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    @retry="load"
  >
    <text class="section-title">事项视图</text>
    <view class="row">
      <view
        v-for="entry in viewEntries"
        :key="entry.key"
        class="chip"
        :class="{ 'chip--active': view === entry.key }"
        @tap="chooseView(entry.key)"
      >
        <text>{{ entry.text }}{{ entry.key === '' ? '' : ` ${countText(page?.view_counts?.[entry.key])}` }}</text>
      </view>
    </view>

    <text class="section-title">筛选事项</text>
    <view v-for="field in filterFields" :key="field.key" class="field">
      <text class="field__label">{{ field.label }}</text>
      <picker
        mode="selector"
        :range="field.options"
        range-key="label"
        :value="field.index"
        @change="selectFilter(field.key, Number(pickerValue($event)))"
      >
        <view class="field__picker">{{ field.options[field.index]?.label }}</view>
      </picker>
    </view>

    <view v-if="page" class="row">
      <text
        v-for="(value, key) in page.counts"
        :key="key"
        class="chip"
      >
        <text>{{ labelOf(workBuckets, key) }} {{ value }}</text>
      </text>
    </view>

    <text class="section-title">待我处理的事项</text>
    <view v-if="items.length === 0 && !busy && error === ''" class="card">
      <text class="hint">
        当前没有符合条件的事项。导入报表并运行运营检查后，这里会显示待办和审批记录。
      </text>
    </view>
    <view v-for="item in items" :key="`${item.kind}:${item.id}`" class="card" @tap="open(item)">
      <text class="card__title">{{ item.label }}</text>
      <text class="hint">{{ item.detail }}</text>
      <FactLine label="处理分组" :value="labelOf(workBuckets, item.bucket)" />
      <FactLine label="来源状态" :value="labelOf(sourceLabels, item.source_status)" />
      <FactLine label="记录时间" :value="item.created_at" :zone="item.timezone || zone" />
    </view>
    <ActionButton v-if="page?.next_cursor" label="加载更多" @tap="load(true)" />

    <text class="section-title">运营待办（{{ tasks.length }}）</text>
    <text class="hint">
      完成核对仅保存本地处理状态。复检固定原对象、渠道、身份、规则和范围，读取新导入依据。
    </text>
    <view v-if="tasks.length === 0 && !busy" class="card">
      <text class="hint">此范围没有运营待办。运行今日运营检查后，异常候选会出现在这里。</text>
    </view>

    <view v-for="task in tasks" :key="task.id" class="card">
      <text class="card__title" @tap="select(task)">
        事项 #{{ task.id }} · {{ labelOf(taskLabels, task.status) }}
      </text>
      <FactLine label="原异常来源" :value="labelOf(sourceLabels, task.source_status)" />
      <FactLine label="业务进展" :value="labelOf(businessLabels, task.business_state)" />
      <FactLine label="负责人 / 版本" :value="`${task.owner_id} / ${task.version}`" />
      <FactLine label="数据身份 / 渠道" :value="`${labelOf(importIdentities, task.data_identity)} / ${labelOf(importChannels, task.channel)}`" />
      <FactLine label="截止时间" :value="task.due_at" :zone="zone" />
      <FactLine label="处理备注" :value="task.note" />

      <template v-if="task.snapshot">
        <text class="card__title">{{ task.snapshot.title }} · {{ task.snapshot.object_label }}</text>
        <FactLine label="依据" :value="task.snapshot.basis" />
        <FactLine label="影响" :value="task.snapshot.impact" />
        <FactLine label="建议" :value="task.snapshot.advice" />
        <FactLine label="证据有效至" :value="task.snapshot.valid_until" :zone="zone" />
      </template>
      <text v-else class="warn">来源已清除，证据和处理备注已擦除，仅保留状态历史。</text>

      <text v-if="task.source_status !== 'current'" class="warn">
        原异常依据已变化或过期，可更新来源后复检；经营规则改变时须重新运行巡检。
      </text>

      <template v-if="selectedId === task.id">
        <view class="divider" />
        <view class="field">
          <text class="field__label">处理备注</text>
          <textarea
            class="field__input"
            :value="note"
            :disabled="busy"
            placeholder="可选，保存到处理记录"
            @input="note = inputValue($event)"
          />
        </view>
        <view class="field">
          <text class="field__label">截止日期（延期时必须晚于当前时间）</text>
          <picker mode="date" :value="dueDay" @change="dueDay = pickerValue($event)">
            <view class="field__picker">{{ dueDay === '' ? '未设置' : dueDay }}</view>
          </picker>
        </view>
        <view class="field">
          <text class="field__label">截止时间</text>
          <picker mode="time" :value="dueClock" @change="dueClock = pickerValue($event)">
            <view class="field__picker">{{ dueClock }}</view>
          </picker>
        </view>

        <view class="row">
          <ActionButton
            v-for="action in allowedActions(task)"
            :key="action"
            :label="labelOf(taskActions, action)"
            :disabled="busy"
            @tap="run(task, action)"
          />
        </view>

        <template v-if="followUp(task)">
          <view class="divider" />
          <text class="hint">
            人工证据只代表卖家自报，不代表渠道确认；复检读取新导入依据后重新判定。
          </text>
          <view class="field">
            <text class="field__label">人工操作说明（卖家自报）</text>
            <textarea
              class="field__input"
              :value="description"
              :disabled="busy"
              @input="description = inputValue($event)"
            />
          </view>
          <view class="field">
            <text class="field__label">操作依据或凭据编号</text>
            <input
              class="field__input"
              :value="evidenceRef"
              :disabled="busy"
              @input="evidenceRef = inputValue($event)"
            />
          </view>
          <view class="field">
            <text class="field__label">操作发生日期</text>
            <picker mode="date" :value="occurredDay" @change="occurredDay = pickerValue($event)">
              <view class="field__picker">{{ occurredDay === '' ? '未设置' : occurredDay }}</view>
            </picker>
          </view>
          <view class="field">
            <text class="field__label">操作发生时间</text>
            <picker mode="time" :value="occurredClock" @change="occurredClock = pickerValue($event)">
              <view class="field__picker">{{ occurredClock }}</view>
            </picker>
          </view>
          <view class="row" @tap="confirmed = !confirmed">
            <text class="chip" :class="{ 'chip--active': confirmed }">
              {{ confirmed ? '已确认' : '未确认' }} · 我确认这是人工自报记录，外部结果仍需有效来源复检
            </text>
          </view>
          <view class="row">
            <ActionButton label="登记操作证据" variant="primary" :disabled="busy" @tap="run(task, 'record_evidence')" />
            <ActionButton label="等待来源更新" :disabled="busy" @tap="run(task, 'wait_source')" />
            <ActionButton label="按原事项复检" :disabled="busy" @tap="run(task, 'recheck')" />
          </view>
        </template>
        <text v-else class="hint">批准或重新打开事项后，可以登记人工证据并复检。</text>

        <template v-if="task.review?.evidence">
          <FactLine label="卖家自报操作" :value="task.review.evidence.description" />
          <FactLine label="依据或凭据编号" :value="task.review.evidence.evidence_ref" />
          <FactLine label="发生时间" :value="task.review.evidence.occurred_at" :zone="zone" />
          <FactLine
            label="登记人 / 登记时间"
            :value="`${task.review.evidence.recorded_by} / ${businessTimeText(task.review.evidence.recorded_at, zone)}`"
          />
        </template>
        <template v-if="task.review?.recheck">
          <FactLine label="存档复检结论" :value="labelOf(businessLabels, task.review.recheck.state)" />
          <FactLine label="复检原因" :value="task.review.recheck.reason" />
          <FactLine
            label="复检时间 / 来源版本"
            :value="`${businessTimeText(task.review.recheck.checked_at, zone)} / ${task.review.recheck.source_revision}`"
          />
          <FactLine label="有效至" :value="task.review.recheck.valid_until" :zone="zone" />
        </template>
      </template>
      <ActionButton
        v-else
        :label="`展开处理 #${task.id}`"
        @tap="select(task)"
      />
    </view>

    <ActionButton v-if="hasMore" label="继续查找待办" @tap="loadTasks(true)" />
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 待办事项：列表、筛选、审批 / 复检 / 完成核对。
 * 接口：
 *   GET  /api/workbench
 *   GET  /api/shops/{shop_id}/operations/tasks
 *   GET  /api/shops/{shop_id}/operations/tasks/{task_id}
 *   POST /api/shops/{shop_id}/operations/tasks/{task_id}
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import ActionButton from '../../ui/ActionButton.vue'
import { apiGet, apiPost, asObject } from '../../core/api'
import { businessTimeText, countText, zonedIsoFromParts } from '../../core/format'
import {
  businessLabels,
  importChannels,
  importIdentities,
  labelOf,
  sourceLabels,
  taskActions,
  taskLabels,
  withAll,
  workBuckets,
  workKinds,
} from '../../core/labels'
import { openWorkPath, takePendingIntent } from '../../core/links'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

interface WorkItem {
  kind: string
  id: number
  bucket: string
  source_status: string
  label: string
  detail: string
  created_at: string
  timezone: string
  path: string
  query: Record<string, string>
}

interface WorkPage {
  items: WorkItem[]
  counts: Record<string, number>
  view_counts: Record<string, number>
  next_cursor: string | null
  read_at: string
}

interface TaskSnapshot {
  title: string
  object_label: string
  basis: string
  impact: string
  advice: string
  valid_until: string | null
}

interface TaskReview {
  evidence: {
    description: string
    evidence_ref: string
    occurred_at: string
    recorded_at: string
    recorded_by: number
  } | null
  recheck: {
    state: string
    reason: string
    checked_at: string
    source_revision: number
    valid_until: string | null
  } | null
}

interface OperationTask {
  id: number
  status: string
  source_status: string
  business_state: string
  data_identity: string
  channel: string
  version: number
  owner_id: number
  note: string
  due_at: string | null
  snapshot: TaskSnapshot | null
  review: TaskReview | null
  review_current: boolean
}

interface TaskPage {
  items: OperationTask[]
  has_more: boolean
}

const viewEntries = [
  { key: '', text: '全部事项' },
  { key: 'attention', text: '待我处理' },
  { key: 'ai_completed', text: 'AI 已完成' },
  { key: 'update_data', text: '需要更新数据' },
]

const page = ref<WorkPage | null>(null)
const items = ref<WorkItem[]>([])
const tasks = ref<OperationTask[]>([])
const hasMore = ref(false)
const offset = ref(0)
const view = ref('')
const filter = ref({ identity: '', channel: '', kind: '', bucket: '' })
const busy = ref(false)
const error = ref('')
const ready = ref(false)
const selectedId = ref<number | null>(null)
const note = ref('')
const dueDay = ref('')
const dueClock = ref('09:00')
const description = ref('')
const evidenceRef = ref('')
const occurredDay = ref('')
const occurredClock = ref('09:00')
const confirmed = ref(false)

const zone = computed(() => shopTimezone())

const filterFields = computed(() => [
  {
    key: 'identity',
    label: '数据身份',
    options: optionsOf(withAll('全部身份', importIdentities)),
    index: indexOf(withAll('全部身份', importIdentities), filter.value.identity),
  },
  {
    key: 'channel',
    label: '来源渠道',
    options: optionsOf(withAll('全部渠道', importChannels)),
    index: indexOf(withAll('全部渠道', importChannels), filter.value.channel),
  },
  {
    key: 'kind',
    label: '业务类型',
    options: optionsOf(withAll('全部类型', workKinds)),
    index: indexOf(withAll('全部类型', workKinds), filter.value.kind),
  },
  {
    key: 'bucket',
    label: '处理分组',
    options: optionsOf(withAll('全部分组', workBuckets)),
    index: indexOf(withAll('全部分组', workBuckets), filter.value.bucket),
  },
])

function optionsOf(map: Record<string, string>): Array<{ key: string; label: string }> {
  return Object.entries(map).map(([key, label]) => ({ key, label }))
}

function indexOf(map: Record<string, string>, key: string): number {
  const index = Object.keys(map).indexOf(key)
  return index < 0 ? 0 : index
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  const intent = takePendingIntent('/pages/tasks/index')
  if (intent) {
    const wanted = Number(intent.task ?? '')
    if (Number.isFinite(wanted) && wanted > 0) selectedId.value = wanted
  }
  await load()
})

function chooseView(key: string): void {
  view.value = key
  void load()
}

function selectFilter(key: string, index: number): void {
  const maps: Record<string, Record<string, string>> = {
    identity: withAll('全部身份', importIdentities),
    channel: withAll('全部渠道', importChannels),
    kind: withAll('全部类型', workKinds),
    bucket: withAll('全部分组', workBuckets),
  }
  const map = maps[key]
  if (map === undefined) return
  filter.value = { ...filter.value, [key]: Object.keys(map)[index] ?? '' }
  void load()
}

async function load(more = false): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    const result = asObject<WorkPage>(
      await apiGet('/api/workbench', {
        shop_id: state.shopId,
        view: view.value,
        data_identity: filter.value.identity,
        channel: filter.value.channel,
        kind: filter.value.kind,
        bucket: filter.value.bucket,
        cursor: more ? page.value?.next_cursor ?? '' : '',
      }),
    )
    if (result === null) throw new Error('工作台响应无法读取，请刷新重试。')
    page.value = result
    const incoming = Array.isArray(result.items) ? result.items : []
    if (more) {
      const keys = new Set(items.value.map((item) => `${item.kind}:${item.id}`))
      items.value = [...items.value, ...incoming.filter((item) => !keys.has(`${item.kind}:${item.id}`))]
    } else {
      items.value = incoming
    }
    offset.value = 0
    await loadTasks(false)
  })
  error.value = message
}

async function loadTasks(more: boolean): Promise<void> {
  try {
    const result = asObject<TaskPage>(
      await apiGet(shopPath('/operations/tasks'), {
        data_identity: filter.value.identity || undefined,
        channel: filter.value.channel || undefined,
        offset: more ? offset.value + 50 : 0,
      }),
    )
    if (result === null) return
    offset.value = more ? offset.value + 50 : 0
    const incoming = Array.isArray(result.items) ? result.items : []
    tasks.value = more ? [...tasks.value, ...incoming] : incoming
    hasMore.value = result.has_more === true
  } catch (failure) {
    error.value = failure instanceof Error ? failure.message : `${failure}`
  }
}

async function open(item: WorkItem): Promise<void> {
  await openWorkPath(item.path, item.query ?? {})
  await load()
}

function select(task: OperationTask): void {
  selectedId.value = selectedId.value === task.id ? null : task.id
  note.value = task.note ?? ''
  dueDay.value = (task.due_at ?? '').slice(0, 10)
  description.value = ''
  evidenceRef.value = ''
  occurredDay.value = ''
  confirmed.value = false
}

function followUp(task: OperationTask): boolean {
  return task.snapshot !== null && ['open', 'deferred', 'completed'].includes(task.status)
}

/** 与 Flutter 端一致的可用动作集合。 */
function allowedActions(task: OperationTask): string[] {
  const actions: string[] = []
  if (task.status === 'pending_approval') actions.push('approve', 'reject')
  if (task.status === 'open' || task.status === 'deferred') actions.push('complete', 'defer')
  if (['pending_approval', 'open', 'deferred'].includes(task.status)) actions.push('ignore')
  if (['completed', 'ignored', 'rejected', 'deferred'].includes(task.status)) actions.push('reopen')
  actions.push('edit')
  return actions
}

function dueIso(): string | null {
  if (dueDay.value === '') return null
  return zonedIsoFromParts(dueDay.value, dueClock.value, zone.value)
}

function occurredIso(): string | null {
  if (occurredDay.value === '') return null
  return zonedIsoFromParts(occurredDay.value, occurredClock.value, zone.value)
}

async function run(task: OperationTask, action: string): Promise<void> {
  if (busy.value) return
  if (['approve', 'reject', 'ignore', 'complete', 'reopen'].includes(action)) {
    const result = await Taro.showModal({
      title: labelOf(taskActions, action),
      content:
        action === 'complete'
          ? '将保存“已完成核对”状态。业务结果由新有效来源复检确定。'
          : '将更新此事项的本地处理状态，并保留操作历史。',
      confirmText: '确认',
      cancelText: '返回',
    })
    if (!result.confirm) return
  }
  busy.value = true
  const message = await perform(async () => {
    const follow = ['record_evidence', 'wait_source', 'recheck'].includes(action)
    let deadline: string | null = task.due_at
    if (!follow) {
      deadline = dueIso()
      if (dueDay.value !== '' && deadline === null) {
        throw new Error('截止时间无效或在该时区不存在，请另选时间。')
      }
    }
    if (action === 'defer') {
      if (deadline === null || Date.parse(deadline) <= Date.now()) {
        throw new Error('延期须设置未来截止时间。')
      }
    }
    const body: Record<string, unknown> = {
      version: task.version,
      action,
      note: follow ? task.note : note.value,
      due_at: deadline,
    }
    if (action === 'record_evidence') {
      const occurred = occurredIso()
      if (!confirmed.value || description.value.trim() === '' || evidenceRef.value.trim() === '') {
        throw new Error('请补齐证据说明、凭据编号，并确认卖家自报。')
      }
      if (occurred === null) {
        throw new Error('请选择有效的操作发生日期与时间。')
      }
      body.evidence = {
        description: description.value.trim(),
        evidence_ref: evidenceRef.value.trim(),
        occurred_at: occurred,
        confirmed: true,
      }
    }
    const result = asObject<OperationTask>(
      await apiPost(shopPath(`/operations/tasks/${task.id}`), body),
    )
    // 写入后回读同一记录，未知结果不推断成功。
    const current = result ?? asObject<OperationTask>(await apiGet(shopPath(`/operations/tasks/${task.id}`)))
    if (current !== null) {
      tasks.value = tasks.value.map((row) => (row.id === current.id ? current : row))
      select(current)
      selectedId.value = current.id
    }
  })
  if (message !== '') {
    error.value = message
  } else {
    error.value = ''
    await Taro.showToast({ title: '事项已更新并回读。', icon: 'none' })
  }
  busy.value = false
}
</script>
