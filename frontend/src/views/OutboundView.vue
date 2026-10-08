<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { linkedId, linkedShop, revealRecord } from '@/composables/deepLink'
import { identityApi } from '@/api/identity'
import { operationsApi } from '@/api/operations'
import { outboundApi } from '@/api/outbound'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import type { OperationRun } from '@/types/operations'
import { mailLabels, type MailChannel, type OutboundMail } from '@/types/outbound'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import OutboundMailReview from '@/components/OutboundMailReview.vue'
const route = useRoute()
const shops = ref<Shop[]>([])
const shop = ref(0)
const identity = ref('user_import')
const sourceChannel = ref('generic')
const channel = ref<MailChannel | null>(null)
const messages = ref<OutboundMail[]>([])
const runs = ref<OperationRun[]>([])
const runId = ref(0)
const selected = ref<OutboundMail | null>(null)
const before = ref<number | null>(null)
const busy = ref(false)
const error = ref('')
const confirmed = ref(false)
const code = ref('')
const timezone = computed(() => shops.value.find((s) => s.id === shop.value)?.timezone ?? 'UTC')
const label = (value: string) => mailLabels[value] ?? value
let epoch = 0
async function load(): Promise<void> {
  const token = ++epoch
  selected.value = channel.value = null
  messages.value = []
  runs.value = []
  before.value = null
  confirmed.value = false
  code.value = error.value = ''
  if (!shop.value) return
  busy.value = true
  try {
    const [connection, page, checks] = await Promise.all([
      outboundApi.channel(shop.value),
      outboundApi.list(shop.value),
      operationsApi.runs(shop.value, identity.value, sourceChannel.value),
    ])
    if (token !== epoch) return
    channel.value = connection
    messages.value = page.items
    before.value = page.next_before_id
    runs.value = checks.filter((r) => r.source_status === 'current')
    runId.value = runs.value[0]?.id ?? 0
    selected.value = messages.value[0] ?? null
  } catch (cause) {
    if (token === epoch) error.value = errorMessage(cause)
  } finally {
    if (token === epoch) busy.value = false
  }
}
async function connectAction(action: 'connect' | 'verify' | 'disconnect'): Promise<void> {
  if (!channel.value || busy.value || (action === 'connect' && !confirmed.value)) return
  busy.value = true
  error.value = ''
  try {
    channel.value =
      action === 'connect'
        ? await outboundApi.connect(shop.value)
        : action === 'verify'
          ? await outboundApi.verify(shop.value, channel.value.id!, code.value)
          : await outboundApi.disconnect(shop.value, channel.value.id!)
    selected.value = null
    confirmed.value = false
    code.value = ''
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
function updated(mail: OutboundMail): void {
  if (mail.shop_id !== shop.value) return
  selected.value = mail
  messages.value = [mail, ...messages.value.filter((m) => m.id !== mail.id)]
}
async function create(): Promise<void> {
  busy.value = true
  error.value = ''
  try {
    updated(await outboundApi.create(shop.value, runId.value))
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function more(): Promise<void> {
  if (!before.value) return
  busy.value = true
  try {
    const page = await outboundApi.list(shop.value, before.value)
    messages.value.push(...page.items)
    before.value = page.next_before_id
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
onMounted(async () => {
  try {
    shops.value = await identityApi.shops()
    shop.value = linkedShop(shops.value, route.query.shop)
    const id = linkedId(route.query.mail)
    if (['synthetic', 'user_import'].includes(String(route.query.identity)))
      identity.value = String(route.query.identity)
    if (['generic', 'shopify', 'amazon', 'other'].includes(String(route.query.channel)))
      sourceChannel.value = String(route.query.channel)
    await load()
    if (id) {
      selected.value = null
      selected.value = await outboundApi.get(shop.value, id)
      await revealRecord('linked-mail')
    }
  } catch (cause) {
    selected.value = null
    error.value = errorMessage(cause)
  }
})
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>测试外发</h1>
      <p>把已核对的经营摘要，送到你自己的测试邮箱。</p>
    </div>
    <span class="outline-label">独立 R2 审批</span>
  </div>
  <FeedbackBanner :message="error" />
  <p v-if="!shops.length">请先在经营资料中添加店铺。</p>
  <template v-else>
    <section class="form-panel" aria-label="测试外发范围">
      <fieldset :disabled="busy">
        <legend>选择店铺与检查范围</legend>
        <div class="form-grid">
          <div class="form-field">
            <label for="mail-shop">外发店铺</label
            ><select id="mail-shop" v-model="shop" @change="load">
              <option v-for="s in shops" :key="s.id" :value="s.id">
                {{ s.name }} · {{ s.code }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label for="mail-identity">摘要数据身份</label
            ><select id="mail-identity" v-model="identity" @change="load">
              <option value="user_import">用户导入文件</option>
              <option value="synthetic">合成测试数据</option>
            </select>
          </div>
          <div class="form-field">
            <label for="mail-channel">摘要来源渠道</label
            ><select id="mail-channel" v-model="sourceChannel" @change="load">
              <option value="generic">通用 / 自建表</option>
              <option value="shopify">Shopify</option>
              <option value="amazon">Amazon</option>
              <option value="other">其他来源</option>
            </select>
          </div>
        </div>
        <button class="button secondary small" @click="load">刷新通道与记录</button>
      </fieldset>
    </section>
    <section
      v-if="channel"
      class="form-panel section-block connection-panel"
      aria-label="本人测试邮箱连接"
    >
      <h2>本人测试邮箱 · {{ label(channel.status) }}</h2>
      <p v-if="!channel.configured">
        尚未配置此店铺的测试外发通道。需先提供已授权的自有发送账号、已验证域名与本人测试收件地址。完成配置后可在此验证邮箱；现有本地检查和审批继续可用。
      </p>
      <template v-else
        ><p>Resend · {{ channel.sender }} → {{ channel.recipient }}</p>
        <p>
          仅此部署名单内的本人测试邮箱可接收；验证邮件不含业务数据。账号 24 小时最多提交 10
          份经营摘要，间隔至少 60 秒。
        </p>
        <fieldset :disabled="busy">
          <template v-if="!['active', 'verifying', 'unknown'].includes(channel.status)">
            <p>验证邮件主题：{{ channel.verification_subject }}</p>
            <p>{{ channel.verification_template }}</p>
            <label class="check-label"
              ><input v-model="confirmed" type="checkbox" />我控制以上账号与测试邮箱，批准发送 1
              封验证邮件，理解邮件不可撤回及可能产生通道费用</label
            ><button
              class="button primary"
              :disabled="!confirmed"
              @click="connectAction('connect')"
            >
              连接并发送验证邮件
            </button>
          </template>
          <form
            v-if="['verifying', 'unknown'].includes(channel.status)"
            class="verify-form"
            @submit.prevent="connectAction('verify')"
          >
            <p>
              请从本人测试收件箱读取 8 位验证码，15 分钟有效，最多 5
              次尝试。重复连接不会再发同一验证邮件。
            </p>
            <label for="mail-code">邮箱验证码</label
            ><input
              id="mail-code"
              v-model="code"
              inputmode="numeric"
              pattern="[0-9]{8}"
              maxlength="8"
              required
              autocomplete="one-time-code"
            /><button class="button primary">验证本人测试邮箱</button>
          </form>
          <button
            v-if="channel.id && channel.status !== 'revoked'"
            class="button secondary small"
            @click="connectAction('disconnect')"
          >
            撤销此通道连接
          </button>
        </fieldset>
      </template>
    </section>
    <section class="form-panel section-block" aria-label="准备经营摘要">
      <h2>准备待审摘要</h2>
      <p>
        正文来自已保存的今日运营检查，可修改后重新审阅。<RouterLink to="/agent"
          >前往任务执行台</RouterLink
        >完成检查与保存。
      </p>
      <div class="form-field">
        <label for="mail-run">关联运营检查</label
        ><select id="mail-run" v-model="runId" :disabled="busy">
          <option :value="0">{{ runs.length ? '选择当前检查' : '当前范围暂无已保存检查' }}</option>
          <option v-for="run in runs" :key="run.id" :value="run.id">
            检查 #{{ run.id }} ·
            {{ new Date(run.created_at).toLocaleString('zh-CN', { timeZone: timezone }) }}
          </option>
        </select>
      </div>
      <button
        class="button primary"
        :disabled="busy || !runId || channel?.status !== 'active'"
        @click="create"
      >
        生成外发预览
      </button>
    </section>
    <section v-if="messages.length" class="form-panel section-block">
      <h2>外发记录</h2>
      <div class="button-row">
        <button
          v-for="mail in messages"
          :key="mail.id"
          class="button secondary small"
          :disabled="busy"
          @click="selected = mail"
        >
          摘要 #{{ mail.id }} · {{ label(mail.status) }}</button
        ><button v-if="before" class="button secondary small" :disabled="busy" @click="more">
          加载更早记录
        </button>
      </div>
    </section>
    <OutboundMailReview
      id="linked-mail"
      v-if="selected"
      :key="`${shop}-${selected.id}`"
      :mail="selected"
      :timezone="timezone"
      @updated="updated"
    />
  </template>
</template>
<style scoped>
fieldset {
  border: 0;
  padding: 0;
  min-width: 0;
}
legend {
  font-weight: 600;
  margin-bottom: 20px;
}
p {
  margin: 14px 0;
  line-height: 1.7;
}
.connection-panel {
  overflow-wrap: anywhere;
}
.verify-form {
  display: grid;
  gap: 12px;
  margin: 20px 0;
}
.verify-form input {
  max-width: 300px;
}
.verify-form .button {
  justify-self: start;
}
.check-label {
  margin: 18px 0;
}
</style>
