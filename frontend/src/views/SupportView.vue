<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { useRecordLink } from '@/composables/useRecordLink'
import { linkedId, linkedShop, revealRecord, returnTaskQuery } from '@/composables/deepLink'
import { supportApi } from '@/api/support'
import { identityApi } from '@/api/identity'
import { ApiError, errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import {
  replyStatus,
  supportTime,
  type MessageFacts,
  type ReplyDraft,
  type SupportWorkspace,
} from '@/types/support'
import { sourceStatus } from '@/types/listings'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import ManualMessage from '@/components/ManualMessage.vue'
import SupportPolicies from '@/components/SupportPolicies.vue'
import SupportReply from '@/components/SupportReply.vue'
import SupportSource from '@/components/SupportSource.vue'

const shops = ref<Shop[]>([])
const route = useRoute()
const recordLink = useRecordLink()
const editorKey = ref(0)
let navigationEpoch = 0
let alive = true
let writingLink = false
function canNavigate(allowReading = false): boolean {
  if (!dirty.value && !(allowReading ? saving.value || deliveryBusy.value : busy.value)) return true
  error.value = dirty.value
    ? '正文或人工记录尚未保存，请先保存或放弃修改，再离开当前草稿。'
    : '正在保存或读取，请等待操作完成。'
  return false
}
onBeforeRouteLeave(() => canNavigate(true))
onBeforeRouteUpdate(() => writingLink || canNavigate())
function beforeUnload(event: BeforeUnloadEvent): void {
  if (dirty.value || saving.value || deliveryBusy.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}
function discard(): void {
  editorKey.value++
  dirty.value = false
  error.value = ''
}
async function remember(draft?: number, message?: number): Promise<void> {
  writingLink = true
  try {
    await recordLink.write({
      shop: shopId.value,
      draft,
      message,
      ...returnTaskQuery(route.query, shopId.value),
    })
  } finally {
    writingLink = false
  }
}
const shopId = ref(0)
const timezone = computed(
  () => shops.value.find((s) => s.id === shopId.value)?.timezone ?? 'Asia/Shanghai',
)
const market = computed(() => shops.value.find((s) => s.id === shopId.value)?.market ?? '')
const messages = ref<MessageFacts[]>([])
const history = ref<ReplyDraft[]>([])
const workspace = ref<SupportWorkspace | null>(null)
const selected = ref<ReplyDraft | null>(null)
const verified = ref(false)
const selectedPolicies = ref<number[]>([])
const query = ref('')
const offset = ref(0)
const actionBusy = ref(false)
const saving = ref(false)
const deliveryBusy = ref(false)
const busy = computed(() => actionBusy.value || deliveryBusy.value)
const dirty = ref(false)
const error = ref('')
const success = ref('')
async function perform(work: () => Promise<void>, writes = false): Promise<void> {
  if (busy.value) return
  actionBusy.value = true
  saving.value = writes
  error.value = ''
  success.value = ''
  try {
    await work()
  } catch (cause) {
    error.value =
      cause instanceof ApiError && cause.status === 404
        ? '记录不存在、来源已撤销或当前店铺无权访问，请从本店消息或处理记录重新打开。'
        : errorMessage(cause)
  } finally {
    actionBusy.value = false
    saving.value = false
  }
}
async function load(): Promise<void> {
  messages.value = await supportApi.messages(shopId.value, query.value, offset.value)
  history.value = await supportApi.history(shopId.value)
}
function resetEvidence(): void {
  verified.value = false
  selectedPolicies.value = []
}
async function loadShop(): Promise<void> {
  workspace.value = null
  selected.value = null
  resetEvidence()
  offset.value = 0
  messages.value = []
  history.value = []
  if (shopId.value) await perform(load)
}
async function changeShop(): Promise<void> {
  if (Number(route.query.shop) === Number(shopId.value)) return
  await remember()
  await loadShop()
}
async function search(page = 0): Promise<void> {
  offset.value = page
  await perform(load)
}
async function choose(id: number, rememberLink = true): Promise<void> {
  await perform(async () => {
    workspace.value = await supportApi.workspace(shopId.value, id)
    resetEvidence()
    selected.value = null
    if (rememberLink) await remember(undefined, id)
  })
}
async function show(id: number, rememberLink = true): Promise<void> {
  await perform(async () => {
    selected.value = null
    workspace.value = null
    selected.value = await supportApi.get(shopId.value, id)
    resetEvidence()
    if (rememberLink) await remember(id)
  })
}
async function refresh(): Promise<void> {
  if (!shopId.value || dirty.value || busy.value) return
  await perform(async () => {
    await load()
    if (selected.value) selected.value = await supportApi.get(shopId.value, selected.value.id)
    const mid = workspace.value?.message.id
    workspace.value = null
    resetEvidence()
    if (mid && messages.value.some((m) => m.id === mid))
      workspace.value = await supportApi.workspace(shopId.value, mid)
  })
}
async function generate(): Promise<void> {
  if (!workspace.value) return
  await perform(async () => {
    selected.value = await supportApi.generate(
      shopId.value,
      workspace.value!,
      verified.value,
      selectedPolicies.value,
    )
    await load()
    await remember(selected.value.id)
    success.value = '草稿与接管摘要已保存，请核对全部诉求和证据。'
  }, true)
}
async function edit(text: string): Promise<void> {
  if (!selected.value) return
  await perform(async () => {
    selected.value = await supportApi.edit(shopId.value, selected.value!, text)
    dirty.value = false
    await load()
    success.value = '正文已保存。'
  }, true)
}
async function act(action: 'handoff' | 'archive' | 'reopen'): Promise<void> {
  if (!selected.value) return
  await perform(async () => {
    selected.value = await supportApi.act(shopId.value, selected.value!, action)
    await load()
    success.value = '处理状态已保存。'
  }, true)
}
function deliveryUpdated(item: ReplyDraft): void {
  if (selected.value?.id !== item.id) return
  selected.value = item
  history.value = history.value.map((existing) => (existing.id === item.id ? item : existing))
}
function onFocus(): void {
  void refresh()
}
async function restoreRoute(): Promise<void> {
  const epoch = ++navigationEpoch
  workspace.value = null
  selected.value = null
  dirty.value = false
  try {
    shopId.value = linkedShop(shops.value, route.query.shop)
    await loadShop()
    if (epoch !== navigationEpoch) return
    const id = linkedId(route.query.draft)
    if (id) {
      await show(id, false)
      if (alive) await revealRecord('linked-reply')
    } else {
      const messageId = linkedId(route.query.message)
      if (messageId) await choose(messageId, false)
    }
  } catch (cause) {
    shopId.value = 0
    error.value = errorMessage(cause)
  }
}
watch(
  () => route.fullPath,
  (path) => {
    if (route.path === '/support' && !recordLink.isOwn(path)) void restoreRoute()
  },
)
onMounted(async () => {
  window.addEventListener('focus', onFocus)
  window.addEventListener('beforeunload', beforeUnload)
  await perform(async () => {
    shops.value = await identityApi.shops()
  })
  if (alive) await restoreRoute()
})
onUnmounted(() => {
  alive = false
  navigationEpoch++
  window.removeEventListener('focus', onFocus)
  window.removeEventListener('beforeunload', beforeUnload)
})
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>每条诉求，都有清楚的回应。</h1>
      <p>核对消息、订单与政策，准备回复草稿并记录人工处理。</p>
    </div>
    <span class="outline-label">客服工作台</span>
  </div>
  <FeedbackBanner
    message="可使用本地中英文模板，或从消息进入 AI 客服候选流程。请核对完整原文、政策与全部诉求；当前草稿仅在本地保存，物流查询需要可靠轨迹。"
    kind="info"
  />
  <FeedbackBanner :message="error" /><FeedbackBanner :message="success" kind="success" />
  <section class="section-block">
    <div class="section-heading">
      <div class="form-field">
        <label for="support-shop">客服店铺</label
        ><select id="support-shop" v-model="shopId" :disabled="busy || dirty" @change="changeShop">
          <option v-for="shop in shops" :key="shop.id" :value="shop.id">
            {{ shop.name }} · {{ shop.code }}
          </option>
        </select>
      </div>
      <button class="button secondary" :disabled="busy || dirty || !shopId" @click="refresh">
        刷新客服数据
      </button>
    </div>
    <p v-if="!shops.length">请先在<RouterLink to="/settings">经营资料</RouterLink>中添加店铺。</p>
    <p v-if="dirty">
      正文或人工记录尚未保存，保存后可切换消息或刷新依据。
      <button type="button" class="button secondary small" :disabled="busy" @click="discard">
        放弃未保存修改
      </button>
    </p>
  </section>
  <template v-if="shopId">
    <ManualMessage
      :key="`manual-${shopId}`"
      :shop-id="shopId"
      :timezone="timezone"
      @saved="refresh"
    />
    <div class="support-layout">
      <section class="section-block support-inbox" aria-label="客服消息列表">
        <div class="section-heading">
          <h2>消息收件箱</h2>
          <RouterLink class="text-link" to="/imports">导入 CSV / Excel</RouterLink>
        </div>
        <form class="listing-search" @submit.prevent="search()">
          <div class="form-field">
            <label for="message-query">搜索正文 / 消息标识</label
            ><input id="message-query" v-model="query" maxlength="120" :disabled="busy || dirty" />
          </div>
          <button class="button secondary" :disabled="busy || dirty">搜索消息</button>
        </form>
        <p v-if="!messages.length">
          尚无匹配消息。可手工录入，或在数据导入页选择“通用客服消息文件”。
        </p>
        <button
          v-for="message in messages"
          :key="message.id"
          class="listing-history"
          :disabled="busy || dirty"
          @click="choose(message.id)"
        >
          <strong>{{ message.message_id }} · {{ message.language }} · {{ message.channel }}</strong
          ><span class="support-excerpt">{{ message.body }}</span
          ><small
            >{{ supportTime(message.sent_at, timezone) }} ·
            {{ message.source.data_identity === 'synthetic' ? '合成测试' : '用户导入' }}</small
          >
        </button>
        <div class="button-row">
          <button
            class="button secondary"
            :disabled="busy || dirty || offset === 0"
            @click="search(Math.max(0, offset - 50))"
          >
            上一页消息</button
          ><button
            class="button secondary"
            :disabled="busy || dirty || messages.length < 50"
            @click="search(offset + 50)"
          >
            下一页消息
          </button>
        </div>
      </section>
      <section v-if="workspace" class="section-block support-evidence" aria-label="消息证据核验">
        <h2>核验消息 #{{ workspace.message.message_id }}</h2>
        <RouterLink
          :to="{
            path: '/agent',
            query: {
              shop: shopId,
              mode: 'support_model',
              message: workspace.message.id,
              identity: workspace.message.source.data_identity,
              channel: workspace.message.channel,
              ...returnTaskQuery(route.query, shopId),
            },
          }"
          class="button secondary"
          >生成 AI 客服候选</RouterLink
        >
        <p class="preserve-text">{{ workspace.message.body }}</p>
        <SupportSource :shop-id="shopId" :source="workspace.message.source" />
        <h3>订单关联</h3>
        <p>
          待核验订单号：{{
            workspace.message.order_id || '未提供'
          }}。仅列出同店铺、同来源渠道及同数据身份的记录。
        </p>
        <p v-if="!workspace.orders.length">没有匹配订单，当前为待关联；可保存一般解释草稿。</p>
        <div
          v-for="order in workspace.orders"
          :key="order.source.row_id"
          class="support-policy-quote"
        >
          <p>
            {{ order.order_id }} / {{ order.line_id }} · SKU {{ order.sku }} · 订单
            {{ order.status }} · 文件履约状态 {{ order.fulfillment_status }}
          </p>
          <SupportSource :shop-id="shopId" :source="order.source" />
        </div>
        <label v-if="workspace.orders.length" class="check-label"
          ><input
            v-model="verified"
            type="checkbox"
            :disabled="busy || dirty"
          />我已核对客户身份及这条消息与以上订单的关联</label
        >
        <h3>适用政策候选</h3>
        <p>
          按
          {{ workspace.market }}、消息渠道、语言、数据身份和当前有效期筛选；请选择本次引用的政策。
        </p>
        <p v-if="!workspace.policies.length">暂无适用政策，请人工核实。可在下方录入政策与 FAQ。</p>
        <div v-for="policy in workspace.policies" :key="policy.id" class="support-policy-quote">
          <label class="check-label"
            ><input
              v-model="selectedPolicies"
              type="checkbox"
              :value="policy.id"
              :disabled="busy || dirty"
            />{{ policy.data?.title }} · v{{ policy.number }} ·
            {{ policy.data?.source_confirmed ? '人工已核对' : '出处待核对' }}</label
          >
          <p>{{ policy.data?.source }} · {{ policy.data?.source_version }}</p>
          <p class="preserve-text">{{ policy.data?.text }}</p>
        </div>
        <button
          class="button primary"
          :disabled="busy || dirty || selectedPolicies.length > 10"
          @click="generate"
        >
          生成本地回复草稿
        </button>
      </section>
      <section v-else class="section-block support-empty">
        <h2>从一条消息开始</h2>
        <p>选择消息，查看原始来源和待核验订单，再准备草稿。</p>
      </section>
    </div>
    <SupportReply
      :key="editorKey"
      id="linked-reply"
      v-if="selected"
      :item="selected"
      :shop-id="shopId"
      :timezone="timezone"
      :busy="actionBusy"
      @edit="edit"
      @action="act"
      @dirty="dirty = $event"
      @working="deliveryBusy = $event"
      @updated="deliveryUpdated"
    />
    <section class="section-block" aria-label="客服处理历史">
      <h2>处理记录</h2>
      <p>最近 50 份草稿；点击查看依据、正文与存档状态。</p>
      <p v-if="!history.length">尚无草稿记录。</p>
      <button
        v-for="item in history"
        :key="item.id"
        class="listing-history"
        :disabled="busy || dirty"
        @click="show(item.id)"
      >
        <strong
          >查看草稿 #{{ item.id }} · {{ item.snapshot?.message.message_id ?? '来源已清除' }} ·
          {{ replyStatus[item.status] }}</strong
        ><span
          >{{ sourceStatus[item.source_status] }} · 外部未提交 ·
          {{ supportTime(item.updated_at, timezone) }}</span
        >
      </button>
    </section>
    <SupportPolicies
      :key="`policies-${shopId}`"
      :shop-id="shopId"
      :market="market"
      :timezone="timezone"
      :disabled="busy || dirty"
      @changed="refresh"
    />
  </template>
</template>
