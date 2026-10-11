<template>
  <PageShell
    title="库存快照"
    subtitle="各渠道分别核对快照。没有快照的 SKU 库存未知，订单不会自动扣减本地快照。"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    @retry="load(offset)"
  >
    <view class="field">
      <text class="field__label">数据身份</text>
      <picker
        mode="selector"
        :range="identityOptions"
        range-key="label"
        :value="identityIndex"
        @change="identity = pickValue(identityOptions, $event)"
      >
        <view class="field__picker">{{ identityOptions[identityIndex]?.label }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">来源渠道</text>
      <picker
        mode="selector"
        :range="channelOptions"
        range-key="label"
        :value="channelIndex"
        @change="channel = pickValue(channelOptions, $event)"
      >
        <view class="field__picker">{{ channelOptions[channelIndex]?.label }}</view>
      </picker>
    </view>
    <view class="field">
      <text class="field__label">快照有效小时数（1–720）</text>
      <input
        class="field__input"
        type="number"
        :value="age"
        :disabled="busy"
        @input="age = inputValue($event)"
      />
    </view>
    <view class="field">
      <text class="field__label">搜索 SKU（最多 120 字）</text>
      <input
        class="field__input"
        :value="search"
        :disabled="busy"
        @input="search = inputValue($event)"
      />
    </view>

    <view class="row">
      <ActionButton label="核对库存" variant="primary" :disabled="busy" @tap="load(0)" />
      <ActionButton label="导入库存 / 更新安全阈值" :disabled="busy" @tap="openImports" />
    </view>

    <template v-if="result">
      <FactLine label="核对时间 / 来源版本" :value="`${businessTimeText(result.checked_at, zone)} / ${result.source_revision}`" />
      <FactLine
        label="本次依据"
        :value="`${labelOf(importIdentities, result.scope.data_identity)} · ${labelOf(importChannels, result.scope.channel)} · ${result.scope.max_age_hours} 小时`"
      />
      <FactLine label="说明" :value="result.note" />

      <view v-if="result.items.length === 0" class="card">
        <text class="warn">库存未知 / 未检查：此范围没有可用快照。</text>
      </view>

      <view v-for="item in result.items" :key="item.id" class="card">
        <text class="card__title">{{ item.sku }} · {{ labelOf(inventoryStatuses, item.status) }}</text>
        <FactLine label="快照可售数量 / 安全阈值" :value="`${item.available} / ${item.safety_threshold}`" />
        <FactLine label="当前库存判定" :value="labelOf(inventoryStatuses, item.status)" />
        <FactLine label="判断依据" :value="item.reason" />
        <FactLine label="快照时间" :value="item.snapshot_at" :zone="zone" />
        <FactLine label="有效至" :value="item.valid_until" :zone="zone" />
        <FactLine label="来源渠道" :value="labelOf(importChannels, item.channel)" />

        <ActionButton
          v-for="task in linkedTasks(item.sku)"
          :key="task.id"
          :label="`关联待办 #${task.id} · ${labelOf(taskLabels, task.status)} · ${labelOf(businessLabels, task.business_state)}`"
          @tap="openTask(task.id)"
        />
      </view>

      <view class="row">
        <ActionButton v-if="offset > 0" label="上一页快照" :disabled="busy" @tap="load(offset - 50)" />
        <ActionButton v-if="result.has_more" label="下一页快照" :disabled="busy" @tap="load(offset + 50)" />
        <ActionButton v-if="moreTasks" label="继续查找关联待办" :disabled="busy" @tap="readTasks(true)" />
      </view>

      <ActionButton
        label="进入运营巡检，生成或复查低库存待办"
        :disabled="busy"
        @tap="openTab('/pages/home/index')"
      />
    </template>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 库存快照：过期未知、低库存与关联待办。
 * 接口：
 *   GET /api/shops/{shop_id}/inventory（data_identity、channel、max_age_hours、search、offset）
 *   GET /api/shops/{shop_id}/operations/tasks（关联待办，kind=low_inventory）
 */
import { computed, ref } from 'vue'
import { useDidShow } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import ActionButton from '../../ui/ActionButton.vue'
import { apiGet, asObject } from '../../core/api'
import { businessTimeText } from '../../core/format'
import {
  businessLabels,
  importChannels,
  importIdentities,
  inventoryStatuses,
  labelOf,
  taskLabels,
} from '../../core/labels'
import { openPage, openTab, setPendingIntent } from '../../core/links'
import { ensureSession, perform, shopPath, shopTimezone, state } from '../../core/store'

interface InventoryItem {
  id: number
  sku: string
  channel: string
  available: number
  safety_threshold: number
  snapshot_at: string
  valid_until: string
  status: string
  reason: string
}

interface InventoryResult {
  checked_at: string
  source_revision: number
  scope: { data_identity: string; channel: string; max_age_hours: number }
  items: InventoryItem[]
  has_more: boolean
  note: string
}

interface OperationTask {
  id: number
  kind: string
  status: string
  business_state: string
  snapshot: { object_label: string } | null
}

interface TaskPage {
  items: OperationTask[]
  has_more: boolean
}

const identityOptions = Object.entries(importIdentities).map(([key, label]) => ({ key, label }))
const channelOptions = Object.entries(importChannels).map(([key, label]) => ({ key, label }))

const identity = ref('user_import')
const channel = ref('generic')
const age = ref('24')
const search = ref('')
const result = ref<InventoryResult | null>(null)
const tasks = ref<OperationTask[]>([])
const offset = ref(0)
const taskOffset = ref(0)
const moreTasks = ref(false)
const busy = ref(false)
const error = ref('')
const ready = ref(false)

const zone = computed(() => shopTimezone())
const identityIndex = computed(() => Math.max(0, identityOptions.findIndex((item) => item.key === identity.value)))
const channelIndex = computed(() => Math.max(0, channelOptions.findIndex((item) => item.key === channel.value)))

function pickValue(
  options: Array<{ key: string; label: string }>,
  event: { detail: { value: string } },
): string {
  return options[Number(event.detail.value)]?.key ?? ''
}

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  await load(0)
})

