// route: /schedules
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Taro, { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import { queryString, requestId } from '../../services/task-policy'
import { supportTime } from '../../services/support-types'
import { openLink } from '../../services/navigation'
import type { SourceChannel } from '../../services/import-types'
import type {
  DataIdentity,
  RuleRevision,
} from '../../services/business-rule-policy'
import {
  channels,
  checkedScheduleConfig,
  createSchedulePayload,
  currencyCodes,
  defaultScheduleForm,
  frequencyLabels,
  identities,
  manualCheckPayload,
  manualCheckReady,
  notificationReady,
  occurrenceReasons,
  scheduleActionPayload,
  scheduleCycleText,
  scheduleForm,
  scheduleGates,
  scheduleLabels,
  scheduleSummary,
  unknownResult,
  type Occurrence,
  type ScheduleAction,
  type ScheduleForm,
  type ScheduleRow,
  type ScheduleStatus,
} from '../../services/schedule-policy'

const form = reactive<ScheduleForm>(defaultScheduleForm('Asia/Shanghai', 'USD'))
const plans = ref<ScheduleRow[]>([]),
  history = ref<Occurrence[]>([]),
  status = ref<ScheduleStatus>(),
  editing = ref<ScheduleRow>()
const busy = ref(false),
  error = ref(''),
  notice = ref(''),
  unknown = ref(false),
  confirmed = ref(false),
  unreadOnly = ref(false),
  activeRule = ref(false),
  ruleVersion = ref(0),
  pendingCreate = ref<Record<string, unknown>>(),
  pendingCheck = ref<{ plan: number; body: Record<string, unknown> }>(),
  showEditor = ref(false)
let alive = true,
  epoch = 0,
  createId = requestId(),
  checkId = requestId(),
  linked: Record<string, string> = {}
const request = scopedRequest(api, () => (alive ? epoch : null))
const base = () => `/shops/${account.shopId}`
const timezone = computed(
  () =>
    account.shops.find((shop) => shop.id === account.shopId)?.timezone ||
    'Asia/Shanghai',
)
const currency = computed(
  () =>
    account.shops.find((shop) => shop.id === account.shopId)?.currency || 'USD',
)
const tasks = ['运营巡检 · 候选逐次审批', '经营报表 · 按期保存摘要']
const frequencies = ['daily', 'weekly', 'monthly']
const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const currencyList = currencyCodes
const reportCurrencyList = currencyCodes
const dirtyForm = computed(() => {
  if (!showEditor.value) return false
  const initial = editing.value
    ? scheduleForm(editing.value.config)
    : defaultScheduleForm(timezone.value, currency.value)
  return JSON.stringify(form) !== JSON.stringify(initial)
})
const protect = computed(
  () =>
    unknown.value ||
    !!pendingCreate.value ||
    !!pendingCheck.value ||
    dirtyForm.value ||
    confirmed.value,
)

useLoad((value) => {
  linked = value as Record<string, string>
})
useUnload(() => {
  alive = false
  epoch++
})
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    epoch++
    plans.value = []
    history.value = []
    status.value = undefined
    editing.value = undefined
    showEditor.value = false
    unreadOnly.value = false
    confirmed.value = false
    unknown.value = false
    pendingCreate.value = undefined
    pendingCheck.value = undefined
    createId = requestId()
    checkId = requestId()
    Object.assign(form, defaultScheduleForm(timezone.value, currency.value))
    error.value = notice.value = ''
  },
  { flush: 'sync' },
)
watch(protect, (value) => {
  if (!alive) return
  if (value)
    Taro.enableAlertBeforeUnload({
      message: '有未保存的计划配置或待核对运行，离开前请确认。',
    })
  else Taro.disableAlertBeforeUnload()
})
watch(
  () => [form.task, form.channel, form.data_identity],
  () => {
    confirmed.value = false
    void loadRule()
  },
)

