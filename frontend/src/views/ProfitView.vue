<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { identityApi } from '@/api/identity'
import { profitApi } from '@/api/profit'
import { errorMessage } from '@/api/client'
import { currencies, type Shop } from '@/types/identity'
import {
  newScenario,
  type SavedStudySummary,
  type StudyInput,
  type StudyResult,
} from '@/types/profit'
import { supportTime } from '@/types/support'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import ProfitScenarioEditor from '@/components/ProfitScenarioEditor.vue'
import ProfitResult from '@/components/ProfitResult.vue'

const shops = ref<Shop[]>([])
const shopId = ref(0)
const form = ref<StudyInput>({
  title: '',
  currency: 'USD',
  data_identity: 'manual_assumption',
  scenarios: [newScenario()],
})
const result = ref<StudyResult | null>(null)
const saved = ref<SavedStudySummary[]>([])
const selectedId = ref<number | null>(null)
const requestKey = ref(crypto.randomUUID())
const confirmClear = ref(false)
const busy = ref(false)
const error = ref('')
const message = ref('')
const offset = ref(0)
const timezone = computed(
  () => shops.value.find((shop) => shop.id === shopId.value)?.timezone ?? 'Asia/Shanghai',
)

watch(
  form,
  () => {
    result.value = null
    selectedId.value = null
    requestKey.value = crypto.randomUUID()
    confirmClear.value = false
    message.value = ''
  },
  { deep: true, flush: 'sync' },
)

