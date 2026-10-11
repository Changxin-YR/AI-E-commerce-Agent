<template>
  <PageShell
    title="我的"
    subtitle="账号、店铺与业务工具入口。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
  >
    <FactLine label="账号" :value="state.session?.username" />
    <FactLine label="客户端类型" :value="state.session?.client_type" />
    <FactLine label="会话到期" :value="state.session?.expires_at" :zone="zone" />
    <FactLine label="服务地址" :value="state.baseUrl" />

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

    <text class="section-title">业务工具</text>
    <view class="row">
      <ActionButton label="业务文件导入" @tap="openPage('/pages/imports/index')" />
      <ActionButton label="库存快照" @tap="openPage('/pages/inventory/index')" />
      <ActionButton label="Listing 草稿" @tap="openPage('/pages/listings/index')" />
      <ActionButton label="环境信息" @tap="openPage('/pages/diagnostics/index')" />
    </view>

    <text class="section-title">会话</text>
    <view class="row">
      <ActionButton label="回读会话与店铺" :disabled="busy" @tap="refresh" />
      <ActionButton label="退出登录" :disabled="busy" @tap="signOut" />
      <ActionButton label="退出全部设备" :disabled="busy" @tap="signOutAll" />
    </view>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 我的：账号、店铺切换与业务工具入口。
 * 接口：GET /api/mobile/auth/session、GET /api/shops、POST /api/mobile/auth/logout(-all)。
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import ActionButton from '../../ui/ActionButton.vue'
import { openPage } from '../../core/links'
import { ensureSession, logout, perform, refreshSession, selectShop, shopTimezone, state } from '../../core/store'

const busy = ref(false)
const error = ref('')
const zone = computed(() => shopTimezone())

useDidShow(async () => {
  if (!(await ensureSession())) return
  const message = await perform(refreshSession)
  error.value = message
})

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
