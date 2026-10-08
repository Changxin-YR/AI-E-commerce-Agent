<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { identityApi } from '@/api/identity'
import { agentApi } from '@/api/agent'
import { listingsApi } from '@/api/listings'
import { supportApi } from '@/api/support'
import { errorMessage } from '@/api/client'
import type {
  AgentAction,
  AgentBudget,
  AgentInput,
  AgentRun,
  ModelStatus,
  SkillDefinition,
} from '@/types/agent'
import { agentLabels } from '@/types/agent'
import type { Shop } from '@/types/identity'
import type { ProductFacts } from '@/types/listings'
import type { MessageFacts } from '@/types/support'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import AgentRunReview from '@/components/AgentRunReview.vue'
import InternalAuthorizations from '@/components/InternalAuthorizations.vue'
import type { InternalAuthorization } from '@/api/authorizations'
import AppliedRules from '@/components/AppliedRules.vue'
import { applyRule, type BusinessRule } from '@/api/businessRules'

const shops = ref<Shop[]>([])
const shopId = ref(0)
const runs = ref<AgentRun[]>([])
const selected = ref<AgentRun | null>(null)
const skills = ref<SkillDefinition[]>([])
const model = ref<ModelStatus | null>(null)
const products = ref<ProductFacts[]>([])
const messages = ref<MessageFacts[]>([])
const query = ref('')
const rulesPending = ref(true)
const activeRule = ref(false)
function rulesLoaded(rule: BusinessRule): void {
  applyRule(form.scope, rule)
  activeRule.value = rule.active
}
const error = ref('')
const busy = ref(false)
const controlling = ref(false)
const driving = ref(false)
let alive = true
const form = reactive<AgentInput>({
  request_id: '',
  template: 'daily',
  goal: '',
  product_id: null,
  message_id: null,
  allow_model: false,
  budget: { max_steps: 12, max_seconds: 120, max_cost_usd: '0' },
  scope: {
    start_at: new Date(Date.now() - 7 * 86400000).toISOString(),
    end_at: new Date().toISOString(),
    timezone: 'Asia/Shanghai',
    currency: 'USD',
    data_identity: 'user_import',
    intent: 'low_margin',
    channel: 'generic',
    max_age_hours: 24,
    min_quantity: 1,
    max_margin_percent: '20',
  },
})
const productOptions = computed(() =>
  products.value.filter((p) => p.source.data_identity === form.scope.data_identity),
)
const messageOptions = computed(() =>
  messages.value.filter(
    (m) => m.source.data_identity === form.scope.data_identity && m.channel === form.scope.channel,
  ),
)

