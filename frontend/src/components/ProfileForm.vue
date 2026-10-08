<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { identityApi } from '@/api/identity'
import { errorMessage } from '@/api/client'
import { currencies, timezones, type SellerProfile } from '@/types/identity'
import FeedbackBanner from './FeedbackBanner.vue'
import FormField from './FormField.vue'

const props = defineProps<{ profile: SellerProfile | null }>()
const emit = defineEmits<{ saved: [profile: SellerProfile] }>()
const form = reactive<SellerProfile>({
  display_name: '',
  target_market: 'US',
  business_model: '',
  category: '',
  currency: 'USD',
  timezone: 'Asia/Shanghai',
  language: 'zh-CN',
  version: 0,
})
const busy = ref(false)
const error = ref('')
const success = ref('')
watch(
  () => props.profile,
  (value) => {
    if (value) Object.assign(form, value)
  },
  { immediate: true },
)
async function save(): Promise<void> {
  if (busy.value) return
  busy.value = true
  error.value = ''
  success.value = ''
  try {
    const result = await identityApi.saveProfile({ ...form })
    Object.assign(form, result)
    emit('saved', result)
    success.value = '经营资料已保存。'
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <form @submit.prevent="save">
    <FeedbackBanner :message="error" /><FeedbackBanner :message="success" kind="success" />
    <div class="form-grid">
      <FormField label="经营名称" for-id="display-name"
        ><input
          id="display-name"
          v-model="form.display_name"
          required
          maxlength="80"
          placeholder="例如：我的跨境工作室"
      /></FormField>
      <FormField label="目标市场" for-id="target-market" hint="两位国家代码，例如 US、GB、DE。"
        ><input
          id="target-market"
          v-model="form.target_market"
          required
          pattern="[A-Z]{2}"
          maxlength="2"
      /></FormField>
      <FormField label="经营模式" for-id="business-model"
        ><input
          id="business-model"
          v-model="form.business_model"
          required
          maxlength="80"
          placeholder="例如：自有品牌 / 精品零售"
      /></FormField>
      <FormField label="主营类目" for-id="category"
        ><input
          id="category"
          v-model="form.category"
          required
          maxlength="120"
          placeholder="例如：家居用品"
      /></FormField>
      <FormField label="默认币种" for-id="profile-currency"
        ><select id="profile-currency" v-model="form.currency">
          <option v-for="currency in currencies" :key="currency">{{ currency }}</option>
        </select></FormField
      >
      <FormField label="经营时区" for-id="profile-timezone"
        ><select id="profile-timezone" v-model="form.timezone">
          <option v-for="timezone in timezones" :key="timezone">{{ timezone }}</option>
          <option v-if="!timezones.includes(form.timezone)">{{ form.timezone }}</option>
        </select></FormField
      >
      <FormField label="默认语言" for-id="language"
        ><select id="language" v-model="form.language">
          <option value="zh-CN">简体中文</option>
          <option value="en">English</option>
          <option value="ja">日本語</option>
          <option value="de">Deutsch</option>
          <option value="fr">Français</option>
          <option value="es">Español</option>
        </select></FormField
      >
    </div>
    <div class="form-actions">
      <span>用于后续文件分析与内容草稿的默认设置</span
      ><button class="button primary" :disabled="busy">
        {{ busy ? '保存中…' : '保存经营资料' }}
      </button>
    </div>
  </form>
</template>
