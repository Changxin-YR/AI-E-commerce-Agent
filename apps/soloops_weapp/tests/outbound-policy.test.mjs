import test from 'node:test'
import assert from 'node:assert/strict'
import {
  activeApproval,
  approvalHours,
  createRecipient,
  mailActions,
  mailEdit,
  receiptEvidence,
  receiptId,
  verificationCode,
} from '../src/services/outbound-policy.ts'

const draft = {
  id: 4,
  shop_id: 1,
  channel_id: 1,
  provider: 'resend',
  smtp_message_id: null,
  run_id: 9,
  sender: 'ops@example.com',
  recipient: 'me@example.com',
  subject: '摘要',
  body: '正文',
  content_hash: 'hash',
  status: 'draft',
  source_status: 'current',
  channel_status: 'active',
  version: 2,
  risk: 'R2',
  max_submissions: 1,
  dispatch_at: null,
  receipt_id: null,
  provider_event: '',
  checked_at: null,
  received_at: null,
  receipt_evidence: null,
  created_at: '2026-10-12T00:00:00Z',
  approvals: [],
}

test('outbound drafts allow edit, reject and approve only on an active channel', () => {
  assert.deepEqual(
    { ...mailActions(draft), reconcile: undefined },
    {
      edit: true,
      reject: true,
      approve: true,
      dispatch: false,
      revoke: false,
      reconcile: undefined,
      receipt: false,
    },
  )
  const unavailable = mailActions({
    ...draft,
    channel_status: 'channel_unavailable',
  })
  assert.equal(unavailable.edit, true)
  assert.equal(unavailable.approve, false)
})

test('outbound write actions fail closed on stale, cleared or dispatched records', () => {
  for (const item of [
    { ...draft, source_status: 'stale' },
    { ...draft, source_status: 'cleared' },
    { ...draft, status: 'sending' },
    { ...draft, status: 'accepted' },
    { ...draft, dispatch_at: '2026-10-12T01:00:00Z' },
  ]) {
    const actions = mailActions(item)
    assert.equal(actions.edit, false)
    assert.equal(actions.reject, false)
    assert.equal(actions.approve, false)
    assert.equal(actions.dispatch, false)
  }
})

test('outbound dispatch requires an active approval and revoke follows it', () => {
  const grant = {
    id: 7,
    mode: 'preauthorized',
    status: 'active',
    max_uses: 1,
    used_count: 0,
    expires_at: '2026-10-12T02:00:00Z',
    created_at: '2026-10-12T00:00:00Z',
  }
  const armed = { ...draft, approvals: [grant] }
  assert.equal(activeApproval(armed)?.id, 7)
  assert.equal(mailActions(armed).dispatch, true)
  assert.equal(mailActions(armed).revoke, true)
  assert.equal(mailActions(armed).edit, true)
  assert.equal(
    mailActions({ ...armed, approvals: [{ ...grant, status: 'used' }] })
      .dispatch,
    false,
  )
})

test('receipt requires accepted state or QQ SMTP unknown with a live body', () => {
  assert.equal(mailActions({ ...draft, status: 'accepted' }).receipt, true)
  assert.equal(
    mailActions({ ...draft, provider: 'qq_smtp', status: 'unknown' }).receipt,
    true,
  )
  assert.equal(
    mailActions({ ...draft, provider: 'resend', status: 'unknown' }).receipt,
    false,
  )
  assert.equal(
    mailActions({ ...draft, status: 'accepted', body: null }).receipt,
    false,
  )
  assert.equal(
    mailActions({
      ...draft,
      status: 'accepted',
      source_status: 'cleared',
    }).receipt,
    false,
  )
})

test('outbound input guards bound verification, hours, addresses and text', () => {
  assert.equal(verificationCode(' 12345678 '), '12345678')
  for (const code of ['1234567', '123456789', 'abcdefgh', ''])
    assert.throws(() => verificationCode(code), /8 位数字/)
  assert.equal(approvalHours('24'), 24)
  for (const hours of [0, 25, 1.5, Number.NaN])
    assert.throws(() => approvalHours(hours), /1–24/)
  assert.equal(createRecipient('resend', ''), undefined)
  assert.equal(createRecipient('qq_smtp', ' me@example.com '), 'me@example.com')
  assert.equal(createRecipient('qq_smtp', ''), undefined)
  for (const address of ['bad', 'a@b', 'x'.repeat(250) + '@example.com'])
    assert.throws(() => createRecipient('qq_smtp', address), /收件地址/)
  assert.throws(() => createRecipient('qq_smtp', 'a\nb@example.com'))
})

test('outbound edit flattens the subject line and bounds both fields', () => {
  assert.deepEqual(mailEdit(' 摘要\n第二行 ', ' 正文 '), {
    subject: '摘要 第二行',
    body: '正文',
  })
  for (const value of ['', '   ', 'x'.repeat(201)])
    assert.throws(() => mailEdit(value, '正文'), /邮件主题/)
  for (const value of ['', 'x'.repeat(12001)])
    assert.throws(() => mailEdit('摘要', value), /邮件全文/)
})

test('receipt evidence and channel message ids stay within contract bounds', () => {
  assert.equal(
    receiptEvidence(' 收件人于当日确认收到，可复查 '),
    '收件人于当日确认收到，可复查',
  )
  for (const value of ['短', 'x'.repeat(501)])
    assert.throws(() => receiptEvidence(value), /5–500/)
  assert.equal(receiptId(''), null)
  assert.equal(
    receiptId('3f2504e0-4f89-11d3-9a0c-0305e82c3301'),
    '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
  )
  assert.throws(() => receiptId('not-a-uuid'), /UUID/)
})
