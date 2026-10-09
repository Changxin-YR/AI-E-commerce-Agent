<script setup lang="ts">
import { computed } from 'vue'
import { agentLabels, type ListingCandidate } from '@/types/agent'
const props = defineProps<{ value: ListingCandidate }>()
const before = computed(
  () =>
    props.value.preparation.before ?? {
      title: props.value.preparation.product.name,
      description: props.value.preparation.product.facts,
    },
)
const changed = computed(
  () =>
    before.value.title !== props.value.candidate.title ||
    before.value.description !== props.value.candidate.description,
)
</script>

<template>
  <section class="section-block listing-review" aria-label="模型 Listing 候选预览">
    <h3>商品事实已组织为候选</h3>
    <p>
      {{ value.preparation.product.sku }} · 基线
      {{
        value.preparation.active_id ? `本地版本 #${value.preparation.active_id}` : '导入商品原文'
      }}
      · {{ agentLabels[value.engine] ?? value.engine }}
    </p>
    <div class="listing-diff">
      <section>
        <h4>当前文案</h4>
        <strong>{{ before.title }}</strong>
        <p class="preserve-text">{{ before.description }}</p>
      </section>
      <section>
        <h4>候选文案 · {{ changed ? '有文字变化' : '与当前文案相同' }}</h4>
        <strong>{{ value.candidate.title }}</strong>
        <p class="preserve-text">{{ value.candidate.description }}</p>
      </section>
    </div>
    <p>
      原文覆盖检查通过：标题保留完整商品名，描述包含全部参数行。事实真实性和平台适用性仍须逐项核对。
    </p>
    <p>批准当前节点会保存待审草稿。进入 Listing 页面核对并单独批准后，本地版本生效。</p>
  </section>
</template>
