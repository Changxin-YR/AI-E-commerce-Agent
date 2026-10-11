<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Taro, { useDidShow, useLoad } from '@tarojs/taro'
import { account, api } from '../../services/session'
import {
  type OperationScope,
  type OperationContext,
  type OperationRun,
  type OperationTask,
  type TaskAction,
  taskLabels,
  sourceLabels,
  businessLabels,
} from '../../services/operation-types'
import {
  actionLabels,
  queryString,
  requestId,
  taskActions,
} from '../../services/task-policy'
import { openLink } from '../../services/navigation'
import SourceList from '../../components/SourceList.vue'
import TaskReview from '../../components/TaskReview.vue'
import AppliedRules from '../../components/AppliedRules.vue'

const rulesPending = ref(true),
  activeRule = ref(false)
function applyRules(rule: {
  version: number
  active: boolean
  values: {
    max_age_hours: number
    min_quantity: number
    max_margin_percent: string
  }
}) {
  scope.rule_revision_id = rule.version
  activeRule.value = rule.active
  scope.max_age_hours = rule.values.max_age_hours
  scope.min_quantity = rule.values.min_quantity
  scope.max_margin_percent = rule.values.max_margin_percent
}

const scope = reactive<OperationScope>({
  cost_mode: 'current_estimate',
  start_at: new Date(Date.now() - 7 * 86400000).toISOString(),
  end_at: new Date().toISOString(),
  timezone: 'Asia/Shanghai',
  currency: 'USD',
  data_identity: 'user_import',
  channel: 'generic',
  intent: 'low_margin',
  min_quantity: 1,
  max_margin_percent: '20',
  max_age_hours: 24,
})
const context = ref<OperationContext>(),
  run = ref<OperationRun>(),
  runs = ref<OperationRun[]>([]),
  tasks = ref<OperationTask[]>([]),
  task = ref<OperationTask>()
const busy = ref(false),
  error = ref(''),
  notice = ref(''),
  more = ref(false),
  offset = ref(0),
  previewReviewed = ref(false)
const note = ref(''),
  due = ref(''),
  description = ref(''),
  evidenceRef = ref(''),
  occurredAt = ref(''),
  confirmed = ref(false)
