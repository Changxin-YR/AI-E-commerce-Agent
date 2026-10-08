<script setup lang="ts">
import { feeLabels, type ScenarioInput } from '@/types/profit'
const scenario = defineModel<ScenarioInput>({ required: true })
defineProps<{ index: number; currency: string }>()
</script>

<template>
  <div class="scenario-editor">
    <div class="form-grid">
      <div class="form-field">
        <label :for="`scenario-name-${index}`">方案名称</label
        ><input :id="`scenario-name-${index}`" v-model="scenario.name" maxlength="80" required />
      </div>
      <div class="form-field">
        <label :for="`scenario-price-${index}`">候选售价（{{ currency }} / 件）</label
        ><input
          :id="`scenario-price-${index}`"
          v-model="scenario.price"
          inputmode="decimal"
          pattern="[0-9]+(\.[0-9]{1,4})?"
          maxlength="14"
          required
        />
      </div>
      <div class="form-field">
        <label :for="`scenario-cost-${index}`">采购成本（{{ currency }} / 件）</label
        ><input
          :id="`scenario-cost-${index}`"
          v-model="scenario.purchase_cost"
          inputmode="decimal"
          pattern="[0-9]+(\.[0-9]{1,4})?"
          maxlength="14"
          required
        />
      </div>
      <div class="form-field">
        <label :for="`scenario-basis-${index}`">售价与采购成本依据</label
        ><input
          :id="`scenario-basis-${index}`"
          v-model="scenario.basis"
          maxlength="500"
          placeholder="报价来源、日期或试算假设"
          required
        />
      </div>
    </div>
    <h4>单件费用假设</h4>
    <p class="muted">
      空白为未知；填写 0
      表示你明确假设此项为零，仍须说明依据。百分比均按候选售价计算，固定项填单件已分摊金额。
    </p>
    <div v-for="fee in scenario.fees" :key="fee.kind" class="fee-row">
      <div class="form-field">
        <label :for="`fee-value-${index}-${fee.kind}`">{{ feeLabels[fee.kind] }}</label
        ><input
          :id="`fee-value-${index}-${fee.kind}`"
          :value="fee.value ?? ''"
          inputmode="decimal"
          pattern="[0-9]+(\.[0-9]{1,4})?"
          maxlength="14"
          placeholder="未知"
          @input="fee.value = ($event.target as HTMLInputElement).value || null"
        />
      </div>
      <div class="form-field">
        <label :for="`fee-mode-${index}-${fee.kind}`">{{ feeLabels[fee.kind] }}计费方式</label
        ><select :id="`fee-mode-${index}-${fee.kind}`" v-model="fee.mode">
          <option value="fixed">{{ currency }} / 件</option>
          <option value="percent">售价比例 %</option>
        </select>
      </div>
      <div class="form-field">
        <label :for="`fee-basis-${index}-${fee.kind}`">{{ feeLabels[fee.kind] }}依据</label
        ><input
          :id="`fee-basis-${index}-${fee.kind}`"
          v-model="fee.basis"
          maxlength="300"
          :required="fee.value !== null"
          placeholder="来源与日期 / 假设说明"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
h4 {
  margin: 24px 0 8px;
}
.fee-row {
  display: grid;
  grid-template-columns: minmax(100px, 1fr) minmax(130px, 1fr) minmax(0, 2fr);
  gap: 16px;
  padding-top: 16px;
}
@media (max-width: 700px) {
  .fee-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    border-bottom: 1px solid var(--line);
    padding-bottom: 16px;
  }
  .fee-row > :last-child {
    grid-column: 1 / -1;
  }
}
</style>
