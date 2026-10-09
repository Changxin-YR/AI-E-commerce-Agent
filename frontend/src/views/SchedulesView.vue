<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { identityApi } from '@/api/identity'
import {
  schedulesApi,
  scheduleLabels as labels,
  type Schedule,
  type ScheduleConfig,
  type Occurrence,
  type ScheduleAction,
} from '@/api/schedules'
import { errorMessage } from '@/api/client'
import type { Shop } from '@/types/identity'
import { supportTime } from '@/types/support'
import FeedbackBanner from '@/components/FeedbackBanner.vue'
import ScheduleEditor from '@/components/ScheduleEditor.vue'

const route = useRoute()
const shops = ref<Shop[]>([])
const shopId = ref(0)
const shop = computed(() => shops.value.find((s) => s.id === shopId.value))
const plans = ref<Schedule[]>([])
const history = ref<Occurrence[]>([])
const editing = ref<Schedule | null>(null)
const showEditor = ref(false)
const unread = ref(true)
const worker = ref<boolean | null>(null)
const busy = ref(false)
const error = ref('')
const info = ref('')
const confirmAction = ref<{ row: Schedule; action: ScheduleAction } | null>(null)
const reasons: Record<string, string> = {
  conflict: '经营规则发生变化，请修改计划并核对当前规则。',
  local_check_failed: '本次检查未完成，已回滚；核对后可恢复计划。',
  range_too_large: '数据量超过本次检查上限，请缩小范围。',
  too_many_findings: '候选数量超过本次检查上限，请缩小范围。',
}
let createId = crypto.randomUUID()
let manualId = crypto.randomUUID()
let manualPlan = 0
function time(value: string | null, zone = shop.value?.timezone ?? 'UTC'): string {
  return value ? supportTime(value, zone) : '—'
}
async function refresh(): Promise<void> {
  const [rows, notices, status] = await Promise.all([
    schedulesApi.list(shopId.value),
    schedulesApi.history(shopId.value, unread.value),
    schedulesApi.status(shopId.value),
  ])
  plans.value = rows
  history.value = notices
  worker.value = status.worker_enabled
}
async function perform(work: () => Promise<void>): Promise<void> {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await work()
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    busy.value = false
  }
}
async function load(): Promise<void> {
  showEditor.value = false
  editing.value = null
  confirmAction.value = null
  plans.value = []
  history.value = []
  worker.value = null
  if (shopId.value) await perform(refresh)
}
function edit(row: Schedule | null): void {
  editing.value = row
  showEditor.value = true
  createId = crypto.randomUUID()
}
async function save(config: ScheduleConfig): Promise<void> {
  await perform(async () => {
    if (editing.value) await schedulesApi.act(editing.value, 'edit', config)
    else await schedulesApi.create(shopId.value, createId, config)
    createId = crypto.randomUUID()
    showEditor.value = false
    info.value = '计划已保存；下一次运行时间见计划卡片。'
    await refresh()
  })
}
async function act(row: Schedule, action: ScheduleAction): Promise<void> {
  await perform(async () => {
    await schedulesApi.act(row, action)
    confirmAction.value = null
    info.value = action === 'revoke' ? '计划已撤销，历史执行可继续查看。' : '计划状态已更新。'
    await refresh()
  })
}
async function check(row: Schedule): Promise<void> {
  if (manualPlan !== row.id) {
    manualId = crypto.randomUUID()
    manualPlan = row.id
  }
  await perform(async () => {
    await schedulesApi.check(row, manualId)
    manualId = crypto.randomUUID()
    unread.value = false
    info.value = '本次检查已保存，请从运行历史查看依据和审批。'
    await refresh()
  })
}
async function read(item: Occurrence): Promise<void> {
  await perform(async () => {
    await schedulesApi.read(shopId.value, item.id)
    await refresh()
  })
}
async function older(): Promise<void> {
  await perform(async () => {
    history.value = await schedulesApi.history(shopId.value, unread.value, history.value.at(-1)?.id)
  })
}
onMounted(async () => {
  await perform(async () => {
    shops.value = await identityApi.shops()
    shopId.value =
      shops.value.find((s) => s.id === Number(route.query.shop))?.id ?? shops.value[0]?.id ?? 0
    if (shopId.value) await refresh()
  })
})
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>定时运营</h1>
      <p>把日常检查排进日历，每次结果都有记录可查。</p>
    </div>
    <span class="outline-label">本地规则 · 站内通知</span>
  </div>
  <FeedbackBanner :message="error" />
  <p v-if="info" role="status">{{ info }}</p>
  <p v-if="!shops.length">请先在经营资料中添加店铺。</p>
  <template v-else>
    <section class="form-panel" aria-label="定时运营范围">
      <div class="form-grid">
        <div class="form-field">
          <label for="schedule-shop">计划店铺</label
          ><select id="schedule-shop" v-model="shopId" :disabled="busy" @change="load">
            <option v-for="value in shops" :key="value.id" :value="value.id">
              {{ value.name }} · {{ value.code }}
            </option>
          </select>
        </div>
      </div>
      <p v-if="worker !== null">
        {{
          worker
            ? '自动检查已启用，API 服务运行期间每 30 秒扫描到期计划。'
            : '当前服务关闭自动调度，可手动检查并查看记录。'
        }}
        时间显示：{{ shop?.timezone }}。
      </p>
      <p>
        巡检已导入的订单、库存、消息与已知毛利，生成待审候选和数据缺口记录。每次使用当时可用数据，审批请进入任务执行台。
      </p>
      <div class="form-actions">
        <button class="button" :disabled="busy" @click="edit(null)">新建计划</button
        ><button class="button secondary" :disabled="busy" @click="perform(refresh)">
          刷新计划与通知
        </button>
      </div>
    </section>
    <ScheduleEditor
      v-if="showEditor && shop"
      :key="`${shopId}-${editing?.id ?? 'new'}`"
      :shop="shop"
      :initial="editing?.config"
      :busy="busy"
      @save="save"
      @cancel="showEditor = false"
    />
    <section class="section-block" aria-label="已保存计划">
      <h2>运行计划</h2>
      <p v-if="!plans.length">还没有定时计划。添加一个周期，开始积累可回读的运营检查。</p>
      <article
        v-for="row in plans"
        :key="row.id"
        class="form-panel section-block"
        :aria-label="`计划 ${row.config.name}`"
      >
        <h3>
          {{ row.config.name }}
          <span class="outline-label">{{ labels[row.status] ?? row.status }}</span>
        </h3>
        <p>
          #{{ row.id }} · 版本 {{ row.version }} · {{ labels[row.config.frequency] }}
          {{ row.config.local_time }} {{ row.config.timezone
          }}<template v-if="row.config.frequency === 'weekly'">
            · 星期{{ ['一', '二', '三', '四', '五', '六', '日'][row.config.weekday] }}</template
          ><template v-if="row.config.frequency === 'monthly'">
            · 每月 {{ row.config.month_day }} 日</template
          >
        </p>
        <p>
          {{ row.config.data_identity === 'synthetic' ? '合成演示数据' : '用户导入数据' }} ·
          {{ row.config.channel }} · {{ row.config.currency }} · 回看
          {{ row.config.lookback_days }} 天 · 规则 #{{ row.config.rule_revision_id }}
        </p>
        <p>下一次：{{ time(row.next_run_at, row.config.timezone) }}</p>
        <p v-if="row.config.quiet_start !== null">
          免打扰：{{ row.config.quiet_start }}:00–{{ row.config.quiet_end }}:00（{{
            row.config.timezone
          }}）
        </p>
        <div v-if="row.status !== 'revoked'" class="form-actions">
          <button
            v-if="row.status === 'active'"
            class="button secondary small"
            :disabled="busy"
            @click="check(row)"
          >
            立即检查一次
          </button>
          <button
            v-if="row.status === 'active'"
            class="button secondary small"
            :disabled="busy"
            @click="act(row, 'pause')"
          >
            暂停
          </button>
          <button
            v-else
            class="button secondary small"
            :disabled="busy"
            @click="confirmAction = { row, action: 'resume' }"
          >
            恢复
          </button>
          <button class="button secondary small" :disabled="busy" @click="edit(row)">修改</button>
          <button
            class="button secondary small"
            :disabled="busy"
            @click="confirmAction = { row, action: 'revoke' }"
          >
            撤销
          </button>
        </div>
        <div v-if="confirmAction?.row.id === row.id" class="data-note section-block">
          <p>
            {{
              confirmAction.action === 'resume'
                ? '确认按卡片中的范围和规则恢复？从下一个周期开始，暂停期间不补跑。'
                : '确认永久撤销此计划？历史执行和已保存候选继续保留。'
            }}
          </p>
          <button
            class="button secondary small"
            :disabled="busy"
            @click="act(row, confirmAction.action)"
          >
            确认{{ confirmAction.action === 'resume' ? '恢复' : '撤销' }}
          </button>
          <button class="button secondary small" :disabled="busy" @click="confirmAction = null">
            取消
          </button>
        </div>
      </article>
    </section>
    <section class="section-block" aria-label="站内通知与运行历史">
      <h2>站内通知与运行历史</h2>
      <label class="check-label"
        ><input
          v-model="unread"
          type="checkbox"
          :disabled="busy"
          @change="perform(refresh)"
        />只看已到提醒时间的未读通知</label
      >
      <p>
        显示周期结束时的状态；原任务的当前来源、审批与处理进度请点“查看检查与审批”。免打扰期间的结果在完整历史中可见。
      </p>
      <p v-if="!history.length">{{ unread ? '当前没有到期的未读通知。' : '还没有运行记录。' }}</p>
      <article
        v-for="item in history"
        :key="item.id"
        class="form-panel section-block"
        :aria-label="`周期记录 ${item.id}`"
      >
        <h3>
          计划 #{{ item.schedule_id }} · {{ labels[item.status] ?? item.status }}
          <span v-if="!item.read_at" class="outline-label">未读</span>
        </h3>
        <p>
          {{ item.trigger === 'timer' ? '定时周期' : '手动检查' }}：{{ time(item.scheduled_at) }} ·
          保存：{{ time(item.created_at) }}
        </p>
        <p v-if="item.coalesced_from">
          从 {{ time(item.coalesced_from) }} 起的错过周期已合并，本次只处理最近一期。
        </p>
        <p v-if="item.status === 'missed'">最近一期已超过 24 小时补跑窗口，等待下一周期。</p>
        <p v-if="['blocked', 'paused', 'circuit_open'].includes(item.status)">
          该周期检查受阻，计划当时已暂停。{{
            reasons[item.reason] ?? '请查看原任务，核对条件后恢复计划。'
          }}
        </p>
        <p>提醒时间：{{ time(item.notify_at) }}</p>
        <div class="form-actions">
          <RouterLink
            v-if="item.execution_id"
            :to="{ path: '/agent', query: { shop: shopId, execution: item.execution_id } }"
            class="button secondary small"
            >查看检查与审批</RouterLink
          ><button
            v-if="!item.read_at"
            class="button secondary small"
            :disabled="busy"
            @click="read(item)"
          >
            标为已读
          </button>
        </div>
      </article>
      <button
        v-if="history.length === 50"
        class="button secondary small"
        :disabled="busy"
        @click="older"
      >
        更早的记录
      </button>
    </section>
  </template>
</template>
