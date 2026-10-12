import test from 'node:test'
import assert from 'node:assert/strict'
import {
  checkedStudyInput,
  copyScenario,
  decimalText,
  feeValue,
  hasMoreStudies,
  newScenario,
  newStudyForm,
  nextScenarioName,
  studiesPerPage,
} from '../src/services/profit-policy.ts'

function scenario(overrides = {}) {
  return {
    ...newScenario('方案 1'),
    price: '19.9',
    purchase_cost: '8',
    basis: '供应商报价',
    ...overrides,
  }
}
function form(overrides = {}) {
  return { ...newStudyForm('USD'), title: '新品 A', ...overrides }
}
function study(scenarioOverrides = {}) {
  return form({ scenarios: [scenario(scenarioOverrides)] })
}
function fee(overrides) {
  return { ...newScenario().fees[0], ...overrides }
}

test('profit form keeps nine fee categories and unique default names', () => {
  const empty = newStudyForm('CNY')
  assert.equal(empty.currency, 'CNY')
  assert.equal(empty.data_identity, 'manual_assumption')
  assert.equal(empty.scenarios.length, 1)
  assert.deepEqual(
    empty.scenarios[0].fees.map((item) => item.kind),
    [
      'inbound',
      'outbound',
      'platform',
      'storage',
      'packaging',
      'advertising',
      'refund',
      'tax',
      'other',
    ],
  )
  assert.ok(empty.scenarios[0].fees.every((item) => item.value === null))
  assert.equal(
    nextScenarioName([newScenario('方案 1'), newScenario('方案 2')]),
    '方案 3',
  )
  assert.equal(nextScenarioName([newScenario('方案 2')]), '方案 1')
})

test('copying a scenario deep-clones values and renames the copy', () => {
  const source = scenario({
    price: '19.9',
    fees: [fee({ value: '2.5', basis: '快递报价' })],
  })
  const copy = copyScenario(source, '方案 9')
  assert.equal(copy.name, '方案 9')
  copy.fees[0].value = '9.9'
  copy.price = '1'
  assert.equal(source.fees[0].value, '2.5')
  assert.equal(source.price, '19.9')
})

test('profit input is trimmed, normalised and leaves the caller untouched', () => {
  const base = newScenario('  方案 1  ')
  const fees = base.fees.map((item) => {
    if (item.kind === 'inbound')
      return { ...item, value: ' 1.5 ', basis: ' 头程报价 ' }
    if (item.kind === 'platform')
      return { ...item, mode: 'percent', value: '15', basis: '平台费率' }
    return item
  })
  const input = form({
    title: ' 新品 A ',
    currency: 'usd',
    scenarios: [
      {
        ...base,
        price: '  19.9000 ',
        purchase_cost: '8.0000',
        basis: ' 供应商报价 ',
        fees,
      },
    ],
  })
  const checked = checkedStudyInput(input)
  assert.equal(checked.title, '新品 A')
  assert.equal(checked.currency, 'USD')
  assert.equal(checked.scenarios[0].name, '方案 1')
  assert.equal(checked.scenarios[0].price, '19.9000')
  assert.equal(checked.scenarios[0].basis, '供应商报价')
  assert.equal(checked.scenarios[0].fees[0].value, '1.5')
  assert.equal(checked.scenarios[0].fees[0].basis, '头程报价')
  assert.equal(checked.scenarios[0].fees[2].mode, 'percent')
  assert.equal(checked.scenarios[0].fees[2].value, '15')
  assert.equal(checked.scenarios[0].fees[3].value, null)
  // An unset fee keeps no amount even when a stale basis is present.
  assert.equal(checked.scenarios[0].fees[3].basis, '')
  // The page form itself stays as typed by the seller.
  assert.equal(input.scenarios[0].price, '  19.9000 ')
  assert.equal(input.currency, 'usd')
  assert.equal(input.scenarios[0].name, '  方案 1  ')
})

test('profit input rejects an invalid header', () => {
  for (const [overrides, message] of [
    [{ title: '' }, /试算名称须为 1–120 个字符/],
    [{ title: 'x'.repeat(121) }, /试算名称须为 1–120 个字符/],
    [{ currency: 'US' }, /结算币种须为三位字母代码/],
    [{ currency: '' }, /结算币种须为三位字母代码/],
    [{ data_identity: 'live' }, /假设来源无效/],
    [{ scenarios: [] }, /方案数量须为 1–5 个/],
    [
      {
        scenarios: Array.from({ length: 6 }, (_, i) =>
          newScenario(`方案 ${i + 1}`),
        ),
      },
      /方案数量须为 1–5 个/,
    ],
  ])
    assert.throws(() => checkedStudyInput(form(overrides)), message)
})

