<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { QualityResult } from '@/types/productQuality'
import { qualityChannels } from '@/types/productQuality'
import { supportTime } from '@/types/support'
import SourceEvidence from './SupportSource.vue'

const props = defineProps<{ result: QualityResult; timezone: string }>()
const filter = ref('all')
const search = ref('')
const page = ref(0)
const filtered = computed(() =>
  props.result.products.filter((p) => {
    const matches = `${p.sku} ${p.name}`
      .toLocaleLowerCase()
      .includes(search.value.toLocaleLowerCase())
    return (
      matches &&
      (filter.value === 'all' ||
        (filter.value === 'none'
          ? !p.issues.length
          : p.issues.some((i) => i.status === filter.value)))
    )
  }),
)
const visible = computed(() => filtered.value.slice(page.value * 20, (page.value + 1) * 20))
watch([filter, search, () => props.result], () => {
  page.value = 0
})
</script>

<template>
  <section aria-label="商品质量检查结果" class="section-block quality-results">
    <div class="section-title">
      <h2>检查结果与依据</h2>
      <span>来源版本 {{ result.source_revision }}</span>
    </div>
    <p class="muted">
      {{ supportTime(result.checked_at, timezone) }} ·
      {{ result.scope.data_identity === 'synthetic' ? '合成测试数据' : '用户导入文件' }} ·
      {{ result.scope.channel ? qualityChannels[result.scope.channel] : '全部导入渠道' }} · SKU 前缀
      {{ result.scope.sku_prefix || '不限' }}
    </p>
    <div v-if="result.product_count" class="quality-summary form-panel">
      <p>
        <strong>{{ result.product_count }}</strong> 个商品已检查
      </p>
      <p>
        <strong>{{ result.affected_products }}</strong> 个商品有核对项
      </p>
      <p>
        <strong>{{ result.missing_count }}</strong> 项缺失 ·
        <strong>{{ result.review_count }}</strong> 项待核对
      </p>
    </div>
    <div v-else class="form-panel empty-state">
      <h3>此范围暂无商品，未检查</h3>
      <p>核对店铺、数据身份、渠道与 SKU 前缀，或先导入商品文件。</p>
    </div>
    <div class="form-panel section-block">
      <h3>本次覆盖范围</h3>
      <ul class="coverage-list">
        <li v-for="item in result.coverage" :key="item.code">
          <strong>{{ item.label }} · {{ item.status === 'checked' ? '已检查' : '未检查' }}</strong>
          <p>{{ item.reason }}</p>
        </li>
      </ul>
      <details>
        <summary>检查口径与边界 · {{ result.rule_version }}</summary>
        <ul>
          <li v-for="note in result.limitations" :key="note">{{ note }}</li>
        </ul>
      </details>
    </div>
    <div v-if="result.product_count" class="form-panel section-block">
      <div class="form-grid">
        <div class="form-field">
          <label for="quality-filter">核对项筛选</label
          ><select id="quality-filter" v-model="filter">
            <option value="all">全部商品</option>
            <option value="missing">有缺失项</option>
            <option value="review">有待核对项</option>
            <option value="none">已检查规则未发现问题</option>
          </select>
        </div>
        <div class="form-field">
          <label for="quality-search">在结果中搜索 SKU / 名称</label
          ><input id="quality-search" v-model="search" maxlength="240" />
        </div>
      </div>
      <p class="muted">筛选仅改变下方展示，保存包含本次范围的全部检查结果。</p>
    </div>
    <p v-if="result.product_count && !filtered.length">没有匹配筛选的商品。</p>
    <article
      v-for="item in visible"
      :key="item.product_id"
      class="form-panel section-block"
      :aria-label="`商品 ${item.sku}`"
    >
      <div class="section-title">
        <h3>{{ item.sku }} · {{ item.name }}</h3>
        <span class="status-tag">{{
          item.issues.length ? `${item.issues.length} 项需核对` : '已检查规则未发现问题'
        }}</span>
      </div>
      <p v-if="!item.issues.length" class="muted">品牌、编码、素材等未检查项仍需核验。</p>
      <ul v-if="item.issues.length" class="quality-issues">
        <li v-for="issue in item.issues" :key="issue.code">
          <strong>{{ issue.status === 'missing' ? '缺失' : '待核对' }} · {{ issue.reason }}</strong>
          <p>{{ issue.suggestion }}</p>
        </li>
      </ul>
      <p v-if="item.similar_sku_count">
        相似 SKU（另有 {{ item.similar_sku_count }} 个，最多展示 20 个）：{{
          item.similar_skus.join('、')
        }}
      </p>
      <details>
        <summary>本次检查的商品字段</summary>
        <dl>
          <dt>名称</dt>
          <dd>{{ item.name }}</dd>
          <dt>参数</dt>
          <dd class="preserve-text">{{ item.facts || '未提供' }}</dd>
          <dt>售价</dt>
          <dd>{{ item.price ?? '未知' }} {{ item.currency ?? '币种未知' }}</dd>
          <dt>采购成本</dt>
          <dd>{{ item.unit_cost ?? '未知' }} {{ item.cost_currency ?? '币种未知' }}</dd>
          <dt>来源渠道</dt>
          <dd>{{ item.channel }}</dd>
        </dl>
      </details>
      <SourceEvidence :shop-id="result.shop_id" :source="item.source" />
    </article>
    <div v-if="filtered.length" class="form-actions">
      <button class="button secondary" :disabled="page === 0" @click="page--">上一页商品</button
      ><span>第 {{ page + 1 }} 页 · 共 {{ filtered.length }} 个 · 每页 20 个</span
      ><button
        class="button secondary"
        :disabled="(page + 1) * 20 >= filtered.length"
        @click="page++"
      >
        下一页商品
      </button>
    </div>
  </section>
</template>

<style scoped>
.quality-results {
  overflow-wrap: anywhere;
}
.quality-summary {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
}
.quality-summary strong {
  font-size: 1.5rem;
}
.coverage-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  list-style: none;
  padding: 0;
}
.coverage-list p,
.quality-issues p {
  margin-top: 0.4rem;
}
.quality-issues {
  padding-left: 1.25rem;
}
details {
  margin-top: 1rem;
}
dt {
  font-weight: 600;
  margin-top: 0.75rem;
}
dd {
  margin-left: 0;
}
@media (max-width: 640px) {
  .coverage-list {
    grid-template-columns: 1fr;
  }
  .section-title {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }
}
</style>
