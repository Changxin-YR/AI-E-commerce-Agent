import test from 'node:test'
import assert from 'node:assert/strict'
import {
  checkedScheduleConfig,
  createSchedulePayload,
  defaultScheduleForm,
  manualCheckPayload,
  manualCheckReady,
  notificationReady,
  scheduleActionPayload,
  scheduleCycleText,
  scheduleGates,
  scheduleSummary,
} from '../src/services/schedule-policy.ts'

function form(overrides = {}) {
  return { ...defaultScheduleForm('Asia/Shanghai', 'USD'), ...overrides }
}

test('default form produces a valid daily operations plan', () => {
  const config = checkedScheduleConfig(form())
  assert.equal(config.task, 'operations')
  assert.equal(config.frequency, 'daily')
  assert.equal(config.local_time, '09:00')
  assert.equal(config.timezone, 'Asia/Shanghai')
  assert.equal(config.weekday, 0)
  assert.equal(config.month_day, 1)
  assert.equal(config.lookback_days, 7)
  assert.equal(config.rule_revision_id, 0)
  assert.equal(config.max_margin_percent, '20')
  assert.equal(config.quiet_start, null)
  assert.equal(config.quiet_end, null)
  assert.deepEqual(config.report_currencies, [])
})

test('quiet hours must be paired, bounded and different', () => {
  assert.deepEqual(
    [
      checkedScheduleConfig(
        form({ quiet: true, quiet_start: '22', quiet_end: '8' }),
      ).quiet_start,
      checkedScheduleConfig(
        form({ quiet: true, quiet_start: '22', quiet_end: '8' }),
      ).quiet_end,
    ],
    [22, 8],
  )
  assert.throws(
    () =>
      checkedScheduleConfig(
        form({ quiet: true, quiet_start: '8', quiet_end: '8' }),
      ),
    /免打扰起止小时不能相同/,
  )
  assert.throws(
    () =>
      checkedScheduleConfig(
        form({ quiet: true, quiet_start: '24', quiet_end: '8' }),
      ),
    /免打扰开始小时须在 0–23 之间/,
  )
  assert.throws(
    () =>
      checkedScheduleConfig(
        form({ quiet: true, quiet_start: '8', quiet_end: '-1' }),
      ),
    /免打扰结束小时/,
  )
})

test('report plans are normalised to the server rule: Monday, day 1, all channels', () => {
  const config = checkedScheduleConfig(
    form({
      task: 'report',
      frequency: 'weekly',
      weekday: '4',
      month_day: '19',
      channel: 'amazon',
      report_currencies: ['USD', 'CNY', 'USD'],
    }),
  )
  assert.equal(config.task, 'report')
  assert.equal(config.weekday, 0)
  assert.equal(config.month_day, 1)
  assert.equal(config.channel, 'generic')
  assert.equal(config.rule_revision_id, 0)
  assert.deepEqual(config.report_currencies, ['CNY', 'USD'])
  assert.deepEqual(
    checkedScheduleConfig(form({ task: 'report' })).report_currencies,
    [],
  )
  assert.throws(
    () =>
      checkedScheduleConfig(
        form({
          task: 'report',
          report_currencies: [
            'USD',
            'CNY',
            'EUR',
            'GBP',
            'JPY',
            'CAD',
            'AUD',
            'HKD',
            'SGD',
            'CHF',
          ],
        }),
      ),
    /报表币种最多选择 9 个/,
  )
})

test('schedule scope fields refuse impossible values and timezones', () => {
  const cases = [
    [{ name: '  ' }, /计划名称/],
    [{ name: 'x'.repeat(81) }, /计划名称最多 80/],
    [{ timezone: 'Mars/Base' }, /IANA 时区/],
    [{ timezone: '' }, /请填写运行时区/],
    [{ local_time: '24:00' }, /HH:MM/],
    [{ local_time: '9:00' }, /HH:MM/],
    [{ weekday: '7' }, /星期须在 0–6 之间/],
    [{ month_day: '29' }, /每月日期须在 1–28 之间/],
    [{ lookback_days: '0' }, /订单回看天数/],
    [{ max_age_hours: '721' }, /库存有效小时/],
    [{ min_quantity: '0' }, /低毛利最少销量/],
    [{ max_margin_percent: '100.001' }, /最多保留 2 位小数/],
    [{ max_margin_percent: '101' }, /低毛利阈值须在/],
    [{ channel: 'etsy' }, /检查渠道/],
    [{ data_identity: 'live' }, /检查数据身份/],
    [{ currency: '' }, /统计币种/],
    [{ frequency: 'hourly' }, /执行周期/],
    [{ task: 'digest' }, /计划内容/],
  ]
  for (const [override, pattern] of cases)
    assert.throws(
      () => checkedScheduleConfig(form(override)),
      pattern,
      JSON.stringify(override),
    )
})

