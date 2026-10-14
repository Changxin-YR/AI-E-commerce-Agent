<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSession } from '@/composables/useSession'
import { errorMessage } from '@/api/client'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import FormField from '@/components/FormField.vue'
import AppIcon from '@/components/AppIcon.vue'

const router = useRouter()
const route = useRoute()
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
    const target = route.query.redirect
    await router.replace(
      typeof target === 'string' && target.startsWith('/') && !target.startsWith('//')
        ? target
        : '/',
    )
  } catch (cause) {
    error.value = errorMessage(cause)
    password.value = ''
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <main class="login-layout page-login">
    <section class="login-story">
      <div class="wordmark">
        <span class="brand-mark" aria-hidden="true"><AppIcon name="leaf" :size="28" /></span
        >SoloOps<span class="brand-dot">.</span>
      </div>
      <div>
        <h1>经营有方向，<br />每一步都有依据。</h1>
        <p>为独立跨境卖家准备的运营工作台。<br />整理数据、理解业务，把想法变成可追踪的行动。</p>
        <div class="login-workflow" aria-label="经营工作流程">
          <div>
            <AppIcon name="upload" :size="24" /><strong>整理你的数据</strong
            ><small>商品、订单与成本</small>
          </div>
          <div>
            <AppIcon name="chart" :size="24" /><strong>看清经营状况</strong
            ><small>每个结论有据可查</small>
          </div>
          <div>
            <AppIcon name="check" :size="24" /><strong>推进下一步</strong
            ><small>审阅、处理与回读</small>
          </div>
        </div>
      </div>
      <div class="story-footer">
        <span>一个人的生意，也可以井然有序。</span><span>SO / 01</span>
      </div>
    </section>
    <section class="login-form-panel" aria-labelledby="login-heading">
      <form class="login-form" @submit.prevent="submit">
        <h2 id="login-heading">回到你的工作台</h2>
        <p class="muted">使用管理员为你开通的账号登录。</p>
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
            首次使用，请向为你部署 SoloOps 的管理员领取工作台网址、账号和密码，并确认求助方式。
            登录后可在网页添加店铺、导入文件，开始经营操作。
          </p>
          <p>忘记密码或无法登录时，请联系管理员核对网址和账号、重置密码；重置后需重新登录。</p>
        </details>
      </form>
      <p class="login-footnote">经营数据保存在管理员为你部署的工作空间中</p>
    </section>
  </main>
</template>
