<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSession } from '@/composables/useSession'
import { errorMessage } from '@/api/client'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import FormField from '@/components/FormField.vue'

const router = useRouter()
const { login, connectionError } = useSession()
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)
async function submit(): Promise<void> {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await login(username.value, password.value)
    password.value = ''
    await router.push('/')
  } catch (cause) {
    error.value = errorMessage(cause)
    password.value = ''
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <main class="login-layout">
    <section class="login-story">
      <div class="wordmark">
        <span class="brand-mark" aria-hidden="true"></span>SoloOps<span class="brand-dot">.</span>
      </div>
      <div>
        <h1>经营有方向，<br />每一步都有依据。</h1>
        <p>为独立跨境卖家准备的运营工作台。<br />整理数据、理解业务，把想法变成可追踪的行动。</p>
      </div>
      <div class="story-footer">
        <span>一个人的生意，也可以井然有序。</span><span>SO / 01</span>
      </div>
    </section>
    <section class="login-form-panel" aria-labelledby="login-heading">
      <form class="login-form" @submit.prevent="submit">
        <h2 id="login-heading">回到你的工作台</h2>
        <p class="muted">使用你的本地账号登录。</p>
        <FeedbackBanner :message="error || connectionError" /><FormField
          label="账号"
          for-id="username"
          ><input
            id="username"
            v-model="username"
            autocomplete="username"
            required
            maxlength="64"
            placeholder="输入账号" /></FormField
        ><FormField label="密码" for-id="password"
          ><input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
            maxlength="128"
            placeholder="输入密码" /></FormField
        ><button class="button primary login-submit" :disabled="busy">
          {{ busy ? '正在登录…' : '进入工作台' }}
        </button>
        <details class="login-help">
          <summary>首次使用或忘记密码？</summary>
          <p>
            由本机管理员通过账号管理命令创建账号或重置密码。具体操作见项目 README
            的“账号管理”；重置后旧会话会失效。
          </p>
        </details>
      </form>
      <p class="login-footnote">经营数据保存在你的 MySQL 数据库中</p>
    </section>
  </main>
</template>