test('plan gates follow status and manual checks need the current version', () => {
  assert.deepEqual(scheduleGates({ status: 'active' }), {
    pause: true,
    resume: false,
    revoke: true,
    edit: true,
    check: true,
  })
  assert.deepEqual(scheduleGates({ status: 'paused' }), {
    pause: false,
    resume: true,
    revoke: true,
    edit: true,
    check: false,
  })
  assert.deepEqual(scheduleGates({ status: 'revoked' }), {
    pause: false,
    resume: false,
    revoke: false,
    edit: false,
    check: false,
  })
  assert.equal(manualCheckReady({ status: 'active', version: 3 }, 3), true)
  assert.equal(manualCheckReady({ status: 'active', version: 3 }, 4), false)
  assert.equal(manualCheckReady({ status: 'paused', version: 3 }, 3), false)
  assert.equal(manualCheckReady(undefined, 3), false)
})

test('notifications can only be marked read after the notify time', () => {
  const now = Date.parse('2026-10-12T02:00:00Z')
  assert.equal(
    notificationReady(
      { read_at: null, notify_at: '2026-10-12T01:00:00Z' },
      now,
    ),
    true,
  )
  assert.equal(
    notificationReady(
      { read_at: '2026-10-12T01:30:00Z', notify_at: '2026-10-12T01:00:00Z' },
      now,
    ),
    false,
  )
  assert.equal(
    notificationReady(
      { read_at: null, notify_at: '2026-10-13T01:00:00Z' },
      now,
    ),
    false,
  )
  assert.equal(
    notificationReady({ read_at: null, notify_at: 'not-a-date' }, now),
    false,
  )
})

test('write payloads keep the confirmation the server enforces', () => {
  const config = checkedScheduleConfig(form())
  assert.deepEqual(createSchedulePayload('req-1', config, true), {
    request_id: 'req-1',
    config,
    confirmed: true,
  })
  assert.throws(() => createSchedulePayload('', config, true), /缺少请求标识/)
  assert.throws(
    () => createSchedulePayload('req-1', config, false),
    /请确认计划范围/,
  )
  const row = { version: 2 }
  assert.deepEqual(scheduleActionPayload(row, 'pause', undefined, false), {
    version: 2,
    action: 'pause',
    confirmed: false,
  })
  assert.deepEqual(scheduleActionPayload(row, 'edit', config, true), {
    version: 2,
    action: 'edit',
    config,
    confirmed: true,
  })
  assert.throws(
    () => scheduleActionPayload(row, 'resume', undefined, false),
    /恢复计划前/,
  )
  assert.throws(
    () => scheduleActionPayload(row, 'edit', undefined, true),
    /完整计划配置/,
  )
  assert.throws(
    () => scheduleActionPayload({ version: 0 }, 'pause', undefined, false),
    /计划版本无效/,
  )
  assert.deepEqual(manualCheckPayload(row, 'req-2'), {
    request_id: 'req-2',
    version: 2,
  })
  assert.throws(() => manualCheckPayload(row, ''), /缺少请求标识/)
})

test('display helpers keep timezone, currency and quiet hours explicit', () => {
  const config = checkedScheduleConfig(
    form({
      quiet: true,
      quiet_start: '22',
      quiet_end: '8',
      rule_revision_id: 7,
    }),
  )
  assert.match(scheduleSummary(config), /generic/)
  assert.match(scheduleSummary(config), /USD/)
  assert.match(scheduleSummary(config), /规则 #7/)
  assert.match(scheduleSummary(config), /22:00–8:00（Asia\/Shanghai）/)
  assert.match(
    scheduleCycleText(checkedScheduleConfig(form({ frequency: 'weekly' }))),
    /周一/,
  )
  assert.match(
    scheduleCycleText(
      checkedScheduleConfig(form({ frequency: 'monthly', month_day: '15' })),
    ),
    /每月 15 日/,
  )
  assert.match(scheduleCycleText(config), /每天 09:00 Asia\/Shanghai/)
})
