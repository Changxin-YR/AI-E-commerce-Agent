<template>
  <view class="shell">
    <view class="shell__head">
      <text class="shell__title">{{ title }}</text>
      <text v-if="subtitle" class="shell__subtitle">{{ subtitle }}</text>
    </view>

    <view v-if="notice" class="shell__notice">
      <text class="shell__notice-text">{{ notice }}</text>
    </view>
    <view v-if="success" class="shell__success">
      <text class="shell__success-text">{{ success }}</text>
    </view>
    <view v-if="error" class="shell__error">
      <text class="shell__error-text">{{ error }}</text>
      <button v-if="retryable" class="shell__retry" size="mini" @tap="emit('retry')">重试</button>
    </view>

    <view v-if="loading" class="shell__loading">
      <text class="shell__loading-text">加载中…</text>
    </view>

    <view v-if="empty" class="shell__empty">
      <text class="shell__empty-text">{{ emptyText }}</text>
    </view>
    <slot v-else />

    <view v-if="footer" class="shell__footer">
      <text class="shell__footer-text">{{ footer }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
/**
 * PageShell：页面骨架，统一标题、返回、加载态、空态、错误态与提示。
 * 页面只负责业务区块；未知值由 FactLine 显示为“未知”。
 */
withDefaults(
  defineProps<{
    title: string
    subtitle?: string
    loading?: boolean
    error?: string
    notice?: string
    success?: string
    empty?: boolean
    emptyText?: string
    footer?: string
    retryable?: boolean
  }>(),
  {
    subtitle: '',
    loading: false,
    error: '',
    notice: '',
    success: '',
    empty: false,
    emptyText: '没有符合当前范围的记录。显示调整范围或导入入口，不生成示例业务数字。',
    footer: '',
    retryable: true,
  },
)

const emit = defineEmits<{ (event: 'retry'): void }>()
</script>