const evidenceDirty = computed(
  () =>
    !!(
      description.value ||
      evidenceRef.value ||
      occurredAt.value ||
      confirmed.value
    ),
)
const noteDirty = computed(
  () =>
    !!task.value &&
    (note.value !== task.value.note || due.value !== (task.value.due_at || '')),
)
const actions = computed(() => (task.value ? taskActions(task.value) : []))
const followActions: TaskAction[] = [
  'record_evidence',
  'wait_source',
  'recheck',
]
const request = ref<{
  request_id: string
  scope: OperationScope
  expected_preview_hash: string
}>()
const query = ref<Record<string, string>>({})
useLoad((params) => {
  query.value = params as Record<string, string>
})
watch(
  scope,
  () => {
    context.value = undefined
    previewReviewed.value = false
  },
  { deep: true },
)
watch(
  () => [scope.data_identity, scope.channel],
  () => {
    tasks.value = []
    runs.value = []
    more.value = false
    offset.value = 0
  },
)
watch([description, evidenceRef, occurredAt], () => {
  confirmed.value = false
})
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    context.value = undefined
    task.value = undefined
    run.value = undefined
    tasks.value = []
    runs.value = []
    request.value = undefined
    previewReviewed.value = false
    query.value = {}
    note.value = due.value = ''
    clearEvidence()
  },
)
function clearEvidence() {
  description.value = ''
  evidenceRef.value = ''
  occurredAt.value = ''
  confirmed.value = false
}
function adopt(value: OperationTask) {
  task.value = value
  note.value = value.note
  due.value = value.due_at || ''
  clearEvidence()
}
function checked(event: unknown) {
  return Boolean((event as { detail: { value: boolean } }).detail.value)
}
function inputNumber(event: unknown) {
  return Number((event as { detail: { value: string } }).detail.value)
}
async function filterHistory() {
  await perform(async () => {
    await Promise.all([loadTasks(), loadRuns()])
  })
}
async function perform(action: () => Promise<void>) {
  if (busy.value) return
  if (!account.session || !account.shopId) {
    error.value = '请返回工作台登录并选择店铺。'
    return
  }
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await action()
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : '操作未完成，请刷新后核对。'
  } finally {
    busy.value = false
  }
}
const base = () => `/shops/${account.shopId}/operations`
async function loadTasks(append = false) {
  const currentOffset = append ? offset.value + tasks.value.length : 0
  const page = await api.request<{ items: OperationTask[]; has_more: boolean }>(
    `${base()}/tasks?${queryString({ data_identity: scope.data_identity, channel: scope.channel, offset: currentOffset })}`,
  )
  tasks.value = append ? [...tasks.value, ...page.items] : page.items
  offset.value = 0
  more.value = page.has_more
}
async function loadRuns() {
  runs.value = await api.request<OperationRun[]>(
    `${base()}/runs?${queryString({ data_identity: scope.data_identity, channel: scope.channel })}`,
  )
}
async function refresh() {
  await perform(async () => {
    if (noteDirty.value || evidenceDirty.value) {
      const answer = await Taro.showModal({
        title: '刷新当前事项',
        content: '刷新将替换尚未保存的备注与证据草稿，是否继续？',
      })
      if (!answer.confirm) return
    }
    await Promise.all([loadTasks(), loadRuns()])
    if (task.value)
      adopt(
        await api.request<OperationTask>(`${base()}/tasks/${task.value.id}`),
      )
    if (run.value)
      run.value = await api.request<OperationRun>(
        `${base()}/runs/${run.value.id}`,
      )
  })
}
async function initialize() {
  await perform(async () => {
    const shop = account.shops.find((s) => s.id === account.shopId)
    if (query.value.shop && Number(query.value.shop) !== account.shopId)
      throw new Error('关联店铺与当前店铺不一致，请从首页重新打开。')
    scope.timezone = shop?.timezone || 'Asia/Shanghai'
    scope.currency = shop?.currency || 'USD'
    if (['synthetic', 'user_import'].includes(query.value.identity || ''))
      scope.data_identity = query.value
        .identity as OperationScope['data_identity']
    if (
      ['generic', 'shopify', 'amazon', 'other'].includes(
        query.value.channel || '',
      )
    )
      scope.channel = query.value.channel!
    await Promise.all([loadTasks(), loadRuns()])
    if (/^[1-9]\d*$/.test(query.value.task || ''))
      adopt(
        await api.request<OperationTask>(`${base()}/tasks/${query.value.task}`),
      )
    if (/^[1-9]\d*$/.test(query.value.run || ''))
      run.value = await api.request<OperationRun>(
        `${base()}/runs/${query.value.run}`,
      )
    if (task.value && !query.value.task)
      adopt(
        await api.request<OperationTask>(`${base()}/tasks/${task.value.id}`),
      )
    if (run.value && !query.value.run)
      run.value = await api.request<OperationRun>(
        `${base()}/runs/${run.value.id}`,
      )
    query.value = {}
  })
}
useDidShow(() => {
  if (noteDirty.value || evidenceDirty.value) {
    notice.value = '保留了当前编辑，请保存后刷新核对最新来源。'
    return
  }
  void initialize()
})
async function preview() {
  await perform(async () => {
    if (rulesPending.value) throw new Error('请先读取当前经营规则。')
    if (request.value) throw new Error('请先回查上次运行结果。')
    context.value = await api.request<OperationContext>(
      `${base()}/preview`,
      'POST',
      { ...scope },
    )
    previewReviewed.value = false
  })
}
async function execute(recover = false) {
  await perform(async () => {
    if (!recover) {
      if (!context.value || !previewReviewed.value || request.value) return
      request.value = {
        request_id: requestId(),
        scope: { ...scope },
        expected_preview_hash: context.value.preview_hash,
      }
    }
    if (!request.value) return
    const result = await api.request<OperationRun>(
      `${base()}/runs`,
      'POST',
      request.value,
    )
    run.value = await api.request<OperationRun>(`${base()}/runs/${result.id}`)
    request.value = undefined
    context.value = undefined
    previewReviewed.value = false
    await Promise.all([loadTasks(), loadRuns()])
    notice.value = '巡检已回读。生成的候选仍须逐项审批。'
  })
}
async function discardRequest() {
  await perform(async () => {
    const pending = request.value
    if (!pending) return
    await loadRuns()
    const result = await Taro.showModal({
      title: '结束同次运行核对',
      content:
        '请先检查下方最近运行记录。结束后才能创建新的巡检；此操作不会撤销服务端已有结果。确认已经核对？',
    })
    if (result.confirm && request.value === pending) request.value = undefined
  })
}
async function openTask(id: number) {
  await perform(async () => {
    if (noteDirty.value || evidenceDirty.value) {
      const answer = await Taro.showModal({
        title: '未保存的编辑',
        content: '打开其他事项会丢弃当前备注或证据草稿，是否继续？',
      })
      if (!answer.confirm) return
    }
    adopt(await api.request<OperationTask>(`${base()}/tasks/${id}`))
  })
}
async function openRun(id: number) {
  await perform(async () => {
    run.value = await api.request<OperationRun>(`${base()}/runs/${id}`)
  })
}
async function act(action: TaskAction) {
  await perform(async () => {
    const selected = task.value
    if (!selected || !actions.value.includes(action)) return
    const followUp = followActions.includes(action)
    if (
      (followUp && noteDirty.value) ||
      (action !== 'record_evidence' && evidenceDirty.value)
    )
      throw new Error('请先保存或清空当前编辑，再执行其他操作。')
    const evidence =
      action === 'record_evidence'
        ? {
            description: description.value,
            evidence_ref: evidenceRef.value,
            occurred_at: occurredAt.value,
            confirmed: confirmed.value,
          }
        : undefined
    if (
      action === 'record_evidence' &&
      (!confirmed.value ||
        !description.value.trim() ||
        !evidenceRef.value.trim() ||
        !occurredAt.value)
    )
      throw new Error('请填写操作说明、凭据、带时区的操作时间并确认自报。')
    if (
      action === 'defer' &&
      (!/(Z|[+-]\d{2}:\d{2})$/.test(due.value) ||
        !(Date.parse(due.value) > Date.now()))
    )
      throw new Error('延期须填写带时区的未来截止时间。')
    if (
      ['approve', 'reject', 'ignore', 'complete', 'reopen'].includes(action)
    ) {
      const answer = await Taro.showModal({
        title: actionLabels[action],
        content:
          action === 'complete'
            ? '完成核对只保存处理状态，异常解除须新有效来源复检支持。是否继续？'
            : `对事项 #${selected.id} 执行“${actionLabels[action]}”，仅更新内部记录。是否继续？`,
      })
      if (
        !answer.confirm ||
        task.value?.id !== selected.id ||
        task.value.version !== selected.version
      )
        return
    }
    await api.request(`${base()}/tasks/${selected.id}`, 'POST', {
      version: selected.version,
      action,
      note: followUp ? selected.note : note.value,
      due_at: followUp ? selected.due_at : due.value || null,
      ...(evidence ? { evidence } : {}),
    })
    adopt(await api.request<OperationTask>(`${base()}/tasks/${selected.id}`))
    await loadTasks()
    notice.value = '已回读事项状态与处理历史。'
  })
}
async function destination(path: string, query: Record<string, string>) {
  await perform(async () => {
    if (noteDirty.value || evidenceDirty.value)
      throw new Error('请先保存当前编辑。')
    await openLink(path, query)
  })
}
</script>

