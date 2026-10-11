<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useDidShow, useLoad, useUnload } from '@tarojs/taro'
import { account, api } from '../../services/session'
import { scopedRequest } from '../../services/scoped-request'
import {
  inventoryScope,
  inventoryTasks,
  type InventoryResult,
} from '../../services/inventory-policy'
import { type OperationTask, taskLabels } from '../../services/operation-types'
import { queryString } from '../../services/task-policy'
import { supportTime } from '../../services/support-types'
import { openLink } from '../../services/navigation'
import SourceList from '../../components/SourceList.vue'

const scope = reactive(inventoryScope({}))
const result = ref<InventoryResult>(),
  tasks = ref<OperationTask[]>([])
const busy = ref(false),
  error = ref(''),
  taskError = ref(''),
  moreTasks = ref(false)
let epoch = 0,
  alive = true,
  taskOffset = 0
const request = scopedRequest(api, () => (alive ? epoch : null))
const timezone = computed(
  () =>
    account.shops.find((s) => s.id === account.shopId)?.timezone ||
    'Asia/Shanghai',
)
const identities = ['user_import', 'synthetic'],
  channels = ['generic', 'shopify', 'amazon', 'other']
const labels = {
  low: '低于安全阈值',
  above_threshold: '未低于安全阈值',
  unknown: '当前库存未知',
}
let linked: Record<string, string> = {}
useLoad((params) => {
  linked = params as Record<string, string>
})
useUnload(() => {
  alive = false
  epoch++
})
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    epoch++
    result.value = undefined
    tasks.value = []
    linked = {}
    moreTasks.value = false
    error.value = taskError.value = ''
  },
  { flush: 'sync' },
)
watch(
  scope,
  () => {
    result.value = undefined
    tasks.value = []
    moreTasks.value = false
  },
  { flush: 'sync' },
)

