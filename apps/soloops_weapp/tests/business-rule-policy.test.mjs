import test from 'node:test'
import assert from 'node:assert/strict'
import {
  authorizationGate,
  canRevokeGrant,
  checkedAuthorization,
  checkedRuleChange,
  defaultRuleValues,
  dirtyRuleForm,
  grantScopeText,
  revertableUses,
  ruleActionGates,
  ruleForm,
  unknownResult,
} from '../src/services/business-rule-policy.ts'

function form(overrides = {}) {
  return {
    max_age_hours: '24',
    min_quantity: '1',
    max_margin_percent: '20',
    advertising_daily_budget: '',
    currency: 'USD',
    notes: {
      target_site: '',
      warehouse: '',
      logistics: '',
      brand_voice: '',
      support_wording: '',
    },
    basis: '系统初始检查口径',
    ...overrides,
  }
}
function revision(overrides = {}) {
  return { active: true, version: 7, ...overrides }
}
function run(overrides = {}) {
  return {
    id: 12,
    shop_id: 3,
    version: 4,
    template: 'daily',
    status: 'waiting_approval',
    next_node: 'propose_tasks',
    source_status: 'current',
    source_revision: 19,
    input: {
      scope: {
        start_at: '2026-10-05T00:00:00Z',
        end_at: '2026-10-12T00:00:00Z',
        timezone: 'Asia/Shanghai',
        currency: 'USD',
        channel: 'generic',
        data_identity: 'user_import',
        rule_revision_id: 7,
        max_age_hours: 24,
        min_quantity: 1,
        max_margin_percent: '20',
      },
    },
    ...overrides,
  }
}

test('rule save normalises decimals, clears an empty budget and keeps the scope', () => {
  const change = checkedRuleChange({
    channel: 'shopify',
    data_identity: 'synthetic',
    expected_version: 0,
    action: 'save',
    form: form({
      advertising_daily_budget: '12.5',
      max_margin_percent: '-3.25',
    }),
  })
  assert.equal(change.action, 'save')
  assert.equal(change.channel, 'shopify')
  assert.equal(change.expected_version, 0)
  assert.equal(change.values.advertising_daily_budget, '12.5')
  assert.equal(change.values.max_margin_percent, '-3.25')
  assert.equal(change.values.max_age_hours, 24)
  assert.equal(change.values.automation, 'manual_only')
  assert.equal(
    checkedRuleChange({
      channel: 'generic',
      data_identity: 'user_import',
      expected_version: 3,
      action: 'save',
      form: form(),
    }).values.advertising_daily_budget,
    null,
  )
})

test('rule save refuses invalid numbers, blank basis and oversized notes', () => {
  const cases = [
    { max_age_hours: '0' },
    { max_age_hours: '721' },
    { max_age_hours: '1.5' },
    { min_quantity: '1000001' },
    { max_margin_percent: 'abc' },
    { max_margin_percent: '100.001' },
    { max_margin_percent: '101' },
    { max_margin_percent: '-1000.5' },
    { advertising_daily_budget: '-1' },
    { advertising_daily_budget: '0.00001' },
    { basis: '   ' },
    { basis: 'x'.repeat(501) },
    { currency: '' },
  ]
  for (const override of cases)
    assert.throws(
      () =>
        checkedRuleChange({
          channel: 'generic',
          data_identity: 'user_import',
          expected_version: 0,
          action: 'save',
          form: form(override),
        }),
      Error,
      JSON.stringify(override),
    )
  assert.throws(
    () =>
      checkedRuleChange({
        channel: 'generic',
        data_identity: 'user_import',
        expected_version: 0,
        action: 'save',
        form: form({
          notes: {
            target_site: 'x'.repeat(201),
            warehouse: '',
            logistics: '',
            brand_voice: '',
            support_wording: '',
          },
        }),
      }),
    /目标站点最多 200 个字符/,
  )
})

test('rule actions follow the action contract and never carry stray values', () => {
  assert.deepEqual(
    checkedRuleChange({
      channel: 'amazon',
      data_identity: 'user_import',
      expected_version: 9,
      action: 'revoke',
      form: form(),
    }),
    {
      channel: 'amazon',
      data_identity: 'user_import',
      expected_version: 9,
      action: 'revoke',
    },
  )
  assert.throws(
    () =>
      checkedRuleChange({
        channel: 'generic',
        data_identity: 'user_import',
        expected_version: 0,
        action: 'save',
      }),
    /请先填写完整规则/,
  )
  assert.throws(
    () =>
      checkedRuleChange({
        channel: 'generic',
        data_identity: 'user_import',
        expected_version: 0,
        action: 'restore',
      }),
    /请选择要恢复的历史版本/,
  )
  assert.throws(
    () =>
      checkedRuleChange({
        channel: 'generic',
        data_identity: 'user_import',
        expected_version: -1,
        action: 'reset',
      }),
    /当前规则版本无效/,
  )
  assert.deepEqual(
    checkedRuleChange({
      channel: 'generic',
      data_identity: 'synthetic',
      expected_version: 4,
      action: 'restore',
      restore_version: 2,
    }),
    {
      channel: 'generic',
      data_identity: 'synthetic',
      expected_version: 4,
      action: 'restore',
      restore_version: 2,
    },
  )
})

