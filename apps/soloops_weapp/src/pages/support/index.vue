<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import Taro, { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import { ApiError } from '../../services/client'
import { queryString, requestId } from '../../services/task-policy'
import { openLink } from '../../services/navigation'
import { replyActions, awareTimestamp } from '../../services/support-policy'
import {
  replyStatus,
  intentLabels,
  supportTime,
  type MessageFacts,
  type ReplyDraft,
  type SupportWorkspace,
  type ManualActionInput,
  type ManualActionRecord,
} from '../../services/support-types'
import type { ManualDelivery } from '../../services/delivery-policy'
import SourceList from '../../components/SourceList.vue'
import ReviewedDelivery from '../../components/ReviewedDelivery.vue'
import SupportPolicies from '../../components/SupportPolicies.vue'

const messages = ref<MessageFacts[]>([]),
  history = ref<ReplyDraft[]>([]),
  workspace = ref<SupportWorkspace>(),
  selected = ref<ReplyDraft>()
const search = ref(''),
  offset = ref(0),
  actionBusy = ref(false),
  policyBusy = ref(false),
  policyEditing = ref(false),
  error = ref(''),
  notice = ref(''),
  unknown = ref(false)
const busy = computed(() => actionBusy.value || policyBusy.value)
const reply = ref(''),
  language = ref('en'),
  confirmed = ref(false),
  verified = ref(false),
  policies = ref<number[]>([])
const records = ref<ManualActionRecord[]>([]),
  moreRecords = ref(false)
const manual = reactive({
  occurred_at: '',
  method: '',
  evidence_ref: '',
  note: '',
  confirmed: false,
})
const pendingManual = ref<{ draft: number; data: ManualActionInput }>()
const params = ref<Record<string, string>>({})
const dirty = computed(
  () =>
    !!selected.value?.snapshot && reply.value !== selected.value.snapshot.reply,
)
const evidenceDirty = computed(
  () =>
    !!(
      manual.method ||
      manual.evidence_ref ||
      manual.note ||
      manual.occurred_at
    ),
)
const actions = computed(() =>
  selected.value
    ? replyActions(selected.value, dirty.value, language.value)
    : null,
)
const shop = computed(() => account.shops.find((s) => s.id === account.shopId))
const timezone = computed(() => shop.value?.timezone || 'Asia/Shanghai')
const base = () => `/shops/${account.shopId}/support`
let epoch = 0,
  alive = true
const request = scopedRequest(api, () => (alive ? epoch : null))
function checked(event: unknown) {
  return Boolean((event as { detail: { value: boolean } }).detail.value)
}
function resetManual() {
  Object.assign(manual, {
    occurred_at: '',
    method: '',
    evidence_ref: '',
    note: '',
    confirmed: false,
  })
}
watch(
  [reply, language],
  () => {
    confirmed.value = false
  },
  { flush: 'sync' },
)

// Consent has its own switch; text input changes invalidate it synchronously.
watch(
  () => [manual.occurred_at, manual.method, manual.evidence_ref, manual.note],
  () => {
    manual.confirmed = false
  },
  { flush: 'sync' },
)
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    epoch++
    policyEditing.value = false
    policyBusy.value = false
    error.value = notice.value = ''
    reply.value = ''
    confirmed.value = false
    messages.value = []
    history.value = []
    workspace.value = undefined
    selected.value = undefined
    records.value = []
    pendingManual.value = undefined
    resetManual()
    unknown.value = false
    policies.value = []
    verified.value = false
    params.value = {}
    offset.value = 0
  },
  { flush: 'sync' },
)
useLoad((value) => {
  // The operations destination adds shop/identity/channel context; support
  // messages are scoped by shop only, so the context keys are not filters here.
  params.value = value as Record<string, string>
})
watch(
  () =>
    dirty.value ||
    evidenceDirty.value ||
    !!pendingManual.value ||
    policyEditing.value ||
    unknown.value ||
    busy.value,
  (protect) => {
    if (!alive) return
    if (protect)
      Taro.enableAlertBeforeUnload({
        message: '有未保存内容或待核对操作，离开前请确认。',
      })
    else Taro.disableAlertBeforeUnload()
  },
)
useUnload(() => {
  alive = false
  epoch++
})
async function perform(work: () => Promise<void>) {
  if (busy.value || !alive) return
  if (!account.session || !account.shopId) {
    error.value = '请先登录并选择店铺。'
    return
  }
  const token = epoch
  actionBusy.value = true
  error.value = ''
  notice.value = ''
  try {
    await work()
  } catch (cause) {
    if (alive && token === epoch)
      error.value =
        cause instanceof Error ? cause.message : '操作失败，请刷新核对。'
  } finally {
    actionBusy.value = false
  }
}
async function discard() {
  if (pendingManual.value) throw new Error('请先核对或恢复待确认的人工记录。')
  if (policyEditing.value) throw new Error('请先保存或取消政策编辑。')
  if (!dirty.value && !evidenceDirty.value) return true
  const token = epoch
  const answer = await Taro.showModal({
    title: '替换未保存内容',
    content: '当前回复或人工记录尚未保存，是否放弃修改并继续？',
  })
  if (!answer.confirm || token !== epoch || !alive) return false
  resetManual()
  return true
}
function adopt(value: ReplyDraft) {
  selected.value = value
  reply.value = value.snapshot?.reply || ''
  language.value =
    value.reviewed_language ||
    (value.snapshot?.message.language === 'zh' ? 'zh' : 'en')
  confirmed.value = false
}
async function list(page = offset.value) {
  messages.value = await request<MessageFacts[]>(
    `${base()}/messages?${queryString({ q: search.value, offset: page })}`,
  )
  offset.value = page
  history.value = await request<ReplyDraft[]>(`${base()}/drafts`)
}
async function readRecords(before?: number) {
  if (!selected.value) return
  const values = await request<ManualActionRecord[]>(
    `${base()}/drafts/${selected.value.id}/manual-actions?${queryString({ before })}`,
  )
  records.value = before ? [...records.value, ...values] : values
  moreRecords.value = values.length === 50
}
async function read(id: number) {
  adopt(await request<ReplyDraft>(`${base()}/drafts/${id}`))
  await readRecords()
}
async function choose(id: number) {
  await perform(async () => {
    if (!(await discard())) return
    workspace.value = await request<SupportWorkspace>(
      `${base()}/messages/${id}`,
    )
    selected.value = undefined
    records.value = []
    verified.value = false
    policies.value = []
  })
}
async function inspect(id: number) {
  await perform(async () => {
    if (!(await discard())) return
    workspace.value = undefined
    await read(id)
    unknown.value = false
  })
}
async function refresh() {
  await perform(async () => {
    if (!(await discard())) return
    await list()
    if (selected.value) await read(selected.value.id)
    if (workspace.value)
      workspace.value = await request<SupportWorkspace>(
        `${base()}/messages/${workspace.value.message.id}`,
      )
    verified.value = false
    policies.value = []
    unknown.value = false
  })
}
function togglePolicy(id: number, event: unknown) {
  policies.value = checked(event)
    ? [...policies.value, id]
    : policies.value.filter((p) => p !== id)
}
async function generate() {
  await perform(async () => {
    if (!workspace.value || unknown.value || !(await discard())) return
    if (policies.value.length > 10) throw new Error('最多选择10条适用政策。')
    unknown.value = true
    const result = await request<ReplyDraft>(
      `${base()}/messages/${workspace.value.message.id}/generate`,
      'POST',
      {
        expected_source_row_id: workspace.value.message.source.row_id,
        expected_order_row_ids: workspace.value.orders.map(
          (o) => o.source.row_id,
        ),
        order_verified: verified.value,
        policy_ids: policies.value,
      },
    )
    adopt(result)
    await read(result.id)
    await list()
    unknown.value = false
    notice.value = '草稿已保存并GET回读，请核对全部诉求。'
  })
}
async function mutate(
  kind: 'edit' | 'review' | 'handoff' | 'archive' | 'reopen',
) {
  await perform(async () => {
    const item = selected.value
    if (!item || !actions.value?.[kind] || unknown.value || pendingManual.value)
      return
    let path = `${base()}/drafts/${item.id}/`,
      data: object
    if (kind === 'edit') {
      if (!reply.value.trim() || reply.value.length > 6000)
        throw new Error('回复须为1–6000字。')
      path += 'edit'
      data = { expected_version: item.version, reply: reply.value }
    } else if (kind === 'review') {
      if (!confirmed.value) throw new Error('请确认全文、语言和接管原因。')
      path += 'review'
      data = {
        expected_version: item.version,
        target_language: language.value,
        confirmed: true,
      }
    } else {
      const token = epoch
      const answer = await Taro.showModal({
        title: '确认处理草稿',
        content: `店铺 #${account.shopId} / 草稿 #${item.id} v${item.version}：${{ handoff: '转人工接管', archive: '归档', reopen: '重新打开并转人工' }[kind]}。平台外部未提交。`,
      })
      if (!answer.confirm || token !== epoch || !alive) return
      path += 'action'
      data = { expected_version: item.version, action: kind }
    }
    unknown.value = true
    const result = await request<ReplyDraft>(path, 'POST', data)
    adopt(result)
    await read(result.id)
    await list()
    unknown.value = false
    notice.value = '已保存并GET回读当前版本。'
  })
}
async function recordManual() {
  await perform(async () => {
    if (!pendingManual.value) {
      if (
        !selected.value ||
        !actions.value?.deliver ||
        unknown.value ||
        !manual.confirmed
      )
        return
      const occurred = awareTimestamp(manual.occurred_at)
      if (Date.parse(occurred) > Date.now())
        throw new Error('请填写已经发生的人工操作时间。')
      if (
        manual.method.trim().length < 2 ||
        manual.evidence_ref.trim().length < 2
      )
        throw new Error('请填写操作方式和可追溯证据。')
      pendingManual.value = {
        draft: selected.value.id,
        data: {
          ...manual,
          occurred_at: occurred,
          request_id: requestId(),
          expected_version: selected.value.version,
        },
      }
    }
    const pending = pendingManual.value
    try {
      await request<ManualActionRecord>(
        `${base()}/drafts/${pending.draft}/manual-actions`,
        'POST',
        pending.data,
      )
    } catch (cause) {
      if (
        cause instanceof ApiError &&
        cause.status >= 400 &&
        cause.status < 500
      )
        pendingManual.value = undefined
      throw cause
    }
    await readRecords()
    pendingManual.value = undefined
    resetManual()
    notice.value = '已GET回读人工自报记录，平台外部未提交。'
  })
}
async function delivery(): Promise<ManualDelivery> {
  if (!selected.value || !actions.value?.deliver)
    throw new Error('请先完成当前版本审阅。')
  return request<ManualDelivery>(
    `${base()}/drafts/${selected.value.id}/delivery?expected_version=${selected.value.version}`,
  )
}
async function agent() {
  await perform(async () => {
    if (workspace.value && (await discard()))
      await openLink('/agent', {
        shop: String(account.shopId),
        mode: 'support_model',
        message: String(workspace.value.message.id),
      })
  })
}
function changeLanguage(event: unknown) {
  language.value = Number((event as { detail: { value: string } }).detail.value)
    ? 'zh'
    : 'en'
}
function policiesChanged() {
  workspace.value = undefined
  selected.value = undefined
  records.value = []
  verified.value = false
  policies.value = []
  confirmed.value = false
  notice.value = '政策已回读。请重新选择消息，核对当前适用政策与草稿。'
}
useDidShow(() => {
  void perform(async () => {
    if (
      dirty.value ||
      evidenceDirty.value ||
      pendingManual.value ||
      policyEditing.value
    ) {
      notice.value = '保留当前未保存内容，请核对后继续。'
      return
    }
    await list()
    if (params.value.shop && Number(params.value.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不同。')
    const id = Number(params.value.draft || selected.value?.id)
    if (id > 0) await read(id)
    else if (Number(params.value.message) > 0)
      workspace.value = await request<SupportWorkspace>(
        `${base()}/messages/${Number(params.value.message)}`,
      )
    params.value = {}
    verified.value = false
    policies.value = []
    unknown.value = false
  })
})
</script>
<template>
  <view class="screen">
    <view class="hero"
      ><text class="eyebrow">SOLOOPS · SUPPORT</text
      ><text class="title">每条诉求，都有清楚的回应。</text
      ><text class="muted"
        >核对消息、订单与政策，审阅完整回复并登记人工处理。</text
      ></view
    >
    <view v-if="error" class="error">{{ error }}</view
    ><view v-if="notice" class="hint">{{ notice }}</view>
    <view v-if="unknown" class="error">操作结果待核对，请刷新历史后继续。</view>
    <view class="card"
      ><text class="section-title">客户消息</text
      ><input
        v-model="search"
        :maxlength="120"
        :disabled="busy"
        placeholder="消息 / 订单关键词"
      /><button :disabled="busy" @tap="perform(() => list(0))">查找</button>
      <text v-if="!messages.length" class="muted"
        >暂无匹配消息，请先导入消息文件。</text
      >
      <button
        v-for="item in messages"
        :key="item.id"
        :disabled="busy"
        @tap="choose(item.id)"
      >
        {{ item.message_id }} · {{ item.order_id || '未关联订单' }} ·
        {{ item.channel }}
      </button>
      <view class="row"
        ><button
          :disabled="busy || offset === 0"
          @tap="perform(() => list(offset - 50))"
        >
          上一页</button
        ><text>{{ offset / 50 + 1 }}</text
        ><button
          :disabled="busy || messages.length < 50"
          @tap="perform(() => list(offset + 50))"
        >
          下一页
        </button></view
      >
    </view>
    <view v-if="workspace" class="card"
      ><text class="section-title">消息 {{ workspace.message.message_id }}</text
      ><text class="prose">{{ workspace.message.body }}</text
      ><text
        >{{ workspace.message.language }} ·
        {{ supportTime(workspace.message.sent_at, timezone) }}</text
      ><SourceList
        :sources="[workspace.message.source]"
        :shop-id="account.shopId"
      />
      <text class="label">关联订单核验</text
      ><text v-if="!workspace.orders.length" class="hint"
        >暂无可关联订单，核对身份后再处理。</text
      >
      <view v-for="order in workspace.orders" :key="order.source.row_id"
        ><text
          >{{ order.order_id }} / {{ order.line_id }} / {{ order.sku }}</text
        ><text>{{ order.status }} · {{ order.fulfillment_status }}</text
        ><SourceList :sources="[order.source]" :shop-id="account.shopId"
      /></view>
      <view class="row"
        ><text>已核对消息身份与全部订单行</text
        ><switch
          :checked="verified"
          :disabled="busy || !workspace.orders.length"
          @change="verified = checked($event)"
      /></view>
      <text class="label">适用政策（最多10条）</text
      ><view v-for="policy in workspace.policies" :key="policy.id"
        ><text>{{ policy.data?.title }} · v{{ policy.number }}</text
        ><text class="prose">{{ policy.data?.text }}</text
        ><text class="hint"
          >{{ policy.data?.source }} / {{ policy.data?.source_version }} ·
          {{ policy.data?.market }} / {{ policy.data?.channel }} /
          {{ policy.data?.language }} · {{ policy.data?.valid_from }} —
          {{ policy.data?.valid_until || '长期' }}</text
        ><switch
          :checked="policies.includes(policy.id)"
          :disabled="busy"
          @change="togglePolicy(policy.id, $event)"
      /></view>
      <button class="primary" :disabled="busy || unknown" @tap="generate">
        生成本地回复候选</button
      ><button :disabled="busy" @tap="agent">准备 AI 客服候选</button>
      <button
        v-for="item in workspace.drafts"
        :key="item.id"
        :disabled="busy"
        @tap="inspect(item.id)"
      >
        草稿 #{{ item.id }} · {{ replyStatus[item.status] || item.status }}
      </button>
    </view>
    <view v-if="selected" class="card"
      ><text class="section-title"
        >草稿 #{{ selected.id }} · v{{ selected.version }}</text
      ><text
        >{{ replyStatus[selected.status] || selected.status }} ·
        {{ selected.source_status }} · {{ selected.engine }}</text
      ><text class="hint"
        >店铺 #{{ account.shopId }} · R1 · 平台外部未提交</text
      >
      <template v-if="selected.snapshot">
        <text class="label">客户原文</text
        ><text class="prose">{{ selected.snapshot.message.body }}</text
        ><SourceList
          :sources="[
            selected.snapshot.message.source,
            ...selected.snapshot.orders.map((o) => o.source),
          ]"
          :shop-id="account.shopId"
        />
        <text
          >订单关联：{{
            selected.snapshot.order_verified ? '已人工核验' : '未核验'
          }}</text
        ><text
          v-for="order in selected.snapshot.orders"
          :key="order.source.row_id"
          >{{ order.order_id }} / {{ order.line_id }} / {{ order.sku }} ·
          {{ order.status }} / {{ order.fulfillment_status }}</text
        >
        <text
          v-for="policy in selected.snapshot.policies"
          :key="policy.id"
          class="prose"
          >{{ policy.data?.title }} v{{ policy.number }}：{{
            policy.data?.text
          }}（{{ policy.data?.source }} /
          {{ policy.data?.source_version }}）</text
        >
        <text class="label">诉求与人工接管</text
        ><text v-for="intent in selected.snapshot.intents" :key="intent">{{
          intentLabels[intent] || intent
        }}</text
        ><text
          v-for="reason in selected.snapshot.reasons"
          :key="reason"
          class="error"
          >{{ reason }}</text
        ><text class="prose">{{ selected.snapshot.handoff_summary }}</text
        ><text
          v-for="fact in selected.snapshot.model_facts"
          :key="fact"
          class="hint"
          >{{ fact }}</text
        >
        <text class="label">已保存回复全文</text
        ><text class="prose">{{
          selected.snapshot.reply || '尚无正文，请人工补充。'
        }}</text>
        <view v-if="actions?.edit"
          ><text class="label">编辑回复</text
          ><textarea
            v-model="reply"
            :maxlength="6000"
            :auto-height="true"
            :disabled="busy || !!pendingManual"
          /><text v-if="dirty" class="hint">修改未保存，保存后需重新审阅。</text
          ><button
            :disabled="busy || unknown || !dirty || !!pendingManual"
            @tap="mutate('edit')"
          >
            保存回复
          </button></view
        >
        <picker
          :range="['English', '中文']"
          :value="language === 'zh' ? 1 : 0"
          :disabled="busy"
          @change="changeLanguage"
          ><view class="field"
            >目标语言：{{ language }}（须核对正文，不会自动翻译）</view
          ></picker
        >
        <view class="row"
          ><text>已核对全文、目标语言和全部接管原因</text
          ><switch
            :checked="confirmed"
            :disabled="busy || dirty"
            @change="confirmed = checked($event)"
        /></view>
        <button
          class="primary"
          :disabled="
            busy || unknown || !actions?.review || !confirmed || !!pendingManual
          "
          @tap="mutate('review')"
        >
          确认当前版本审阅</button
        ><text class="hint"
          >审阅版本 {{ selected.reviewed_version || '未审阅' }} / 语言
          {{ selected.reviewed_language || '待确认' }}</text
        >
        <button
          :disabled="busy || unknown || !actions?.handoff"
          @tap="mutate('handoff')"
        >
          转人工接管</button
        ><button
          :disabled="busy || unknown || !actions?.archive"
          @tap="mutate('archive')"
        >
          归档</button
        ><button
          :disabled="busy || unknown || !actions?.reopen"
          @tap="mutate('reopen')"
        >
          重新打开
        </button>
        <ReviewedDelivery
          :context-key="`${selected.id}:${selected.version}:${language}`"
          :allowed="!!actions?.deliver"
          :disabled="busy || dirty || unknown || !!pendingManual"
          :load-artifact="delivery"
        />
        <text class="label">登记已发生的人工处理</text
        ><text class="hint"
          >人工自报证据，不代表系统已发送或平台已受理。时间需包含时区。</text
        >
        <input
          v-model="manual.occurred_at"
          :disabled="busy || !!pendingManual"
          placeholder="2026-10-11T09:00:00+08:00"
          :maxlength="40"
        /><input
          v-model="manual.method"
          :disabled="busy || !!pendingManual"
          placeholder="操作方式，例如原渠道人工回复"
          :maxlength="80"
        /><input
          v-model="manual.evidence_ref"
          :disabled="busy || !!pendingManual"
          placeholder="可追溯凭据 / 工单编号"
          :maxlength="500"
        /><textarea
          v-model="manual.note"
          :disabled="busy || !!pendingManual"
          placeholder="处理说明"
          :maxlength="1000"
        />
        <view class="row"
          ><text>确认是已发生的人工操作</text
          ><switch
            :checked="manual.confirmed"
            :disabled="busy || !!pendingManual"
            @change="manual.confirmed = checked($event)"
        /></view>
        <button
          :disabled="
            busy ||
            (!pendingManual &&
              (!actions?.deliver || !manual.confirmed || unknown))
          "
          @tap="recordManual"
        >
          {{ pendingManual ? '按原请求恢复人工记录并回读' : '保存人工记录' }}
        </button> </template
      ><text v-else class="muted">来源及正文已清除，仅保留处理记录。</text>
      <text class="label">人工操作历史</text
      ><text v-if="!records.length" class="muted">暂无人工记录。</text
      ><view v-for="record in records" :key="record.id"
        ><text
          >#{{ record.id }} / v{{ record.draft_version }} ·
          {{ supportTime(record.occurred_at, timezone) }}</text
        ><text class="prose"
          >{{ record.details?.method }} / {{ record.details?.evidence_ref }} /
          {{ record.details?.note || '详情为空或已清除' }}</text
        ><text class="hint">卖家自报 · 外部未提交</text></view
      ><button
        v-if="moreRecords"
        :disabled="busy"
        @tap="perform(() => readRecords(records[records.length - 1]?.id))"
      >
        加载更早记录
      </button>
    </view>
    <view class="card"
      ><text class="section-title">最近草稿历史</text
      ><button :disabled="busy || !!pendingManual" @tap="refresh">
        刷新并GET回读</button
      ><button
        v-for="item in history"
        :key="item.id"
        :disabled="busy"
        @tap="inspect(item.id)"
      >
        #{{ item.id }} ·
        {{ item.snapshot?.message.message_id || '正文已清除' }} ·
        {{ replyStatus[item.status] || item.status }} · {{ item.source_status }}
      </button></view
    >
    <SupportPolicies
      v-if="account.shopId"
      :key="`${account.shopId}:${account.session?.session_id}`"
      :market="shop?.market || ''"
      :disabled="actionBusy || dirty || evidenceDirty || !!pendingManual"
      @working="policyBusy = $event"
      @editing="policyEditing = $event"
      @changed="policiesChanged"
    />
  </view>
</template>
<style scoped>
.prose {
  display: block;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