async function readTasks(append = false) {
  const page = await request<{ items: OperationTask[]; has_more: boolean }>(
    `/shops/${account.shopId}/operations/tasks?${queryString({ data_identity: scope.data_identity, channel: scope.channel, offset: append ? taskOffset : 0 })}`,
  )
  tasks.value = append ? [...tasks.value, ...page.items] : page.items
  taskOffset = (append ? taskOffset : 0) + page.items.length
  moreTasks.value = page.has_more
}
async function load(page = 0) {
  if (busy.value || !alive) return
  const token = epoch
  busy.value = true
  error.value = taskError.value = ''
  result.value = undefined
  tasks.value = []
  taskOffset = 0
  moreTasks.value = false
  try {
    if (!account.session || !account.shopId)
      throw new Error('请先登录并选择店铺。')
    const input = inventoryScope({
      ...scope,
      max_age_hours: String(scope.max_age_hours),
      offset: String(page),
    })
    scope.offset = page
    result.value = await request<InventoryResult>(
      `/shops/${account.shopId}/inventory?${queryString({ ...input, offset: page })}`,
    )
    try {
      await readTasks()
    } catch (cause) {
      if (alive && token === epoch)
        taskError.value =
          cause instanceof Error ? cause.message : '关联待办读取失败。'
    }
  } catch (cause) {
    if (alive && token === epoch)
      error.value = cause instanceof Error ? cause.message : '库存读取失败。'
  } finally {
    busy.value = false
  }
}
async function more() {
  if (busy.value) return
  const token = epoch
  busy.value = true
  taskError.value = ''
  try {
    await readTasks(true)
  } catch (cause) {
    if (alive && token === epoch)
      taskError.value =
        cause instanceof Error ? cause.message : '待办读取失败。'
  } finally {
    busy.value = false
  }
}
async function navigate(path: string, extra: Record<string, string> = {}) {
  try {
    await openLink(path, {
      shop: String(account.shopId),
      identity: scope.data_identity,
      channel: scope.channel,
      max_age_hours: String(scope.max_age_hours),
      ...extra,
    })
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '打开页面失败。'
  }
}
function pick(field: 'data_identity' | 'channel', event: unknown) {
  const index = Number((event as { detail: { value: string } }).detail.value)
  if (field === 'data_identity')
    scope.data_identity = identities[index] as typeof scope.data_identity
  else scope.channel = channels[index] || 'generic'
}
useDidShow(() => {
  try {
    if (linked.shop && Number(linked.shop) !== account.shopId)
      throw new Error('链接店铺与当前店铺不同。')
    if (Object.keys(linked).length) Object.assign(scope, inventoryScope(linked))
    linked = {}
    void load(scope.offset)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '链接范围无效。'
  }
})
</script>
<template>
  <view class="screen">
    <view class="hero"
      ><text class="eyebrow">SOLOOPS · INVENTORY</text
      ><text class="title">库存判断，从快照出发。</text
      ><text class="muted">核对可售数量、快照时间和安全阈值。</text></view
    >
    <view v-if="error" class="error">{{ error }}</view>
    <view class="card">
      <text class="hint"
        >库存是可选数据，未列出的 SKU
        库存未知。订单不会自动扣减本地快照；跨渠道不合计。</text
      >
      <picker
        :range="['用户导入', '合成测试']"
        :value="identities.indexOf(scope.data_identity)"
        :disabled="busy"
        @change="pick('data_identity', $event)"
        ><view class="field"
          >身份：{{
            scope.data_identity === 'synthetic' ? '合成测试' : '用户导入'
          }}</view
        ></picker
      >
      <picker
        :range="channels"
        :value="channels.indexOf(scope.channel)"
        :disabled="busy"
        @change="pick('channel', $event)"
        ><view class="field">渠道：{{ scope.channel }}</view></picker
      >
      <text class="label">快照有效时长（1–720小时）</text
      ><input
        v-model.number="scope.max_age_hours"
        type="number"
        :disabled="busy"
      />
      <text class="label">SKU 筛选</text
      ><input
        v-model="scope.search"
        :maxlength="120"
        :disabled="busy"
        placeholder="输入 SKU"
      />
      <button class="primary" :disabled="busy" :loading="busy" @tap="load()">
        查询库存
      </button>
      <button
        :disabled="busy"
        @tap="navigate('/imports', { kind: 'inventory' })"
      >
        导入库存快照
      </button>
      <text class="hint"
        >安全阈值来自已确认导入行，调整时请重新导入并核对差异。</text
      >
    </view>
    <view v-if="result" class="card">
      <text class="section-title"
        >当前快照 · 来源版本 {{ result.source_revision }}</text
      >
      <text class="hint"
        >核对时间 {{ supportTime(result.checked_at, timezone) }} · 有效时长
        {{ result.scope.max_age_hours }} 小时</text
      ><text>{{ result.note }}</text>
      <text v-if="!result.items.length" class="muted"
        >此范围没有可用快照，库存未知；请检查范围或导入文件。</text
      >
      <view v-for="item in result.items" :key="item.id" class="card">
        <text class="section-title"
          >{{ item.sku }} · {{ labels[item.status] || '状态未知' }}</text
        >
        <text
          >快照可售 {{ item.available }} · 安全阈值
          {{ item.safety_threshold }}</text
        ><text>{{ item.reason }}</text>
        <text class="hint"
          >快照 {{ supportTime(item.snapshot_at, timezone) }} · 有效至
          {{ supportTime(item.valid_until, timezone) }}</text
        >
        <SourceList :sources="[item.source]" :shop-id="account.shopId" />
        <button
          v-for="task in inventoryTasks(tasks, item.sku)"
          :key="task.id"
          :disabled="busy"
          @tap="navigate('/', { task: String(task.id) })"
        >
          待办 #{{ task.id }} · {{ taskLabels[task.status] || task.status }} ·
          {{ task.source_status }}
        </button>
        <text v-if="!inventoryTasks(tasks, item.sku).length" class="hint"
          >已读取记录中无关联低库存待办。</text
        >
      </view>
      <view class="row"
        ><button
          :disabled="busy || scope.offset === 0"
          @tap="load(Math.max(0, scope.offset - 50))"
        >
          上一页</button
        ><text>{{ scope.offset / 50 + 1 }}</text
        ><button
          :disabled="busy || !result.has_more"
          @tap="load(scope.offset + 50)"
        >
          下一页
        </button></view
      >
      <text v-if="taskError" class="error">关联待办：{{ taskError }}</text>
      <button v-if="moreTasks || taskError" :disabled="busy" @tap="more">
        继续读取关联待办
      </button>
      <button :disabled="busy" @tap="navigate('/')">打开运营巡检与待办</button>
    </view>
  </view>
</template>
