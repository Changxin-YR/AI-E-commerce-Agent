<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { identityApi } from '@/api/identity'
import { workbenchApi } from '@/api/workbench'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import { type WorkItem, type WorkPage, workBuckets, workKinds } from '@/types/workbench'
import { agentLabels } from '@/types/agent'
import { taskLabels, sourceLabels } from '@/types/operations'
import { listingStatus } from '@/types/listings'
import { replyStatus, supportTime } from '@/types/support'
import { mailLabels } from '@/types/outbound'
import { authorizationLabels } from '@/api/authorizations'
import FeedbackBanner from './FeedbackBanner.vue'

const shops = ref<Shop[]>([])
const filters = reactive({ shop_id: '', data_identity: '', channel: '', kind: '', bucket: '' })
const data = ref<WorkPage | null>(null)
const busy = ref(false)
const error = ref('')
let epoch = 0
let alive = true
function statusLabel(item: WorkItem): string {
  const maps: Record<string, Record<string, string>> = {
    agent: agentLabels,
    operation_task: taskLabels,
    listing: listingStatus,
    reply: replyStatus,
    outbound: mailLabels,
    authorization: authorizationLabels,
    analysis_todo: { open: '待核对', completed: '已核对完成' },
  }
  return maps[item.kind]?.[item.status] ?? (item.status === 'saved' ? '已保存' : item.status)
}
function channelLabel(channel: string | null): string {
  const names: Record<string, string> = {
    generic: '通用文件',
    shopify: 'Shopify',
    amazon: 'Amazon',
    other: '其他',
  }
  return channel ? (names[channel] ?? channel) : '跨渠道 / 不可追溯'
}
async function load(more = false): Promise<void> {
  const token = ++epoch
  const previous = data.value
  if (!more) data.value = null
  busy.value = true
  error.value = ''
  try {
    const result = await workbenchApi.list(
      { ...filters },
      more ? (previous?.next_cursor ?? undefined) : undefined,
    )
    if (!alive || token !== epoch) return
    if (more && previous) {
      const seen = new Set(previous.items.map((item) => `${item.kind}:${item.id}`))
      result.items = [
        ...previous.items,
        ...result.items.filter((item) => !seen.has(`${item.kind}:${item.id}`)),
      ]
    }
    data.value = result
  } catch (cause) {
    if (alive && token === epoch) {
      data.value = null
      error.value = errorMessage(cause)
    }
  } finally {
    if (alive && token === epoch) busy.value = false
  }
}
function choose(bucket: string): void {
  filters.bucket = bucket
  void load()
}
function focus(): void {
  void load()
}
onMounted(async () => {
  window.addEventListener('focus', focus)
  void load()
  try {
    shops.value = await identityApi.shops()
  } catch (cause) {
    if (alive) error.value = errorMessage(cause)
  }
})
onUnmounted(() => {
  alive = false
  epoch++
  window.removeEventListener('focus', focus)
})
</script>

