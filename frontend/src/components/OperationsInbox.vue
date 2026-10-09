<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { linkedId, linkedShop, revealRecord } from '@/composables/deepLink'
import { identityApi } from '@/api/identity'
import { operationsApi } from '@/api/operations'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import type { OperationRun, OperationScope, OperationTask } from '@/types/operations'
import { sourceLabels, taskLabels } from '@/types/operations'
import { supportTime } from '@/types/support'
import FeedbackBanner from './FeedbackBanner.vue'
import OperationTaskReview from './OperationTaskReview.vue'
import AppliedRules from './AppliedRules.vue'
import { applyRule, type BusinessRule } from '@/api/businessRules'
import SourceEvidence from './SupportSource.vue'

const shops = ref<Shop[]>([])
const route = useRoute()
const shopId = ref(0)
const scope = reactive<OperationScope>({
  start_at: new Date(Date.now() - 7 * 86400000).toISOString(),
  end_at: new Date().toISOString(),
  timezone: 'Asia/Shanghai',
  currency: 'USD',
  data_identity: 'user_import',
  intent: 'low_margin',
  channel: 'generic',
  max_age_hours: 24,
  min_quantity: 1,
  max_margin_percent: '20',
})
const history = ref<OperationRun[]>([])
const run = ref<OperationRun | null>(null)
const tasks = ref<OperationTask[]>([])
const selected = ref<OperationTask | null>(null)
const offset = ref(0)
const hasMore = ref(false)
const busy = ref(false)
const dirty = ref(false)
const error = ref('')
const info = ref('')
const rulesPending = ref(true)
const activeRule = ref(false)
function rulesLoaded(rule: BusinessRule): void {
  applyRule(scope, rule)
  activeRule.value = rule.active
}
const timezone = computed(
  () => shops.value.find((s) => s.id === shopId.value)?.timezone ?? 'Asia/Shanghai',
)
const branchLabels: Record<string, string> = {
  checked: '已检查',
  partial: '部分可核对',
  not_checked: '未检查',
}

