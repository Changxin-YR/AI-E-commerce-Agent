<template>
  <view class="screen">
    <view class="hero"><text class="eyebrow">SOLOOPS · 卖家工作台</text><text class="title">经营有据，行动有序。</text><text class="muted">把店铺日常，交给清晰的运营流程。</text></view>
    <view v-if="!account.session" class="card">
      <text class="section-title">登录工作台</text>
      <text class="label">服务地址</text><input v-model="server" placeholder="https://api.example.com" :disabled="busy" :maxlength="240" />
      <text class="hint">使用已配置为小程序合法域名的 HTTPS 服务地址。</text>
      <text class="label">用户名</text><input v-model="username" placeholder="SoloOps 账号" :disabled="busy" :maxlength="64" />
      <text class="label">密码</text><input v-model="password" password placeholder="请输入密码" :disabled="busy" :maxlength="128" @confirm="login" />
      <button class="primary" :loading="busy" :disabled="busy || !server || !username || !password" @tap="login">登录</button>
      <text class="hint">本次登录仅在当前小程序会话中有效，重新打开后请再次登录。</text>
    </view>
    <template v-else>
      <view class="card">
        <view class="row"><text class="section-title">{{ account.session.username }}，你好</text><text class="badge">已连接</text></view>
        <text class="label">当前店铺</text>
        <picker v-if="account.shops.length" :range="account.shops" range-key="name" :value="shopIndex" @change="changeShop"><view class="select">{{ activeShop?.name }} · 切换店铺</view></picker>
        <text v-else class="muted">还没有店铺，请先创建经营店铺。</text>
        <text v-if="activeShop" class="hint">{{ activeShop.currency }} · {{ activeShop.timezone }} · 文件导入模式</text>
        <button class="primary" @tap="Taro.navigateTo({ url: '/pages/settings/index' })">店铺与经营资料</button>
        <button :disabled="busy" @tap="refresh">刷新店铺</button>
        <button :disabled="!account.shopId" @tap="Taro.navigateTo({ url: '/pages/imports/index' })">文件导入与批次管理</button>
        <button class="primary" :disabled="!account.shopId" @tap="Taro.navigateTo({ url: '/pages/workbench/index' })">今日首页与待办</button>
      </view>
      <view class="card"><text class="section-title">账号与会话</text><text class="hint">退出全部设备会撤销该账号的所有登录会话。</text><button :disabled="busy" @tap="logout(false)">退出当前设备</button><button class="danger" :disabled="busy" @tap="logout(true)">退出全部设备</button></view>
    </template>
    <view v-if="error || account.notice" class="error">{{ error || account.notice }}</view>
  </view>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import { account, api, clearAccount, loadShops, selectShop } from '../../services/session'
const server = ref(String(Taro.getStorageSync('soloops.server') || ''))
const username = ref(''), password = ref(''), error = ref(''), busy = ref(false)
const shopIndex = computed(() => Math.max(0, account.shops.findIndex(shop => shop.id === account.shopId)))
const activeShop = computed(() => account.shops.find(shop => shop.id === account.shopId))
function changeShop(event: { detail: { value: string | number } }) { const shop = account.shops[Number(event.detail.value)]; if (shop) selectShop(shop.id) }
async function perform(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true; error.value = ''; account.notice = ''
  try { await action() } catch (cause) { error.value = cause instanceof Error ? cause.message : '操作失败，请重试。' } finally { busy.value = false }
}
async function login() {
  await perform(async () => {
    account.session = await api.login(server.value, username.value, password.value)
    password.value = ''
    try { Taro.setStorageSync('soloops.server', server.value.trim()) } catch { /* Optional setting. */ }
    await loadShops()
  })
}
async function refresh() { await perform(loadShops) }
async function logout(all: boolean) {
  if (all) { const answer = await Taro.showModal({ title: '退出全部设备', content: '所有设备上的会话都将失效，是否继续？' }); if (!answer.confirm) return }
  await perform(async () => { await api.logout(all); clearAccount() })
}
useDidShow(() => { if (account.session) void perform(async () => { await api.request('/mobile/auth/session'); await loadShops() }) })
</script>