function accept(run: AgentRun): void {
  if (!alive || shopId.value !== run.shop_id) return
  if (!selected.value || (selected.value.id === run.id && run.version >= selected.value.version))
    selected.value = run
}
async function readOptions(): Promise<void> {
  if (!shopId.value) return
  const shop = shopId.value
  try {
    const [p, m] = await Promise.all([
      listingsApi.products(shop, query.value, 0),
      supportApi.messages(shop, query.value),
    ])
    if (shopId.value === shop) {
      products.value = p
      messages.value = m
    }
  } catch (cause) {
    error.value = errorMessage(cause)
  }
}
async function loadShop(): Promise<void> {
  if (!shopId.value || driving.value) return
  selected.value = null
  const shop = shops.value.find((s) => s.id === shopId.value)
  if (shop) {
    form.scope.timezone = shop.timezone
    form.scope.currency = shop.currency
  }
  busy.value = true
  error.value = ''
  try {
    const id = shopId.value
    const [history, registry, status] = await Promise.all([
      agentApi.runs(id),
      agentApi.skills(id),
      agentApi.model(id),
    ])
    runs.value = history
    skills.value = registry
    model.value = status
    if (history[0]) selected.value = await agentApi.get(id, history[0].id)
    await readOptions()
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function refresh(): Promise<void> {
  if (!shopId.value || controlling.value) return
  const shop = shopId.value
  try {
    const history = await agentApi.runs(shop)
    if (shopId.value !== shop) return
    runs.value = history
    if (selected.value) accept(await agentApi.get(shop, selected.value.id))
  } catch (cause) {
    error.value = errorMessage(cause)
  }
}
async function inspect(id: number): Promise<void> {
  if (busy.value) return
  try {
    selected.value = await agentApi.get(shopId.value, id)
  } catch (cause) {
    error.value = errorMessage(cause)
  }
}
async function drive(): Promise<void> {
  driving.value = true
  // One server-bounded node per request. Refreshing or revisiting never starts work.
  for (let i = 0; i < 100 && alive && driving.value && selected.value?.status === 'ready'; i++) {
    accept(await agentApi.act(selected.value, 'advance'))
  }
  driving.value = false
}
async function start(): Promise<void> {
  if (busy.value || !shopId.value || rulesPending.value) return
  busy.value = true
  error.value = ''
  selected.value = null
  try {
    selected.value = await agentApi.start(shopId.value, {
      ...form,
      request_id: crypto.randomUUID(),
    })
    await drive()
    await refresh()
  } catch (cause) {
    error.value = errorMessage(cause)
    driving.value = false
  } finally {
    busy.value = false
  }
}
async function act(
  action: AgentAction,
  budget?: AgentBudget,
  authorizationId?: number,
): Promise<void> {
  if (!selected.value || controlling.value) return
  if (busy.value && !['pause', 'cancel'].includes(action)) return
  driving.value = false
  controlling.value = true
  error.value = ''
  const current = selected.value
  try {
    const latest = await agentApi.get(current.shop_id, current.id)
    accept(await agentApi.act(latest, action, budget, authorizationId))
    if (['approve', 'resume', 'advance', 'use_authorization'].includes(action)) {
      busy.value = true
      await drive()
    }
  } catch (cause) {
    error.value = errorMessage(cause)
    driving.value = false
  } finally {
    controlling.value = false
    if (!driving.value) busy.value = false
    await refresh()
  }
}
async function startAuthorized(grant: InternalAuthorization): Promise<void> {
  if (busy.value || controlling.value || grant.shop_id !== shopId.value) return
  busy.value = true
  error.value = ''
  selected.value = null
  try {
    selected.value = await agentApi.start(grant.shop_id, {
      ...form,
      request_id: crypto.randomUUID(),
      template: 'daily',
      scope: grant.scope,
      authorization_id: grant.id,
      allow_model: false,
      goal: '',
      product_id: null,
      message_id: null,
    })
    await drive()
  } catch (cause) {
    error.value = errorMessage(cause)
    driving.value = false
  } finally {
    busy.value = false
    await refresh()
  }
}
onMounted(async () => {
  window.addEventListener('focus', refresh)
  try {
    shops.value = await identityApi.shops()
    shopId.value = shops.value[0]?.id ?? 0
    await loadShop()
  } catch (cause) {
    error.value = errorMessage(cause)
  }
})
onUnmounted(() => {
  alive = false
  driving.value = false
  window.removeEventListener('focus', refresh)
})
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>受控任务，一步一步有据可查。</h1>
      <p>选择流程，查看依据和分支，批准内部写入，随时查看执行记录。</p>
    </div>
    <span class="outline-label">Agent 执行台</span>
  </div>
  <FeedbackBanner :message="error" />
  <p v-if="!shops.length">先在经营资料中添加店铺，再导入商品、订单或消息。</p>
  <template v-else>
    <label class="agent-shop"
      >任务店铺<select v-model.number="shopId" :disabled="busy || controlling" @change="loadShop">
        <option v-for="shop in shops" :key="shop.id" :value="shop.id">{{ shop.name }}</option>
      </select></label
    >
    <section class="section-block">
      <div class="section-title">
        <h2>启动任务</h2>
        <span>{{
          model?.status === 'configured'
            ? `模型已配置：${model.model}`
            : '模型待配置 · 固定流程可用'
        }}</span>
      </div>
      <form @submit.prevent="start">
        <AppliedRules
          :shop="shopId"
          :scope="form.scope"
          @loaded="rulesLoaded"
          @pending="rulesPending = $event"
        />
        <fieldset class="analysis-fields" :disabled="busy || controlling">
          <label
            >执行流程<select v-model="form.template">
              <option value="daily">今日运营：检查 → 异常候选 → 核验</option>
              <option value="analysis">销售与已知毛利（全店所选身份）</option>
              <option value="listing">商品事实 → Listing 模板草稿</option>
              <option value="support">消息 → 人工接管草稿</option>
              <option value="natural">自然语言目标（需要模型）</option>
            </select></label
          >
          <label
            >数据身份<select v-model="form.scope.data_identity">
              <option value="user_import">用户导入</option>
              <option value="synthetic">合成测试</option>
            </select></label
          >
          <label
            >检查渠道<select v-model="form.scope.channel">
              <option value="generic">通用</option>
              <option value="amazon">Amazon</option>
              <option value="shopify">Shopify</option>
            </select></label
          >
          <label>币种<input v-model="form.scope.currency" required maxlength="3" /></label>
          <template v-if="['listing', 'support', 'natural'].includes(form.template)">
            <label
              >查找商品或消息<input
                v-model="query"
                placeholder="关键词，最多显示 50 项"
                @change="readOptions"
            /></label>
            <label v-if="form.template !== 'support'"
              >目标商品<select v-model="form.product_id">
                <option :value="null">未选择</option>
                <option
                  v-for="product in productOptions"
                  :key="product.product_id"
                  :value="product.product_id"
                >
                  {{ product.sku }} · {{ product.name }}
                </option>
              </select></label
            >
            <label v-if="form.template !== 'listing'"
              >目标消息<select v-model="form.message_id">
                <option :value="null">未选择</option>
                <option v-for="message in messageOptions" :key="message.id" :value="message.id">
                  {{ message.message_id }} · {{ message.body.slice(0, 60) }}
                </option>
              </select></label
            >
          </template>
          <template v-if="form.template === 'natural'">
            <label class="full-width"
              >运营目标<textarea
                v-model="form.goal"
                maxlength="500"
                required
                placeholder="例如：检查已导入订单，找出需要核对的事项"
              />
            </label>
            <label class="full-width"
              ><span
                ><input v-model="form.allow_model" type="checkbox" /> 同意将本次目标文本发送至配置的
                OpenAI 模型，并使用下方美元预算</span
              ></label
            >
          </template>
        </fieldset>
        <details>
          <summary>数据窗口、规则与任务预算</summary>
          <fieldset class="analysis-fields" :disabled="busy || controlling">
            <label>订单起始时间（含时区）<input v-model="form.scope.start_at" required /></label
            ><label>订单结束时间（不包含）<input v-model="form.scope.end_at" required /></label>
            <label
              >库存时效（小时）<input
                v-model.number="form.scope.max_age_hours"
                :disabled="activeRule || rulesPending"
                type="number"
                min="1"
                max="720"
                required
            /></label>
            <label
              >低毛利率上限（%）<input
                v-model="form.scope.max_margin_percent"
                :disabled="activeRule || rulesPending"
                type="number"
                min="-1000"
                max="100"
                step="0.01"
                required
            /></label>
            <label
              >执行步数上限<input
                v-model.number="form.budget.max_steps"
                type="number"
                min="1"
                max="100"
                required /></label
            ><label
              >累计执行秒数上限<input
                v-model.number="form.budget.max_seconds"
                type="number"
                min="1"
                max="3600"
                required
            /></label>
            <label
              >模型预算（USD）<input
                v-model="form.budget.max_cost_usd"
                type="number"
                min="0"
                max="10"
                step="0.000001"
                required
            /></label>
          </fieldset>
        </details>
        <p>
          固定流程使用本地规则或事实模板，模型费用为
          0。自然语言仅用于选择受控流程，模型不会计算金额或改写业务事实。
        </p>
        <button class="button primary" :disabled="busy || controlling || rulesPending">
          {{ busy ? '正在执行…' : '启动并运行' }}
        </button>
      </form>
    </section>
    <div class="section-title">
      <h2>执行记录</h2>
      <button class="button secondary" :disabled="controlling" @click="refresh">刷新任务</button>
    </div>
    <div class="button-row">
      <button
        v-for="run in runs"
        :key="run.id"
        class="button secondary small"
        :disabled="busy || controlling"
        @click="inspect(run.id)"
      >
        #{{ run.id }} · {{ agentLabels[run.template] }} · {{ agentLabels[run.status] }}
      </button>
    </div>
    <p v-if="!runs.length">尚未运行任务。启动后，实际结果会保存在这里。</p>
    <AgentRunReview v-if="selected" :run="selected" :busy="busy || controlling" @action="act" />
    <InternalAuthorizations
      :shop="shopId"
      :run="selected"
      :busy="busy || controlling"
      @use="act('use_authorization', undefined, $event)"
      @start="startAuthorized"
      @inspect="inspect"
    />
    <details class="section-block">
      <summary>内置技能与权限（{{ skills.length }} 项）</summary>
      <article v-for="skill in skills" :key="skill.name" class="analysis-line">
        <h3>{{ skill.purpose }}</h3>
        <p>
          {{ skill.name }} v{{ skill.version }} · {{ skill.risk }} ·
          {{ skill.side_effects ? '内部写入需审批' : '只读' }}
        </p>
        <p>{{ skill.read_scope }}；{{ skill.write_scope }}</p>
        <p>{{ skill.failure_policy }}</p>
        <p>{{ skill.confirmation }}</p>
        <details>
          <summary>完整输入、输出与权限声明</summary>
          <pre class="agent-contract">{{ JSON.stringify(skill, null, 2) }}</pre>
        </details>
      </article>
    </details>
  </template>
</template>
<style scoped>
.agent-shop {
  display: grid;
  gap: 8px;
  max-width: 460px;
}
.agent-contract {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 400px;
  overflow-y: auto;
  font-size: 12px;
}
input[type='checkbox'] {
  width: 18px;
  height: 18px;
  vertical-align: middle;
  margin-right: 8px;
}
</style>
