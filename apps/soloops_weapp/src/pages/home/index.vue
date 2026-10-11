<template>
  <PageShell
    title="今天，从一件事开始"
    :subtitle="state.session ? `账号：${state.session.username} · 店铺：${shopName}` : ''"
    :loading="busy"
    :error="error"
    :notice="state.notice"
    @retry="load"
  >
    <FactLine label="读取截至" :value="page?.read_at" :zone="zone" />

    <view class="row">
      <ActionButton label="导入业务文件" @tap="openPage('/pages/imports/index')" />
      <ActionButton label="刷新工作台" @tap="load" />
    </view>

    <view v-if="showOnboarding" class="card">
      <text class="card__title">准备经营资料</text>
      <FactLine label="经营档案" :value="onboarding?.profile_complete === true ? '已完成' : '待完善'" />
      <FactLine label="店铺数量" :value="onboarding?.shop_count" />
      <text class="hint">填写经营档案、添加店铺记录，再导入一类报表即可开始。</text>
      <ActionButton label="完善经营资料" @tap="openPage('/pages/mine/index')" />
    </view>

    <text class="section-title">事项总览</text>
    <view class="row">
      <view
        v-for="entry in viewEntries"
        :key="entry.key"
        class="chip"
        :class="{ 'chip--active': view === entry.key }"
        @tap="filter(entry.key)"
      >
        <text>{{ entry.text }} {{ countText(page?.view_counts?.[entry.key]) }}</text>
      </view>
    </view>

    <text class="section-title">业务入口</text>
    <view class="row">
      <view v-for="entry in tabEntries" :key="entry.key" class="chip" @tap="openTab(entry.page)">
        <text>{{ entry.title }}</text>
      </view>
    </view>

    <text class="section-title">事项列表</text>
    <view v-if="items.length === 0 && !busy && error === ''" class="card">
      <text class="hint">
        当前没有符合条件的事项。导入报表并运行运营检查后，这里会显示待办和审批记录。
      </text>
    </view>
    <view v-for="item in items" :key="`${item.kind}:${item.id}`" class="card" @tap="open(item)">
      <text class="card__title">{{ item.label }}</text>
      <text class="hint">{{ item.detail }}</text>
      <FactLine label="类型 / 处理分组" :value="`${labelOf(workKinds, item.kind)} / ${labelOf(workBuckets, item.bucket)}`" />
      <FactLine label="来源状态" :value="labelOf(sourceLabels, item.source_status)" />
      <FactLine
        v-if="item.business_state !== null && item.business_state !== undefined"
        label="业务进展"
        :value="labelOf(businessLabels, item.business_state)"
      />
      <FactLine label="所属店铺" :value="item.shop_name" />
      <FactLine label="记录时间" :value="item.created_at" :zone="item.timezone || zone" />
      <FactLine v-if="item.due_at" label="截止时间" :value="item.due_at" :zone="item.timezone || zone" />
      <text v-if="item.source_status !== 'current'" class="warn">先核对来源时效，再继续业务操作。</text>
    </view>
    <ActionButton v-if="page?.next_cursor" label="加载更多" @tap="loadMore" />
  </PageShell>
</template>

<script setup lang="ts">
/**
 * 首页 / 工作台。
 * 接口：GET /api/workbench（shop_id、view、data_identity、channel、kind、bucket、cursor）、
 *       GET /api/onboarding。
 * 三个计数来自 workbench 的 view_counts：待我处理 / AI 已完成 / 需要更新数据。
 */
import { computed, ref } from 'vue'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import PageShell from '../../ui/PageShell.vue'
import FactLine from '../../ui/FactLine.vue'
import { inputValue, pickerValue } from '../../ui/forms'
import ActionButton from '../../ui/ActionButton.vue'
import { apiGet, asObject } from '../../core/api'
import { countText } from '../../core/format'
import { labelOf, workBuckets, workKinds, sourceLabels, businessLabels } from '../../core/labels'
import { openPage, openTab, openWorkPath, tabEntries } from '../../core/links'
import { ensureSession, perform, shopTimezone, state } from '../../core/store'

interface WorkItem {
  kind: string
  id: number
  target_id: number
  shop_name: string
  timezone: string
  status: string
  source_status: string
  bucket: string
  business_state: string | null
  label: string
  detail: string
  created_at: string
  due_at: string | null
  path: string
  query: Record<string, string>
}

interface WorkPage {
  items: WorkItem[]
  recent_runs: WorkItem[]
  counts: Record<string, number>
  view_counts: Record<string, number>
  next_cursor: string | null
  read_at: string
}

interface Onboarding {
  profile_complete: boolean
  shop_count: number
}

const viewEntries = [
  { key: 'attention', text: '待我处理' },
  { key: 'ai_completed', text: 'AI 已完成' },
  { key: 'update_data', text: '需要更新数据' },
]

const page = ref<WorkPage | null>(null)
const onboarding = ref<Onboarding | null>(null)
const items = ref<WorkItem[]>([])
const view = ref('')
const busy = ref(false)
const error = ref('')
const ready = ref(false)

const zone = computed(() => shopTimezone())
const shopName = computed(() => state.shops.find((shop) => shop.id === state.shopId)?.name ?? '未知')
const showOnboarding = computed(
  () => onboarding.value !== null && (onboarding.value.profile_complete !== true || onboarding.value.shop_count === 0),
)

usePullDownRefresh(async () => {
  await load()
  await Taro.stopPullDownRefresh()
})

useDidShow(async () => {
  if (!(await ensureSession())) return
  ready.value = true
  await load()
})

function filter(key: string): void {
  view.value = view.value === key ? '' : key
  void load()
}

async function load(more = false): Promise<void> {
  if (!ready.value || busy.value) return
  busy.value = true
  error.value = ''
  const message = await perform(async () => {
    const result = asObject<WorkPage>(
      await apiGet('/api/workbench', {
        shop_id: state.shopId,
        view: view.value,
        cursor: more ? page.value?.next_cursor ?? '' : '',
      }),
    )
    if (result === null) throw new Error('工作台响应无法读取，请刷新重试。')
    page.value = result
    const incoming = Array.isArray(result.items) ? result.items : []
    if (more) {
      const keys = new Set(items.value.map((item) => `${item.kind}:${item.id}`))
      items.value = [...items.value, ...incoming.filter((item) => !keys.has(`${item.kind}:${item.id}`))]
    } else {
      items.value = incoming
    }
    if (!more) {
      onboarding.value = asObject<Onboarding>(await apiGet('/api/onboarding'))
    }
  })
  if (message !== '') error.value = message
  busy.value = false
}

function loadMore(): void {
  void load(true)
}

async function open(item: WorkItem): Promise<void> {
  if (busy.value) return
  await openWorkPath(item.path, item.query ?? {})
  await load()
}
</script>
