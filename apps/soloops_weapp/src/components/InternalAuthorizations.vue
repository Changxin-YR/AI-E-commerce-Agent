<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Taro from '@tarojs/taro'
import { api, account } from '../services/session'
import { requestId } from '../services/task-policy'
import type { AgentRun, AgentInput } from '../services/agent-types'
interface Grant {
  id: number
  shop_id: number
  version: number
  origin_execution_id: number
  scope: AgentInput['scope']
  source_revision: number
  candidate_count: number
  max_uses: number
  used_count: number
  status: string
  expires_at: string
  source_valid_until: string | null
  uses: {
    id: number
    execution_id: number
    operation_run_id: number
    reused_count: number
    created_at: string
    reverted_at: string | null
    changes: {
      task_id: number
      before: string
      after: string
      version: number
    }[]
  }[]
}
function checked(event: unknown) {
  return Boolean((event as { detail: { value: boolean } }).detail.value)
}
const props = defineProps<{ run?: AgentRun; busy: boolean }>()
const emit = defineEmits<{ use: [number]; start: [Grant]; inspect: [number] }>()
const grants = ref<Grant[]>([]),
  next = ref<number | null>(null),
  loading = ref(false),
  error = ref(''),
  count = ref(1),
  hours = ref(24),
  confirmed = ref(false)
