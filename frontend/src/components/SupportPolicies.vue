<script setup lang="ts">
import BusinessDateTime from './BusinessDateTime.vue'
import { onMounted, reactive, ref } from 'vue'
import { supportApi } from '@/api/support'
import { errorMessage } from '@/api/client'
import { policyStatus, supportTime, type Policy, type PolicyData } from '@/types/support'
import FeedbackBanner from './FeedbackBanner.vue'

const props = defineProps<{ shopId: number; market: string; timezone: string; disabled: boolean }>()
const emit = defineEmits<{ changed: [] }>()
const policies = ref<Policy[]>([])
const query = ref('')
const offset = ref(0)
const busy = ref(false)
const error = ref('')
const success = ref('')
const editing = ref(false)
const expected = ref<number | null>(null)
const clearing = ref<number | null>(null)
const defaults = (): PolicyData => ({
  code: '',
  title: '',
  topic: 'faq',
  text: '',
  market: props.market,
  channel: 'generic',
  language: 'en',
  data_identity: 'user_import',
  source: '',
  source_version: '',
  source_confirmed: false,
  valid_from: '',
  valid_until: null,
})
const form = reactive<PolicyData>(defaults())
async function perform(work: () => Promise<void>): Promise<void> {
  if (busy.value) return
  busy.value = true
  error.value = ''
  success.value = ''
  try {
    await work()
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function load(page = 0): Promise<void> {
  await perform(async () => {
    policies.value = await supportApi.policies(props.shopId, query.value, page)
    offset.value = page
  })
}
function edit(policy?: Policy): void {
  if (policy?.data) {
    Object.assign(form, policy.data)
    expected.value = policy.id
  } else {
    Object.assign(form, defaults())
    expected.value = null
  }
  editing.value = true
  clearing.value = null
}
async function save(): Promise<void> {
  await perform(async () => {
    await supportApi.savePolicy(
      props.shopId,
      { ...form, valid_until: form.valid_until || null },
      expected.value,
    )
    editing.value = false
    policies.value = await supportApi.policies(props.shopId, query.value, offset.value)
    success.value = '政策版本已保存。已有草稿需重新核对政策。'
    emit('changed')
  })
}
async function clear(id: number): Promise<void> {
  await perform(async () => {
    await supportApi.clearPolicy(props.shopId, id)
    clearing.value = null
    policies.value = await supportApi.policies(props.shopId, query.value, offset.value)
    success.value = '此政策版本及引用它的草稿正文已清除。'
    emit('changed')
  })
}
onMounted(() => load())
</script>
<template>
  <section class="section-block support-policies" aria-label="政策与 FAQ">
    <div class="section-heading">
      <div>
        <h2>政策与 FAQ</h2>
        <p>按出处、市场、渠道、语言与有效期核对。创建新版本后，已有草稿需重新核验。</p>
      </div>
      <button class="button secondary" :disabled="busy || disabled" @click="edit()">
        录入政策
      </button>
    </div>
    <FeedbackBanner :message="error" /><FeedbackBanner :message="success" kind="success" />
    <form class="listing-search" @submit.prevent="load()">
      <div class="form-field">
        <label for="policy-query">检索政策 / FAQ</label
        ><input id="policy-query" v-model="query" maxlength="120" />
      </div>
      <button class="button secondary" :disabled="busy">检索政策</button>
    </form>
    <form v-if="editing" class="listing-edit" @submit.prevent="save">
      <h3>{{ expected ? '保存政策新版本' : '录入政策' }}</h3>
      <fieldset :disabled="busy || disabled">
        <div class="form-grid">
          <div class="form-field">
            <label for="policy-code">政策编号</label
            ><input
              id="policy-code"
              v-model="form.code"
              :readonly="!!expected"
              maxlength="80"
              required
            />
          </div>
          <div class="form-field">
            <label for="policy-title">政策标题</label
            ><input id="policy-title" v-model="form.title" maxlength="120" required />
          </div>
          <div class="form-field">
            <label for="policy-topic">政策主题</label
            ><select id="policy-topic" v-model="form.topic">
              <option value="faq">一般 FAQ</option>
              <option value="shipping">物流规则</option>
              <option value="refund">退货退款</option>
              <option value="warranty">保修条款</option>
            </select>
          </div>
          <div class="form-field">
            <label for="policy-market">适用市场</label
            ><input
              id="policy-market"
              v-model="form.market"
              pattern="[A-Z]{2}"
              maxlength="2"
              required
            />
          </div>
          <div class="form-field">
            <label for="policy-channel">适用渠道</label
            ><select id="policy-channel" v-model="form.channel">
              <option value="generic">通用来源</option>
              <option value="amazon">Amazon 文件</option>
              <option value="shopify">Shopify 文件</option>
              <option value="other">其他合法来源</option>
            </select>
          </div>
          <div class="form-field">
            <label for="policy-language">政策语言</label
            ><select id="policy-language" v-model="form.language">
              <option value="en">English</option>
              <option value="zh">中文</option>
            </select>
          </div>
          <div class="form-field">
            <label for="policy-identity">政策数据身份</label
            ><select id="policy-identity" v-model="form.data_identity">
              <option value="user_import">用户录入资料</option>
              <option value="synthetic">合成测试资料</option>
            </select>
          </div>
          <div class="form-field">
            <label for="policy-source">政策出处</label
            ><input id="policy-source" v-model="form.source" maxlength="400" required />
          </div>
          <div class="form-field">
            <label for="policy-version">来源版本</label
            ><input id="policy-version" v-model="form.source_version" maxlength="80" required />
          </div>
          <BusinessDateTime
            class="full-width"
            v-model="form.valid_from"
            :timezone="timezone"
            label="生效时间（含时区）"
            required
          />
          <BusinessDateTime
            class="full-width"
            v-model="form.valid_until"
            :timezone="timezone"
            label="失效时间（可选，含时区）"
          />
        </div>
        <div class="form-field">
          <label for="policy-text">政策 / FAQ 原文</label
          ><textarea id="policy-text" v-model="form.text" rows="5" maxlength="4000" required />
        </div>
        <label class="check-label"
          ><input
            v-model="form.source_confirmed"
            type="checkbox"
          />我已核对政策出处、适用范围与有效期</label
        >
      </fieldset>
      <div class="button-row">
        <button class="button primary" :disabled="busy || disabled">保存政策版本</button
        ><button type="button" class="button secondary" :disabled="busy" @click="editing = false">
          取消编辑
        </button>
      </div>
    </form>
    <p v-if="!policies.length">未找到政策。请录入可核对的规则，缺少依据时草稿将提示人工核实。</p>
    <details v-for="policy in policies" :key="policy.id" class="support-policy-quote">
      <summary>
        {{ policy.data?.title ?? '已清除政策' }} · #{{ policy.id }} / v{{ policy.number }} ·
        {{ policyStatus[policy.availability] }}
      </summary>
      <template v-if="policy.data"
        ><p>
          {{ policy.data.code }} · {{ policy.data.market }} / {{ policy.data.channel }} /
          {{ policy.data.language }} ·
          {{ policy.data.data_identity === 'synthetic' ? '合成测试资料' : '用户录入资料' }}
        </p>
        <p>
          出处 {{ policy.data.source }} · 来源版本 {{ policy.data.source_version }} ·
          {{ policy.data.source_confirmed ? '人工已核对' : '出处待核对' }}
        </p>
        <p>
          生效 {{ supportTime(policy.data.valid_from, timezone) }}；失效
          {{ policy.data.valid_until ? supportTime(policy.data.valid_until, timezone) : '未设置' }}
        </p>
        <p class="preserve-text">{{ policy.data.text }}</p>
        <div class="button-row">
          <button
            v-if="policy.status === 'active'"
            class="button secondary"
            :disabled="busy || disabled"
            @click="edit(policy)"
          >
            编辑并另存新版本</button
          ><button
            class="button secondary"
            :disabled="busy || disabled"
            @click="clearing = policy.id"
          >
            清除此版本
          </button>
        </div>
        <div v-if="clearing === policy.id" role="alert">
          <p>将擦除此版本原文，以及所有引用它的草稿正文与证据快照。此操作不能恢复。</p>
          <button class="button secondary" :disabled="busy || disabled" @click="clear(policy.id)">
            确认清除政策及关联草稿</button
          ><button class="button secondary" :disabled="busy" @click="clearing = null">
            取消清除
          </button>
        </div>
      </template>
    </details>
    <div class="button-row">
      <button
        class="button secondary"
        :disabled="busy || offset === 0"
        @click="load(Math.max(0, offset - 100))"
      >
        上一页政策</button
      ><button
        class="button secondary"
        :disabled="busy || policies.length < 100"
        @click="load(offset + 100)"
      >
        下一页政策
      </button>
    </div>
  </section>
</template>
