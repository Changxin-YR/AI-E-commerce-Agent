import test from 'node:test'
import assert from 'node:assert/strict'
import {
  approveGate,
  approvePayload,
  catalogFields,
  changedPreview,
  changedProducts,
  checkedEditCreate,
  controlPayload,
  editGates,
  editItemDiff,
  editSummary,
  selectedCount,
  unknownResult,
  visibleProducts,
} from '../src/services/product-edit-policy.ts'

function product(id, overrides = {}) {
  return {
    product_id: id,
    sku: `SKU-${id}`,
    name: `名称${id}`,
    facts: `参数${id}`,
    price: '10.00',
    currency: 'USD',
    unit_cost: null,
    cost_currency: null,
    channel: 'shopify',
    source: { batch_id: 1, row_id: 100 + id },
    issues: [],
    similar_skus: [],
    similar_sku_count: 0,
    ...overrides,
  }
}
function draft(overrides = {}) {
  return {
    status: 'draft',
    version: 1,
    preview_hash: 'b'.repeat(64),
    snapshot: { items: [{ product_id: 1 }] },
    output_batch_id: null,
    current_count: 0,
    ...overrides,
  }
}

test('catalog fields start unselected and only changed selections become changes', () => {
  const products = [product(1), product(2), product(3)]
  const fields = catalogFields(products)
  assert.deepEqual(Object.keys(fields), ['1', '2', '3'])
  assert.equal(selectedCount(fields), 0)
  fields[1].selected = true
  fields[1].name = '新名称1'
  fields[2].selected = true
  fields[3].selected = true
  fields[3].facts = '新参数3'
  const changes = changedProducts(products, fields)
  assert.deepEqual(changes, [
    {
      product_id: 1,
      expected_source_row_id: 101,
      name: '新名称1',
      facts: '参数1',
    },
    {
      product_id: 3,
      expected_source_row_id: 103,
      name: '名称3',
      facts: '新参数3',
    },
  ])
  assert.equal(selectedCount(fields), 3)
})

test('edit drafts are bounded to 50 unique changed products with a reason', () => {
  const changes = Array.from({ length: 3 }, (_, index) => ({
    product_id: index + 1,
    expected_source_row_id: 100 + index,
    name: `名称${index}`,
    facts: '',
  }))
  const checked = checkedEditCreate({
    data_identity: 'user_import',
    channel: 'shopify',
    reason: '  更正规格  ',
    changes,
    request_id: 'req-1',
  })
  assert.equal(checked.reason, '更正规格')
  assert.equal(checked.changes.length, 3)
  const tooMany = Array.from({ length: 51 }, (_, index) => ({
    product_id: index + 1,
    expected_source_row_id: index + 1,
    name: `n${index}`,
    facts: '',
  }))
  assert.throws(
    () =>
      checkedEditCreate({
        data_identity: 'user_import',
        channel: 'shopify',
        reason: 'r',
        changes: tooMany,
        request_id: 'req-1',
      }),
    /每批最多 50 个商品/,
  )
  assert.throws(
    () =>
      checkedEditCreate({
        data_identity: 'user_import',
        channel: 'shopify',
        reason: 'r',
        changes: [changes[0], { ...changes[0], name: '另一个名称' }],
        request_id: 'req-1',
      }),
    /同一商品只能修订一次/,
  )
})

test('edit drafts reject blank names, oversized text and missing evidence', () => {
  const base = {
    data_identity: 'user_import',
    channel: 'shopify',
    reason: '依据',
    changes: [
      { product_id: 1, expected_source_row_id: 101, name: '名称', facts: '' },
    ],
    request_id: 'req-1',
  }
  assert.throws(() => checkedEditCreate({ ...base, reason: '   ' }), /修订依据/)
  assert.throws(
    () => checkedEditCreate({ ...base, reason: 'x'.repeat(501) }),
    /修订依据最多 500 个字符/,
  )
  assert.throws(() => checkedEditCreate({ ...base, changes: [] }), /至少一个/)
  assert.throws(
    () => checkedEditCreate({ ...base, request_id: '' }),
    /缺少请求标识/,
  )
  assert.throws(
    () =>
      checkedEditCreate({
        ...base,
        changes: [{ ...base.changes[0], name: '   ' }],
      }),
    /商品名称不能为空白/,
  )
  assert.throws(
    () =>
      checkedEditCreate({
        ...base,
        changes: [{ ...base.changes[0], name: 'x'.repeat(241) }],
      }),
    /商品名称最多 240 个字符/,
  )
  assert.throws(
    () =>
      checkedEditCreate({
        ...base,
        changes: [{ ...base.changes[0], facts: 'x'.repeat(2001) }],
      }),
    /商品参数最多 2000 个字符/,
  )
  assert.throws(
    () =>
      checkedEditCreate({
        ...base,
        changes: [{ ...base.changes[0], expected_source_row_id: 0 }],
      }),
    /商品来源行无效/,
  )
  assert.throws(() => checkedEditCreate({ ...base, channel: '' }), /来源渠道/)
  assert.throws(
    () => checkedEditCreate({ ...base, data_identity: 'live' }),
    /修订数据身份/,
  )
})