let createId = requestId()
const root = () => `/shops/${account.shopId}/authorizations`
const canCreate = computed(
  () =>
    props.run?.template === 'daily' &&
    props.run.status === 'waiting_approval' &&
    props.run.next_node === 'propose_tasks' &&
    props.run.source_status === 'current',
)
const labels: Record<string, string> = {
  active: '有效',
  revoked: '已撤销',
  expired: '已到期',
  exhausted: '额度用尽',
  source_changed: '来源已变化',
  rules_changed: '规则已变化',
}
watch(
  () => [props.run?.id, props.run?.version, count.value, hours.value],
  () => {
    confirmed.value = false
    createId = requestId()
  },
)
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    grants.value = []
    next.value = null
    confirmed.value = false
    createId = requestId()
  },
)
async function page(more = false) {
  const value = await api.request<{
    items: Grant[]
    next_before_id: number | null
  }>(`${root()}${more && next.value ? `?before_id=${next.value}` : ''}`)
  grants.value = more ? [...grants.value, ...value.items] : value.items
  next.value = value.next_before_id
}
async function work(action: () => Promise<void>) {
  if (loading.value || props.busy || !account.shopId) return
  loading.value = true
  error.value = ''
  try {
    await action()
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : '操作失败，请刷新核对。'
  } finally {
    loading.value = false
  }
}
async function load(more = false) {
  await work(() => page(more))
}
async function create() {
  await work(async () => {
    if (!props.run || !canCreate.value || !confirmed.value) return
    const value = await api.request<Grant>(root(), 'POST', {
      request_id: createId,
      execution_id: props.run.id,
      expected_version: props.run.version,
      max_uses: count.value,
      valid_hours: hours.value,
      confirmed: true,
    })
    await api.request<Grant>(`${root()}/${value.id}`)
    confirmed.value = false
    createId = requestId()
    await page()
  })
}
async function change(grant: Grant, useId?: number) {
  await work(async () => {
    const session = account.session?.session_id
    const answer = await Taro.showModal({
      title: useId ? '撤回本次新增候选' : '撤销授权',
      content: useId
        ? '仅将本次新增且未被编辑或处理的候选设为已拒绝；历史保留，额度不返还。任一候选已变化则整批拒绝撤回。'
        : '后续不能使用此授权；此前保存结果保留。',
    })
    if (
      !answer.confirm ||
      grant.shop_id !== account.shopId ||
      session !== account.session?.session_id
    )
      return
    await api.request(
      `${root()}/${grant.id}/${useId ? `uses/${useId}/revert` : 'revoke'}`,
      'POST',
      useId ? undefined : { version: grant.version },
    )
    await api.request<Grant>(`${root()}/${grant.id}`)
    await page()
  })
}
</script>
<template>
  <view class="card"
    ><text class="section-title">R1 内部预授权</text
    ><text class="hint"
      >在固定来源、规则和范围内保存异常候选；每次保存或复用消耗1次，费用0
      USD。业务候选仍逐项审批。</text
    ><view v-if="error" class="error">{{ error }}</view>
    <view v-if="canCreate && run?.input"
      ><text class="label"
        >任务 #{{ run.id }} · 版本 {{ run.version }} 的已审候选</text
      ><text class="hint"
        >{{ run.input.scope.start_at }} 至 {{ run.input.scope.end_at }} ·
        {{ run.input.scope.currency }} · {{ run.input.scope.channel }} ·
        {{ run.input.scope.data_identity }} · 来源版本
        {{ run.source_revision }}</text
      ><text class="label">最大次数1–20 / 有效小时1–168</text
      ><input
        v-model.number="count"
        type="number"
        :disabled="loading || busy"
      /><input
        v-model.number="hours"
        type="number"
        :disabled="loading || busy"
      /><view class="row"
        ><text>已核对全部候选、范围及撤回边界</text
        ><switch
          :checked="confirmed"
          :disabled="loading || busy"
          @change="confirmed = checked($event)" /></view
      ><button :disabled="loading || busy || !confirmed" @tap="create">
        创建授权并回读
      </button></view
    >
    <button :disabled="loading || busy" @tap="load(false)">刷新授权</button>
    <view v-for="grant in grants" :key="grant.id" class="card"
      ><text class="label"
        >授权 #{{ grant.id }} · {{ labels[grant.status] || grant.status }} · v{{
          grant.version
        }}</text
      ><text class="hint"
        >已用 {{ grant.used_count }}/{{ grant.max_uses }} 次 ·
        {{ grant.candidate_count }} 项候选 · 到期 {{ grant.expires_at }}</text
      ><text class="hint"
        >{{ grant.scope.start_at }} 至 {{ grant.scope.end_at }} ·
        {{ grant.scope.timezone }} · {{ grant.scope.currency }} ·
        {{ grant.scope.data_identity }} / {{ grant.scope.channel }} · 来源
        {{ grant.source_revision }} · 来源有效至
        {{ grant.source_valid_until || '未提供' }}</text
      ><button
        :disabled="loading || busy"
        @tap="emit('inspect', grant.origin_execution_id)"
      >
        回读原始任务 #{{ grant.origin_execution_id }}</button
      ><button
        v-if="grant.status === 'active' && canCreate"
        :disabled="loading || busy"
        @tap="emit('use', grant.id)"
      >
        用于当前候选（服务端再次核对）</button
      ><button
        v-if="grant.status === 'active'"
        :disabled="loading || busy"
        @tap="emit('start', grant)"
      >
        按授权范围启动</button
      ><button
        v-if="grant.status === 'active'"
        :disabled="loading || busy"
        @tap="change(grant)"
      >
        撤销授权
      </button>
      <view v-for="use in grant.uses" :key="use.id"
        ><text class="label"
          >使用 #{{ use.id }} · {{ use.created_at }} · 复用
          {{ use.reused_count }} 项</text
        ><text v-for="item in use.changes" :key="item.task_id" class="hint"
          >待办 #{{ item.task_id }} · {{ item.before }} → {{ item.after }} · v{{
            item.version
          }}</text
        ><text v-if="use.reverted_at" class="hint"
          >已撤回 {{ use.reverted_at }}</text
        ><button
          :disabled="loading || busy"
          @tap="emit('inspect', use.execution_id)"
        >
          回读本次任务</button
        ><button
          v-if="!use.reverted_at && use.changes.length"
          :disabled="loading || busy"
          @tap="change(grant, use.id)"
        >
          撤回本次新增候选
        </button></view
      > </view
    ><button v-if="next" :disabled="loading || busy" @tap="load(true)">
      更早授权
    </button>
  </view>
</template>
