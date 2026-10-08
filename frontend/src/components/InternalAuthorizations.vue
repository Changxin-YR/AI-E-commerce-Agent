<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  authorizationsApi,
  authorizationLabels,
  type InternalAuthorization,
} from '@/api/authorizations'
import type { AgentRun } from '@/types/agent'
import { errorMessage } from '@/api/client'
import { supportTime } from '@/types/support'
import FeedbackBanner from './FeedbackBanner.vue'

const props = defineProps<{ shop: number; run: AgentRun | null; busy: boolean }>()
const emit = defineEmits<{
  use: [id: number]
  start: [grant: InternalAuthorization]
  inspect: [id: number]
}>()
const grants = ref<InternalAuthorization[]>([])
const next = ref<number | null>(null)
const loading = ref(false)
const error = ref('')
const info = ref('')
const count = ref(1)
const hours = ref(24)
const confirmed = ref(false)
const restoreConfirm = ref<Record<number, boolean>>({})
let sequence = 0
let createRequest = crypto.randomUUID()
const canCreate = computed(
  () =>
    props.run?.template === 'daily' &&
    props.run?.status === 'waiting_approval' &&
    props.run.next_node === 'propose_tasks' &&
    props.run.source_status === 'current',
)
const countFindings = computed(
  () => (props.run?.result?.findings as unknown[] | undefined)?.length ?? 0,
)
watch([() => props.shop, () => props.run?.id, () => props.run?.version, count, hours], () => {
  confirmed.value = false
  createRequest = crypto.randomUUID()
})
watch(
  [() => props.shop, () => props.run?.version],
  () => {
    void load()
  },
  { immediate: true },
)