<template>
  <section class="work-inbox" aria-label="统一工作收件箱">
    <div class="inbox-heading">
      <div>
        <span class="inbox-eyebrow">YOUR NEXT MOVE</span>
        <h2>把下一步，放在一起。</h2>
        <p>任务、草稿、审批与报告，回到同一份工作清单。</p>
      </div>
      <div class="button-row">
        <RouterLink class="button primary" to="/agent">创建受控任务</RouterLink
        ><a class="button secondary" href="#operations">运行今日检查</a>
      </div>
    </div>
    <form class="inbox-filters" aria-label="收件箱筛选" @submit.prevent="load()">
      <label
        >查看店铺<select v-model="filters.shop_id" @change="load()">
          <option value="">全部店铺</option>
          <option v-for="shop in shops" :key="shop.id" :value="String(shop.id)">
            {{ shop.name }}
          </option>
        </select></label
      >
      <label
        >筛选身份<select v-model="filters.data_identity" @change="load()">
          <option value="">全部身份</option>
          <option value="user_import">用户导入</option>
          <option value="synthetic">合成数据</option>
        </select></label
      >
      <label
        >来源渠道<select v-model="filters.channel" @change="load()">
          <option value="">全部渠道 / 跨渠道</option>
          <option value="generic">通用文件</option>
          <option value="shopify">Shopify</option>
          <option value="amazon">Amazon</option>
          <option value="other">其他</option>
        </select></label
      >
      <label
        >事项类型<select v-model="filters.kind" @change="load()">
          <option value="">全部事项</option>
          <option v-for="(name, key) in workKinds" :key="key" :value="key">{{ name }}</option>
        </select></label
      >
    </form>
    <FeedbackBanner :message="error" />
    <div class="inbox-counts" aria-label="事项状态">
      <button
        v-for="(name, key) in workBuckets"
        :key="key"
        type="button"
        :aria-pressed="filters.bucket === key"
        :class="['inbox-count', key]"
        @click="choose(key)"
      >
        <span>{{ name }}</span
        ><strong>{{ data ? (data.counts[key] ?? 0) : '—' }}</strong>
      </button>
    </div>
    <div class="inbox-toolbar">
      <button class="button secondary small" :aria-pressed="!filters.bucket" @click="choose('')">
        全部状态</button
      ><span>按创建时间倒序 · 每页 20 条</span
      ><button class="button secondary small" :disabled="busy" @click="load()">刷新收件箱</button>
    </div>
    <p v-if="busy" role="status">正在核对工作记录…</p>
    <template v-if="data">
      <p class="inbox-scope-note">
        数量为当前筛选范围内的全部记录。跨渠道分析只在“全部渠道”显示；清除后身份不可追溯的记录仅在“全部身份”显示。
      </p>
      <details v-if="data.recent_runs.length" class="inbox-recent" open>
        <summary>最近实际运行 · {{ data.recent_runs.length }} 条</summary>
        <div class="recent-grid">
          <RouterLink
            v-for="item in data.recent_runs"
            :key="`${item.kind}:${item.id}`"
            :to="{ path: item.path, query: item.query }"
            ><span>{{ workKinds[item.kind] }} #{{ item.id }} · {{ item.shop_name }}</span
            ><strong
              >{{ statusLabel(item) }} ·
              {{ sourceLabels[item.source_status] ?? item.source_status }}</strong
            ><span>{{ item.detail }}</span
            ><small>{{ supportTime(item.created_at, item.timezone) }}</small></RouterLink
          >
        </div>
      </details>
      <div v-if="!data.items.length" class="inbox-empty">
        <h3>
          {{
            Object.values(data.counts).some(Boolean) ? '此状态下暂无事项' : '当前范围还没有工作记录'
          }}
        </h3>
        <p>从导入一份文件、运行一次检查或创建草稿开始，结果会出现在这里。</p>
        <RouterLink to="/imports" class="button secondary small">导入业务数据</RouterLink>
      </div>
      <ol v-else class="inbox-list" aria-label="工作事项">
        <li v-for="item in data.items" :key="`${item.kind}:${item.id}`" :data-kind="item.kind">
          <div class="inbox-item-head">
            <span class="outline-label">{{ workKinds[item.kind] }} #{{ item.id }}</span
            ><span :class="['inbox-state', item.bucket]">{{ workBuckets[item.bucket] }}</span>
          </div>
          <h3>
            {{
              item.label
                ? item.kind === 'agent'
                  ? (agentLabels[item.label] ?? item.label)
                  : item.label
                : workKinds[item.kind]
            }}
            <span>· {{ statusLabel(item) }}</span>
          </h3>
          <p>
            {{ item.shop_name }} ·
            {{
              item.data_identity === 'synthetic'
                ? '合成数据'
                : item.data_identity === 'user_import'
                  ? '用户导入'
                  : '身份不可追溯'
            }}
            · {{ channelLabel(item.channel) }}
          </p>
          <p v-if="item.detail">{{ item.detail }}</p>
          <div class="inbox-item-foot">
            <div>
              <span
                >{{ sourceLabels[item.source_status] ?? item.source_status }} ·
                {{ item.risk }}</span
              ><small>创建于 {{ supportTime(item.created_at, item.timezone) }}</small
              ><small v-if="item.due_at"
                >{{ item.kind === 'authorization' ? '授权到期' : '截止时间' }}
                {{ supportTime(item.due_at, item.timezone) }}</small
              >
            </div>
            <RouterLink
              class="button secondary small"
              :to="{ path: item.path, query: item.query }"
              >{{
                item.kind === 'outbound'
                  ? '核对 R2 预览与回执'
                  : item.bucket === 'approval'
                    ? '打开审批预览'
                    : '查看与处理'
              }}</RouterLink
            >
          </div>
        </li>
      </ol>
      <button v-if="data.next_cursor" class="button secondary" :disabled="busy" @click="load(true)">
        加载更早记录
      </button>
      <p class="inbox-scope-note">
        读取时间：{{
          supportTime(data.read_at, 'Asia/Shanghai')
        }}。打开记录会再次核验来源、状态与授权；外发结果未知时请进入原记录回查。
      </p>
    </template>
    <button v-if="error" class="button secondary" @click="load()">重新加载收件箱</button>
  </section>
