<script setup lang="ts">
import { reactive, ref } from 'vue'
import { identityApi } from '@/api/identity'
import { errorMessage } from '@/api/client'
import { currencies, timezones, type Shop, type ShopInput } from '@/types/identity'
import FeedbackBanner from './FeedbackBanner.vue'
import FormField from './FormField.vue'

const emit = defineEmits<{ created: [shop: Shop]; cancel: [] }>()
const form = reactive<ShopInput>({
  code: '',
  name: '',
  platform: 'manual',
  market: 'US',
  currency: 'USD',
  timezone: 'Asia/Shanghai',
})
const busy = ref(false)
const error = ref('')
async function create(): Promise<void> {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    emit('created', await identityApi.createShop({ ...form }))
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <form class="shop-form" @submit.prevent="create">
    <FeedbackBanner :message="error" />
    <div class="form-grid">
      <FormField label="店铺名称" for-id="shop-name"
        ><input id="shop-name" v-model="form.name" required maxlength="80"
      /></FormField>
      <FormField label="店铺标识" for-id="shop-code" hint="2–40 位小写字母、数字、下划线或短横线。"
        ><input
          id="shop-code"
          v-model="form.code"
          required
          pattern="[a-z0-9][a-z0-9_-]{1,39}"
          maxlength="40"
          placeholder="例如：home-us"
      /></FormField>
      <FormField label="来源平台" for-id="shop-platform"
        ><select id="shop-platform" v-model="form.platform">
          <option value="manual">通用文件</option>
          <option value="shopify">Shopify</option>
          <option value="amazon">Amazon</option>
          <option value="other">其他平台</option>
        </select></FormField
      >
      <FormField label="销售市场" for-id="shop-market"
        ><input id="shop-market" v-model="form.market" pattern="[A-Z]{2}" maxlength="2" required
      /></FormField>
      <FormField label="店铺币种" for-id="shop-currency"
        ><select id="shop-currency" v-model="form.currency">
          <option v-for="currency in currencies" :key="currency">{{ currency }}</option>
        </select></FormField
      >
      <FormField label="报表时区" for-id="shop-timezone"
        ><select id="shop-timezone" v-model="form.timezone">
          <option v-for="timezone in timezones" :key="timezone">{{ timezone }}</option>
        </select></FormField
      >
    </div>
    <div class="form-actions">
      <span>店铺标识用于区分后续导入文件的归属</span>
      <div class="button-group">
        <button type="button" class="button secondary" :disabled="busy" @click="emit('cancel')">
          取消</button
        ><button class="button primary" :disabled="busy">
          {{ busy ? '添加中…' : '确认添加' }}
        </button>
      </div>
    </div>
  </form>
</template>
