<script setup lang="ts">
import { ref, watch } from 'vue'
import Taro, { useDidShow } from '@tarojs/taro'
import { account, api } from '../../services/session'
import {
  type WorkPage,
  workViews,
  workKinds,
  workBuckets,
} from '../../services/workbench-types'
import { queryString } from '../../services/task-policy'
import { openLink } from '../../services/navigation'
const views = Object.keys(workViews),
  buckets = ['', ...Object.keys(workBuckets)],
  kinds = ['', ...Object.keys(workKinds)]
const view = ref('attention'),
  bucket = ref(''),
  kind = ref(''),
  identity = ref('user_import'),
  channel = ref('generic')
const page = ref<WorkPage>(),
  busy = ref(false),
  error = ref('')
function changeView(value: string) {
  view.value = value
  void load()
}
function changeFilter(field: 'identity' | 'channel' | 'bucket' | 'kind', event: unknown) {
  const index = Number((event as { detail: { value: string | number } }).detail.value)
  if (field === 'identity') identity.value = index ? 'synthetic' : 'user_import'
  if (field === 'channel') channel.value = ['generic', 'shopify', 'amazon', 'other'][index] || 'generic'
  if (field === 'bucket') bucket.value = buckets[index] || ''
  if (field === 'kind') kind.value = kinds[index] || ''
  void load()
}
watch(
  () => [account.shopId, account.session?.session_id],
  () => {
    page.value = undefined
  },
)
async function load(more = false) {
  if (busy.value) return
  if (!account.session || !account.shopId) {
    error.value = '请返回工作台登录并选择店铺。'
    return
  }
  busy.value = true
  error.value = ''
  if (!more) page.value = undefined
  try {
    const result = await api.request<WorkPage>(
      `/workbench?${queryString({ shop_id: account.shopId, data_identity: identity.value, channel: channel.value, view: view.value, bucket: bucket.value, kind: kind.value, cursor: more ? page.value?.next_cursor : undefined })}`,
    )
    page.value = {
      ...result,
      items:
        more && page.value
          ? [
              ...page.value.items,
              ...result.items.filter(
                (item) =>
                  !page.value!.items.some(
                    (old) => old.kind === item.kind && old.id === item.id,
                  ),
              ),
            ]
          : result.items,
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '读取失败'
  } finally {
    busy.value = false
  }
}
async function open(path: string, query: Record<string, string>) {
  try {
    await openLink(path, query)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '无法打开详情'
  }
}
useDidShow(() => {
  void load()
})
</script>
<template>
  <view class="screen">
    <view class="hero"
      ><text class="eyebrow"
        >TODAY ·
        {{ account.shops.find((s) => s.id === account.shopId)?.name }}</text
      ><text class="title">今天，先处理这些事。</text
      ><text class="muted">候选、审批和完成核对均保留各自业务含义。</text></view
    >
    <view class="card"
      ><view class="row"
        ><button
          v-for="key in views"
          :key="key"
          :class="{ primary: view === key }"
          :disabled="busy"
          @tap="changeView(key)"
        >
          {{ workViews[key] }} {{ page?.view_counts[key] ?? '—' }}
        </button></view
      >
      <text class="label">数据身份</text
      ><picker
        :range="['用户导入', '合成测试']"
        :disabled="busy"
        @change="changeFilter('identity', $event)"
        ><view class="select">{{
          identity === 'synthetic' ? '合成测试' : '用户导入'
        }}</view></picker
      >
      <text class="label">渠道</text
      ><picker
        :range="['generic', 'shopify', 'amazon', 'other']"
        :disabled="busy"
        @change="changeFilter('channel', $event)"
        ><view class="select">{{ channel }}</view></picker
      >
      <text class="label">状态筛选</text
      ><picker
        :range="buckets.map((key) => workBuckets[key] || '全部状态')"
        :disabled="busy"
        @change="changeFilter('bucket', $event)"
        ><view class="select">{{
          workBuckets[bucket] || '全部状态'
        }}</view></picker
      >
      <text class="label">业务类型</text
      ><picker
        :range="kinds.map((key) => workKinds[key] || '全部类型')"
        :disabled="busy"
        @change="changeFilter('kind', $event)"
        ><view class="select">{{ workKinds[kind] || '全部类型' }}</view></picker
      >
      <button :disabled="busy" @tap="load()">刷新收件箱</button
      ><button
        class="primary"
        @tap="Taro.navigateTo({ url: '/pages/operations/index' })"
      >
        运营巡检与待办
      </button>
    </view>
    <text v-if="busy" class="hint">正在读取…</text
    ><view v-if="error" class="error">{{ error }}</view>
    <text v-if="page" class="hint"
      >读取截至 {{ page.read_at }} ·
      {{
        account.shops.find((s) => s.id === account.shopId)?.timezone
      }}（下方原始时间含时区）</text
    >
    <view v-if="page" class="row"
      ><text v-for="(count, key) in page.counts" :key="key" class="hint"
        >{{ workBuckets[key] || key }} {{ count }}</text
      ></view
    >
    <view v-if="page && !page.items.length" class="card"
      ><text class="muted"
        >当前范围没有事项。可调整筛选、导入新数据或运行巡检。</text
      ></view
    >
    <view
      v-for="item in page?.items"
      :key="`${item.kind}-${item.id}`"
      class="card"
      ><text class="section-title">{{ item.label || '正文已清除' }}</text
      ><text class="muted">{{ item.detail }}</text
      ><text class="hint"
        >{{ workKinds[item.kind] || item.kind }} · {{ item.status }} ·
        {{ item.source_status }} · {{ item.risk }}</text
      ><text class="hint"
        >{{ item.shop_name }} · {{ item.data_identity }} · {{ item.channel }} ·
        {{ item.created_at }}</text
      ><text v-if="item.due_at" class="hint">截止 {{ item.due_at }}</text
      ><text v-if="item.business_state" class="hint"
        >业务进展 {{ item.business_state }} ·
        {{ item.review_current ? '依据有效' : '请核对当前依据' }}</text
      ><button :disabled="busy" @tap="open(item.path, item.query)">
        查看记录 #{{ item.target_id }}
      </button></view
    >
    <button v-if="page?.next_cursor" :disabled="busy" @tap="load(true)">
      更多事项
    </button>
    <view v-if="page?.recent_runs.length" class="card"
      ><text class="section-title">最近运营记录</text
      ><view v-for="item in page.recent_runs" :key="`${item.kind}-${item.id}`"
        ><text class="hint"
          >{{ item.label }} · {{ item.status }} · {{ item.created_at }}</text
        ><button :disabled="busy" @tap="open(item.path, item.query)">
          回读记录 #{{ item.target_id }}
        </button></view
      ></view
    >
  </view>
</template>