test('profit input rejects duplicate and malformed scenarios', () => {
  const duplicated = form({
    scenarios: [scenario({ name: '同名' }), scenario({ name: '同名' })],
  })
  assert.throws(() => checkedStudyInput(duplicated), /方案名称不能重复/)
  for (const [overrides, message] of [
    [{ name: '' }, /名称须为 1–80 个字符/],
    [{ price: '' }, /方案 1售价须为最多四位小数的非负金额字符串/],
    [{ price: '-1' }, /方案 1售价须为最多四位小数的非负金额字符串/],
    [{ price: '1.23456' }, /方案 1售价须为最多四位小数的非负金额字符串/],
    [{ price: '100000000.0001' }, /方案 1售价不能超过 100000000/],
    [{ price: '100000001' }, /方案 1售价不能超过 100000000/],
    [{ purchase_cost: 'abc' }, /采购成本须为最多四位小数的非负金额字符串/],
    [{ basis: '' }, /价格与采购成本依据须为 1–500 个字符/],
    [{ basis: 'x'.repeat(501) }, /价格与采购成本依据须为 1–500 个字符/],
  ])
    assert.throws(() => checkedStudyInput(study(overrides)), message)
  assert.equal(
    checkedStudyInput(study({ price: '100000000', purchase_cost: '0' }))
      .scenarios[0].price,
    '100000000',
  )
})

test('profit input requires exactly one of each fee category', () => {
  const nine = newScenario().fees
  assert.throws(
    () => checkedStudyInput(study({ fees: nine.slice(0, 8) })),
    /须包含九类费用各一次/,
  )
  assert.throws(
    () => checkedStudyInput(study({ fees: [...nine.slice(0, 8), nine[0]] })),
    /同类费用不能重复/,
  )
  const unknown = [...nine.slice(0, 8), fee({ kind: 'custom' })]
  assert.throws(
    () => checkedStudyInput(study({ fees: unknown })),
    /存在未知费用类别/,
  )
})

test('profit fees need a basis once an amount is entered and stay under 100%', () => {
  const nine = newScenario().fees
  const withAmount = (index, overrides) =>
    nine.map((item, position) =>
      position === index ? { ...item, ...overrides } : item,
    )
  assert.throws(
    () =>
      checkedStudyInput(
        study({
          fees: withAmount(0, { kind: 'inbound', value: '2', basis: '' }),
        }),
      ),
    /头程物流已填金额，必须填写 1–300 字的假设依据/,
  )
  assert.throws(
    () =>
      checkedStudyInput(
        study({
          fees: withAmount(1, {
            kind: 'outbound',
            mode: 'percent',
            value: '100.0001',
            basis: '费率',
          }),
        }),
      ),
    /单项售价费率不能超过 100%/,
  )
  const zero = checkedStudyInput(
    study({
      fees: withAmount(2, {
        kind: 'platform',
        value: '0',
        basis: '本期免佣，仍按零假设',
      }),
    }),
  )
  assert.equal(zero.scenarios[0].fees[2].value, '0')
  assert.equal(zero.scenarios[0].fees[2].basis, '本期免佣，仍按零假设')
  const percent = checkedStudyInput(
    study({
      fees: withAmount(3, {
        kind: 'storage',
        mode: 'percent',
        value: '100',
        basis: '上限假设',
      }),
    }),
  )
  assert.equal(percent.scenarios[0].fees[3].value, '100')
})

test('profit fee labels and page size follow the served contract', () => {
  assert.equal(
    feeValue({ kind: 'tax', mode: 'fixed', value: null, basis: '' }),
    '未计入',
  )
  assert.equal(
    feeValue({ kind: 'tax', mode: 'fixed', value: '0.0000', basis: 'x' }),
    '0',
  )
  assert.equal(
    feeValue({ kind: 'tax', mode: 'percent', value: '12.5000', basis: 'x' }),
    '12.5%',
  )
  assert.equal(decimalText('12.5000'), '12.5')
  assert.equal(decimalText(null), '未知')
  assert.equal(studiesPerPage, 50)
  assert.equal(hasMoreStudies(new Array(50).fill({})), true)
  assert.equal(hasMoreStudies(new Array(49).fill({})), false)
})