async function load(more = false): Promise<void> {
  const seq = ++sequence
  const shop = props.shop
  if (!more) {
    grants.value = []
    next.value = null
  }
  if (!shop) return
  loading.value = true
  error.value = ''
  try {
    const page = await authorizationsApi.list(shop, more ? (next.value ?? undefined) : undefined)
    if (seq !== sequence || props.shop !== shop) return
    grants.value = more ? [...grants.value, ...page.items] : page.items
    next.value = page.next_before_id
  } catch (cause) {
    if (seq === sequence) error.value = errorMessage(cause)
  } finally {
    if (seq === sequence) loading.value = false
  }
}
async function create(): Promise<void> {
  if (!props.run || !canCreate.value || !confirmed.value || loading.value || props.busy) return
  const shop = props.shop
  loading.value = true
  error.value = ''
  info.value = ''
  try {
    await authorizationsApi.create(props.run, count.value, hours.value, createRequest)
    if (shop === props.shop) {
      info.value = '授权已保存。可用于当前候选，或按相同范围启动新的检查。'
      confirmed.value = false
      createRequest = crypto.randomUUID()
      await load()
    }
  } catch (cause) {
    if (shop === props.shop) error.value = errorMessage(cause)
  } finally {
    loading.value = false
  }
}
async function change(grant: InternalAuthorization, useId?: number): Promise<void> {
  if (loading.value || props.busy) return
  loading.value = true
  error.value = ''
  info.value = ''
  try {
    if (useId !== undefined) {
      if (!restoreConfirm.value[useId]) return
      await authorizationsApi.revert(grant, useId)
    } else await authorizationsApi.revoke(grant)
    if (grant.shop_id === props.shop) {
      info.value =
        useId !== undefined
          ? '本次新增候选已拒绝，历史保留，额度不返还。'
          : '授权已撤销，已保存结果保留。'
      await load()
    }
  } catch (cause) {
    if (grant.shop_id === props.shop) error.value = errorMessage(cause)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="section-block authorization-panel" aria-label="R1 内部预授权">
    <div class="section-title">
      <h2>R1 内部预授权</h2>
      <button class="button secondary small" :disabled="busy || loading" @click="load()">
        刷新授权
      </button>
    </div>
    <p>允许在已核对的范围内保存异常候选。每次成功保存消耗 1 次，复用候选也计次；费用 0 USD。</p>
    <p>
      来源、规则、内容或检查范围变化后须重新核对。候选处理仍逐项审批；邮件外发属于独立的 R2 操作。
    </p>
    <FeedbackBanner :message="error" />
    <p v-if="info" role="status">{{ info }}</p>
    <form v-if="canCreate && run?.input" class="data-note" @submit.prevent="create">
      <h3>为当前预览创建授权</h3>
      <p>
        检查窗口：{{ supportTime(run.input.scope.start_at, run.input.scope.timezone) }} 至
        {{ supportTime(run.input.scope.end_at, run.input.scope.timezone) }}（不含结束） ·
        {{ run.input.scope.currency }}。库存 {{ run.input.scope.max_age_hours }} 小时；最低销量
        {{ run.input.scope.min_quantity }} 件；低毛利率不高于
        {{ run.input.scope.max_margin_percent }}%；规则 #{{
          run.input.scope.rule_revision_id ?? 0
        }}。
      </p>
      <p>
        店铺 #{{ shop }} · {{ run.input.scope.channel }} ·
        {{ run.input.scope.data_identity === 'synthetic' ? '合成测试' : '用户导入' }} ·
        {{ countFindings }} 项候选
      </p>
      <p>
        依据为上方任务 #{{ run.id }}
        的对象、异常全文与来源；新增候选的原值为“无”，新值为“待审批”，已有候选保留处理状态。
      </p>
      <p>
        撤回仅将本次新增且未被后续编辑或处理的候选设为“已拒绝”，保留历史；任一项已变化则整批拒绝撤回。撤销授权不会撤回已有结果。
      </p>
      <fieldset class="analysis-fields" :disabled="busy || loading">
        <label
          >最多保存次数<input v-model.number="count" type="number" min="1" max="20" required
        /></label>
        <label
          >有效小时数<input v-model.number="hours" type="number" min="1" max="168" required
        /></label>
      </fieldset>
      <label class="check-label"
        ><input
          v-model="confirmed"
          type="checkbox"
          :disabled="busy || loading"
        />我已核对候选和恢复边界，同意此有限范围预授权</label
      >
      <button class="button primary" :disabled="busy || loading || !confirmed">保存预授权</button>
    </form>
    <p v-if="!grants.length && !loading">尚无授权。先运行今日运营检查，在待审批候选下创建。</p>
    <details v-for="grant in grants" :key="grant.id" class="authorization-item">
      <summary>
        授权 #{{ grant.id }} · {{ authorizationLabels[grant.status] }} · 已用
        {{ grant.used_count }} / {{ grant.max_uses }} 次
      </summary>
      <p>
        店铺 #{{ grant.shop_id }} · {{ grant.scope.channel }} ·
        {{ grant.scope.data_identity === 'synthetic' ? '合成测试' : '用户导入' }} · 来源版本
        {{ grant.source_revision }} · 规则 #{{ grant.scope.rule_revision_id ?? 0 }}
      </p>
      <p>
        范围：{{ supportTime(grant.scope.start_at, grant.scope.timezone) }} 至
        {{ supportTime(grant.scope.end_at, grant.scope.timezone) }}（不含结束） ·
        {{ grant.scope.currency }}
      </p>
      <p>
        库存 {{ grant.scope.max_age_hours }} 小时；最低销量
        {{ grant.scope.min_quantity }} 件；低毛利率不高于
        {{ grant.scope.max_margin_percent }}%。绑定预览 {{ grant.candidate_count }} 项，原任务 #{{
          grant.origin_execution_id
        }}。
      </p>
      <p>
        授权到期：{{ supportTime(grant.expires_at, grant.scope.timezone)
        }}<span v-if="grant.source_valid_until"
          >；来源到期：{{ supportTime(grant.source_valid_until, grant.scope.timezone) }}</span
        >。以较早时间为准。
      </p>
      <div class="button-row">
        <button
          class="button secondary"
          :disabled="busy || loading"
          @click="emit('inspect', grant.origin_execution_id)"
        >
          查看原预览
        </button>
        <button
          v-if="grant.status === 'active' && canCreate"
          class="button primary"
          :disabled="busy || loading"
          @click="emit('use', grant.id)"
        >
          为当前候选使用此授权
        </button>
        <button
          v-if="grant.status === 'active'"
          class="button secondary"
          :disabled="busy || loading"
          @click="emit('start', grant)"
        >
          按授权范围运行
        </button>
        <button
          v-if="!grant.revoked_at"
          class="button secondary"
          :disabled="busy || loading"
          @click="change(grant)"
        >
          撤销授权
        </button>
      </div>
      <h3 v-if="grant.uses.length">实际消耗与恢复</h3>
      <article v-for="use in grant.uses" :key="use.id" class="analysis-line">
        <p>
          任务 #{{ use.execution_id }} → 检查记录 #{{ use.operation_run_id }} ·
          {{ supportTime(use.created_at, grant.scope.timezone) }}
        </p>
        <p>新增 {{ use.changes.length }} 项，复用 {{ use.reused_count }} 项；消耗 1 次。</p>
        <p v-for="changeRow in use.changes" :key="changeRow.task_id">
          候选 #{{ changeRow.task_id }}：无 → 待审批（保存时版本 {{ changeRow.version }}）
        </p>
        <p v-if="use.reverted_at">
          已撤回新增候选 · {{ supportTime(use.reverted_at, grant.scope.timezone) }}
        </p>
        <template v-else-if="use.changes.length">
          <label class="check-label"
            ><input
              v-model="restoreConfirm[use.id]"
              type="checkbox"
              :disabled="busy || loading"
            />将本次未处理的新增候选设为已拒绝；额度不返还</label
          >
          <button
            class="button secondary"
            :disabled="busy || loading || !restoreConfirm[use.id]"
            @click="change(grant, use.id)"
          >
            撤回新增候选
          </button>
        </template>
      </article>
    </details>
    <button v-if="next" class="button secondary" :disabled="busy || loading" @click="load(true)">
      加载更早授权
    </button>
  </section>
</template>

<style scoped>
.authorization-panel {
  min-width: 0;
  overflow-wrap: anywhere;
}
.authorization-panel form.data-note {
  display: block;
}
.authorization-panel form.data-note p {
  margin: 12px 0;
}
.authorization-item {
  border-top: 1px solid var(--line);
  padding: 18px 0;
}
fieldset {
  border: 0;
  padding: 0;
}
.check-label {
  margin: 14px 0;
}
</style>
