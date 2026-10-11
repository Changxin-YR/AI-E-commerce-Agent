<script setup lang="ts">
import { onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import Taro from '@tarojs/taro'
import { account, api } from '../services/session'
import { scopedRequest } from '../services/scoped-request'
import { queryString } from '../services/task-policy'
import { awareTimestamp } from '../services/support-policy'
import {
  policyStatus,
  type Policy,
  type PolicyData,
} from '../services/support-types'
const props = defineProps<{ market: string; disabled: boolean }>()
const emit = defineEmits<{
  changed: []
  working: [value: boolean]
  editing: [value: boolean]
}>()
const items = ref<Policy[]>([]),
  search = ref(''),
  offset = ref(0),
  busy = ref(false),
  error = ref(''),
  unknown = ref(false),
  editing = ref(false),
  expected = ref<number | null>(null)
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
const form = reactive(defaults())
const options = {
  topic: ['faq', 'shipping', 'refund', 'warranty'],
  channel: ['generic', 'shopify', 'amazon', 'other'],
  language: ['en', 'zh'],
  data_identity: ['user_import', 'synthetic'],
} as const
let alive = true
const request = scopedRequest(api, () =>
  alive ? `${account.shopId}:${account.session?.session_id}` : null,
)
watch(editing, (value) => emit('editing', value), { flush: 'sync' })
onBeforeUnmount(() => {
  alive = false
})
watch(
  () => [
    form.code,
    form.title,
    form.topic,
    form.text,
    form.market,
    form.channel,
    form.language,
    form.data_identity,
    form.source,
    form.source_version,
    form.valid_from,
    form.valid_until,
  ],
  () => {
    form.source_confirmed = false
  },
  { flush: 'sync' },
)
const base = () => `/shops/${account.shopId}/support/policies`
function checked(event: unknown) {
  return Boolean((event as { detail: { value: boolean } }).detail.value)
}
function pick(field: keyof typeof options, event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  Object.assign(form, { [field]: options[field][index] })
}
async function run(work: () => Promise<void>) {
  if (busy.value || props.disabled || !alive) return
  busy.value = true
  emit('working', true)
  error.value = ''
  try {
    await work()
  } catch (cause) {
    if (alive)
      error.value =
        cause instanceof Error ? cause.message : '政策操作失败，请刷新核对。'
  } finally {
    busy.value = false
    if (alive) emit('working', false)
  }
}
async function load(page = 0) {
  const values = await request<Policy[]>(
    `${base()}?${queryString({ q: search.value, offset: page })}`,
  )
  if (!alive) return
  items.value = values
  offset.value = page
  unknown.value = false
}
async function edit(item?: Policy) {
  if (busy.value || props.disabled || !alive) return
  if (editing.value) {
    const answer = await Taro.showModal({
      title: '替换政策编辑',
      content: '当前政策表单尚未保存，是否替换？',
    })
    if (!answer.confirm || !alive) return
  }
  Object.assign(form, item?.data || defaults())
  form.source_confirmed = false
  expected.value = item?.id || null
  editing.value = true
}
async function cancel() {
  if (busy.value || props.disabled || unknown.value) return
  const answer = await Taro.showModal({
    title: '取消政策编辑',
    content: '放弃未保存的政策内容？',
  })
  if (answer.confirm && alive) {
    editing.value = false
    Object.assign(form, defaults())
  }
}
async function save() {
  await run(async () => {
    if (unknown.value) throw new Error('请先刷新政策核对上次保存结果。')
    if (!form.source_confirmed) throw new Error('请先核对政策出处及适用范围。')
    const from = awareTimestamp(form.valid_from),
      until = form.valid_until ? awareTimestamp(form.valid_until) : null
    if (until && until <= from) throw new Error('结束时间须晚于生效时间。')
    if (!/^[A-Z]{2}$/.test(form.market))
      throw new Error('市场须为两位大写国家代码。')
    unknown.value = true
    await request<Policy>(base(), 'POST', {
      expected_policy_id: expected.value,
      data: { ...form, valid_from: from, valid_until: until },
    })
    editing.value = false
    search.value = ''
    await load()
    emit('changed')
  })
}
async function clear(item: Policy) {
  await run(async () => {
    if (unknown.value) throw new Error('请先刷新核对。')
    const shopId = account.shopId,
      sessionId = account.session?.session_id
    const answer = await Taro.showModal({
      title: '清除政策正文',
      content: `清除政策 #${item.id} v${item.number} 及引用它的草稿正文，保留无正文处理记录。此操作不可恢复，是否继续？`,
    })
    if (
      !answer.confirm ||
      !alive ||
      shopId !== account.shopId ||
      sessionId !== account.session?.session_id
    )
      return
    unknown.value = true
    await request<Policy>(`${base()}/${item.id}/clear`, 'POST')
    await load(offset.value)
    emit('changed')
  })
}
onMounted(() => {
  void run(() => load())
})
</script>
<template>
  <view class="card"
    ><text class="section-title">政策与 FAQ</text
    ><text class="hint"
      >保存新版本后，已有草稿需重新核验。时间填写 ISO 格式并带时区。</text
    ><text v-if="error" class="error">{{ error }}</text
    ><text v-if="unknown" class="error">操作结果待核对，请刷新政策。</text>
    <input
      v-model="search"
      :maxlength="120"
      :disabled="busy || disabled"
      placeholder="政策标题 / 正文关键词"
    /><button :disabled="busy || disabled" @tap="run(() => load())">
      查找 / 刷新政策</button
    ><button :disabled="busy || disabled || unknown" @tap="edit()">
      录入政策
    </button>
    <view v-if="editing"
      ><text class="label">{{
        expected ? `基于 #${expected} 保存新版本` : '新政策'
      }}</text>
      <input
        v-model="form.code"
        :maxlength="80"
        :disabled="busy || disabled || !!expected"
        placeholder="政策编号"
      /><input
        v-model="form.title"
        :maxlength="120"
        :disabled="busy || disabled"
        placeholder="标题"
      />
      <picker
        v-for="(values, field) in options"
        :key="field"
        :range="values"
        :disabled="busy || disabled"
        @change="pick(field, $event)"
        ><view class="field"
          >{{
            {
              topic: '主题',
              channel: '渠道',
              language: '语言',
              data_identity: '数据身份',
            }[field]
          }}：{{ form[field] }}</view
        ></picker
      >
      <input
        v-model="form.market"
        :maxlength="2"
        :disabled="busy || disabled"
        placeholder="市场，例如 US"
      /><textarea
        v-model="form.text"
        :maxlength="4000"
        :auto-height="true"
        :disabled="busy || disabled"
        placeholder="政策全文"
      /><input
        v-model="form.source"
        :maxlength="400"
        :disabled="busy || disabled"
        placeholder="政策出处"
      /><input
        v-model="form.source_version"
        :maxlength="80"
        :disabled="busy || disabled"
        placeholder="来源版本"
      /><input
        v-model="form.valid_from"
        :maxlength="40"
        :disabled="busy || disabled"
        placeholder="生效时间，如 2026-10-11T00:00:00+08:00"
      /><input
        v-model="form.valid_until"
        :maxlength="40"
        :disabled="busy || disabled"
        placeholder="结束时间（可留空，不含该时刻）"
      />
      <view class="row"
        ><text>已核对出处、版本及适用范围</text
        ><switch
          :checked="form.source_confirmed"
          :disabled="busy || disabled"
          @change="form.source_confirmed = checked($event)" /></view
      ><button
        :disabled="busy || disabled || unknown || !form.source_confirmed"
        @tap="save"
      >
        保存政策版本并回读
      </button>
      <button :disabled="busy || disabled || unknown" @tap="cancel">
        取消编辑
      </button>
    </view>
    <text v-if="!items.length" class="muted">暂无匹配政策。</text
    ><view v-for="item in items" :key="item.id"
      ><text class="label"
        >#{{ item.id }} · v{{ item.number }} ·
        {{ policyStatus[item.availability] || item.availability }}</text
      ><template v-if="item.data"
        ><text>{{ item.data.code }} · {{ item.data.title }}</text
        ><text class="prose">{{ item.data.text }}</text
        ><text class="hint"
          >{{ item.data.source }} / {{ item.data.source_version }} ·
          {{ item.data.market }} / {{ item.data.channel }} /
          {{ item.data.language }} / {{ item.data.data_identity }}</text
        ><text class="hint"
          >{{ item.data.valid_from }} 至
          {{ item.data.valid_until || '长期' }}</text
        ><button :disabled="busy || disabled || unknown" @tap="edit(item)">
          以此政策创建新版本</button
        ><button :disabled="busy || disabled || unknown" @tap="clear(item)">
          清除此政策版本及派生正文
        </button></template
      ><text v-else>正文已清除。</text></view
    >
    <view class="row"
      ><button
        :disabled="busy || disabled || offset === 0"
        @tap="run(() => load(offset - 100))"
      >
        上一页</button
      ><text>{{ offset / 100 + 1 }}</text
      ><button
        :disabled="busy || disabled || items.length < 100"
        @tap="run(() => load(offset + 100))"
      >
        下一页
      </button></view
    >
  </view>
</template>
<style scoped>
.prose {
  display: block;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
