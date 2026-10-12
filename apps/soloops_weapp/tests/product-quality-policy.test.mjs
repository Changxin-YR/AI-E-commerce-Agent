import test from 'node:test'
import assert from 'node:assert/strict'
import {
  checkedQualityScope,
  clearsQualityReport,
  coverageGaps,
  defaultQualityForm,
  dirtyQualityForm,
  productIssues,
  productMoney,
  qualitySavePayload,
  qualitySummary,
  unknownResult,
} from '../src/services/product-quality-policy.ts'

const hash = 'a'.repeat(64)
function result(overrides = {}) {
  return {
    scope: {
      data_identity: 'user_import',
      channel: 'shopify',
      sku_prefix: 'AB',
    },
    source_revision: 12,
    preview_hash: hash,
    product_count: 3,
    affected_products: 2,
    missing_count: 1,
    review_count: 2,
    rule_version: 'quality-v1',
    coverage: [
      { code: 'name', label: '名称', status: 'checked', reason: '' },
      {
        code: 'images',
        label: '图片',
        status: 'not_checked',
        reason: '本地主档不含图片',
      },
    ],
    ...overrides,
  }
}

test('quality scope keeps an optional channel and trims the SKU prefix', () => {
  assert.deepEqual(checkedQualityScope(defaultQualityForm()), {
    data_identity: 'user_import',
    channel: null,
    sku_prefix: '',
  })
  assert.deepEqual(
    checkedQualityScope({
      data_identity: 'synthetic',
      channel: 'amazon',
      sku_prefix: ' A ',
    }),
    { data_identity: 'synthetic', channel: 'amazon', sku_prefix: 'A' },
  )
  assert.throws(
    () =>
      checkedQualityScope({
        data_identity: 'live',
        channel: '',
        sku_prefix: '',
      }),
    /数据身份/,
  )
  assert.throws(
    () =>
      checkedQualityScope({
        data_identity: 'user_import',
        channel: 'etsy',
        sku_prefix: '',
      }),
    /来源渠道/,
  )
  assert.throws(
    () =>
      checkedQualityScope({
        data_identity: 'user_import',
        channel: '',
        sku_prefix: 'x'.repeat(121),
      }),
    /SKU 前缀最多 120 个字符/,
  )
})

test('save payload pins the reviewed revision, hash and request id', () => {
  assert.deepEqual(qualitySavePayload(result(), 'req-1', true), {
    scope: {
      data_identity: 'user_import',
      channel: 'shopify',
      sku_prefix: 'AB',
    },
    expected_revision: 12,
    expected_preview_hash: hash,
    request_id: 'req-1',
    confirm: true,
  })
  assert.throws(() => qualitySavePayload(result(), 'req-1', false), /确认保存/)
  assert.throws(() => qualitySavePayload(result(), '', true), /缺少请求标识/)
  assert.throws(
    () => qualitySavePayload(result({ preview_hash: 'ABCD' }), 'req-1', true),
    /预览指纹无效/,
  )
  assert.throws(
    () => qualitySavePayload(result({ source_revision: -1 }), 'req-1', true),
    /来源版本无效/,
  )
})

test('clear is only offered while a report body still exists', () => {
  assert.equal(clearsQualityReport({ status: 'current' }), true)
  assert.equal(clearsQualityReport({ status: 'stale' }), true)
  assert.equal(clearsQualityReport({ status: 'cleared' }), false)
  assert.equal(clearsQualityReport(undefined), false)
})

test('coverage gaps and summary stay explicit about unchecked fields', () => {
  assert.deepEqual(
    coverageGaps(result()).map((item) => item.code),
    ['images'],
  )
  assert.equal(coverageGaps(result({ coverage: [] })).length, 0)
  const summary = qualitySummary(result())
  assert.match(summary, /共 3 个商品/)
  assert.match(summary, /有缺项或待复核 2 个/)
  assert.match(summary, /缺失 1 项/)
  assert.match(summary, /规则 quality-v1/)
})

test('money and issue text never invents values', () => {
  assert.equal(productMoney('12.30', 'USD'), '12.30 USD')
  assert.equal(productMoney('12.30', null), '12.30')
  assert.equal(productMoney(null, 'USD'), '未知')
  assert.equal(productMoney('', 'USD'), '未知')
  const lines = productIssues({
    issues: [
      {
        code: 'missing_name',
        field: 'name',
        status: 'missing',
        reason: '名称为空',
        suggestion: '补全名称',
      },
      {
        code: 'similar_sku',
        field: 'sku',
        status: 'review',
        reason: '存在相似 SKU',
        suggestion: '核对是否重复',
      },
    ],
  })
  assert.match(lines[0], /缺少资料 · name：名称为空（建议：补全名称）/)
  assert.match(lines[1], /待人工复核 · sku/)
})

test('quality form dirtiness compares the checked scope', () => {
  const scope = { data_identity: 'user_import', channel: null, sku_prefix: '' }
  assert.equal(dirtyQualityForm(defaultQualityForm(), scope), false)
  assert.equal(
    dirtyQualityForm({ ...defaultQualityForm(), sku_prefix: 'AB' }, scope),
    true,
  )
  assert.equal(
    dirtyQualityForm({ ...defaultQualityForm(), sku_prefix: 'AB' }, undefined),
    false,
  )
})

test('unknown results keep the request id while context switches do not', () => {
  assert.equal(unknownResult({ status: 0, code: 'network_error' }), true)
  assert.equal(unknownResult({ status: 0, code: 'stale_response' }), false)
  assert.equal(unknownResult({ status: 422 }), false)
})
