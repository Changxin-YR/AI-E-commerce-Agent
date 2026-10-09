<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { ScheduleConfig } from '@/api/schedules'
import { rulesApi } from '@/api/businessRules'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import FeedbackBanner from './FeedbackBanner.vue'

const props = defineProps<{ shop: Shop; initial?: ScheduleConfig; busy: boolean }>()
const emit = defineEmits<{ save: [config: ScheduleConfig]; cancel: [] }>()
const form = reactive<ScheduleConfig>(
  props.initial
    ? (JSON.parse(JSON.stringify(props.initial)) as ScheduleConfig)
    : {
        name: '每日运营检查',
        timezone: props.shop.timezone,
        frequency: 'daily',
        local_time: '09:00',
        weekday: 0,
        month_day: 1,
        lookback_days: 7,
        channel: 'generic',
        data_identity: 'user_import',
        currency: props.shop.currency,
        rule_revision_id: 0,
        max_age_hours: 24,
        min_quantity: 1,
        max_margin_percent: '20',
        quiet_start: null,
        quiet_end: null,
      },
)
const confirmed = ref(false)
const quiet = ref(form.quiet_start !== null)
const pending = ref(true)
const activeRule = ref(false)
const error = ref('')
let epoch = 0
async function rules(): Promise<void> {
  const current = ++epoch
  pending.value = true
  error.value = ''
  confirmed.value = false
  try {
    const result = await rulesApi.current(props.shop.id, form.channel, form.data_identity)
    if (current !== epoch) return
    form.rule_revision_id = result.version
    activeRule.value = result.active
    if (result.active) {
      form.max_age_hours = result.values.max_age_hours
      form.min_quantity = result.values.min_quantity
      form.max_margin_percent = result.values.max_margin_percent
    }
    pending.value = false
  } catch (cause) {
    if (current === epoch) error.value = errorMessage(cause)
  }
}
watch(() => [form.channel, form.data_identity], rules, { immediate: true })
watch(
  form,
  () => {
    confirmed.value = false
  },
  { deep: true, flush: 'sync' },
)
watch(quiet, (value) => {
  form.quiet_start = value ? 22 : null
  form.quiet_end = value ? 8 : null
})
function save(): void {
  if (!confirmed.value || pending.value || props.busy) return
  emit('save', JSON.parse(JSON.stringify(form)) as ScheduleConfig)
}
</script>
<template>
  <form class="form-panel section-block" aria-label="定时计划配置" @submit.prevent="save">
    <h2>{{ initial ? '修改计划' : '新建定时检查' }}</h2>
    <FeedbackBanner :message="error" />
    <fieldset :disabled="busy">
      <legend>周期与范围</legend>
      <div class="form-grid">
        <div class="form-field">
          <label for="schedule-name">计划名称</label
          ><input id="schedule-name" v-model="form.name" required maxlength="80" />
        </div>
        <div class="form-field">
          <label for="schedule-zone">运行时区</label
          ><input id="schedule-zone" v-model="form.timezone" required maxlength="64" />
        </div>
        <div class="form-field">
          <label for="schedule-frequency">执行周期</label
          ><select id="schedule-frequency" v-model="form.frequency">
            <option value="daily">每天</option>
            <option value="weekly">每周</option>
            <option value="monthly">每月</option>
          </select>
        </div>
        <div class="form-field">
          <label for="schedule-time">当地运行时间</label
          ><input id="schedule-time" v-model="form.local_time" type="time" required />
        </div>
        <div v-if="form.frequency === 'weekly'" class="form-field">
          <label for="schedule-weekday">星期</label
          ><select id="schedule-weekday" v-model="form.weekday">
            <option
              v-for="(day, i) in ['一', '二', '三', '四', '五', '六', '日']"
              :key="i"
              :value="i"
            >
              星期{{ day }}
            </option>
          </select>
        </div>
        <div v-if="form.frequency === 'monthly'" class="form-field">
          <label for="schedule-day">每月日期（1–28）</label
          ><input
            id="schedule-day"
            v-model.number="form.month_day"
            type="number"
            min="1"
            max="28"
            required
          />
        </div>
        <div class="form-field">
          <label for="schedule-lookback">订单回看天数</label
          ><input
            id="schedule-lookback"
            v-model.number="form.lookback_days"
            type="number"
            min="1"
            max="365"
            required
          />
        </div>
        <div class="form-field">
          <label for="schedule-identity">检查数据身份</label
          ><select id="schedule-identity" v-model="form.data_identity">
            <option value="user_import">用户导入数据</option>
            <option value="synthetic">合成演示数据</option>
          </select>
        </div>
        <div class="form-field">
          <label for="schedule-channel">检查渠道</label
          ><select id="schedule-channel" v-model="form.channel">
            <option value="generic">通用文件</option>
            <option value="shopify">Shopify</option>
            <option value="amazon">Amazon</option>
            <option value="other">其他渠道</option>
          </select>
        </div>
        <div class="form-field">
          <label for="schedule-currency">统计币种</label
          ><select id="schedule-currency" v-model="form.currency">
            <option
              v-for="value in ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']"
              :key="value"
            >
              {{ value }}
            </option>
          </select>
        </div>
      </div>
      <p>
        按每次计划时刻向前回看指定天数（每一天为 24 小时）；商品、库存和消息读取当时可用的导入记录。
      </p>
      <p>
        夏令时重复时刻只运行第一次；不存在的时刻跳过。停机后最多补最近一期，超过 24
        小时记为错过；暂停期间不补跑。
      </p>
      <div class="section-block">
        <p role="status">
          {{
            pending
              ? '正在核对经营规则…'
              : `绑定经营规则版本 #${form.rule_revision_id}${activeRule ? '，使用已生效阈值' : '，使用下方检查阈值'}`
          }}
        </p>
        <button type="button" class="button secondary small" @click="rules">刷新经营规则</button>
        <div class="form-grid">
          <div class="form-field">
            <label for="schedule-age">库存有效小时</label
            ><input
              id="schedule-age"
              v-model.number="form.max_age_hours"
              :disabled="activeRule || pending"
              type="number"
              min="1"
              max="720"
              required
            />
          </div>
          <div class="form-field">
            <label for="schedule-quantity">最少销量</label
            ><input
              id="schedule-quantity"
              v-model.number="form.min_quantity"
              :disabled="activeRule || pending"
              type="number"
              min="1"
              max="1000000"
              required
            />
          </div>
          <div class="form-field">
            <label for="schedule-margin">低毛利阈值 %</label
            ><input
              id="schedule-margin"
              v-model="form.max_margin_percent"
              :disabled="activeRule || pending"
              type="number"
              min="-1000"
              max="100"
              step="0.01"
              required
            />
          </div>
        </div>
      </div>
      <label class="check-label"><input v-model="quiet" type="checkbox" />启用免打扰时段</label>
      <div v-if="quiet" class="form-grid">
        <div class="form-field">
          <label for="quiet-start">免打扰开始小时</label
          ><input
            id="quiet-start"
            v-model.number="form.quiet_start"
            type="number"
            min="0"
            max="23"
            required
          />
        </div>
        <div class="form-field">
          <label for="quiet-end">免打扰结束小时</label
          ><input
            id="quiet-end"
            v-model.number="form.quiet_end"
            type="number"
            min="0"
            max="23"
            required
          />
        </div>
      </div>
      <p>
        免打扰按运行时区生效，期间检查照常保存，未读提醒延后显示；运行历史可随时查看。规则版本变化后计划自动暂停，需核对并更新配置。
      </p>
      <label class="check-label"
        ><input
          v-model="confirmed"
          type="checkbox"
          :disabled="pending"
        />我确认按此周期和范围执行本地检查并保存站内通知，候选逐次审批</label
      >
      <div class="form-actions">
        <button class="button" :disabled="!confirmed || pending || busy">保存计划</button
        ><button class="button secondary" type="button" @click="emit('cancel')">收起配置</button>
      </div>
    </fieldset>
  </form>
</template>
