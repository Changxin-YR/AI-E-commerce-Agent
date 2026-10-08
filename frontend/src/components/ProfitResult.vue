<script setup lang="ts">
import { decimalText, feeLabels, type StudyResult } from '@/types/profit'
import { supportTime } from '@/types/support'
defineProps<{ result: StudyResult; timezone: string }>()
</script>

<template>
  <section class="section-block profit-result" aria-label="利润情景结果">
    <div class="section-title">
      <h2>{{ result.input.title }}</h2>
      <span class="status-tag">假设估算</span>
    </div>
    <p class="muted">
      {{ result.input.data_identity === 'synthetic' ? '合成测试数据' : '手工假设' }} ·
      {{ result.input.currency }} · {{ supportTime(result.calculated_at, timezone) }}
    </p>
    <p class="scope-note">{{ result.scope_note }}</p>
    <details>
      <summary>计算公式与口径</summary>
      <p>{{ result.formula }}</p>
      <p class="muted">
        规则版本：{{ result.rule_version }}；订单状态、订单行：不适用（独立新品假设）。
      </p>
    </details>
    <p class="muted">表格可横向滚动查看全部金额。</p>
    <div class="comparison-scroll" tabindex="0" role="region" aria-label="方案对比表">
      <table>
        <caption>
          同币种方案对比 · 金额为原始精度
        </caption>
        <thead>
          <tr>
            <th scope="col">方案</th>
            <th scope="col">候选售价</th>
            <th scope="col">采购毛利</th>
            <th scope="col">已填费用</th>
            <th scope="col">已知费用后余额</th>
            <th scope="col">余额率</th>
            <th scope="col">假设保本价</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in result.scenarios" :key="item.assumption.name">
            <th scope="row">{{ item.assumption.name }}</th>
            <td>{{ decimalText(item.assumption.price) }}</td>
            <td>{{ decimalText(item.purchase_gross) }}</td>
            <td>{{ decimalText(item.known_fees) }}</td>
            <td>{{ decimalText(item.known_balance) }}</td>
            <td>
              {{
                item.margin_percent === null ? '无法确定' : `${decimalText(item.margin_percent)}%`
              }}
            </td>
            <td>{{ decimalText(item.break_even_price) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <article
      v-for="(item, index) in result.scenarios"
      :key="index"
      class="form-panel section-block"
    >
      <h3>{{ item.assumption.name }}</h3>
      <p>采购毛利：{{ decimalText(item.purchase_gross) }} {{ result.input.currency }}</p>
      <p>
        已知费用后余额：<strong
          >{{ decimalText(item.known_balance) }} {{ result.input.currency }}</strong
        >
      </p>
      <p v-if="item.missing_fees.length" class="support-handoff" role="status">
        未计入的未知费用：{{ item.missing_fees.join('、') }}。余额仅扣除了已填项。
      </p>
      <p v-else class="muted">九类费用均已填写假设，仍需核对依据与实际结算。</p>
      <p>
        假设保本售价：<strong
          >{{ decimalText(item.break_even_price)
          }}<template v-if="item.break_even_price !== null">
            {{ result.input.currency }}</template
          ></strong
        >
      </p>
      <p>{{ item.break_even_reason }}</p>
      <details class="section-block">
        <summary>输入依据与费用明细 · {{ item.assumption.name }}</summary>
        <p>
          售价 {{ decimalText(item.assumption.price) }} / 采购价
          {{ decimalText(item.assumption.purchase_cost) }} {{ result.input.currency }}
        </p>
        <p class="preserve-text">{{ item.assumption.basis }}</p>
        <p>
          固定费用合计 {{ decimalText(item.fixed_fees) }} {{ result.input.currency }} · 售价费率合计
          {{ decimalText(item.rate_percent) }}%
        </p>
        <dl class="fee-evidence">
          <template v-for="fee in item.fees" :key="fee.assumption.kind"
            ><dt>{{ feeLabels[fee.assumption.kind] }}</dt>
            <dd>
              {{
                fee.assumption.value === null
                  ? '未知 / 未计入'
                  : `${decimalText(fee.assumption.value)} ${fee.assumption.mode === 'percent' ? '% × 售价' : result.input.currency + ' / 件'} → ${decimalText(fee.amount)} ${result.input.currency}`
              }}<br /><span class="muted preserve-text">{{
                fee.assumption.basis || '尚未提供依据'
              }}</span>
            </dd></template
          >
        </dl>
      </details>
      <details class="section-block">
        <summary>敏感性分析 · {{ item.assumption.name }}</summary>
        <p class="muted">
          每次只改变一个输入，其余假设保持原值；未知费用继续未计入。不会预测销量。
        </p>
        <div
          class="comparison-scroll"
          tabindex="0"
          role="region"
          :aria-label="`${item.assumption.name}敏感性表`"
        >
          <table>
            <thead>
              <tr>
                <th scope="col">变化</th>
                <th scope="col">售价</th>
                <th scope="col">采购价</th>
                <th scope="col">已知费用后余额</th>
                <th scope="col">余额率</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="point in item.sensitivity" :key="point.label">
                <th scope="row">{{ point.label }}</th>
                <td>{{ decimalText(point.price) }}</td>
                <td>{{ decimalText(point.purchase_cost) }}</td>
                <td>{{ decimalText(point.known_balance) }}</td>
                <td>
                  {{
                    point.margin_percent === null
                      ? '无法确定'
                      : `${decimalText(point.margin_percent)}%`
                  }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>
    </article>
  </section>
</template>

<style scoped>
.profit-result {
  min-width: 0;
  overflow-wrap: anywhere;
}
.profit-result p {
  margin: 12px 0;
}
.scope-note {
  padding: 16px;
  background: var(--canvas);
  border-left: 3px solid var(--line);
}
.comparison-scroll {
  overflow-x: auto;
  max-width: 100%;
  margin-top: 20px;
}
table {
  border-collapse: collapse;
  width: 100%;
  font-variant-numeric: tabular-nums;
  font-size: 13px;
}
th,
td {
  padding: 12px 10px;
  text-align: left;
  border-bottom: 1px solid var(--line);
  min-width: 95px;
}
caption {
  text-align: left;
  padding: 10px 0;
  color: var(--muted);
}
.fee-evidence {
  display: grid;
  grid-template-columns: minmax(80px, 1fr) minmax(0, 3fr);
  gap: 12px;
  margin-top: 16px;
}
.fee-evidence dd {
  margin: 0;
}
</style>