async function load(nextOffset: number): Promise<void> {
  if (!ready.value) return
  const hours = Number(age.value)
  if (!Number.isInteger(hours) || hours < 1 || hours > 720) {
    error.value = '有效时长须为 1–720 小时，SKU 搜索最多 120 字。'
    return
  }
  if (search.value.length > 120) {
    error.value = '有效时长须为 1–720 小时，SKU 搜索最多 120 字。'
    return
  }
  const message = await perform(async () => {
    const value = asObject<InventoryResult>(
      await apiGet(shopPath('/inventory'), {
        data_identity: identity.value,
        channel: channel.value,
        max_age_hours: hours,
        search: search.value.trim(),
        offset: nextOffset,
      }),
    )
    if (value === null) throw new Error('库存响应无法读取，请刷新重试。')
    result.value = value
    offset.value = nextOffset
    tasks.value = []
    taskOffset.value = 0
    await readTasks(false)
  })
  error.value = message
}

async function readTasks(more: boolean): Promise<void> {
  const scope = result.value?.scope
  if (!scope) return
  const value = asObject<TaskPage>(
    await apiGet(shopPath('/operations/tasks'), {
      data_identity: scope.data_identity,
      channel: scope.channel,
      offset: more ? taskOffset.value + 50 : 0,
    }),
  )
  if (value === null) return
  taskOffset.value = more ? taskOffset.value + 50 : 0
  const incoming = (Array.isArray(value.items) ? value.items : []).filter(
    (task) => task.kind === 'low_inventory',
  )
  tasks.value = more ? [...tasks.value, ...incoming] : incoming
  moreTasks.value = value.has_more === true
}

/** 关联待办：按快照对象标签（SKU）匹配低库存待办。 */
function linkedTasks(sku: string): OperationTask[] {
  return tasks.value.filter((task) => task.snapshot?.object_label === sku)
}

function openTask(id: number): void {
  setPendingIntent('/pages/tasks/index', { task: `${id}` })
  openTab('/pages/tasks/index')
}

function openImports(): void {
  openPage('/pages/imports/index', {
    kind: 'inventory',
    identity: identity.value,
    channel: channel.value,
  })
}
</script>
