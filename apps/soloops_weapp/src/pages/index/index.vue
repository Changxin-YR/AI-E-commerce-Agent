<template>
  <view class="startup">
    <text class="title">SoloOps</text>
    <text class="description">M0-B · 微信小程序模拟器验证</text>
    <button @tap="Taro.navigateTo({ url: '/pages/diagnostics/index' })">查看环境信息</button>
    <text class="detail">生命周期：{{ lifecycle }}</text>
  </view>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import Taro, { useDidShow, useDidHide } from '@tarojs/taro'
const lifecycle = ref('initial')
useDidShow(() => { lifecycle.value = 'show'; console.info('SOLOOPS_M0B lifecycle show') })
useDidHide(() => { lifecycle.value = 'hide'; console.info('SOLOOPS_M0B lifecycle hide') })
</script>