test('edit gates only expose actions the server still accepts', () => {
  assert.deepEqual(
    editGates({
      status: 'draft',
      snapshot: { items: [] },
      output_batch_id: null,
    }),
    {
      approve: true,
      reject: true,
      withdraw: false,
      clear: true,
    },
  )
  assert.deepEqual(
    editGates({ status: 'applied', snapshot: null, output_batch_id: 9 }),
    {
      approve: false,
      reject: false,
      withdraw: true,
      clear: true,
    },
  )
  assert.deepEqual(
    editGates({ status: 'cleared', snapshot: null, output_batch_id: 9 }),
    {
      approve: false,
      reject: false,
      withdraw: true,
      clear: false,
    },
  )
  assert.deepEqual(
    editGates({ status: 'rejected', snapshot: null, output_batch_id: null }),
    {
      approve: false,
      reject: false,
      withdraw: false,
      clear: false,
    },
  )
})

test('approval requires the reviewed hash, a draft and explicit confirmation', () => {
  assert.deepEqual(approveGate(draft(), true), [])
  assert.match(approveGate(draft(), false).join(' '), /逐项核对/)
  assert.match(
    approveGate(draft({ status: 'applied' }), true).join(' '),
    /仅待审批草稿/,
  )
  assert.match(
    approveGate(draft({ snapshot: { items: [] } }), true).join(' '),
    /差异明细/,
  )
  assert.match(
    approveGate(draft({ preview_hash: 'short' }), true).join(' '),
    /指纹无效/,
  )
  assert.deepEqual(approvePayload(draft(), true), {
    version: 1,
    expected_preview_hash: 'b'.repeat(64),
    confirm: true,
  })
  assert.throws(() => approvePayload(draft(), false), /逐项核对/)
})

test('control payloads refuse actions the object can no longer accept', () => {
  assert.deepEqual(controlPayload(draft(), 'reject', true), {
    version: 1,
    confirm: true,
  })
  assert.deepEqual(
    controlPayload(
      draft({ status: 'applied', output_batch_id: 5 }),
      'withdraw',
      true,
    ),
    { version: 1, confirm: true },
  )
  assert.deepEqual(controlPayload(draft(), 'clear', true), {
    version: 1,
    confirm: true,
  })
  assert.throws(() => controlPayload(draft(), 'reject', false), /确认处理/)
  assert.throws(
    () => controlPayload(draft({ status: 'applied' }), 'reject', true),
    /仅待审草稿可以拒绝/,
  )
  assert.throws(
    () =>
      controlPayload(
        draft({ status: 'draft', output_batch_id: null }),
        'withdraw',
        true,
      ),
    /尚未本地生效/,
  )
  assert.throws(
    () => controlPayload(draft({ status: 'cleared' }), 'clear', true),
    /正文已清除/,
  )
  assert.throws(
    () => controlPayload(draft({ version: 0 }), 'clear', true),
    /版本无效/,
  )
})

test('summaries, diffs and paging stay explicit about what changed', () => {
  assert.equal(
    editItemDiff({
      before: { name: 'A', facts: 'f' },
      after: { name: 'B', facts: 'g' },
    }),
    '名称 / 参数',
  )
  assert.equal(
    editItemDiff({
      before: { name: 'A', facts: 'f' },
      after: { name: 'A', facts: 'g' },
    }),
    '参数',
  )
  assert.match(editSummary(draft()), /本批 1 项差异/)
  assert.match(
    editSummary(draft({ status: 'applied', current_count: 4 })),
    /当前 4 项仍为主档来源/,
  )
  assert.match(editSummary(draft({ status: 'failed' })), /整批未生效/)
  const products = Array.from({ length: 45 }, (_, index) => product(index + 1))
  assert.equal(visibleProducts(products, 0).length, 20)
  assert.equal(visibleProducts(products, 2).length, 5)
  assert.equal(changedPreview({ 1: { selected: false } }, '前缀', ''), false)
  assert.equal(changedPreview({ 1: { selected: true } }, '  ', ''), false)
  assert.equal(changedPreview({ 1: { selected: true } }, '前缀', ''), true)
  assert.equal(changedPreview({ 1: { selected: true } }, '', '追加'), true)
})

test('unknown results keep the request id while context switches do not', () => {
  assert.equal(unknownResult({ status: 0, code: 'network_error' }), true)
  assert.equal(unknownResult({ status: 0, code: 'stale_response' }), false)
  assert.equal(unknownResult({ status: 409 }), false)
})
