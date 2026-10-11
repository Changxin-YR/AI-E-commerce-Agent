<template>
  <view class="screen">
    <text class="title">店铺与经营资料</text>
    <text v-if="busy" class="hint">正在处理，请稍候…</text>
    <view v-if="error" class="error">{{ error }}<button :disabled="busy" @tap="load">重新读取</button></view>
    <text v-if="notice" class="hint">{{ notice }}</text>
    <template v-if="ready && account.session">
      <view class="card">
        <text class="section-title">经营档案</text>
        <text class="hint">{{ onboarding?.profile_complete ? '已建立经营档案' : '先完善经营方向，再建立店铺并导入文件。' }}</text>
        <view v-for="field in profileFields" :key="field.key"><text class="label">{{ field.label }}</text><input v-model="profile[field.key]" :maxlength="field.max" :disabled="busy" /></view>
        <text class="label">默认币种</text><picker :range="currencies" :value="currencies.indexOf(profile.currency)" @change="profile.currency = currencies[Number($event.detail.value)] || 'USD'"><view class="select">{{ profile.currency }}</view></picker>
        <text class="label">默认语言</text><picker :range="languages" :value="languages.indexOf(profile.language)" @change="profile.language = languages[Number($event.detail.value)] || 'zh-CN'"><view class="select">{{ profile.language }}</view></picker>
        <button class="primary" :disabled="busy" @tap="saveProfile">保存经营档案</button>
      </view>
      <view class="card">
        <text class="section-title">我的店铺 · {{ account.shops.length }}</text>
        <view v-for="shop in account.shops" :key="shop.id"><text class="label">{{ shop.name }}</text><text class="hint">{{ shop.code }} · {{ shop.market }} · {{ shop.currency }} · {{ shop.timezone }}</text><button :disabled="busy || account.shopId === shop.id" @tap="selectShop(shop.id)">{{ account.shopId === shop.id ? '当前店铺' : '使用此店铺' }}</button></view>
        <text v-if="!account.shops.length" class="hint">建立第一个店铺，为导入数据确定归属。</text>
      </view>
      <view class="card">
        <text class="section-title">添加店铺</text>
        <view v-for="field in shopFields" :key="field.key"><text class="label">{{ field.label }}</text><input v-model="shopForm[field.key]" :maxlength="field.max" :disabled="busy" /></view>
        <text class="label">来源平台</text><picker :range="platforms" :value="platforms.indexOf(shopForm.platform)" @change="shopForm.platform = platforms[Number($event.detail.value)] || 'manual'"><view class="select">{{ shopForm.platform }}</view></picker>
        <text class="label">店铺币种</text><picker :range="currencies" :value="currencies.indexOf(shopForm.currency)" @change="shopForm.currency = currencies[Number($event.detail.value)] || 'USD'"><view class="select">{{ shopForm.currency }}</view></picker>
        <text class="hint">当前以文件导入经营数据，平台字段用于标记来源。</text>
        <button class="primary" :disabled="busy" @tap="createShop">创建店铺</button>
      </view>
    </template>
    <button @tap="Taro.reLaunch({ url: '/pages/index/index' })">返回工作台</button>
  </view>
</template>
<script setup lang="ts">
import { reactive, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import { account, api, loadShops, selectShop, type Shop } from '../../services/session'
interface Profile { display_name: string; target_market: string; business_model: string; category: string; currency: string; timezone: string; language: string; version: number }
interface Onboarding { profile_complete: boolean; shop_count: number; next_step: string }
const profile = reactive<Profile>({ display_name: '', target_market: 'US', business_model: '', category: '', currency: 'USD', timezone: 'Asia/Shanghai', language: 'zh-CN', version: 0 })
const shopForm = reactive({ code: '', name: '', platform: 'manual', market: 'US', currency: 'USD', timezone: 'Asia/Shanghai' })
const currencies = ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']
const languages = ['zh-CN', 'en', 'ja', 'de', 'fr', 'es'], platforms = ['manual', 'shopify', 'amazon', 'other']
const profileFields = [
  { key: 'display_name', label: '经营者名称', max: 80 }, { key: 'target_market', label: '目标市场（两位大写代码，如 US）', max: 2 },
  { key: 'business_model', label: '经营模式', max: 80 }, { key: 'category', label: '主营品类', max: 120 }, { key: 'timezone', label: '业务时区（如 Asia/Shanghai）', max: 64 },
] as const
const shopFields = [
  { key: 'code', label: '店铺代码（2–40 位小写字母、数字、下划线或连字符）', max: 40 }, { key: 'name', label: '店铺名称', max: 80 },
  { key: 'market', label: '市场（两位大写代码，如 US）', max: 2 }, { key: 'timezone', label: '业务时区', max: 64 },
] as const
const busy = ref(false), ready = ref(false), error = ref(''), notice = ref(''), onboarding = ref<Onboarding | null>(null)
async function perform(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try { await action() } catch (cause) { error.value = cause instanceof Error ? cause.message : '操作失败，请重试。' } finally { busy.value = false }
}
async function readProfile() {
  const result = await api.request<Profile | null>('/profile')
  if (result) Object.assign(profile, result)
  onboarding.value = await api.request<Onboarding>('/onboarding')
}
async function load() {
  if (!account.session) { await Taro.reLaunch({ url: '/pages/index/index' }); return }
  await perform(async () => { ready.value = false; await readProfile(); await loadShops(); ready.value = true })
}
async function saveProfile() {
  await perform(async () => {
    if (profileFields.some(field => !profile[field.key].trim())) throw new Error('请填写完整经营资料。')
    if (!/^[A-Z]{2}$/.test(profile.target_market)) throw new Error('目标市场请输入两位大写代码。')
    Object.assign(profile, await api.request<Profile>('/profile', 'PUT', { ...profile }))
    notice.value = '经营资料已保存。'
  })
}
async function createShop() {
  await perform(async () => {
    if (!/^[a-z0-9][a-z0-9_-]{1,39}$/.test(shopForm.code)) throw new Error('请按要求填写店铺代码。')
    if (!shopForm.name.trim() || !/^[A-Z]{2}$/.test(shopForm.market) || !shopForm.timezone.trim()) throw new Error('请填写店铺名称、两位大写市场代码及业务时区。')
    const result = await api.request<Shop>('/shops', 'POST', { ...shopForm })
    shopForm.code = ''; shopForm.name = ''
    await loadShops(); selectShop(result.id)
    notice.value = `店铺“${result.name}”已建立，可返回工作台使用。`
  })
}
useDidShow(() => { void load() })
</script>