async function readLists(): Promise<void> {
  const [runs, page] = await Promise.all([
    operationsApi.runs(shopId.value, scope.data_identity, scope.channel),
    operationsApi.tasks(shopId.value, scope.data_identity, scope.channel, offset.value),
  ])
  history.value = runs
  tasks.value = page.items
  hasMore.value = page.has_more
}
async function refresh(reset = false): Promise<void> {
  if (busy.value || dirty.value || !shopId.value) return
  busy.value = true
  error.value = ''
  if (reset) {
    selected.value = null
    run.value = null
    offset.value = 0
  }
  try {
    await readLists()
    const id = run.value?.id ?? history.value[0]?.id
    run.value = id ? await operationsApi.getRun(shopId.value, id) : null
    if (selected.value)
      selected.value = await operationsApi.getTask(shopId.value, selected.value.id)
  } catch (cause) {
    error.value = errorMessage(cause)
    run.value = null
    selected.value = null
  } finally {
    busy.value = false
  }
}
function changeShop(): void {
  const shop = shops.value.find((s) => s.id === shopId.value)
  if (shop) {
    scope.currency = shop.currency
    scope.timezone = shop.timezone
  }
  void refresh(true)
}
async function start(): Promise<void> {
  if (busy.value || dirty.value || rulesPending.value) return
  busy.value = true
  error.value = ''
  info.value = ''
  selected.value = null
  try {
    run.value = await operationsApi.run(shopId.value, { ...scope }, crypto.randomUUID())
    offset.value = 0
    await readLists()
    info.value = '检查已保存。候选需经批准成为待办；已有处理状态已保留。'
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function inspect(id: number, kind: 'task' | 'run'): Promise<void> {
  if (busy.value || dirty.value) return
  busy.value = true
  error.value = ''
  try {
    if (kind === 'task') selected.value = await operationsApi.getTask(shopId.value, id)
    else run.value = await operationsApi.getRun(shopId.value, id)
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
function updated(task: OperationTask): void {
  selected.value = task
  tasks.value = tasks.value.map((t) => (t.id === task.id ? task : t))
  dirty.value = false
}
function page(delta: number): void {
  offset.value += delta
  void refresh()
}
function focus(): void {
  void refresh()
}
onMounted(async () => {
  window.addEventListener('focus', focus)
  try {
    shops.value = await identityApi.shops()
    shopId.value = linkedShop(shops.value, route.query.shop)
    const taskId = linkedId(route.query.task)
    const runId = linkedId(route.query.run)
    const identity = route.query.identity
    if (identity === 'synthetic' || identity === 'user_import') scope.data_identity = identity
    if (['generic', 'shopify', 'amazon', 'other'].includes(String(route.query.channel)))
      scope.channel = String(route.query.channel)
    const currentShop = shops.value.find((s) => s.id === shopId.value)
    if (currentShop) {
      scope.currency = currentShop.currency
      scope.timezone = currentShop.timezone
    }
    await refresh(true)
    if (taskId) {
      await inspect(taskId, 'task')
      await revealRecord('linked-task')
    }
    if (runId) {
      run.value = null
      await inspect(runId, 'run')
      await revealRecord('operations')
    }
  } catch (cause) {
    run.value = null
    selected.value = null
    error.value = errorMessage(cause)
  }
})
onUnmounted(() => window.removeEventListener('focus', focus))
</script>

<template>
  <section aria-label="今日运营收件箱">
    <div class="section-title">
      <h2>今日运营</h2>
      <span class="outline-label">导入数据检查</span>
    </div>
    <p>检查已导入数据，查看证据，将需要核对的事项批准为本地待办。</p>
    <RouterLink v-if="shopId" :to="{ path: '/agent', query: { shop: shopId, mode: 'daily_model' } }"
      >启动 AI 今日运营概览</RouterLink
    >
    <FeedbackBanner :message="error" />
    <p v-if="info" role="status">{{ info }}</p>
    <p v-if="dirty" role="status">有未保存的处理记录，请先保存后切换或刷新。</p>
    <aside v-if="run" class="data-note section-block" aria-label="最近检查摘要">
      <div>
        <strong>检查 #{{ run.id }} · {{ sourceLabels[run.source_status] }}</strong>
        <p>
          分析完成 {{ supportTime(run.created_at, timezone) }} ·
          {{ run.snapshot?.data_as_of ?? '来源内容已清除' }}
        </p>
        <p v-if="run.source_status === 'stale'">需更新数据并重新检查；下方保留历史结果。</p>
      </div>
    </aside>
    <form v-if="shops.length" class="form-panel" @submit.prevent="start">
      <AppliedRules
        :shop="shopId"
        :scope="scope"
        @loaded="rulesLoaded"
        @pending="rulesPending = $event"
      />
      <fieldset :disabled="busy || dirty">
        <legend>本次检查范围</legend>
        <div class="form-grid">
          <div class="form-field">
            <label for="ops-shop">所属店铺</label
            ><select id="ops-shop" v-model="shopId" @change="changeShop">
              <option v-for="shop in shops" :key="shop.id" :value="shop.id">
                {{ shop.name }} · {{ shop.code }}
              </option>
            </select>
          </div>
          <div class="form-field">
            <label for="ops-identity">数据身份</label
            ><select id="ops-identity" v-model="scope.data_identity" @change="refresh(true)">
              <option value="user_import">用户导入文件</option>
              <option value="synthetic">合成测试数据</option>
            </select>
          </div>
          <div class="form-field">
            <label for="ops-channel">检查渠道</label
            ><select id="ops-channel" v-model="scope.channel" @change="refresh(true)">
              <option value="generic">通用 / 自建表</option>
              <option value="shopify">Shopify</option>
              <option value="amazon">Amazon</option>
              <option value="other">其他来源</option>
            </select>
          </div>
        </div>
        <details class="scope-options">
          <summary>检查口径（订单时间、币种与阈值）</summary>
          <div class="form-grid">
            <div class="form-field">
              <label for="ops-currency">统计币种</label
              ><select id="ops-currency" v-model="scope.currency">
                <option
                  v-for="c in ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']"
                  :key="c"
                >
                  {{ c }}
                </option>
              </select>
            </div>
            <div class="form-field">
              <label for="ops-start">订单起始时间（含时区偏移）</label
              ><input id="ops-start" v-model="scope.start_at" required />
            </div>
            <div class="form-field">
              <label for="ops-end">订单结束时间（不含，含时区偏移）</label
              ><input id="ops-end" v-model="scope.end_at" required />
            </div>
            <div class="form-field">
              <label for="ops-age">库存时效（小时）</label
              ><input
                id="ops-age"
                v-model.number="scope.max_age_hours"
                :disabled="activeRule || rulesPending"
                type="number"
                min="1"
                max="720"
                required
              />
            </div>
            <div class="form-field">
              <label for="ops-qty">低毛利最低购买量</label
              ><input
                id="ops-qty"
                v-model.number="scope.min_quantity"
                :disabled="activeRule || rulesPending"
                type="number"
                min="1"
                max="1000000"
                required
              />
            </div>
            <div class="form-field">
              <label for="ops-margin">毛利率上限（%）</label
              ><input
                id="ops-margin"
                v-model="scope.max_margin_percent"
                :disabled="activeRule || rulesPending"
                type="number"
                min="-1000"
                max="100"
                step="0.01"
                required
              />
            </div>
          </div>
        </details>
        <p class="muted">
          下次运行：{{ supportTime(scope.start_at, timezone) }} 至
          {{ supportTime(scope.end_at, timezone) }} · {{ scope.currency }} · 库存时效
          {{ scope.max_age_hours }} 小时。
        </p>
        <p class="muted">
          订单按所选时间窗检查；库存与消息读取此渠道当前导入记录。商品与已知成本使用店铺主档。时间显示
          {{ timezone }}。
        </p>
        <div class="form-actions">
          <button type="button" class="button secondary" @click="refresh()">刷新记录</button
          ><button class="button primary" :disabled="rulesPending">运行今日运营</button>
        </div>
      </fieldset>
    </form>
    <p v-if="busy" role="status">正在读取并核对数据…</p>
    <section v-if="!run && !busy" class="data-note section-block">
      <div>
        <h3>尚无本范围的检查记录</h3>
        <p>先添加店铺或导入文件，再运行今日运营。缺数据的检查会明确列出。</p>
        <RouterLink to="/imports" class="button secondary small">导入业务文件</RouterLink>
      </div>
    </section>
    <section v-if="run" class="form-panel section-block" aria-label="巡检结果">
      <div class="section-title">
        <h3>检查 #{{ run.id }} · {{ sourceLabels[run.source_status] }}</h3>
        <span>来源版本 {{ run.source_revision }}</span>
      </div>
      <p>分析完成 {{ supportTime(run.created_at, timezone) }}</p>
      <RouterLink
        v-if="run.scope.rule_revision_id"
        :to="{
          path: '/rules',
          query: {
            shop: run.shop_id,
            channel: run.scope.channel,
            identity: run.scope.data_identity,
            version: run.scope.rule_revision_id,
          },
        }"
        >查看使用的经营规则 #{{ run.scope.rule_revision_id }}</RouterLink
      >
      <p>
        订单时间窗 {{ supportTime(run.scope.start_at, timezone) }} 至
        {{ supportTime(run.scope.end_at, timezone) }} · {{ run.scope.currency }} · 库存时效
        {{ run.scope.max_age_hours }} 小时
      </p>
      <p v-if="run.source_status === 'stale'" role="status">
        数据、经营规则已变化或快照时效已到，需重新检查。以下为历史结果。
      </p>
      <template v-if="run.snapshot">
        <p>数据截至：{{ run.snapshot.data_as_of }}</p>
        <p>
          新增候选 {{ run.snapshot.created_candidates }} · 复用事项
          {{ run.snapshot.reused_candidates }}
        </p>
        <ul class="branch-list">
          <li v-for="branch in run.snapshot.branches" :key="branch.name">
            <div>
              <strong>{{ branch.name }}</strong
              ><span class="status-tag">{{ branchLabels[branch.status] }}</span>
            </div>
            <p>{{ branch.reason }}</p>
          </li>
        </ul>
        <details>
          <summary>来源批次（每批展示一个原始行入口）</summary>
          <SourceEvidence
            v-for="source in run.snapshot.sources"
            :key="`${run.id}-${source.row_id}`"
            :shop-id="shopId"
            :source="source"
          />
        </details>
        <details v-if="run.snapshot.task_ids.length">
          <summary>本次关联事项</summary>
          <div class="history-buttons">
            <button
              v-for="id in run.snapshot.task_ids"
              :key="id"
              class="button secondary small"
              :disabled="busy || dirty"
              @click="inspect(id, 'task')"
            >
              查看事项 #{{ id }}
            </button>
          </div>
        </details>
      </template>
      <p v-else>来源已清除，检查内容已擦除。</p>
    </section>
    <section class="section-block" aria-label="运营事项">
      <div class="section-title">
        <h3>待审与处理记录</h3>
        <span>每页 50 条</span>
      </div>
      <p v-if="!tasks.length">
        此范围暂无事项。可运行检查，或前往 Listing 与客服查看已保存的草稿。
      </p>
      <div class="task-list">
        <button
          v-for="task in tasks"
          :key="task.id"
          class="task-row"
          :disabled="busy || dirty"
          @click="inspect(task.id, 'task')"
        >
          <span
            ><strong>{{ task.snapshot?.title ?? '来源已清除' }}</strong
            ><small
              >#{{ task.id }} · {{ task.snapshot?.object_label }} ·
              {{ sourceLabels[task.source_status] }}</small
            ></span
          ><span class="status-tag">{{ taskLabels[task.status] }}</span>
        </button>
      </div>
      <div class="form-actions">
        <button class="button secondary" :disabled="busy || dirty || !offset" @click="page(-50)">
          上一页</button
        ><button class="button secondary" :disabled="busy || dirty || !hasMore" @click="page(50)">
          下一页
        </button>
      </div>
    </section>
    <OperationTaskReview
      id="linked-task"
      v-if="selected"
      :task="selected"
      :timezone="timezone"
      @updated="updated"
      @dirty="dirty = $event"
      @working="busy = $event"
    />
    <details class="form-panel section-block">
      <summary>检查历史（最近 50 次）</summary>
      <div class="history-buttons">
        <button
          v-for="item in history"
          :key="item.id"
          class="button secondary"
          :disabled="busy || dirty"
          @click="inspect(item.id, 'run')"
        >
          #{{ item.id }} · {{ supportTime(item.created_at, timezone) }} ·
          {{ sourceLabels[item.source_status] }}
        </button>
      </div>
    </details>
    <div class="history-buttons">
      <RouterLink to="/listings" class="button secondary">查看 Listing 草稿与审批</RouterLink
      ><RouterLink to="/support" class="button secondary">查看客服草稿</RouterLink
      ><RouterLink to="/analytics" class="button secondary">查看经营分析</RouterLink>
    </div>
  </section>
</template>

<style scoped>
fieldset {
  margin: 0;
  border: 0;
  padding: 0;
  min-width: 0;
}
.scope-options {
  margin-top: 1rem;
}
.scope-options .form-grid {
  margin-top: 1rem;
}
.branch-list {
  padding: 0;
  list-style: none;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}
.branch-list li {
  border: 1px solid var(--line);
  padding: 1rem;
  border-radius: 12px;
}
.branch-list li > div {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}
.task-list {
  display: grid;
  gap: 0.75rem;
}
.task-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  text-align: left;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  color: inherit;
  cursor: pointer;
  min-width: 0;
}
.task-row small {
  display: block;
  margin-top: 0.5rem;
}
.history-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1rem;
}
section {
  overflow-wrap: anywhere;
}
@media (max-width: 640px) {
  .branch-list {
    grid-template-columns: 1fr;
  }
  .section-title,
  .task-row {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.75rem;
  }
}
</style>