<template>
  <view class="screen">
    <view class="hero"
      ><text class="eyebrow"
        >OPERATIONS ·
        {{ account.shops.find((s) => s.id === account.shopId)?.name }}</text
      ><text class="title">核对事实，再处理事项。</text
      ><text class="muted"
        >本地规则巡检，模型未调用。区间为 [开始,
        结束)，金额保持服务端币种口径。</text
      ></view
    >
    <view v-if="error" class="error"
      >{{ error
      }}<text class="hint"
        >写入断线时请先回查记录；版本冲突请刷新并重新审阅。</text
      ></view
    ><text v-if="notice" class="hint">{{ notice }}</text
    ><text v-if="busy" class="hint">正在处理…</text
    ><button :disabled="busy" @tap="refresh">刷新记录与当前详情</button>
    <view class="card"
      ><text class="section-title">巡检范围</text>
      <text class="label">数据身份</text
      ><picker
        :range="['用户导入', '合成测试']"
        :disabled="busy || !!request"
        @change="
          scope.data_identity = Number($event.detail.value)
            ? 'synthetic'
            : 'user_import'
        "
        ><view class="select">{{
          scope.data_identity === 'synthetic' ? '合成测试' : '用户导入'
        }}</view></picker
      >
      <text class="label">渠道</text
      ><picker
        :range="['generic', 'shopify', 'amazon', 'other']"
        :disabled="busy || !!request"
        @change="
          scope.channel = ['generic', 'shopify', 'amazon', 'other'][
            Number($event.detail.value)
          ]!
        "
        ><view class="select">{{ scope.channel }}</view></picker
      >
      <text class="label">开始时间（含时区）</text
      ><input
        v-model="scope.start_at"
        :disabled="busy || !!request"
        placeholder="2026-10-01T00:00:00+08:00"
      />
      <text class="label">结束时间（不含，含时区）</text
      ><input
        v-model="scope.end_at"
        :disabled="busy || !!request"
        placeholder="2026-10-08T00:00:00+08:00"
      />
      <text class="label">业务时区</text
      ><input v-model="scope.timezone" :disabled="busy || !!request" /><text
        class="label"
        >币种</text
      ><input
        v-model="scope.currency"
        :disabled="busy || !!request"
        :maxlength="3"
      />
      <AppliedRules
        :scope="scope"
        :disabled="busy || !!request"
        @pending="rulesPending = $event"
        @loaded="applyRules"
      />
      <text class="label">最低数量</text
      ><input
        :value="scope.min_quantity"
        type="number"
        :disabled="busy || !!request || activeRule"
        @input="scope.min_quantity = inputNumber($event)"
      /><text class="label">毛利率上限 %</text
      ><input
        v-model="scope.max_margin_percent"
        :disabled="busy || !!request || activeRule"
      /><text class="label">来源最大时效（小时）</text
      ><input
        :value="scope.max_age_hours"
        type="number"
        :disabled="busy || !!request || activeRule"
        @input="scope.max_age_hours = inputNumber($event)"
      />
      <button :disabled="busy" @tap="filterHistory">
        按当前身份/渠道读取历史</button
      ><button
        class="primary"
        :disabled="busy || !!request || rulesPending"
        @tap="preview"
      >
        预览巡检
      </button>
    </view>
    <view v-if="context" class="card"
      ><text class="section-title"
        >巡检预览 · 来源修订 {{ context.preview.source_revision }}</text
      ><text class="hint"
        >有效至 {{ context.preview.valid_until || '未知' }}</text
      ><view v-for="branch in context.preview.branches" :key="branch.name"
        ><text class="label"
          >{{ branch.name }} · {{ branch.status }} · {{ branch.count }}</text
        ><text class="hint">{{ branch.reason }}</text></view
      ><view v-for="(finding, index) in context.preview.findings" :key="index"
        ><text class="label"
          >{{ finding.title }} · {{ finding.object_label }}</text
        ><text class="hint">{{ finding.basis }}</text
        ><text class="hint">{{ finding.advice }} · {{ finding.impact }}</text
        ><text v-for="(value, key) in finding.facts" :key="key" class="hint"
          >{{ key }}：{{ value }}</text
        ></view
      ><SourceList
        :sources="context.preview.sources"
        :shop-id="account.shopId"
      /><view class="row"
        ><text>已核对范围、发现和来源，允许保存候选</text
        ><switch
          :checked="previewReviewed"
          :disabled="busy"
          @change="previewReviewed = checked($event)" /></view
      ><button
        class="primary"
        :disabled="busy || !previewReviewed || !!request"
        @tap="execute()"
      >
        执行巡检并回读
      </button></view
    >
    <view v-if="request" class="card"
      ><text class="section-title">同次运行待核对</text
      ><text class="hint"
        >请求编号
        {{
          request.request_id
        }}。断线可能发生在保存后，先回查下方运行历史。</text
      ><button :disabled="busy" @tap="execute(true)">
        使用同一请求编号继续核对</button
      ><button :disabled="busy" @tap="discardRequest">
        已核对历史，结束此次核对
      </button></view
    >
    <view v-if="run" class="card"
      ><text class="section-title"
        >运行 #{{ run.id }} · {{ run.source_status }}</text
      ><text class="hint"
        >{{ run.created_at }} · {{ run.scope.data_identity }} ·
        {{ run.scope.channel }} · {{ run.scope.currency }}</text
      ><text class="hint"
        >{{ run.scope.start_at }} 至 {{ run.scope.end_at }} ·
        {{ run.scope.timezone }}</text
      ><text v-if="!run.snapshot" class="muted">来源正文已清除。</text
      ><template v-else
        ><text class="hint"
          >数据截至 {{ run.snapshot.data_as_of }} · 新建候选
          {{ run.snapshot.created_candidates }} · 复用候选
          {{ run.snapshot.reused_candidates }}</text
        ><view v-for="branch in run.snapshot.branches" :key="branch.name"
          ><text class="label"
            >{{ branch.name }} · {{ branch.status }} · {{ branch.count }}</text
          ><text class="hint">{{ branch.reason }}</text></view
        ><SourceList
          :sources="run.snapshot.sources"
          :shop-id="run.shop_id"
        /><button
          v-for="id in run.snapshot.task_ids"
          :key="id"
          :disabled="busy"
          @tap="openTask(id)"
        >
          审阅待办 #{{ id }}
        </button></template
      ></view
    >
    <view v-if="task" class="card"
      ><text class="section-title"
        >事项 #{{ task.id }} ·
        {{ taskLabels[task.status] || task.status }}</text
      ><text class="hint"
        >版本 {{ task.version }} ·
        {{ sourceLabels[task.source_status] || task.source_status }} ·
        {{ task.risk }} · 外部未提交</text
      ><text class="hint"
        >{{
          businessLabels[task.business_state || ''] || task.business_state
        }}
        · 截止 {{ task.due_at || '未设置' }}</text
      >
      <template v-if="task.snapshot"
        ><text class="label"
          >{{ task.snapshot.title }} · {{ task.snapshot.object_label }}</text
        ><text class="muted">{{ task.snapshot.basis }}</text
        ><text class="hint"
          >建议 {{ task.snapshot.advice }} · 影响
          {{ task.snapshot.impact }}</text
        ><text
          v-for="(value, key) in task.snapshot.facts"
          :key="key"
          class="hint"
          >{{ key }}：{{ value }}</text
        ><text class="hint"
          >原依据有效至 {{ task.snapshot.valid_until || '未知' }}</text
        ><SourceList
          :sources="task.snapshot.sources"
          :shop-id="task.shop_id"
        /><button
          v-for="item in task.destinations"
          :key="item.label"
          :disabled="
            busy ||
            noteDirty ||
            evidenceDirty ||
            task.source_status !== 'current'
          "
          @tap="destination(item.path, item.query)"
        >
          {{ item.label }}
        </button></template
      ><text v-else class="muted">来源正文已清除，不能新增处理证据。</text>
      <text class="label">处理备注</text
      ><textarea
        v-model="note"
        :disabled="busy || !actions.length"
        :maxlength="1000"
        placeholder="填写核对结果"
      /><text class="label">截止时间（含时区，可空）</text
      ><input
        v-model="due"
        :disabled="busy || !actions.length"
        placeholder="2026-10-12T12:00:00+08:00"
      /><button
        v-for="action in actions.filter((a) => !followActions.includes(a))"
        :key="action"
        :disabled="busy || evidenceDirty"
        :class="{ primary: action === 'approve' }"
        @tap="act(action)"
      >
        {{ actionLabels[action] }}
      </button>
      <TaskReview
        v-if="task.review"
        :review="task.review"
        :shop-id="task.shop_id"
        :current="task.review_current"
      />
      <template v-if="actions.includes('record_evidence')"
        ><text class="label">人工操作证据</text
        ><text class="hint"
          >完成核对仅保存处理状态；异常解除须新有效来源复检支持。</text
        ><textarea
          v-model="description"
          :disabled="busy"
          :maxlength="1000"
          placeholder="实际进行了什么操作"
        /><input
          v-model="evidenceRef"
          :disabled="busy"
          :maxlength="500"
          placeholder="凭据引用"
        /><input
          v-model="occurredAt"
          :disabled="busy"
          placeholder="操作时间：2026-10-11T10:00:00+08:00"
        /><view class="row"
          ><text>确认这是卖家自报，不代表渠道确认</text
          ><switch
            :checked="confirmed"
            :disabled="busy"
            @change="confirmed = checked($event)" /></view
        ><button :disabled="busy" @tap="clearEvidence">清空证据草稿</button
        ><button
          :disabled="busy || noteDirty || !confirmed"
          @tap="act('record_evidence')"
        >
          登记证据并回读</button
        ><button
          :disabled="busy || noteDirty || evidenceDirty"
          @tap="act('wait_source')"
        >
          等待来源更新</button
        ><button
          :disabled="busy || noteDirty || evidenceDirty"
          @tap="act('recheck')"
        >
          按原事项复检
        </button></template
      >
      <text class="label">处理历史</text
      ><view
        v-for="(event, index) in task.history"
        :key="`${event.version}-${index}`"
        ><text class="hint"
          >v{{ event.version }} · {{ event.action }} ·
          {{ taskLabels[event.from_status] || event.from_status }} →
          {{ taskLabels[event.to_status] || event.to_status }} ·
          {{ event.created_at }}</text
        ><text class="hint"
          >{{ event.note }} · 截止 {{ event.due_at || '无' }}</text
        ><TaskReview
          v-if="event.review"
          :review="event.review"
          :shop-id="task.shop_id"
      /></view>
    </view>
    <view class="card"
      ><text class="section-title">待办记录</text
      ><text v-if="!tasks.length" class="muted"
        >当前身份/渠道暂无待办，导入数据后运行巡检。</text
      ><view v-for="item in tasks" :key="item.id"
        ><text class="label">{{ item.snapshot?.title || '正文已清除' }}</text
        ><text class="hint"
          >#{{ item.id }} · {{ taskLabels[item.status] || item.status }} ·
          {{ sourceLabels[item.source_status] || item.source_status }}</text
        ><button :disabled="busy" @tap="openTask(item.id)">
          查看依据与处理
        </button></view
      ><button
        v-if="more"
        :disabled="busy"
        @tap="perform(() => loadTasks(true))"
      >
        更多待办
      </button></view
    >
    <view class="card"
      ><text class="section-title">巡检历史</text
      ><text v-if="!runs.length" class="muted">暂无运行记录。</text
      ><view v-for="item in runs" :key="item.id"
        ><text class="hint"
          >#{{ item.id }} · {{ item.source_status }} ·
          {{ item.created_at }}</text
        ><button :disabled="busy" @tap="openRun(item.id)">
          回读运行详情
        </button></view
      ></view
    >
  </view>
</template>
