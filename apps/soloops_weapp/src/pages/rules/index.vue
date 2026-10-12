// route: /rules
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Taro, { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import { queryString, requestId } from '../../services/task-policy'
import { supportTime } from '../../services/support-types'
import { openLink } from '../../services/navigation'
import type { SourceChannel } from '../../services/import-types'
import {
  authorizationGate,
  authorizationLabels,
  authorizationMaxHours,
  authorizationMaxUses,
  canRevokeGrant,
  channels,
  checkedAuthorization,
  checkedRuleChange,
  defaultRuleValues,
  dirtyRuleForm,
  grantScopeText,
  identities,
  currencies,
  noteLabels,
  revertableUses,
  ruleActionGates,
  ruleActionLabels,
  ruleForm,
  unknownResult,
  type AuthorizationGrant,
  type AuthorizationPage,
  type DataIdentity,
  type RuleAction,
  type RuleForm,
  type RuleRevision,
  type RunFacts,
} from '../../services/business-rule-policy'

const scope = reactive({
  channel: 'generic' as SourceChannel,
  data_identity: 'user_import' as DataIdentity,
})
const revision = ref<RuleRevision>(),
  history = ref<RuleRevision[]>([]),
  inspected = ref<RuleRevision>(),
  grants = ref<AuthorizationGrant[]>([]),
  grant = ref<AuthorizationGrant>(),
  nextBeforeId = ref<number | null>(null),
  run = ref<RunFacts>()
const draft = reactive<RuleForm>(ruleForm(defaultRuleValues()))
const runForm = reactive({ execution_id: '', max_uses: '1', valid_hours: '24' })
const busy = ref(false),
  error = ref(''),
  notice = ref(''),
  confirmed = ref(false),
  authConfirmed = ref(false),
  unknownRule = ref(false),
  pendingAuth = ref<Record<string, unknown>>()
let alive = true,
  epoch = 0,
  authRequestId = requestId(),
  linked: Record<string, string> = {}
const request = scopedRequest(api, () => (alive ? epoch : null))
const identityLabels: Record<string, string> = {
  user_import: '用户导入文件',
  synthetic: '合成测试数据',
}
const channelLabels = ['通用 / 自建表', 'Shopify', 'Amazon', '其他来源']
const base = () => `/shops/${account.shopId}`
const gates = computed(() =>
  ruleActionGates(revision.value ?? { active: false, version: 0 }),
)
const dirtyDraft = computed(
  () => !!revision.value && dirtyRuleForm(draft, revision.value.values),
)
const protect = computed(
  () => unknownRule.value || !!pendingAuth.value || dirtyDraft.value,
)
const gateReasons = computed(() => authorizationGate(run.value))
const scopeText = computed(() =>
  run.value?.input ? grantScopeText(run.value.input.scope) : '',
)
const canRevoke = computed(() => !!grant.value && canRevokeGrant(grant.value))

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
    revision.value = undefined
    history.value = []
    inspected.value = undefined
    grants.value = []
    grant.value = undefined
    run.value = undefined
    nextBeforeId.value = null
    confirmed.value = authConfirmed.value = false
    unknownRule.value = false
    pendingAuth.value = undefined
    authRequestId = requestId()
    error.value = notice.value = ''
  },
  { flush: 'sync' },
)
watch(protect, (value) => {
  if (!alive) return
  if (value)
    Taro.enableAlertBeforeUnload({
      message: '有未保存的规则草稿或待核对授权，离开前请确认。',
    })
  else Taro.disableAlertBeforeUnload()
})
watch(
  () => [scope.channel, scope.data_identity],
  () => {
    revision.value = undefined
    inspected.value = undefined
    confirmed.value = false
    unknownRule.value = false
  },
  { flush: 'sync' },
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
function adopt(value: RuleRevision) {
  revision.value = value
  Object.assign(draft, ruleForm(value.values))
  confirmed.value = false
  unknownRule.value = false
}
async function loadRule() {
  if (!account.session || !account.shopId)
    throw new Error('请先登录并选择店铺。')
  const value = await request<RuleRevision>(
    `${base()}/business-rules?${queryString({ channel: scope.channel, data_identity: scope.data_identity })}`,
  )
  adopt(value)
}
async function loadHistory(more = false) {
  const before = more ? history.value[history.value.length - 1]?.version : null
  const rows = await request<RuleRevision[]>(
    `${base()}/business-rules/history?${queryString({
      channel: scope.channel,
      data_identity: scope.data_identity,
      before,
    })}`,
  )
  history.value = more ? [...history.value, ...rows] : rows
}
async function loadGrants(more = false) {
  const page = await request<AuthorizationPage>(
    `${base()}/authorizations${more && nextBeforeId.value ? `?before_id=${nextBeforeId.value}` : ''}`,
  )
  grants.value = more ? [...grants.value, ...page.items] : page.items
  nextBeforeId.value = page.next_before_id
}
async function showGrant(id: number) {
  grant.value = await request<AuthorizationGrant>(
    `${base()}/authorizations/${id}`,
  )
}
async function inspect(version: number) {
  inspected.value = await request<RuleRevision>(
    `${base()}/business-rules/${version}`,
  )
  confirmed.value = false
}
async function changeRule(action: RuleAction) {
  await perform(async () => {
    if (!revision.value) throw new Error('请先读取当前经营规则。')
    if (unknownRule.value)
      throw new Error('上次写入结果未知，请先重新读取当前规则核对。')
    if (!confirmed.value) throw new Error('请先勾选已核对范围与数值。')
    const body = checkedRuleChange({
      channel: scope.channel,
      data_identity: scope.data_identity,
      expected_version: revision.value.version,
      action,
      form: action === 'save' ? draft : undefined,
      restore_version: action === 'restore' ? inspected.value?.version : null,
    })
    if (action !== 'save') {
      const answer = await Taro.showModal({
        title: `${ruleActionLabels[action]}经营规则`,
        content:
          action === 'revoke'
            ? '撤销后所选范围不再受规则约束，历史检查与已完成记录继续可查。确认继续？'
            : action === 'reset'
              ? '重置会写回 24 小时、1 件、20% 的初始口径并保留历史版本。确认继续？'
              : `将历史版本 #${body.restore_version} 恢复为新版本，用于后续检查。确认继续？`,
      })
      if (!answer.confirm || !alive) return
    }
    let value: RuleRevision
    try {
      value = await request<RuleRevision>(
        `${base()}/business-rules`,
        'POST',
        body,
      )
    } catch (cause) {
      if (unknownResult(cause)) unknownRule.value = true
      throw cause
    }
    const readback = await request<RuleRevision>(
      `${base()}/business-rules/${value.version}`,
    )
    adopt(readback)
    inspected.value = undefined
    await loadHistory()
    notice.value = `已${ruleActionLabels[action]}，当前版本 #${readback.version}，已按编号回读。`
  })
}
async function checkRun() {
  await perform(async () => {
    const id = Number(runForm.execution_id.trim())
    if (!runForm.execution_id.trim() || !Number.isInteger(id) || id < 1)
      throw new Error('请输入要授权的任务编号。')
    const value = await request<RunFacts>(`${base()}/agent/runs/${id}`)
    run.value = value
    authConfirmed.value = false
    authRequestId = requestId()
    const reasons = authorizationGate(value)
    notice.value = reasons.length
      ? `任务 #${value.id} 暂不满足预授权条件。`
      : `已核对任务 #${value.id} · 版本 ${value.version}。`
  })
}
async function createGrant(retry = false) {
  await perform(async () => {
    if (!retry) {
      if (!authConfirmed.value)
        throw new Error('请先核对候选范围与撤回边界并勾选确认。')
      pendingAuth.value = checkedAuthorization(
        {
          execution_id: runForm.execution_id,
          max_uses: runForm.max_uses,
          valid_hours: runForm.valid_hours,
        },
        authRequestId,
        run.value,
      )
    }
    const body = pendingAuth.value
    if (!body) return
    let value: AuthorizationGrant
    value = await request<AuthorizationGrant>(
      `${base()}/authorizations`,
      'POST',
      body,
    )
    const readback = await request<AuthorizationGrant>(
      `${base()}/authorizations/${value.id}`,
    )
    grant.value = readback
    pendingAuth.value = undefined
    authConfirmed.value = false
    authRequestId = requestId()
    await loadGrants()
    notice.value = `授权 #${readback.id} 已创建并回读，状态 ${authorizationLabels[readback.status] || readback.status}。`
  })
}
async function revokeGrant() {
  await perform(async () => {
    const current = grant.value
    if (!current || !canRevokeGrant(current)) return
    const session = account.session?.session_id
    const answer = await Taro.showModal({
      title: '撤销授权',
      content:
        '后续不能再使用此授权；此前保存的候选与额度记录保留，不能返还额度。确认继续？',
    })
    if (
      !answer.confirm ||
      current.shop_id !== account.shopId ||
      session !== account.session?.session_id ||
      !alive
    )
      return
    const value = await request<AuthorizationGrant>(
      `${base()}/authorizations/${current.id}/revoke`,
      'POST',
      { version: current.version },
    )
    grant.value = await request<AuthorizationGrant>(
      `${base()}/authorizations/${value.id}`,
    )
    await loadGrants()
    notice.value = '授权已撤销并回读。'
  })
}
async function revertUse(useId: number) {
  await perform(async () => {
    const current = grant.value
    if (!current) return
    const session = account.session?.session_id
    const answer = await Taro.showModal({
      title: '撤回本次新增候选',
      content:
        '仅将本次新增且未被处理或编辑的候选设为已拒绝；任一候选已变化则整批不撤回，额度不返还。确认继续？',
    })
    if (
      !answer.confirm ||
      current.shop_id !== account.shopId ||
      session !== account.session?.session_id ||
      !alive
    )
      return
    const value = await request<AuthorizationGrant>(
      `${base()}/authorizations/${current.id}/uses/${useId}/revert`,
      'POST',
    )
    grant.value = await request<AuthorizationGrant>(
      `${base()}/authorizations/${value.id}`,
    )
    await loadGrants()
    notice.value = '本次新增候选已按整批撤回，结果已回读。'
  })
}
async function openRun(id: number) {
  try {
    await openLink('/agent', { execution: String(id) })
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '无法打开任务。'
  }
}
function pickChannel(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  scope.channel = channels[index] ?? 'generic'
}
function pickIdentity(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  scope.data_identity = identities[index] ?? 'user_import'
}
function pickCurrency(event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  draft.currency = currencies[index] ?? 'USD'
}
function toggleConfirmed(event: unknown) {
  const value = (event as { detail: { value?: unknown[] } }).detail.value
  confirmed.value = Array.isArray(value) && value.length > 0
}
function toggleAuthConfirmed(event: unknown) {
  const value = (event as { detail: { value?: unknown[] } }).detail.value
  authConfirmed.value = Array.isArray(value) && value.length > 0
}
useDidShow(() => {
  void perform(async () => {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    if (linked.shop && Number(linked.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不同。')
    if (channels.includes(linked.channel as SourceChannel))
      scope.channel = linked.channel as SourceChannel
    if (identities.includes(linked.identity as DataIdentity))
      scope.data_identity = linked.identity as DataIdentity
    await loadRule()
    await loadHistory()
    await loadGrants()
    const version = Number(linked.version)
    if (Number.isInteger(version) && version > 0) await inspect(version)
    linked = {}
  })
})
</script>
<template>
  <view class="screen">
    <view class="hero"
      ><text class="eyebrow">SOLOOPS · RULES</text
      ><text class="title">经营规则写清楚，授权有边界。</text
      ><text class="muted"
        >检查阈值按店、渠道与数据身份版本化；内部预授权固定来源、规则与候选范围。</text
      ></view
    >
    <text v-if="error" class="error">{{ error }}</text
    ><text v-if="notice" class="hint">{{ notice }}</text
    ><text v-if="unknownRule" class="error"
      >上次规则写入结果未知：请重新读取当前规则核对后，再决定是否保存；不要更换范围重复提交。</text
    >
    <view class="card"
      ><text class="section-title">规则范围</text
      ><picker
        :range="channelLabels"
        :value="Math.max(0, channels.indexOf(scope.channel))"
        :disabled="busy"
        @change="pickChannel($event)"
        ><view class="field">渠道：{{ scope.channel }}</view></picker
      ><picker
        :range="['用户导入文件', '合成测试数据']"
        :value="identities.indexOf(scope.data_identity)"
        :disabled="busy"
        @change="pickIdentity($event)"
        ><view class="field"
          >数据身份：{{ identityLabels[scope.data_identity] }}</view
        ></picker
      ><button :disabled="busy" @tap="perform(loadRule)">
        重新读取当前规则
      </button></view
    >
    <view v-if="revision" class="card"
      ><view class="row"
        ><text class="section-title">当前规则 #{{ revision.version }}</text
        ><text class="badge">{{
          revision.active ? '约束已启用' : '未启用约束'
        }}</text></view
      ><text class="hint"
        >{{ ruleActionLabels[revision.action] || revision.action }} · 前版 #{{
          revision.previous_version
        }}<template v-if="revision.restored_from">
          · 恢复自 #{{ revision.restored_from }}</template
        >
        ·
        {{
          revision.created_at
            ? supportTime(
                revision.created_at,
                account.shops.find((s) => s.id === account.shopId)?.timezone ||
                  'Asia/Shanghai',
              )
            : '初始口径，未写入版本'
        }}</text
      ><text class="hint"
        >未启用约束时，可按次填写阈值；启用后用于所选范围的运营检查与定时计划。</text
      ><text class="label">库存有效小时（1–720）</text
      ><input
        v-model="draft.max_age_hours"
        type="number"
        :disabled="busy"
      /><text class="label">低毛利最少销量（1–1000000）</text
      ><input
        v-model="draft.min_quantity"
        type="number"
        :disabled="busy"
      /><text class="label">低毛利阈值 %（-1000–100，最多 2 位小数）</text
      ><input v-model="draft.max_margin_percent" :disabled="busy" /><text
        class="label"
        >每日广告计划金额（留空为未知，最多 4 位小数）</text
      ><input
        v-model="draft.advertising_daily_budget"
        :disabled="busy"
      /><picker
        :range="currencies"
        :value="Math.max(0, currencies.indexOf(draft.currency))"
        :disabled="busy"
        @change="pickCurrency($event)"
        ><view class="field">预算币种：{{ draft.currency }}</view></picker
      ><text class="label">经营偏好与预算记录</text
      ><text class="hint"
        >以下是卖家手填参考，尚未用于生成文案、选仓、物流或广告投放；广告金额是计划值，未授权支出。</text
      ><template v-for="item in noteLabels" :key="item.key"
        ><text class="label">{{ item.label }}（最多 {{ item.max }} 字）</text
        ><textarea
          v-model="draft.notes[item.key]"
          :maxlength="item.max"
          :disabled="busy"
        /></template
      ><text class="label">规则与偏好依据（必填，最多 500 字）</text
      ><textarea
        v-model="draft.basis"
        :maxlength="500"
        :disabled="busy"
      /><checkbox-group @change="toggleConfirmed($event)"
        ><label class="label"
          ><checkbox
            value="confirm"
            :checked="confirmed"
            :disabled="busy"
          />我已核对范围与数值，同意保存或恢复后用于后续检查</label
        ></checkbox-group
      ><button
        class="primary"
        :disabled="busy || !confirmed || unknownRule"
        @tap="changeRule('save')"
      >
        保存并启用规则
      </button>
      <view class="row"
        ><button
          :disabled="busy || !confirmed || !gates.revoke || unknownRule"
          @tap="changeRule('revoke')"
        >
          撤销当前规则</button
        ><button
          :disabled="busy || !confirmed || unknownRule"
          @tap="changeRule('reset')"
        >
          重置到初始口径
        </button></view
      >
      <text class="hint"
        >撤销/重置停止约束并恢复 24 小时、1 件、20%
        初始值，偏好清空；历史保留，旧检查与待审任务须重新运行。</text
      ><text v-if="dirtyDraft" class="hint"
        >表单有未保存修改；保存或重新读取前不会生效。</text
      ></view
    >
    <view class="card"
      ><view class="row"
        ><text class="section-title">规则历史与依据</text
        ><text class="hint">恢复会建立新版本，不改写历史检查数值</text></view
      ><text v-if="!history.length" class="muted"
        >此范围还没有写入过规则版本。</text
      ><button
        v-for="row in history"
        :key="row.version"
        :disabled="busy"
        @tap="inspect(row.version)"
      >
        #{{ row.version }} · {{ ruleActionLabels[row.action] || row.action }} ·
        {{ row.active ? '启用' : '未启用' }}
      </button>
      <button
        v-if="history.length >= 50"
        :disabled="busy"
        @tap="loadHistory(true)"
      >
        更早 50 个版本
      </button>
      <view v-if="inspected" class="card"
        ><text class="section-title"
          >版本 #{{ inspected.version }} ·
          {{ ruleActionLabels[inspected.action] || inspected.action }}</text
        ><text class="hint"
          >前版 #{{ inspected.previous_version
          }}<template v-if="inspected.restored_from">
            · 恢复自 #{{ inspected.restored_from }}</template
          ></text
        ><text
          >库存有效 {{ inspected.values.max_age_hours }} 小时 · 最少
          {{ inspected.values.min_quantity }} 件 · 低毛利
          {{ inspected.values.max_margin_percent }}% · 广告计划
          {{ inspected.values.advertising_daily_budget ?? '未知' }}
          {{ inspected.values.currency }}</text
        ><text class="hint">依据：{{ inspected.values.basis }}</text
        ><text v-for="item in noteLabels" :key="item.key" class="hint"
          >{{ item.label }}：{{
            inspected.values.notes[item.key] || '未填写'
          }}</text
        ><button
          v-if="inspected.active"
          :disabled="busy || !confirmed || unknownRule"
          @tap="changeRule('restore')"
        >
          将此版本恢复为新规则
        </button></view
      ></view
    >
    <view class="card"
      ><text class="section-title">R1 内部预授权</text
      ><text class="hint"
        >在固定来源、规则和范围内保存异常候选；每次保存或复用消耗 1 次，费用 0
        USD。业务候选仍逐项审批，撤销和撤回都不返还额度。</text
      ><text class="label">待审批任务编号</text
      ><input
        v-model="runForm.execution_id"
        type="number"
        :disabled="busy"
        placeholder="例如 12"
      /><button :disabled="busy" @tap="checkRun">读取并核对任务</button>
      <view v-if="run"
        ><text class="label"
          >任务 #{{ run.id }} · 版本 {{ run.version }} · {{ run.template }} /
          {{ run.status }} / {{ run.next_node }}</text
        ><text class="hint">{{ scopeText }}</text
        ><text v-if="gateReasons.length" class="error">{{
          gateReasons.join(' ')
        }}</text>
        <text class="label"
          >最大次数 1–{{ authorizationMaxUses }} / 有效小时 1–{{
            authorizationMaxHours
          }}</text
        ><input
          v-model="runForm.max_uses"
          type="number"
          :disabled="busy"
        /><input v-model="runForm.valid_hours" type="number" :disabled="busy" />
        <checkbox-group @change="toggleAuthConfirmed($event)"
          ><label class="label"
            ><checkbox
              value="confirm"
              :checked="authConfirmed"
              :disabled="busy"
            />已核对全部候选、范围与撤回边界</label
          ></checkbox-group
        ><button
          class="primary"
          :disabled="busy || !authConfirmed || gateReasons.length > 0"
          @tap="createGrant(false)"
        >
          创建授权并回读
        </button></view
      >
      <view v-if="pendingAuth"
        ><text class="hint"
          >上次创建结果尚未确认；可用同一请求标识回查，不要更换范围重复提交。</text
        ><button :disabled="busy" @tap="createGrant(true)">
          回查上次创建请求
        </button></view
      >
      <button :disabled="busy" @tap="perform(() => loadGrants())">
        刷新授权列表
      </button>
      <text v-if="!grants.length" class="muted">本店暂无内部预授权。</text>
      <text v-for="row in grants" :key="row.id" class="hint"
        >授权 #{{ row.id }} ·
        {{ authorizationLabels[row.status] || row.status }} · v{{
          row.version
        }}
        · {{ row.used_count }}/{{ row.max_uses }} 次 ·
        {{ row.candidate_count }} 项候选 · 到期
        {{
          supportTime(
            row.expires_at,
            account.shops.find((s) => s.id === account.shopId)?.timezone ||
              'Asia/Shanghai',
          )
        }}</text
      >
      <button
        v-for="row in grants"
        :key="`open-${row.id}`"
        :disabled="busy"
        @tap="showGrant(row.id)"
      >
        回读授权 #{{ row.id }} 详情
      </button>
      <button v-if="nextBeforeId" :disabled="busy" @tap="loadGrants(true)">
        更早授权
      </button>
      <view v-if="grant" class="card"
        ><view class="row"
          ><text class="section-title">授权 #{{ grant.id }}</text
          ><text class="badge">{{
            authorizationLabels[grant.status] || grant.status
          }}</text></view
        ><text class="hint"
          >已用 {{ grant.used_count }}/{{ grant.max_uses }} 次 · 来源版本
          {{ grant.source_revision }} · {{ grant.candidate_count }} 项候选 ·
          原始任务 #{{ grant.origin_execution_id }}</text
        ><text class="hint">{{ grantScopeText(grant.scope) }}</text
        ><text class="hint"
          >来源有效至 {{ grant.source_valid_until || '未提供' }} · 撤销于
          {{ grant.revoked_at || '未撤销' }}</text
        ><button :disabled="busy" @tap="openRun(grant.origin_execution_id)">
          回读原始任务 #{{ grant.origin_execution_id }}</button
        ><button
          v-if="canRevoke"
          class="danger"
          :disabled="busy"
          @tap="revokeGrant"
        >
          撤销授权
        </button>
        <text v-if="!grant.uses.length" class="muted">此授权尚未被使用。</text>
        <view v-for="use in grant.uses" :key="use.id" class="card"
          ><text class="label"
            >使用 #{{ use.id }} · 任务 #{{ use.execution_id }} · 复用
            {{ use.reused_count }} 项 · {{ use.created_at }}</text
          ><text
            v-for="change in use.changes"
            :key="change.task_id"
            class="hint"
            >待办 #{{ change.task_id }} · {{ change.before }} →
            {{ change.after }} · v{{ change.version }}</text
          ><text v-if="use.reverted_at" class="hint"
            >已撤回 {{ use.reverted_at }}</text
          ><button :disabled="busy" @tap="openRun(use.execution_id)">
            回读本次任务 {{ use.execution_id }}</button
          ><button
            v-if="!use.reverted_at && use.changes.length"
            class="danger"
            :disabled="busy"
            @tap="revertUse(use.id)"
          >
            撤回本次新增候选（{{ use.changes.length }} 项）
          </button></view
        ></view
      ></view
    >
  </view>
</template>