</template>

<style scoped>
.work-inbox {
  margin: 1.5rem 0 3rem;
}
.inbox-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1.5rem;
  margin-bottom: 1.6rem;
}
.inbox-heading h2 {
  font-size: clamp(1.5rem, 2.5vw, 2.1rem);
  margin: 0.5rem 0;
  letter-spacing: -0.04em;
}
.inbox-heading p {
  color: var(--muted);
  margin-bottom: 0;
}
.inbox-eyebrow {
  font-size: 0.7rem;
  letter-spacing: 0.16em;
  color: var(--green);
}
.inbox-filters {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.8rem;
}
.inbox-filters label {
  display: grid;
  gap: 0.4rem;
  font-size: 0.8rem;
}
.inbox-counts {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  margin: 1.5rem 0 0.8rem;
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
}
.inbox-count {
  text-align: left;
  background: #fff;
  padding: 1rem;
  border: 0;
  border-right: 1px solid var(--line);
  cursor: pointer;
  color: var(--ink);
}
.inbox-count:last-child {
  border-right: 0;
}
.inbox-count[aria-pressed='true'] {
  background: #e5eee5;
  box-shadow: inset 0 -3px #2a6348;
}
.inbox-count span {
  display: block;
  font-size: 0.73rem;
  white-space: nowrap;
}
.inbox-count strong {
  display: block;
  font-size: 1.8rem;
  font-weight: 500;
  margin-top: 0.45rem;
  font-variant-numeric: tabular-nums;
}
.inbox-toolbar {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  flex-wrap: wrap;
}
.inbox-toolbar span {
  margin-right: auto;
  font-size: 0.8rem;
  color: var(--muted);
}
.inbox-scope-note {
  font-size: 0.75rem;
  line-height: 1.8;
  color: var(--muted);
}
.inbox-recent {
  margin: 1.5rem 0;
}
.inbox-recent summary {
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}
.recent-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
  margin-top: 0.9rem;
}
.recent-grid a {
  display: grid;
  align-content: start;
  gap: 0.5rem;
  padding: 1rem;
  background: #f1f4ef;
  border-radius: 8px;
  text-decoration: none;
  font-size: 0.8rem;
  color: inherit;
  overflow-wrap: anywhere;
}
.recent-grid strong {
  color: #2a6348;
}
.recent-grid small {
  color: var(--muted);
}
.inbox-list {
  list-style: none;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}
.inbox-list li {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 1.15rem;
  background: #fff;
  overflow-wrap: anywhere;
}
.inbox-item-head,
.inbox-item-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}
.inbox-state {
  font-size: 0.75rem;
  color: #496456;
}
.inbox-state.unknown,
.inbox-state.failed {
  color: #a44432;
}
.inbox-state.stale {
  color: #80591f;
}
.inbox-list h3 {
  font-size: 1.02rem;
  margin: 1rem 0 0.5rem;
}
.inbox-list h3 span {
  font-size: 0.9rem;
  font-weight: 400;
}
.inbox-list p {
  margin: 0.4rem 0;
  font-size: 0.8rem;
  color: var(--muted);
}
.inbox-item-foot {
  border-top: 1px solid var(--line);
  padding-top: 0.8rem;
  margin-top: 1rem;
  align-items: end;
}
.inbox-item-foot div {
  display: grid;
  gap: 0.3rem;
  font-size: 0.78rem;
}
.inbox-item-foot small {
  color: var(--muted);
  font-size: 0.7rem;
}
.inbox-item-foot a {
  flex-shrink: 0;
}
.inbox-empty {
  padding: 2rem;
  background: #f1f4ef;
  margin: 1rem 0;
  border-radius: 12px;
}
.inbox-empty h3 {
  margin-top: 0;
}
@media (max-width: 1100px) {
  .inbox-counts {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .inbox-count {
    border-bottom: 1px solid var(--line);
  }
  .recent-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 640px) {
  .inbox-heading {
    display: block;
  }
  .inbox-heading .button-row {
    margin-top: 1rem;
  }
  .inbox-filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .inbox-list {
    grid-template-columns: 1fr;
  }
  .inbox-item-foot {
    flex-wrap: wrap;
  }
  .inbox-count {
    padding: 0.75rem;
  }
}
</style>
