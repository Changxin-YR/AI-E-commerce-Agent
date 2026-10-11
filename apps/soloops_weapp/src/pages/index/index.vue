<template>
  <view class="startup">
    <text class="title">SoloOps</text>
    <text class="description">M0-A · 微信小程序最小工程</text>
    <button @tap="showDetails = !showDetails">{{ showDetails ? '收起' : '查看环境信息' }}</button>
    <view v-if="showDetails" class="detail">
      <text>Taro 4 · Vue 3 · TypeScript\n本页面用于微信目标编译验证。</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const showDetails = ref(false)
</script>