async function run(work: () => Promise<void>): Promise<void> {
  if (busy.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    await work()
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function listSaved(): Promise<void> {
  saved.value = await profitApi.list(shopId.value, offset.value)
}
async function changeShop(): Promise<void> {
  result.value = null
  saved.value = []
  selectedId.value = null
  confirmClear.value = false
  offset.value = 0
  form.value = {
    title: '',
    currency: shops.value.find((shop) => shop.id === shopId.value)?.currency ?? 'USD',
    data_identity: 'manual_assumption',
    scenarios: [newScenario()],
  }
  await run(listSaved)
}
function addScenario(copy = false): void {
  if (form.value.scenarios.length >= 5) return
  let n = 1
  while (form.value.scenarios.some((item) => item.name === `方案 ${n}`)) n++
  const previous = form.value.scenarios[form.value.scenarios.length - 1]
  form.value.scenarios.push(
    copy && previous
      ? {
          ...(JSON.parse(JSON.stringify(previous)) as typeof previous),
          name: `方案 ${n}`,
        }
      : newScenario(`方案 ${n}`),
  )
}
async function calculate(): Promise<void> {
  result.value = null
  selectedId.value = null
  await run(async () => {
    result.value = await profitApi.calculate(shopId.value, form.value)
  })
}
async function save(): Promise<void> {
  if (!result.value || selectedId.value) return
  await run(async () => {
    const record = await profitApi.save(shopId.value, form.value, requestKey.value)
    result.value = record.result
    selectedId.value = record.id
    offset.value = 0
    await listSaved()
    message.value = '方案已保存，可从历史记录重新打开。'
  })
}
async function open(id: number): Promise<void> {
  result.value = null
  selectedId.value = null
  confirmClear.value = false
  await run(async () => {
    const record = await profitApi.get(shopId.value, id)
    form.value = record.result.input
    result.value = record.result
    selectedId.value = record.id
  })
}
async function clear(): Promise<void> {
  if (!selectedId.value || !confirmClear.value) return
  await run(async () => {
    await profitApi.clear(shopId.value, selectedId.value!)
    form.value = {
      title: '',
      currency: form.value.currency,
      data_identity: 'manual_assumption',
      scenarios: [newScenario()],
    }
    await listSaved()
    message.value = '已清除所选方案的名称、假设、金额及依据。'
  })
}
async function page(delta: number): Promise<void> {
  offset.value = Math.max(0, offset.value + delta)
  await run(listSaved)
}
onMounted(async () => {
  await run(async () => {
    shops.value = await identityApi.shops()
    shopId.value = shops.value[0]?.id ?? 0
    form.value.currency = shops.value[0]?.currency ?? 'USD'
    if (shopId.value) await listSaved()
  })
})
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>新品利润，先把假设算清。</h1>
      <p>独立输入成本，比较售价与物流方案；无需导入订单。</p>
    </div>
  </div>
  <FeedbackBanner :message="error" />
  <p v-if="message" role="status">{{ message }}</p>
  <section class="data-note">
    <span class="note-symbol" aria-hidden="true">i</span>
    <div>
      <h3>每个数字，都有前提</h3>
      <p>
        同一试算仅使用一个结算币种。采购毛利与已知费用后余额均为估算；物流、平台、广告、税费等空白项会明确标为未计入。价格建议仅依据你填入的假设。
      </p>
    </div>
  </section>
  <section v-if="!shops.length && !busy" class="form-panel section-block empty-state">
    <h2>先添加店铺记录</h2>
    <p>用于隔离保存的方案，无需绑定真实平台。</p>
    <RouterLink to="/settings" class="button secondary">经营资料</RouterLink>
  </section>
  <template v-if="shops.length">
    <div class="form-field section-block">
      <label for="profit-shop">计算器店铺</label
      ><select id="profit-shop" v-model="shopId" :disabled="busy" @change="changeShop">
        <option v-for="shop in shops" :key="shop.id" :value="shop.id">
          {{ shop.name }} · {{ shop.code }}
        </option>
      </select>
    </div>
    <details :open="!result" class="section-block">
      <summary>编辑试算输入</summary>
      <form class="section-block" @submit.prevent="calculate">
        <fieldset :disabled="busy">
          <legend class="sr-only">新品利润假设</legend>
          <section class="form-panel">
            <div class="section-title">
              <h2>建立你的价格情景</h2>
              <span>最多 5 个方案</span>
            </div>
            <div class="form-grid section-block">
              <div class="form-field">
                <label for="profit-title">试算名称</label
                ><input
                  id="profit-title"
                  v-model="form.title"
                  maxlength="120"
                  placeholder="新品 / SKU 与试算主题"
                  required
                />
              </div>
              <div class="form-field">
                <label for="profit-currency">结算币种</label
                ><select id="profit-currency" v-model="form.currency">
                  <option v-for="currency in currencies" :key="currency">
                    {{ currency }}
                  </option></select
                ><small>更改币种仅更换标注，请自行重新核对全部金额；不执行换汇。</small>
              </div>
              <div class="form-field">
                <label for="profit-identity">假设来源</label
                ><select id="profit-identity" v-model="form.data_identity">
                  <option value="manual_assumption">手工假设</option>
                  <option value="synthetic">合成测试数据</option>
                </select>
              </div>
            </div>
          </section>
          <section
            v-for="(_, index) in form.scenarios"
            :key="index"
            class="form-panel section-block"
            :aria-label="`编辑方案 ${index + 1}`"
          >
            <div class="section-title">
              <h3>方案 {{ index + 1 }}</h3>
              <button
                v-if="form.scenarios.length > 1"
                type="button"
                class="button secondary"
                @click="form.scenarios.splice(index, 1)"
              >
                移除此方案
              </button>
            </div>
            <ProfitScenarioEditor
              v-model="form.scenarios[index]!"
              :index="index"
              :currency="form.currency"
            />
          </section>
          <div class="form-actions">
            <div class="button-row">
              <button
                type="button"
                class="button secondary"
                :disabled="form.scenarios.length >= 5"
                @click="addScenario()"
              >
                新增空白方案</button
              ><button
                type="button"
                class="button secondary"
                :disabled="form.scenarios.length >= 5"
                @click="addScenario(true)"
              >
                复制末个方案
              </button>
            </div>
            <button class="button primary">计算并比较</button>
          </div>
        </fieldset>
      </form>
    </details>
    <p v-if="busy" role="status">正在处理方案…</p>
    <ProfitResult v-if="result" :result="result" :timezone="timezone" />
    <div v-if="result" class="form-panel section-block">
      <template v-if="selectedId"
        ><p>已存档方案 #{{ selectedId }} · 修改输入后，可重新计算并另存新记录。</p>
        <label class="check-label"
          ><input
            v-model="confirmClear"
            type="checkbox"
            :disabled="busy"
          />确认清除所选方案及其输入依据</label
        ><button class="button secondary" :disabled="busy || !confirmClear" @click="clear">
          清除所选方案
        </button></template
      >
      <template v-else
        ><p>保存输入、依据及规则版本，便于后续复查。</p>
        <button class="button primary" :disabled="busy" @click="save">
          保存本次方案
        </button></template
      >
    </div>
    <section class="form-panel section-block" aria-label="已保存利润方案">
      <div class="section-title">
        <h2>已保存的试算</h2>
        <button class="button secondary" :disabled="busy" @click="run(listSaved)">刷新记录</button>
      </div>
      <p v-if="!saved.length" class="muted">本页没有已保存方案。填写假设、计算后即可存档。</p>
      <ul class="saved-list">
        <li v-for="item in saved" :key="item.id">
          <button class="saved-study" :disabled="busy" @click="open(item.id)">
            <strong>{{ item.title }}</strong
            ><span
              >{{ item.currency }} ·
              {{ item.data_identity === 'synthetic' ? '合成测试数据' : '手工假设' }} ·
              {{ supportTime(item.created_at, timezone) }}</span
            >
          </button>
        </li>
      </ul>
      <div class="form-actions">
        <button class="button secondary" :disabled="busy || !offset" @click="page(-50)">
          上一页</button
        ><span>每页最多 50 条</span
        ><button class="button secondary" :disabled="busy || saved.length < 50" @click="page(50)">
          下一页
        </button>
      </div>
    </section>
  </template>
</template>

<style scoped>
fieldset {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
.saved-list {
  list-style: none;
  padding: 0;
}
.saved-study {
  width: 100%;
  text-align: left;
  display: grid;
  gap: 8px;
  padding: 16px 0;
  background: none;
  border: 0;
  border-bottom: 1px solid var(--line);
  color: var(--ink);
  cursor: pointer;
  overflow-wrap: anywhere;
}
.saved-study span {
  color: var(--muted);
  font-size: 12px;
}
.form-panel > p {
  margin-bottom: 16px;
}
.check-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 16px 0;
}
@media (max-width: 640px) {
  .section-title {
    flex-wrap: wrap;
    gap: 12px;
  }
}
</style>
