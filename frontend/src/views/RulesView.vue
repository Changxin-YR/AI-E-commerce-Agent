<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { identityApi } from '@/api/identity'
import { errorMessage } from '@/api/client'
import { rulesApi, type BusinessRule, type RuleAction, type RuleValues } from '@/api/businessRules'
import type { Shop } from '@/types/identity'
import { supportTime } from '@/types/support'
import FeedbackBanner from '@/components/FeedbackBanner.vue'

const route = useRoute()
const shops = ref<Shop[]>([])
const shopId = ref(0)
const channel = ref('generic')
const identity = ref('user_import')
const current = ref<BusinessRule | null>(null)
const form = ref<RuleValues | null>(null)
const history = ref<BusinessRule[]>([])
const inspected = ref<BusinessRule | null>(null)
const busy = ref(false)
const error = ref('')
const info = ref('')
const confirmed = ref(false)
const labels: Record<string, string> = {
  save: '保存',
  restore: '恢复历史',
  revoke: '撤销',
  reset: '重置',
  default: '初始口径',
}
const noteLabels = {
  target_site: '目标站点',
  warehouse: '常用仓库',
  logistics: '物流偏好',
  brand_voice: '品牌语言规范',
  support_wording: '客服话术偏好',
}

async function load(): Promise<void> {
  if (!shopId.value || busy.value) return
  busy.value = true
  error.value = ''
  info.value = ''
  confirmed.value = false
  inspected.value = null
  current.value = null
  form.value = null
  try {
    const [rule, rows] = await Promise.all([
      rulesApi.current(shopId.value, channel.value, identity.value),
      rulesApi.history(shopId.value, channel.value, identity.value),
    ])
    current.value = rule
    form.value = structuredClone(rule.values)
    history.value = rows
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function change(action: RuleAction): Promise<void> {
  if (!current.value || !form.value || !confirmed.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const values = JSON.parse(JSON.stringify(form.value)) as RuleValues
    if (values.advertising_daily_budget === '') values.advertising_daily_budget = null
    const rule = await rulesApi.change(
      current.value,
      action,
      action === 'save' ? values : undefined,
      action === 'restore' ? inspected.value?.version : undefined,
    )
    current.value = rule
    form.value = structuredClone(rule.values)
    confirmed.value = false
    history.value = await rulesApi.history(shopId.value, channel.value, identity.value)
    info.value = `已${labels[action]}，当前版本 #${rule.version}。后续检查使用新版本。`
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function more(): Promise<void> {
  if (!history.value.length) return
  busy.value = true
  try {
    history.value = await rulesApi.history(
      shopId.value,
      channel.value,
      identity.value,
      history.value.at(-1)?.version,
    )
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
onMounted(async () => {
  try {
    shops.value = await identityApi.shops()
    shopId.value =
      shops.value.find((s) => s.id === Number(route.query.shop))?.id ?? shops.value[0]?.id ?? 0
    if (['generic', 'shopify', 'amazon', 'other'].includes(String(route.query.channel)))
      channel.value = String(route.query.channel)
    if (['synthetic', 'user_import'].includes(String(route.query.identity)))
      identity.value = String(route.query.identity)
    await load()
    if (Number(route.query.version) > 0)
      inspected.value = await rulesApi.get(shopId.value, Number(route.query.version))
  } catch (cause) {
    error.value = errorMessage(cause)
  }
})
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>经营规则</h1>
      <p>把经营判断写清楚，每次检查都有可回看的版本。</p>
    </div>
    <span class="outline-label">卖家确认 · 版本留存</span>
  </div>
  <FeedbackBanner :message="error" />
  <p v-if="info" role="status">{{ info }}</p>
  <p v-if="!shops.length">请先在经营资料中添加店铺。</p>
  <section v-else class="form-panel" aria-label="规则范围">
    <fieldset :disabled="busy">
      <legend>生效范围</legend>
      <div class="form-grid">
        <div class="form-field">
          <label for="rule-shop">规则店铺</label
          ><select id="rule-shop" v-model="shopId" @change="load">
            <option v-for="shop in shops" :key="shop.id" :value="shop.id">
              {{ shop.name }} · {{ shop.code }}
            </option>
          </select>
        </div>
        <div class="form-field">
          <label for="rule-channel">规则渠道</label
          ><select id="rule-channel" v-model="channel" @change="load">
            <option value="generic">通用 / 自建表</option>
            <option value="shopify">Shopify</option>
            <option value="amazon">Amazon</option>
            <option value="other">其他来源</option>
          </select>
        </div>
        <div class="form-field">
          <label for="rule-identity">规则数据身份</label
          ><select id="rule-identity" v-model="identity" @change="load">
            <option value="user_import">用户导入文件</option>
            <option value="synthetic">合成测试数据</option>
          </select>
        </div>
      </div>
      <button type="button" class="button secondary small" @click="load">重新读取规则</button>
    </fieldset>
  </section>
  <form v-if="form && current" class="form-panel section-block" @submit.prevent="change('save')">
    <fieldset :disabled="busy">
      <legend>检查阈值 · 当前版本 #{{ current.version }}</legend>
      <p>
        {{
          current.active ? '当前已启用经营约束' : '当前未启用经营约束，可按次填写检查阈值'
        }}。保存后用于所选范围的今日运营、Agent 检查；独立问数、库存页与利润试算保留各自显式口径。
      </p>
      <div class="form-grid">
        <div class="form-field">
          <label for="rule-age">库存有效小时</label
          ><input
            id="rule-age"
            v-model.number="form.max_age_hours"
            type="number"
            min="1"
            max="720"
            required
          />
        </div>
        <div class="form-field">
          <label for="rule-quantity">低毛利最少销量</label
          ><input
            id="rule-quantity"
            v-model.number="form.min_quantity"
            type="number"
            min="1"
            max="1000000"
            required
          />
        </div>
        <div class="form-field">
          <label for="rule-margin">低毛利阈值（%）</label
          ><input
            id="rule-margin"
            v-model="form.max_margin_percent"
            type="text"
            inputmode="decimal"
            required
          />
        </div>
      </div>
      <p>毛利率不高于阈值才产生核对候选；费用缺失仍标未知。库存安全数量来自每条快照。</p>
      <details class="scope-options">
        <summary>经营偏好与预算记录</summary>
        <p>
          以下是卖家手填参考，保留依据与版本供人工核对；尚未用于生成文案、选仓、物流或广告投放。广告金额是计划值，未授权支出。
        </p>
        <div class="form-grid">
          <div v-for="(label, key) in noteLabels" :key="key" class="form-field">
            <label :for="`rule-${key}`">{{ label }}</label
            ><textarea
              :id="`rule-${key}`"
              v-model="form.notes[key]"
              :maxlength="
                key === 'target_site' || key === 'warehouse'
                  ? 200
                  : key === 'logistics'
                    ? 500
                    : 1000
              "
              rows="3"
            />
          </div>
        </div>
        <div class="form-grid">
          <div class="form-field">
            <label for="rule-ad-budget">每日广告计划金额（留空为未知）</label
            ><input
              id="rule-ad-budget"
              v-model="form.advertising_daily_budget"
              inputmode="decimal"
            />
          </div>
          <div class="form-field">
            <label for="rule-currency">预算币种</label
            ><select id="rule-currency" v-model="form.currency">
              <option
                v-for="c in ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']"
                :key="c"
              >
                {{ c }}
              </option>
            </select>
          </div>
        </div>
      </details>
      <div class="form-field">
        <label for="rule-basis">规则与偏好依据</label
        ><textarea id="rule-basis" v-model="form.basis" maxlength="500" rows="3" required />
      </div>
      <p>自动执行范围：逐次审批。文本偏好不会授予工具、外发或资金操作权限。</p>
      <label class="check-label"
        ><input
          v-model="confirmed"
          type="checkbox"
        />我已核对范围与数值，同意保存或恢复后用于后续检查</label
      >
      <div class="form-actions">
        <button class="button primary" :disabled="!confirmed">保存并启用规则</button
        ><button
          class="button secondary"
          type="button"
          :disabled="!confirmed || !current.active"
          @click="change('revoke')"
        >
          撤销当前规则</button
        ><button
          class="button secondary"
          type="button"
          :disabled="!confirmed"
          @click="change('reset')"
        >
          重置到初始口径
        </button>
      </div>
      <p class="panel-footnote">
        撤销/重置停止约束并恢复 24 小时、1 件、20%
        的初始值，偏好当前值清空；历史保留。旧检查和待审任务须重新运行，已完成记录继续可查。
      </p>
    </fieldset>
  </form>
  <section class="form-panel section-block" aria-label="规则历史">
    <h2>规则历史与依据</h2>
    <p>恢复会建立新版本；不会改写历史检查使用的数值。</p>
    <div class="form-actions">
      <button
        v-for="row in history"
        :key="row.version"
        class="button secondary small"
        @click="inspected = row"
      >
        #{{ row.version }} · {{ labels[row.action] }}
      </button>
    </div>
    <button
      v-if="history.length === 50"
      class="button secondary small"
      :disabled="busy"
      @click="more"
    >
      更早 50 条
    </button>
    <article v-if="inspected" class="data-note section-block" aria-label="历史规则详情">
      <div>
        <h3>版本 #{{ inspected.version }} · {{ labels[inspected.action] }}</h3>
        <p>
          {{
            inspected.created_at
              ? supportTime(
                  inspected.created_at,
                  shops.find((s) => s.id === shopId)?.timezone ?? 'Asia/Shanghai',
                )
              : ''
          }}
          · 前版 #{{ inspected.previous_version
          }}<span v-if="inspected.restored_from"> · 恢复自 #{{ inspected.restored_from }}</span>
        </p>
        <p>
          库存有效 {{ inspected.values.max_age_hours }} 小时 · 最少
          {{ inspected.values.min_quantity }} 件 · 低毛利 {{ inspected.values.max_margin_percent }}%
        </p>
        <p>依据：{{ inspected.values.basis }}</p>
        <p v-for="(label, key) in noteLabels" :key="key">
          {{ label }}：{{ inspected.values.notes[key] || '未填写' }}
        </p>
        <p>
          广告计划：{{ inspected.values.advertising_daily_budget ?? '未知' }}
          {{ inspected.values.currency }}
        </p>
        <button
          v-if="inspected.active"
          class="button secondary"
          :disabled="busy || !confirmed"
          @click="change('restore')"
        >
          将此版本恢复为新规则
        </button>
      </div>
    </article>
  </section>
</template>

<style scoped>
fieldset {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
legend {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
}
.form-panel p {
  margin: 16px 0;
  line-height: 1.8;
}
.scope-options {
  margin: 20px 0;
}
.scope-options .form-grid {
  margin-top: 16px;
}
textarea {
  width: 100%;
  font: inherit;
  resize: vertical;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--ink);
}
.check-label {
  margin-top: 20px;
  line-height: 1.8;
}
.form-panel {
  overflow-wrap: anywhere;
}
</style>