async function perform(work: () => Promise<void>) {
  if (busy.value || !alive) return
  const token = epoch
  busy.value = true
  error.value = notice.value = ''
  try {
    await work()
  } catch (cause) {
    if (alive && token === epoch)
      error.value =
        cause instanceof Error ? cause.message : '操作失败，请刷新核对。'
  } finally {
    busy.value = false
  }
}
async function loadRule() {
  if (!account.shopId || form.task === 'report') {
    activeRule.value = false
    ruleVersion.value = 0
    return
  }
  const value = await request<RuleRevision>(
    `${base()}/business-rules?${queryString({ channel: form.channel, data_identity: form.data_identity })}`,
  )
  ruleVersion.value = value.version
  activeRule.value = value.active
  if (value.active) {
    form.max_age_hours = String(value.values.max_age_hours)
    form.min_quantity = String(value.values.min_quantity)
    form.max_margin_percent = value.values.max_margin_percent
  }
}
async function load(more = false) {
  if (!account.session || !account.shopId)
    throw new Error('请先登录并选择店铺。')
  const [rows, notices, current] = await Promise.all([
    request<ScheduleRow[]>(`${base()}/schedules`),
    request<Occurrence[]>(
      `${base()}/schedules/history?${queryString({
        unread: unreadOnly.value ? 'true' : 'false',
        before: more ? history.value[history.value.length - 1]?.id : null,
      })}`,
    ),
    request<ScheduleStatus>(`${base()}/schedules/status`),
  ])
  plans.value = rows
  history.value = more ? [...history.value, ...notices] : notices
  status.value = current
  unknown.value = false
}
function startCreate() {
  editing.value = undefined
  Object.assign(form, defaultScheduleForm(timezone.value, currency.value))
  createId = requestId()
  confirmed.value = false
  showEditor.value = true
  void loadRule()
}
function startEdit(row: ScheduleRow) {
  editing.value = row
  Object.assign(form, scheduleForm(row.config))
  confirmed.value = false
  activeRule.value = false
  ruleVersion.value = row.config.rule_revision_id
  showEditor.value = true
  if (row.config.task === 'operations') void loadRule()
}
async function save() {
  await perform(async () => {
    if (unknown.value)
      throw new Error('上次写入结果未知，请先刷新计划与通知核对。')
    if (!confirmed.value) throw new Error('请先确认计划周期、范围和通知方式。')
    const config = checkedScheduleConfig(form)
    if (editing.value) {
      const body = scheduleActionPayload(editing.value, 'edit', config, true)
      let value: ScheduleRow
      try {
        value = await request<ScheduleRow>(
          `${base()}/schedules/${editing.value.id}`,
          'POST',
          body,
        )
      } catch (cause) {
        if (unknownResult(cause)) unknown.value = true
        throw cause
      }
      const readback = await request<ScheduleRow[]>(`${base()}/schedules`)
      const found = readback.find((row) => row.id === value.id)
      if (!found) throw new Error('计划已更新但未能在列表中回读，请刷新核对。')
      notice.value = `计划 #${found.id} 已修改，当前版本 ${found.version}。`
    } else {
      pendingCreate.value = createSchedulePayload(createId, config, true)
      const body = pendingCreate.value
      if (!body) return
      let value: ScheduleRow
      try {
        value = await request<ScheduleRow>(`${base()}/schedules`, 'POST', body)
      } catch (cause) {
        if (unknownResult(cause)) unknown.value = true
        throw cause
      }
      const readback = await request<ScheduleRow[]>(`${base()}/schedules`)
      const found = readback.find((row) => row.id === value.id)
      if (!found) throw new Error('计划已创建但未能在列表中回读，请刷新核对。')
      pendingCreate.value = undefined
      createId = requestId()
      notice.value = `计划 #${found.id} 已创建，下一次运行见卡片。`
    }
    showEditor.value = false
    confirmed.value = false
    await load()
  })
}
async function retryCreate() {
  await perform(async () => {
    const body = pendingCreate.value
    if (!body) return
    let value: ScheduleRow
    try {
      value = await request<ScheduleRow>(`${base()}/schedules`, 'POST', body)
    } catch (cause) {
      if (unknownResult(cause)) unknown.value = true
      throw cause
    }
    const readback = await request<ScheduleRow[]>(`${base()}/schedules`)
    const found = readback.find((row) => row.id === value.id)
    if (!found) throw new Error('计划已创建但未能在列表中回读，请刷新核对。')
    pendingCreate.value = undefined
    createId = requestId()
    unknown.value = false
    showEditor.value = false
    await load()
    notice.value = `计划 #${found.id} 已创建并回读，下一次运行见卡片。`
  })
}
async function act(row: ScheduleRow, action: ScheduleAction) {
  await perform(async () => {
    if (unknown.value)
      throw new Error('上次写入结果未知，请先刷新计划与通知核对。')
    const session = account.session?.session_id
    const answer = await Taro.showModal({
      title:
        action === 'pause'
          ? '暂停计划'
          : action === 'resume'
            ? '恢复计划'
            : '撤销计划',
      content:
        action === 'pause'
          ? '暂停期间不补跑，恢复后从下一个周期开始。确认继续？'
          : action === 'resume'
            ? '确认按卡片中的范围和规则恢复？从下一个周期开始，暂停期间不补跑。'
            : '确认永久撤销此计划？历史执行和已保存候选继续保留。',
    })
    if (!answer.confirm || !alive || session !== account.session?.session_id)
      return
    const body = scheduleActionPayload(
      row,
      action,
      action === 'edit' ? checkedScheduleConfig(form) : undefined,
      action !== 'pause' && action !== 'revoke',
    )
    try {
      await request<ScheduleRow>(`${base()}/schedules/${row.id}`, 'POST', body)
    } catch (cause) {
      if (unknownResult(cause)) unknown.value = true
      throw cause
    }
    await load()
    notice.value = `计划 #${row.id} 已${
      action === 'pause' ? '暂停' : action === 'resume' ? '恢复' : '撤销'
    }并回读列表。`
  })
}
async function check(row: ScheduleRow, retry = false) {
  await perform(async () => {
    if (!retry && unknown.value)
      throw new Error('上次写入结果未知，请先刷新计划与通知核对。')
    if (!retry) {
      if (!manualCheckReady(row, row.version))
        throw new Error('仅已启用且版本最新的计划可以立即检查。')
      pendingCheck.value = {
        plan: row.id,
        body: manualCheckPayload(row, checkId),
      }
    }
    const pending = pendingCheck.value
    if (!pending) return
    const answer = await Taro.showModal({
      title: row.config.task === 'report' ? '立即生成报表' : '立即检查一次',
      content:
        '本次使用最近完整周期与当时可用的导入数据，结果保存到运行历史；站内通知按免打扰设置延后显示。确认继续？',
    })
    if (!answer.confirm || !alive) return
    let occurrence: Occurrence
    try {
      occurrence = await request<Occurrence>(
        `${base()}/schedules/${pending.plan}/check`,
        'POST',
        pending.body,
      )
    } catch (cause) {
      if (unknownResult(cause)) unknown.value = true
      throw cause
    }
    pendingCheck.value = undefined
    checkId = requestId()
    unreadOnly.value = false
    await load()
    notice.value = `本次${
      row.config.task === 'report' ? '报表' : '检查'
    }已保存（周期 #${occurrence.id} · ${
      scheduleLabels[occurrence.status] || occurrence.status
    }），请从运行历史查看依据。`
  })
}
async function markRead(item: Occurrence) {
  await perform(async () => {
    if (!notificationReady(item, Date.now())) return
    if (unknown.value)
      throw new Error('上次写入结果未知，请先刷新计划与通知核对。')
    const answer = await Taro.showModal({
      title: '标记为已读',
      content: '仅更新本条站内通知的已读时间，不影响执行结果与来源。确认继续？',
    })
    if (!answer.confirm || !alive) return
    const read = await request<Occurrence>(
      `${base()}/schedules/history/${item.id}/read`,
      'POST',
    )
    await load()
    notice.value = `通知 #${read.id} 已标记已读。`
  })
}
async function openTarget(path: string, id: number, key: string) {
  try {
    await openLink(path, { [key]: String(id) })
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '无法打开目标页面。'
  }
}
async function toggleUnread(event: unknown) {
  unreadOnly.value = Boolean(
    (event as { detail: { value: boolean } }).detail.value,
  )
  await perform(() => load())
}
function toggleQuiet(event: unknown) {
  form.quiet = Boolean((event as { detail: { value: boolean } }).detail.value)
  confirmed.value = false
}
function pickTask(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  form.task = index === 1 ? 'report' : 'operations'
  if (form.task === 'report') {
    form.weekday = '0'
    form.month_day = '1'
    form.channel = 'generic'
  }
}
function pickFrequency(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  form.frequency =
    frequencies[index] === 'weekly'
      ? 'weekly'
      : frequencies[index] === 'monthly'
        ? 'monthly'
        : 'daily'
}
function pickWeekday(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  form.weekday = String(index)
}
function pickChannel(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  form.channel = channels[index] ?? 'generic'
}
function pickIdentity(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  form.data_identity = identities[index] ?? 'user_import'
}
function pickCurrency(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  form.currency = currencyList[index] ?? 'USD'
}
function toggleReportCurrency(event: unknown) {
  const value = (event as { detail: { value?: unknown[] } }).detail.value
  form.report_currencies = Array.isArray(value) ? value.map(String) : []
  confirmed.value = false
}
function toggleConfirmed(event: unknown) {
  const value = (event as { detail: { value?: unknown[] } }).detail.value
  confirmed.value = Array.isArray(value) && value.length > 0
}
useDidShow(() => {
  void perform(async () => {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    if (linked.shop && Number(linked.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不同。')
    if (channels.includes(linked.channel as SourceChannel))
      form.channel = linked.channel as SourceChannel
    if (identities.includes(linked.identity as DataIdentity))
      form.data_identity = linked.identity as DataIdentity
    if (!showEditor.value) {
      form.timezone = timezone.value
      form.currency = currency.value
    }
    await load()
    const plan = Number(linked.plan)
    if (Number.isInteger(plan) && plan > 0) {
      const found = plans.value.find((row) => row.id === plan)
      if (found) startEdit(found)
    }
    linked = {}
  })
})
</script>
<template>
  <view class="screen">
    <view class="hero"
      ><text class="eyebrow">SOLOOPS · SCHEDULES</text
      ><text class="title">定时运营，按期留痕。</text
      ><text class="muted"
        >运营巡检与经营报表按本地时区周期运行，结果与站内通知都可回读。</text
      ></view
    >
    <text v-if="error" class="error">{{ error }}</text
    ><text v-if="notice" class="hint">{{ notice }}</text
    ><text v-if="unknown" class="error"
      >上次写入结果未知：请刷新计划与通知核对后再操作，不要重复提交。</text
    >
    <view class="card"
      ><text class="section-title">本地自动调度</text
      ><text v-if="status" class="hint">{{
        status.worker_enabled
          ? '自动调度已配置启用，API 服务运行期间约每 30 秒扫描到期计划。'
          : '当前服务关闭自动调度，可手动检查并查看记录。'
      }}</text
      ><text class="hint"
        >API
        关闭、电脑关机或休眠期间不运行；服务需保持运行，当前配置不代表持续在线。恢复时仅尝试最近一期，较早周期合并；超过
        24 小时记为错过，暂停期间不补跑。</text
      ><text class="hint"
        >时间显示：{{ timezone }}。最近自动周期：
        {{ status?.latest_timer ? `#${status.latest_timer.id}` : '暂无' }}</text
      ><text v-if="status?.latest_timer" class="hint"
        >计划 #{{ status.latest_timer?.schedule_id }} · 周期 #{{
          status.latest_timer?.id
        }}
        ·
        {{
          scheduleLabels[status.latest_timer?.status || ''] ||
          status.latest_timer?.status
        }}
        · 计划时刻
        {{ supportTime(status.latest_timer?.scheduled_at || '', timezone) }} ·
        保存
        {{ supportTime(status.latest_timer?.created_at || '', timezone) }}</text
      ><button :disabled="busy" @tap="perform(() => load())">
        刷新计划与通知
      </button>
      <button :disabled="busy" @tap="startCreate">新建计划</button></view
    >
    <view v-if="showEditor" class="card"
      ><view class="row"
        ><text class="section-title">{{
          editing ? `修改计划 #${editing.id}` : '新建定时计划'
        }}</text
        ><text class="badge">{{
          editing ? `v${editing.version}` : '未保存'
        }}</text></view
      ><picker
        :range="tasks"
        :value="form.task === 'report' ? 1 : 0"
        :disabled="busy"
        @change="pickTask($event)"
        ><view class="field"
          >计划内容：{{ form.task === 'report' ? tasks[1] : tasks[0] }}</view
        ></picker
      ><text class="label">计划名称（最多 80 字）</text
      ><input v-model="form.name" :maxlength="80" :disabled="busy" /><text
        class="label"
        >运行时区（IANA）</text
      ><input v-model="form.timezone" :disabled="busy" /><picker
        :range="['每天', '每周', '每月']"
        :value="Math.max(0, frequencies.indexOf(form.frequency))"
        :disabled="busy"
        @change="pickFrequency($event)"
        ><view class="field"
          >执行周期：{{ frequencyLabels[form.frequency] }}</view
        ></picker
      ><text class="label">当地运行时间（HH:MM）</text
      ><input v-model="form.local_time" :disabled="busy" /><template
        v-if="form.task === 'operations' && form.frequency === 'weekly'"
        ><picker
          :range="weekdays"
          :value="Number(form.weekday)"
          :disabled="busy"
          @change="pickWeekday($event)"
          ><view class="field"
            >星期：{{ weekdays[Number(form.weekday)] || '周一' }}</view
          ></picker
        ></template
      ><template
        v-if="form.task === 'operations' && form.frequency === 'monthly'"
        ><text class="label">每月日期（1–28）</text
        ><input v-model="form.month_day" type="number" :disabled="busy"
      /></template>
      <text v-if="form.task === 'operations'" class="label"
        >订单回看天数（1–365）</text
      ><input
        v-if="form.task === 'operations'"
        v-model="form.lookback_days"
        type="number"
        :disabled="busy"
      /><picker
        :range="['用户导入数据', '合成演示数据']"
        :value="identities.indexOf(form.data_identity)"
        :disabled="busy"
        @change="pickIdentity($event)"
        ><view class="field"
          >检查数据身份：{{ form.data_identity }}</view
        ></picker
      ><template v-if="form.task === 'operations'"
        ><picker
          :range="['通用文件', 'Shopify', 'Amazon', '其他渠道']"
          :value="Math.max(0, channels.indexOf(form.channel))"
          :disabled="busy"
          @change="pickChannel($event)"
          ><view class="field">检查渠道：{{ form.channel }}</view></picker
        ><picker
          :range="currencyList"
          :value="Math.max(0, currencyList.indexOf(form.currency))"
          :disabled="busy"
          @change="pickCurrency($event)"
          ><view class="field">统计币种：{{ form.currency }}</view></picker
        ><text class="hint"
          >绑定经营规则版本 #{{ ruleVersion
          }}{{ activeRule ? '，使用已生效阈值' : '，使用下方检查阈值' }}</text
        ><button :disabled="busy" @tap="perform(loadRule)">
          刷新经营规则
        </button></template
      >
      <template v-else
        ><text class="label">报表币种（不选则全部币种分别统计）</text
        ><checkbox-group @change="toggleReportCurrency($event)"
          ><label v-for="code in reportCurrencyList" :key="code" class="label"
            ><checkbox
              :value="code"
              :checked="form.report_currencies.includes(code)"
              :disabled="busy"
            />{{ code }}</label
          ></checkbox-group
        ><text class="hint"
          >日报汇总前一自然日；周报每周一汇总上一完整周；月报每月 1
          日汇总上一自然月，均按运行时区计算。报表使用独立阈值并覆盖全部导入渠道。</text
        ></template
      >
      <text v-if="form.task === 'report'" class="label"
        >报表独立阈值：库存有效小时 / 最少销量 / 低毛利 %</text
      ><input
        v-if="form.task === 'operations'"
        v-model="form.max_age_hours"
        type="number"
        :disabled="busy || activeRule"
      /><input
        v-model="form.min_quantity"
        type="number"
        :disabled="busy || (form.task === 'operations' && activeRule)"
      /><input
        v-model="form.max_margin_percent"
        :disabled="busy || (form.task === 'operations' && activeRule)"
      />
      <view class="row"
        ><text>启用免打扰时段（按运行时区）</text
        ><switch
          :checked="form.quiet"
          :disabled="busy"
          @change="toggleQuiet($event)"
      /></view>
      <template v-if="form.quiet"
        ><text class="label">免打扰开始 / 结束小时（0–23，不能相同）</text
        ><input
          v-model="form.quiet_start"
          type="number"
          :disabled="busy" /><input
          v-model="form.quiet_end"
          type="number"
          :disabled="busy"
      /></template>
      <text class="hint"
        >免打扰期间结果照常保存，未读提醒延后显示；运行历史随时可查。经营规则版本变化后计划自动暂停，需核对并更新配置。</text
      >
      <checkbox-group @change="toggleConfirmed($event)"
        ><label class="label"
          ><checkbox value="confirm" :checked="confirmed" :disabled="busy" />{{
            form.task === 'report'
              ? '我确认按此周期和范围自动生成并保存本地经营报表及站内通知'
              : '我确认按此周期和范围执行本地检查并保存站内通知，候选逐次审批'
          }}</label
        ></checkbox-group
      >
      <button class="primary" :disabled="busy || !confirmed" @tap="save">
        {{ editing ? '保存计划修改' : '创建计划并回读' }}
      </button>
      <button :disabled="busy" @tap="showEditor = false">收起配置</button>
      <view v-if="pendingCreate"
        ><text class="hint"
          >上次创建结果尚未确认；可用同一请求标识回查，不要更换范围重复提交。</text
        ><button :disabled="busy" @tap="retryCreate">
          回查上次创建请求
        </button></view
      ></view
    >
    <view class="card"
      ><text class="section-title">运行计划</text
      ><text v-if="!plans.length" class="muted"
        >还没有定时计划。添加一个周期，开始积累可回读的运营检查。</text
      >
      <view v-for="row in plans" :key="row.id" class="card"
        ><view class="row"
          ><text class="label"
            >{{ row.config.name }} ·
            {{ scheduleLabels[row.status] || row.status }}</text
          ><text class="badge">v{{ row.version }}</text></view
        ><text class="hint"
          >#{{ row.id }} · {{ scheduleCycleText(row.config) }}</text
        ><text class="hint"
          >{{
            row.config.data_identity === 'synthetic'
              ? '合成演示数据'
              : '用户导入数据'
          }}
          · {{ scheduleSummary(row.config) }}</text
        ><text class="hint"
          >下一次：{{
            row.next_run_at
              ? supportTime(row.next_run_at, row.config.timezone)
              : '未安排（暂停或未启用）'
          }}</text
        >
        <button
          v-if="scheduleGates(row).check"
          :disabled="busy"
          @tap="check(row, false)"
        >
          {{ row.config.task === 'report' ? '立即生成报表' : '立即检查一次' }}
        </button>
        <button
          v-if="scheduleGates(row).pause"
          :disabled="busy"
          @tap="act(row, 'pause')"
        >
          暂停
        </button>
        <button
          v-if="scheduleGates(row).resume"
          :disabled="busy"
          @tap="act(row, 'resume')"
        >
          恢复
        </button>
        <button
          v-if="scheduleGates(row).edit"
          :disabled="busy"
          @tap="startEdit(row)"
        >
          修改
        </button>
        <button
          v-if="scheduleGates(row).revoke"
          class="danger"
          :disabled="busy"
          @tap="act(row, 'revoke')"
        >
          撤销计划
        </button>
        <button
          v-if="pendingCheck && pendingCheck.plan === row.id"
          :disabled="busy"
          @tap="check(row, true)"
        >
          回查上次检查请求
        </button>
      </view>
    </view>
    <view class="card"
      ><view class="row"
        ><text class="section-title">站内通知与运行历史</text
        ><text class="badge">{{ history.length }} 条</text></view
      ><view class="row"
        ><text>只看已到提醒时间的未读通知</text
        ><switch
          :checked="unreadOnly"
          :disabled="busy"
          @change="toggleUnread($event)"
      /></view>
      <text class="hint"
        >显示周期结束时的状态；进入对应检查或报表查看当前进度与来源状态。免打扰期间的结果在完整历史中可见。</text
      ><text v-if="!history.length" class="muted">{{
        unreadOnly ? '当前没有到期的未读通知。' : '还没有运行记录。'
      }}</text
      ><view v-for="item in history" :key="item.id" class="card"
        ><view class="row"
          ><text class="label"
            >计划 #{{ item.schedule_id }} ·
            {{
              item.task === 'report' && item.status === 'succeeded'
                ? '报表已保存'
                : scheduleLabels[item.status] || item.status
            }}</text
          ><text v-if="!item.read_at" class="badge">未读</text></view
        ><text class="hint"
          >{{ item.trigger === 'timer' ? '定时周期' : '手动检查' }}：{{
            supportTime(item.scheduled_at, timezone)
          }}
          · 保存 {{ supportTime(item.created_at, timezone) }} · 提醒
          {{ supportTime(item.notify_at, timezone) }}</text
        ><text v-if="item.coalesced_from" class="hint"
          >从
          {{
            supportTime(item.coalesced_from, timezone)
          }}
          起的错过周期已合并，本次只处理最近一期。</text
        ><text
          v-if="['blocked', 'paused', 'circuit_open'].includes(item.status)"
          class="hint"
          >该周期运行受阻，计划当时已暂停。{{
            occurrenceReasons[item.reason] ||
            '请查看原任务，核对条件后恢复计划。'
          }}</text
        ><text v-else-if="occurrenceReasons[item.reason]" class="hint">{{
          occurrenceReasons[item.reason]
        }}</text
        ><button
          v-if="item.report_id"
          :disabled="busy"
          @tap="openTarget('/overview', item.report_id ?? 0, 'report')"
        >
          查看报表与依据 #{{ item.report_id }}</button
        ><button
          v-if="item.execution_id"
          :disabled="busy"
          @tap="openTarget('/agent', item.execution_id ?? 0, 'execution')"
        >
          查看检查与审批 #{{ item.execution_id }}</button
        ><button
          v-if="!item.read_at"
          :disabled="busy || !notificationReady(item, Date.now())"
          @tap="markRead(item)"
        >
          标为已读
        </button>
        <text
          v-if="!item.read_at && !notificationReady(item, Date.now())"
          class="hint"
          >未到提醒时间，暂不能标记已读；免打扰结束或提醒时间到达后可标记。</text
        ></view
      >
      <button
        v-if="history.length >= 50"
        :disabled="busy"
        @tap="perform(() => load(true))"
      >
        更早的记录
      </button></view
    >
  </view>
</template>