test('rule gates only offer revoke and restore on an active revision', () => {
  assert.deepEqual(ruleActionGates(revision()), {
    save: true,
    revoke: true,
    reset: true,
    restore: true,
  })
  assert.deepEqual(ruleActionGates(revision({ active: false })), {
    save: true,
    revoke: false,
    reset: true,
    restore: false,
  })
  assert.deepEqual(ruleActionGates(revision({ version: 0, active: false })), {
    save: true,
    revoke: false,
    reset: true,
    restore: false,
  })
})

test('rule form dirtiness compares the exact editable payload', () => {
  const values = defaultRuleValues()
  assert.equal(dirtyRuleForm(ruleForm(values), values), false)
  assert.equal(
    dirtyRuleForm(ruleForm(values), { ...values, max_margin_percent: '25' }),
    true,
  )
})

test('authorization gate lists every precondition the server re-checks', () => {
  assert.deepEqual(authorizationGate(run()), [])
  assert.match(authorizationGate(undefined).join(' '), /先读取并核对/)
  assert.match(
    authorizationGate(run({ template: 'margin_review' })).join(' '),
    /日常巡检/,
  )
  assert.match(
    authorizationGate(run({ status: 'running' })).join(' '),
    /待审批状态/,
  )
  assert.match(
    authorizationGate(run({ next_node: 'verify' })).join(' '),
    /候选审批/,
  )
  assert.match(
    authorizationGate(run({ source_status: 'stale' })).join(' '),
    /来源已变化/,
  )
  assert.match(
    authorizationGate(run({ input: null })).join(' '),
    /缺少已审范围/,
  )
})

test('authorization payload uses the verified run version and bounded numbers', () => {
  const payload = checkedAuthorization(
    { execution_id: '12', max_uses: '3', valid_hours: '24' },
    'req-1',
    run(),
  )
  assert.deepEqual(payload, {
    request_id: 'req-1',
    execution_id: 12,
    expected_version: 4,
    max_uses: 3,
    valid_hours: 24,
    confirmed: true,
  })
  for (const invalid of [
    { execution_id: '13', max_uses: '3', valid_hours: '24' },
    { execution_id: '12', max_uses: '0', valid_hours: '24' },
    { execution_id: '12', max_uses: '21', valid_hours: '24' },
    { execution_id: '12', max_uses: '3', valid_hours: '0' },
    { execution_id: '12', max_uses: '3', valid_hours: '169' },
    { execution_id: '12', max_uses: '3.5', valid_hours: '24' },
  ])
    assert.throws(
      () => checkedAuthorization(invalid, 'req-1', run()),
      Error,
      JSON.stringify(invalid),
    )
  assert.throws(
    () =>
      checkedAuthorization(
        { execution_id: '12', max_uses: '1', valid_hours: '1' },
        '',
        run(),
      ),
    /缺少请求标识/,
  )
  assert.throws(
    () =>
      checkedAuthorization(
        { execution_id: '12', max_uses: '1', valid_hours: '1' },
        'req-1',
        run({ status: 'waiting_approval', source_status: 'stale' }),
      ),
    /来源已变化/,
  )
})

test('grant actions only offer what the server can still act on', () => {
  assert.equal(canRevokeGrant({ status: 'active' }), true)
  for (const status of [
    'revoked',
    'expired',
    'exhausted',
    'source_changed',
    'rules_changed',
  ])
    assert.equal(canRevokeGrant({ status }), false)
  const uses = revertableUses({
    uses: [
      { id: 1, changes: [{ task_id: 5 }], reverted_at: null },
      { id: 2, changes: [{ task_id: 6 }], reverted_at: '2026-10-12T00:00:00Z' },
      { id: 3, changes: [], reverted_at: null },
    ],
  })
  assert.deepEqual(
    uses.map((use) => use.id),
    [1],
  )
})

test('unknown results keep the request id while context switches do not', () => {
  assert.equal(unknownResult({ status: 0, code: 'network_error' }), true)
  assert.equal(unknownResult({ status: 0, code: 'stale_response' }), false)
  assert.equal(unknownResult({ status: 0, code: 'session_expired' }), false)
  assert.equal(unknownResult({ status: 409 }), false)
  assert.equal(unknownResult(new Error('boom')), false)
  assert.equal(unknownResult(null), false)
})

test('grant scope text exposes money, timezone and rule revision', () => {
  const text = grantScopeText(run().input.scope)
  assert.match(text, /Asia\/Shanghai/)
  assert.match(text, /USD/)
  assert.match(text, /规则 #7/)
  assert.match(text, /毛利 ≤20%/)
})
