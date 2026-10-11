<template>
  <PageShell
    title="我的"
    subtitle="账号、经营档案、店铺与业务工具入口。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    :success="successText"
    @retry="loadProfile"
  >
    <FactLine label="账号" :value="state.session?.username" />
    <FactLine label="客户端类型" :value="state.session?.client_type" />
    <FactLine label="会话到期" :value="state.session?.expires_at" :zone="zone" />
    <FactLine label="服务地址" :value="state.baseUrl" />

    <text class="section-title">开始经营</text>
    <view v-if="onboarding === null" class="card">
      <text class="hint">尚未读取起步状态，请回读会话与店铺后重试。</text>
    </view>
    <template v-else>
      <FactLine
        label="起步状态"
        :value="`经营档案：${onboarding.profile_complete === true ? '已填写' : '待填写'} · 店铺 ${onboarding.shop_count} 家`"
      />
      <FactLine label="数据方式" :value="onboarding.data_mode === 'file_import' ? '文件导入 · 不直连平台' : factText(onboarding.data_mode)" />
      <FactLine label="下一步" :value="labelOf(nextSteps, onboarding.next_step)" />
      <view class="row">
        <ActionButton
          :label="labelOf(nextSteps, onboarding.next_step)"
          variant="primary"
          :disabled="busy"
          @tap="gotoNextStep"
        />
        <ActionButton label="导入业务数据" :disabled="busy" @tap="openPage('/pages/imports/index')" />
      </view>
      <text class="hint">按店铺保存来源与业务记录，后续可以反复核对和修订。</text>
    </template>

    <text class="section-title">经营档案</text>
    <FactLine label="档案版本" :value="profile === null ? '尚未创建' : profile.version" />
    <view class="field">
      <text class="field__label">经营名称</text>
      <input class="field__input" :value="profileForm.displayName" :disabled="busy" @input="profileForm.displayName = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">目标市场（两位大写字母，如 US）</text>
      <input class="field__input" :value="profileForm.targetMarket" :disabled="busy" @input="profileForm.targetMarket = inputValue($event).toUpperCase()" />
    </view>
    <view class="field">
      <text class="field__label">经营模式</text>
      <input class="field__input" :value="profileForm.businessModel" :disabled="busy" @input="profileForm.businessModel = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">主营类目</text>
      <input class="field__input" :value="profileForm.category" :disabled="busy" @input="profileForm.category = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">常用币种</text>
      <picker mode="selector" :range="currencyOptions" :value="profileCurrencyIndex" @change="profileForm.currency = currencyOptions[Number(pickerValue($event))] ?? profileForm.currency">
        <view class="field__picker">{{ profileForm.currency }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">业务时区（IANA）</text>
      <input class="field__input" :value="profileForm.timezone" :disabled="busy" @input="profileForm.timezone = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">默认语言</text>
      <picker mode="selector" :range="languageOptions" range-key="label" :value="languageIndex" @change="profileForm.language = languageOptions[Number(pickerValue($event))]?.key ?? 'zh-CN'">
        <view class="field__picker">{{ labelOf(languages, profileForm.language) }}</view>
      </picker>
    </view>
    <text v-if="profileMustRefresh" class="warn">资料版本或保存结果需要核对，请读取最新资料后继续。</text>
    <view class="row">
      <ActionButton label="读取最新资料并替换表单" :disabled="busy" @tap="readProfile" />
      <ActionButton label="保存经营资料" variant="primary" :disabled="busy" @tap="saveProfile" />
    </view>

    <text class="section-title">当前店铺</text>
    <view v-if="state.shops.length === 0" class="card">
      <text class="hint">尚未创建店铺记录。请先在网页端完善经营资料，再回到小程序选择店铺。</text>
    </view>
    <view
      v-for="shop in state.shops"
      :key="shop.id"
      class="card"
      @tap="choose(shop.id)"
    >
      <text class="card__title">{{ shop.name }}</text>
      <text class="hint">
        {{ shop.market ?? '未知' }} · {{ shop.currency ?? '未知' }} · {{ shop.timezone ?? '未知' }}
      </text>
      <text class="chip" :class="{ 'chip--active': shop.id === state.shopId }">
        {{ shop.id === state.shopId ? '当前店铺' : '切换到此店铺' }}
      </text>
    </view>

    <text class="section-title">店铺管理</text>
    <text class="hint">店铺标识用于内部区分来源与渠道，创建后不可更改；平台写入能力由部署者配置，本版本只做本地文件导入。</text>
    <view class="field">
      <text class="field__label">店铺名称</text>
      <input class="field__input" :value="shopForm.name" :disabled="busy" @input="shopForm.name = inputValue($event)" />
    </view>
    <view class="field">
      <text class="field__label">店铺标识（小写字母、数字、下划线或连字符）</text>
      <input class="field__input" :value="shopForm.code" :disabled="busy" @input="shopForm.code = inputValue($event).toLowerCase()" />
    </view>
    <view class="field">
      <text class="field__label">市场（两位大写字母，如 US）</text>
      <input class="field__input" :value="shopForm.market" :disabled="busy" @input="shopForm.market = inputValue($event).toUpperCase()" />
    </view>
    <view class="field">
      <text class="field__label">平台</text>
      <picker mode="selector" :range="platformOptions" range-key="label" :value="platformIndex" @change="shopForm.platform = platformOptions[Number(pickerValue($event))]?.key ?? 'manual'">
        <view class="field__picker">{{ labelOf(platforms, shopForm.platform) }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">币种</text>
      <picker mode="selector" :range="currencyOptions" :value="shopCurrencyIndex" @change="shopForm.currency = currencyOptions[Number(pickerValue($event))] ?? shopForm.currency">
        <view class="field__picker">{{ shopForm.currency }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">时区（IANA）</text>
      <input class="field__input" :value="shopForm.timezone" :disabled="busy" @input="shopForm.timezone = inputValue($event)" />
    </view>
    <view class="row">
      <ActionButton label="创建店铺" variant="primary" :disabled="busy" @tap="createShop" />
      <ActionButton label="回读当前店铺资料" :disabled="busy || state.shopId === null" @tap="readShop" />
    </view>
    <template v-if="shopDetail !== null">
      <FactLine label="店铺资料" :value="`#${shopDetail.id} · ${shopDetail.name}`" />
      <FactLine label="标识 / 平台 / 市场" :value="`${shopDetail.code} / ${labelOf(platforms, shopDetail.platform)} / ${shopDetail.market}`" />
      <FactLine label="币种 / 时区" :value="`${shopDetail.currency} / ${shopDetail.timezone}`" />
      <FactLine label="连接状态" :value="connectionStatuses[shopDetail.connection_status] ?? shopDetail.connection_status" />
    </template>

    <text class="section-title">业务工具</text>
    <view class="row">
      <ActionButton label="业务文件导入" @tap="openPage('/pages/imports/index')" />
      <ActionButton label="库存快照" @tap="openPage('/pages/inventory/index')" />
      <ActionButton label="Listing 草稿" @tap="openPage('/pages/listings/index')" />
      <ActionButton label="环境信息" @tap="openPage('/pages/diagnostics/index')" />
    </view>

    <text class="section-title">经营与财务</text>
    <view class="row">
      <ActionButton label="经营分析" @tap="openPage('/pages/analytics/index')" />
      <ActionButton label="跨店经营总览" @tap="openPage('/pages/overview/index')" />
      <ActionButton label="新品利润测算" @tap="openPage('/pages/profit/index')" />
      <ActionButton label="实际费用" @tap="openPage('/pages/expenses/index')" />
      <ActionButton label="渠道账单" @tap="openPage('/pages/statements/index')" />
      <ActionButton label="订单账单核对" @tap="openPage('/pages/order_reconciliation/index')" />
      <ActionButton label="费用映射规则" @tap="openPage('/pages/fee_rules/index')" />
      <ActionButton label="结算回款" @tap="openPage('/pages/settlements/index')" />
    </view>

    <text class="section-title">规则、自动化与外发</text>
    <view class="row">
      <ActionButton label="经营规则与授权" @tap="openPage('/pages/rules/index')" />
      <ActionButton label="定时运营与通知" @tap="openPage('/pages/schedules/index')" />
      <ActionButton label="测试外发管理" @tap="openPage('/pages/outbound/index')" />
    </view>

    <text class="section-title">商品维护</text>
    <view class="row">
      <ActionButton label="商品质量检查" @tap="openPage('/pages/product_quality/index')" />
      <ActionButton label="商品本地修订" @tap="openPage('/pages/product_edits/index')" />
    </view>

    <text class="section-title">登录与设备</text>
    <FactLine label="会话标识" :value="state.session?.session_id" />
    <FactLine label="本机客户端" :value="state.session?.client_type" />
    <FactLine label="本机凭据" :value="state.session === null ? '未保存' : '已保存到本机小程序存储（仅服务地址与令牌）'" />
    <text class="hint">退出当前设备只清除本机凭据；退出全部设备会注销其它设备上的移动会话。</text>
    <view class="row">
      <ActionButton label="回读会话与店铺" :disabled="busy" @tap="refresh" />
      <ActionButton label="退出登录" :disabled="busy" @tap="signOut" />
      <ActionButton label="退出全部设备" :disabled="busy" @tap="signOutAll" />
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 我的：账号、经营档案、店铺管理、创建店铺、业务工具入口与登录设备。
 * 接口：
 *   GET  /api/mobile/auth/session、POST /api/mobile/auth/logout(-all)
 *   GET  /api/onboarding、GET /api/profile、PUT /api/profile
 *   GET  /api/shops、POST /api/shops、GET /api/shops/{shop_id}
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import ActionButton from '../../ui/ActionButton.vue'
import { ApiError, apiGet, apiRequest, asObject } from '../../core/api'
import { factText } from '../../core/format'
import { languages, labelOf } from '../../core/labels'
import { openPage } from '../../core/links'
import { ensureSession, loadShopList, logout, perform, refreshSession, selectShop, shopTimezone, state } from '../../core/store'

/** 起步引导的下一步文案（后端 OnboardingOutput.next_step）。 */
const nextSteps: Record<string, string> = {
  profile: '填写经营资料',
  shop: '创建经营店铺',
  import: '导入第一份报表',
}

const platforms: Record<string, string> = {
  manual: '手工经营',
  shopify: 'Shopify',
  amazon: 'Amazon',
  other: '其他',
}

const connectionStatuses: Record<string, string> = {
  file_only: '仅文件导入 · 未直连平台',
}

/** 与后端 Currency / 语言枚举一致；不由本机猜测其它币种。 */
const currencyOptions = ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']

interface ProfileOutput {
  display_name: string
  target_market: string
  business_model: string
  category: string
  currency: string
  timezone: string
  language: string
  version: number
}

interface OnboardingOutput {
  profile_complete: boolean
  shop_count: number
  data_mode: string
  next_step: string
}

interface ShopDetail {
  id: number
  code: string
  name: string
  platform: string
  market: string
  currency: string
  timezone: string
  connection_status: string
}

const busy = ref(false)
const error = ref('')
const successText = ref('')
const ready = ref(false)
const profile = ref<ProfileOutput | null>(null)
const profileMustRefresh = ref(false)
const onboarding = ref<OnboardingOutput | null>(null)
const shopDetail = ref<ShopDetail | null>(null)
const profileForm = ref({
  displayName: '',
  targetMarket: '',
  businessModel: '',
  category: '',
  currency: 'USD',
  timezone: '',
  language: 'zh-CN',
})
const shopForm = ref({
  name: '',
  code: '',
  market: '',
  platform: 'manual',
  currency: 'USD',
  timezone: '',
})
const zone = computed(() => shopTimezone())
const profileCurrencyIndex = computed(() => Math.max(0, currencyOptions.indexOf(profileForm.value.currency)))
const shopCurrencyIndex = computed(() => Math.max(0, currencyOptions.indexOf(shopForm.value.currency)))
const languageOptions = computed(() => Object.entries(languages).map(([key, label]) => ({ key, label })))
const languageIndex = computed(() => Math.max(0, Object.keys(languages).indexOf(profileForm.value.language)))
const platformOptions = computed(() => Object.entries(platforms).map(([key, label]) => ({ key, label })))
const platformIndex = computed(() => Math.max(0, Object.keys(platforms).indexOf(shopForm.value.platform)))

function success(text: string): void {
  successText.value = text
  void Taro.showToast({ title: text, icon: 'none' })
}

/** 写操作：断线/超时提示“结果未知，请回读”，不推断成功。 */
async function writeAction(action: () => Promise<void>, done: string, hint: string): Promise<void> {
  let unknown = false
  const message = await perform(async () => {
    try {
      await action()
    } catch (caught) {
      unknown = caught instanceof ApiError && caught.kind === 'network_unknown'
      throw caught
    }
  })
  if (message === '') {
    success(done)
    return
  }
  error.value = unknown ? `${message} 结果未知，请回读${hint}核对后再决定。` : message
  if (unknown) profileMustRefresh.value = true
}

function applyProfile(value: ProfileOutput): void {
  profile.value = value
  profileForm.value = {
    displayName: value.display_name,
    targetMarket: value.target_market,
    businessModel: value.business_model,
    category: value.category,
    currency: value.currency,
    timezone: value.timezone,
    language: value.language,
  }
  profileMustRefresh.value = false
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  if (shopForm.value.timezone === '') shopForm.value.timezone = shopTimezone()
  const message = await perform(refreshSession)
  error.value = message
  await loadProfile()
})

/** 经营档案与起步状态；档案可能尚未创建，缺失时保留表单默认值。 */
async function loadProfile(): Promise<void> {
  if (!ready.value) return
  const message = await perform(async () => {
    onboarding.value = asObject<OnboardingOutput>(await apiGet('/api/onboarding'))
    const value = asObject<ProfileOutput>(await apiGet('/api/profile'))
    if (value === null) {
      profile.value = null
      if (profileForm.value.timezone === '') profileForm.value.timezone = shopTimezone()
      return
    }
    applyProfile(value)
  })
  error.value = message
}

async function readProfile(): Promise<void> {
  if (profile.value !== null) {
    const modal = await Taro.showModal({
      title: '读取最新资料',
      content: '服务端最新资料将替换当前表单输入。',
      confirmText: '读取',
      cancelText: '返回',
    })
    if (!modal.confirm) return
  }
  await loadProfile()
  if (error.value === '') success('已读取服务端经营资料。')
}

async function saveProfile(): Promise<void> {
  await writeAction(async () => {
    const form = profileForm.value
    if (form.displayName.trim() === '') throw new Error('请填写经营名称。')
    if (!/^[A-Z]{2}$/.test(form.targetMarket.trim())) throw new Error('目标市场须为两位大写字母，例如 US。')
    if (form.businessModel.trim() === '') throw new Error('请填写经营模式。')
    if (form.category.trim() === '') throw new Error('请填写主营类目。')
    if (form.timezone.trim() === '') throw new Error('请填写业务时区（IANA）。')
    const value = asObject<ProfileOutput>(
      await apiRequest<ProfileOutput>('/api/profile', {
        method: 'PUT',
        body: {
          display_name: form.displayName.trim(),
          target_market: form.targetMarket.trim(),
          business_model: form.businessModel.trim(),
          category: form.category.trim(),
          currency: form.currency,
          timezone: form.timezone.trim(),
          language: form.language,
          version: profile.value?.version ?? 0,
        },
      }),
    )
    if (value === null) throw new Error('保存响应无法读取，请读取最新资料核对。')
    applyProfile(value)
    onboarding.value = asObject<OnboardingOutput>(await apiGet('/api/onboarding'))
  }, '经营资料已保存。', '经营档案')
}

async function createShop(): Promise<void> {
  await writeAction(async () => {
    const form = shopForm.value
    if (form.name.trim() === '') throw new Error('请填写店铺名称。')
    if (!/^[a-z0-9][a-z0-9_-]{1,39}$/.test(form.code.trim())) {
      throw new Error('店铺标识须为 2–40 位小写字母、数字、下划线或连字符。')
    }
    if (!/^[A-Z]{2}$/.test(form.market.trim())) throw new Error('市场须为两位大写字母，例如 US。')
    if (form.timezone.trim() === '') throw new Error('请填写时区（IANA）。')
    const value = asObject<ShopDetail>(
      await apiRequest<ShopDetail>('/api/shops', {
        method: 'POST',
        body: {
          code: form.code.trim(),
          name: form.name.trim(),
          platform: form.platform,
          market: form.market.trim(),
          currency: form.currency,
          timezone: form.timezone.trim(),
        },
      }),
    )
    if (value === null) throw new Error('创建响应无法读取，请回读店铺列表核对。')
    shopDetail.value = value
    await loadShopList()
    selectShop(value.id)
    onboarding.value = asObject<OnboardingOutput>(await apiGet('/api/onboarding'))
  }, '店铺已创建并切换为当前店铺。', '店铺列表')
}

async function readShop(): Promise<void> {
  const shopId = state.shopId
  if (shopId === null) return
  const message = await perform(async () => {
    const value = asObject<ShopDetail>(await apiGet(`/api/shops/${shopId}`))
    if (value === null) throw new Error('店铺资料无法读取，请刷新重试。')
    shopDetail.value = value
  })
  error.value = message
}

/** 起步引导深链：按服务端 next_step 跳到对应页面。 */
function gotoNextStep(): void {
  const step = onboarding.value?.next_step ?? 'profile'
  if (step === 'import') openPage('/pages/imports/index')
  else if (step === 'shop') success('请在下方的“店铺管理”填写资料并创建店铺。')
  else success('请在下方的“经营档案”填写并保存资料。')
}

function choose(shopId: number): void {
  if (shopId === state.shopId) return
  selectShop(shopId)
  void Taro.showToast({ title: '已切换店铺，业务页面会重新读取。', icon: 'none' })
}

async function refresh(): Promise<void> {
  busy.value = true
  error.value = await perform(refreshSession)
  busy.value = false
}

async function signOut(): Promise<void> {
  await doLogout(false)
}

async function signOutAll(): Promise<void> {
  const modal = await Taro.showModal({
    title: '退出全部设备',
    content: '将同时注销其他设备上的移动会话。',
    confirmText: '确认',
    cancelText: '返回',
  })
  if (!modal.confirm) return
  await doLogout(true)
}

async function doLogout(all: boolean): Promise<void> {
  busy.value = true
  await perform(() => logout(all))
  busy.value = false
  await Taro.reLaunch({ url: '/pages/login/index' })
}
</script>
