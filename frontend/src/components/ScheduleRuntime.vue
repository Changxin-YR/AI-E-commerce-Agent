<script setup lang="ts">
import { scheduleLabels, type Occurrence } from '@/api/schedules'
import { supportTime } from '@/types/support'

defineProps<{ worker: boolean; latest: Occurrence | null; timezone: string }>()
</script>

<template>
  <section class="source-detail schedule-runtime" aria-label="自动调度运行说明">
    <h3>本地自动调度</h3>
    <p>
      {{
        worker
          ? '自动调度已配置启用，API 服务运行期间约每 30 秒扫描到期计划。'
          : '当前服务关闭自动调度，可手动检查并查看记录。'
      }}
      时间显示：{{ timezone }}。
    </p>
    <p>API 关闭、电脑关机或休眠期间不运行。服务需保持运行，当前配置不代表持续在线。</p>
    <p>
      恢复时仅尝试最近一期，较早周期合并；最近一期超过 24
      小时会记为错过周期。暂停期间不补跑，恢复从下一期开始。
    </p>
    <template v-if="latest">
      <h4>最近自动周期记录</h4>
      <p>计划 #{{ latest.schedule_id }} · 周期 #{{ latest.id }}</p>
      <p>保存时间：{{ supportTime(latest.created_at, timezone) }}</p>
      <p>计划时刻：{{ supportTime(latest.scheduled_at, timezone) }}</p>
      <p>
        当次状态：{{
          latest.task === 'report' && latest.status === 'succeeded'
            ? '报表已保存'
            : (scheduleLabels[latest.status] ?? latest.status)
        }}
      </p>
      <p v-if="latest.coalesced_from">
        从
        {{ supportTime(latest.coalesced_from, timezone) }} 起的较早周期已合并，本次只处理最近一期。
      </p>
      <p v-if="latest.status === 'missed'">本期超过 24 小时补跑窗口，未执行，等待下一周期。</p>
      <p v-if="['blocked', 'paused', 'circuit_open'].includes(latest.status)">
        本期受阻，计划当时已暂停。请核对下方计划与运行历史，再决定恢复。
      </p>
      <RouterLink
        v-if="latest.execution_id"
        :to="{ path: '/agent', query: { shop: latest.shop_id, execution: latest.execution_id } }"
        >查看最近自动检查当前进度</RouterLink
      >
      <RouterLink
        v-if="latest.report_id"
        :to="{ path: '/overview', query: { report: latest.report_id } }"
        >查看最近自动报表与依据</RouterLink
      >
    </template>
    <p v-else>尚无自动周期记录。手动检查记录请看下方运行历史。</p>
    <p class="muted">这里显示已保存的自动周期，不受未读筛选影响；记录时间不代表服务当前在线。</p>
  </section>
</template>

<style scoped>
.schedule-runtime {
  margin-block: 1rem;
  overflow-wrap: anywhere;
}
</style>
