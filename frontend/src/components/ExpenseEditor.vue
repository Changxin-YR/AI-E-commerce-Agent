<script setup lang="ts">
import BusinessDateTime from '@/components/BusinessDateTime.vue'
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { expensesApi } from '@/api/expenses'
import { errorMessage } from '@/api/client'
import {
  expenseCategories,
  type ExpenseContent,
  type ExpenseOrder,
  type ExpenseSaved,
  type ExpenseScope,
} from '@/types/expenses'
import SupportSource from './SupportSource.vue'
import FeedbackBanner from './FeedbackBanner.vue'

const props = defineProps<{ shopId: number; scope: ExpenseScope; existing: ExpenseSaved | null }>()
const emit = defineEmits<{ save: [content: ExpenseContent]; cancel: [] }>()
const form = reactive<ExpenseContent>(
  props.existing?.snapshot
    ? { ...props.existing.snapshot.content }
    : {
        label: '',
        category: 'other',
        amount: '',
        currency: 'USD',
        occurred_at: new Date().toISOString(),
        timezone: 'UTC',
        evidence_ref: '',
        evidence_note: '',
        allocation: 'shop',
        order_line_id: null,
        expected_source_row_id: null,
        expected_source_revision: null,
        reason: '',
      },
)
const orderQuery = ref(props.existing?.snapshot?.order_id ?? '')
const orders = ref<ExpenseOrder[]>([])
const revision = ref<number | null>(null)
const error = ref('')
const busy = ref(false)
const confirmed = ref(false)
let epoch = 0
let alive = true
const selected = computed(() => orders.value.find((o) => o.id === form.order_line_id))
function unlink(): void {
  form.order_line_id = null
  form.expected_source_row_id = null
  form.expected_source_revision = null
  orders.value = []
  revision.value = null
  epoch++
  busy.value = false
}
// Every edit re-reads its current order source before confirming the allocation.
unlink()
watch(
  form,
  () => {
    confirmed.value = false
  },
  { deep: true, flush: 'sync' },
)
watch(
  () => [
    props.shopId,
    props.scope.data_identity,
    props.scope.channel,
    form.allocation,
    orderQuery.value,
  ],
  unlink,
  { flush: 'sync' },
)
async function findOrders(): Promise<void> {
  unlink()
  const current = epoch
  busy.value = true
  error.value = ''
  try {
    const result = await expensesApi.orders(props.shopId, props.scope, orderQuery.value)
    if (!alive || current !== epoch) return
    orders.value = result.items
    revision.value = result.source_revision
    if (!result.items.length) error.value = '此范围没有当前订单行，请核对订单号、身份和渠道。'
  } catch (cause) {
    if (alive && current === epoch) error.value = errorMessage(cause)
  } finally {
    if (alive && current === epoch) busy.value = false
  }
}
function link(): void {
  form.expected_source_row_id = selected.value?.source.row_id ?? null
  form.expected_source_revision = selected.value ? revision.value : null
}
function save(): void {
  if (!confirmed.value || busy.value || (form.allocation === 'order_line' && !selected.value))
    return
  emit('save', { ...form })
}
onUnmounted(() => {
  alive = false
  epoch++
})
</script>
<template>
  <section class="form-panel section-block" aria-label="费用录入">
    <h2>
      {{ existing ? `修订费用 #${existing.id} · 当前版本 ${existing.version}` : '录入实际费用' }}
    </h2>
    <p>
      人工记录已发生的费用；凭据编号在本店铺、身份和渠道内去重。请保留可核查的凭据，文字依据不会自动证明付款或结算。
    </p>
    <FeedbackBanner :message="error" />
    <form @submit.prevent="save">
      <div class="form-grid">
        <div class="form-field">
          <label for="fee-label">费用名称</label
          ><input id="fee-label" v-model="form.label" maxlength="100" required />
        </div>
        <div class="form-field">
          <label for="fee-category">费用类别</label
          ><select id="fee-category" v-model="form.category">
            <option v-for="(label, key) in expenseCategories" :key="key" :value="key">
              {{ label }}
            </option>
          </select>
        </div>
        <div class="form-field">
          <label for="fee-amount">实际费用金额</label
          ><input
            id="fee-amount"
            v-model="form.amount"
            inputmode="decimal"
            pattern="[0-9]+(\.[0-9]{1,4})?"
            required
          /><small>大于零，最多四位小数；每笔只录入一次总额。</small>
        </div>
        <div class="form-field">
          <label for="fee-currency">费用币种</label
          ><select id="fee-currency" v-model="form.currency">
            <option
              v-for="currency in ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']"
              :key="currency"
            >
              {{ currency }}
            </option>
          </select>
        </div>
        <BusinessDateTime
          v-model="form.occurred_at"
          :timezone="form.timezone"
          label="发生时间（含偏移）"
          required
        />
        <div class="form-field">
          <label for="fee-zone">发生时区（IANA）</label
          ><input id="fee-zone" v-model="form.timezone" required maxlength="64" /><small
            >例如 UTC、Asia/Shanghai，须与上述偏移一致。</small
          >
        </div>
        <div class="form-field">
          <label for="fee-ref">凭据编号</label
          ><input id="fee-ref" v-model="form.evidence_ref" required maxlength="120" /><small
            >使用账单/收据的唯一费用行编号；更正同一笔请修订。</small
          >
        </div>
        <div class="form-field">
          <label for="fee-allocation">费用归属</label
          ><select id="fee-allocation" v-model="form.allocation">
            <option value="shop">店铺费用 · 尚未分摊</option>
            <option value="order_line">单条订单行 · 全额直接归属</option>
          </select>
        </div>
      </div>
      <div v-if="form.allocation === 'order_line'" class="section-block">
        <div class="form-field">
          <label for="fee-order">订单号（精确匹配）</label
          ><input id="fee-order" v-model="orderQuery" maxlength="120" />
        </div>
        <button
          class="button secondary"
          type="button"
          :disabled="busy || !orderQuery.trim()"
          @click="findOrders"
        >
          查找当前订单行
        </button>
        <div v-if="orders.length" class="form-field">
          <label for="fee-line">关联订单行</label
          ><select id="fee-line" v-model="form.order_line_id" @change="link">
            <option :value="null">请选择并核对</option>
            <option v-for="order in orders" :key="order.id" :value="order.id">
              {{ order.order_id }} / {{ order.line_id }} · {{ order.sku }} · {{ order.currency }} ·
              {{ order.status }}
            </option>
          </select>
        </div>
        <p>
          费用总额直接归属选中行，适用于有明确行级凭据的费用；多行分摊、汇率和平台账单核对仍待支持。
        </p>
        <SupportSource
          v-if="selected"
          :key="selected.source.row_id"
          :shop-id="shopId"
          :source="selected.source"
        />
      </div>
      <div class="form-field">
        <label for="fee-note">事实依据</label
        ><textarea id="fee-note" v-model="form.evidence_note" maxlength="1000" required rows="3" />
      </div>
      <div class="form-field">
        <label for="fee-reason">本次录入或修订理由</label
        ><textarea id="fee-reason" v-model="form.reason" maxlength="500" required rows="2" />
      </div>
      <p>
        本次保存：{{ form.currency }} {{ form.amount || '—' }} ·
        {{ expenseCategories[form.category] }} ·
        {{
          form.allocation === 'shop'
            ? '店铺未分摊'
            : selected
              ? `${selected.order_id} / ${selected.line_id} 全额归属`
              : '尚未选择订单行'
        }}。
      </p>
      <label class="check-label"
        ><input
          v-model="confirmed"
          type="checkbox"
        />我已核对金额、发生时间、凭据和归属，确认保存本版本</label
      >
      <div class="form-actions">
        <button class="button secondary" type="button" @click="emit('cancel')">取消编辑</button
        ><button
          class="button primary"
          :disabled="!confirmed || busy || (form.allocation === 'order_line' && !selected)"
        >
          确认保存费用
        </button>
      </div>
    </form>
  </section>
</template>
