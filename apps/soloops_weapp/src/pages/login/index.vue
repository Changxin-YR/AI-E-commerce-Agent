<template>
  <PageShell
    title="SoloOps"
    subtitle="把每天的经营事务，整理成下一步行动。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
  >
    <FactLine label="服务地址" :value="state.baseUrl" />
    <text class="hint">
      小程序只能在后台配置的合法域名内请求；如需更换地址，请用 TARO_APP_API_BASE 重新构建。
    </text>

    <view class="field">
      <text class="field__label">账号</text>
      <input
        class="field__input"
        :value="username"
        :disabled="busy"
        placeholder="请输入经营账号"
        @input="username = inputValue($event)"
      />
    </view>
    <view class="field">
      <text class="field__label">密码</text>
      <input
        class="field__input"
        password
        :value="password"
        :disabled="busy"
        placeholder="请输入密码"
        @input="password = inputValue($event)"
      />
    </view>

    <ActionButton
      :label="busy ? '正在登录…' : '登录'"
      variant="primary"
      block
      :disabled="busy"
      @tap="submit"
    />

    <text class="hint">使用管理员创建的经营账号。登录后可创建店铺、导入报表并开始处理事务。</text>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 登录页。
 * 接口：POST /api/mobile/auth/login（client_type=weapp）、GET /api/shops。
 * 说明：契约 r2.login 的 api_ref 指向 Web Cookie 会话 /api/auth/login；
 * 小程序使用 Bearer 移动会话入口，与 Flutter 端保持一致。
 */
import { ref } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import ActionButton from '../../ui/ActionButton.vue'
import { errorMessage } from '../../core/api'
import { login, state } from '../../core/store'

const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')

useDidShow(() => {
  if (state.session !== null) {
    void Taro.reLaunch({ url: '/pages/home/index' })
  }
})

async function submit(): Promise<void> {
  if (busy.value) return
  const account = username.value.trim()
  if (account === '') {
    error.value = '请填写账号'
    return
  }
  if (password.value === '') {
    error.value = '请填写密码'
    return
  }
  busy.value = true
  error.value = ''
  try {
    await login(account, password.value)
    password.value = ''
    await Taro.reLaunch({ url: '/pages/home/index' })
  } catch (failure) {
    error.value = errorMessage(failure)
  } finally {
    busy.value = false
  }
}
</script>
