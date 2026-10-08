<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { importsApi } from '@/api/imports'
import { errorMessage } from '@/api/client'
import type { FieldDefinition, ImportBatch } from '@/types/imports'
import FeedbackBanner from './FeedbackBanner.vue'
import ImportRows from './ImportRows.vue'

const props = defineProps<{ shopId: number; timezone: string }>()
const emit = defineEmits<{ saved: [] }>()
const form = reactive({
  message_id: '',
  sent_at: '',
  body: '',
  language: 'und',
  order_id: '',
  channel: 'generic',
  identity: 'user_import',
})
const batch = ref<ImportBatch | null>(null)
const fields = ref<FieldDefinition[]>([])
const busy = ref(false)
const error = ref('')
const allowUpdates = ref(false)
const fingerprint = ref('')
const current = computed(() => JSON.stringify(form))
const dirty = computed(() => current.value !== fingerprint.value)
watch(
  () => props.shopId,
  () => {
    batch.value = null
    error.value = ''
    form.body = ''
    form.message_id = ''
    form.order_id = ''
  },
)
async function preview(): Promise<void> {
  busy.value = true
  error.value = ''
  batch.value = null
  allowUpdates.value = false
  try {
    fields.value = (await importsApi.catalog()).messages
    const keys = ['message_id', 'sent_at', 'body', 'language', 'order_id'] as const
    const escape = (value: string) => `"${value.replaceAll('"', '""')}"`
    const csv = `${keys.join(',')}\n${keys.map((key) => escape(form[key])).join(',')}\n`
    const file = new File([csv], 'manual-message.csv', { type: 'text/csv' })
    const uploaded = await importsApi.upload(props.shopId, file, {
      filename: file.name,
      kind: 'messages',
      source_channel: form.channel,
      data_identity: form.identity,
      timezone: props.timezone,
    })
    batch.value = await importsApi.preview(uploaded.id, uploaded.version, uploaded.mapping, {})
    fingerprint.value = current.value
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function save(): Promise<void> {
  if (!batch.value || dirty.value) return
  busy.value = true
  error.value = ''
  try {
    await importsApi.commit(batch.value.id, batch.value.version, allowUpdates.value)
    batch.value = null
    form.body = ''
    form.message_id = ''
    form.order_id = ''
    emit('saved')
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <details class="section-block">
    <summary>手工录入客服消息</summary>
    <p>填写原消息与来源，核对预览后保存；可在数据导入页撤销或清除这条记录。</p>
    <form class="listing-edit" @submit.prevent="preview">
      <fieldset :disabled="busy">
        <div class="form-grid">
          <div class="form-field">
            <label for="message-id">消息标识</label
            ><input id="message-id" v-model="form.message_id" maxlength="120" required />
          </div>
          <div class="form-field">
            <label for="message-time">消息时间</label
            ><input
              id="message-time"
              v-model="form.sent_at"
              placeholder="2026-10-09T09:00:00+08:00"
              required
            /><small>无偏移时按 {{ timezone }} 解析</small>
          </div>
          <div class="form-field">
            <label for="message-channel">消息来源渠道</label
            ><select id="message-channel" v-model="form.channel">
              <option value="generic">通用来源</option>
              <option value="amazon">Amazon 文件</option>
              <option value="shopify">Shopify 文件</option>
              <option value="other">其他合法来源</option>
            </select>
          </div>
          <div class="form-field">
            <label for="message-identity">消息数据身份</label
            ><select id="message-identity" v-model="form.identity">
              <option value="user_import">用户导入数据</option>
              <option value="synthetic">合成测试数据</option>
            </select>
          </div>
          <div class="form-field">
            <label for="message-language">消息语言</label
            ><select id="message-language" v-model="form.language">
              <option value="und">待人工确认 / 其他语言</option>
              <option value="en">English</option>
              <option value="zh">中文</option>
            </select>
          </div>
          <div class="form-field">
            <label for="message-order">待核验订单号（可选）</label
            ><input id="message-order" v-model="form.order_id" maxlength="120" />
          </div>
        </div>
        <div class="form-field">
          <label for="message-body">消息原文</label
          ><textarea id="message-body" v-model="form.body" rows="4" maxlength="2000" required />
        </div>
      </fieldset>
      <button class="button secondary" :disabled="busy">预览消息</button>
    </form>
    <FeedbackBanner :message="error" />
    <div v-if="batch" class="support-preview">
      <p>
        批次 #{{ batch.id }} · 新增 {{ batch.new_rows }} · 更新 {{ batch.updated_rows }} · 相同
        {{ batch.unchanged_rows }} · 错误 {{ batch.error_rows }}
      </p>
      <ImportRows
        :rows="batch.rows"
        :fields="fields"
        :editable="false"
        :corrections="{}"
        :disabled="busy"
      />
      <label v-if="batch.updated_rows" class="check-label"
        ><input v-model="allowUpdates" type="checkbox" />我已核对旧值与新值，允许覆盖这条消息</label
      >
      <p v-if="dirty">输入已变化，请重新预览。</p>
      <button
        class="button primary"
        :disabled="
          busy ||
          dirty ||
          batch.error_rows > 0 ||
          batch.errors.length > 0 ||
          (!!batch.updated_rows && !allowUpdates)
        "
        @click="save"
      >
        确认保存消息
      </button>
    </div>
  </details>
</template>
