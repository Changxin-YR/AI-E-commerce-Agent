import '../../ui/edit_guard.dart';
import '../../ui/business_time_fields.dart';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/api_client.dart';
import '../../core/business_navigation.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/finance_inputs.dart';
import '../imports/import_repository.dart';
import '../profit/profit_page.dart' show moneyCurrencies;
import '../finance/finance_common.dart' show FinanceRows;

const scheduleLabels = {
  'active': '已启用',
  'paused': '已暂停',
  'revoked': '已撤销',
  'waiting_approval': '等待审批',
  'succeeded': '已完成',
  'blocked': '运行受阻',
  'missed': '错过周期',
  'ready': '等待继续',
  'circuit_open': '读取失败',
  'cancelled': '已取消',
  'daily': '每天',
  'weekly': '每周',
  'monthly': '每月'
};
const scheduleReasons = {
  'conflict': '经营规则已变化，请编辑计划并重新读取规则。',
  'local_check_failed': '运行未完成并已回滚，请核对后恢复。',
  'range_too_large': '数据超过上限，请缩小范围。',
  'too_many_findings': '候选过多，请缩小范围。',
  'invalid_local_date': '报告日期起点在所选时区不存在。'
};

class SchedulesPage extends StatefulWidget {
  const SchedulesPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<SchedulesPage> createState() => _SchedulesPageState();
}

class _SchedulesPageState extends BusinessPageState<SchedulesPage> {
  List<Json> plans = [], history = [];
  Json? status, pending;
  String? pendingPath;
  bool unread = true;
  bool get locked => busy || pending != null;
  String path(String tail) => widget.app.shopPath('/schedules$tail');
  @override
  void initState() {
    super.initState();
    Future.microtask(() => perform(refresh));
  }

  Future<void> refresh() async {
    final values = await Future.wait([
      widget.app.api.get(path('')),
      widget.app.api.get(path('/status')),
      widget.app.api.get(path('/history'), query: {'unread': unread})
    ]);
    if (mounted) {
      setState(() {
        plans = rows(values[0]);
        final target = int.tryParse(widget.query['schedule'] ?? '');
        if (target != null) {
          plans.sort((a, b) => a['id'] == target
              ? -1
              : b['id'] == target
                  ? 1
                  : 0);
        }
        status = object(values[1]);
        history = rows(values[2]);
      });
    }
  }

  Future<void> edit([Json? plan]) async {
    await Navigator.of(context).push<void>(MaterialPageRoute(
        builder: (_) => ScheduleEditor(widget.app, initial: plan)));
    if (mounted) await perform(refresh);
  }

  Future<void> send() async {
    try {
      await widget.app.api.post(pendingPath!, pending);
      pending = null;
      pendingPath = null;
      await refresh();
      success = '计划与运行记录已更新。';
    } on ApiFailure catch (e) {
      if (e.status >= 400 && e.status < 500 && e.status != 408) {
        pending = null;
        pendingPath = null;
      }
      rethrow;
    }
  }

  Future<void> act(Json plan, String action) async {
    if (!await confirmAction(
        context,
        action == 'check'
            ? '立即执行一次'
            : '${{'pause': '暂停', 'resume': '恢复', 'revoke': '撤销'}[action]}计划',
        action == 'check'
            ? '按此计划范围运行本地巡检或保存报表，结果进入运行历史。'
            : '计划 #${plan['id']} · ${object(plan['config'])['name']}，操作后回读当前状态。')) {
      return;
    }
    await perform(() async {
      pendingPath = path('/${plan['id']}${action == 'check' ? '/check' : ''}');
      pending = {
        'version': plan['version'],
        if (action == 'check') 'request_id': newRequestId(),
        if (action != 'check') 'action': action,
        if (action != 'check') 'confirmed': true
      };
      if (action == 'check') unread = false;
      await send();
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('定时运营与通知')),
      body: PageBody(children: [
        ...feedback,
        if (status != null) ...[
          FactLine(
              '自动调度配置',
              status!['worker_enabled'] == true
                  ? '已启用 · 服务运行时约每 30 秒扫描'
                  : '当前服务未启用'),
          const Text('API 服务须保持运行。恢复后只尝试最近一期，超过 24 小时记为错过；暂停期间不补跑。'),
          if (status!['latest_timer'] != null)
            OccurrenceView(widget.app, object(status!['latest_timer']))
          else
            const Text('尚无自动周期记录。'),
          const Text('周期记录用于回查实际运行，其时间不代表服务当前在线。')
        ],
        Wrap(spacing: 8, children: [
          FilledButton(
              onPressed: locked ? null : () => edit(),
              child: const Text('新建计划')),
          OutlinedButton(
              onPressed: busy ? null : () => perform(refresh),
              child: const Text('刷新计划与通知')),
          if (pending != null)
            OutlinedButton(
                onPressed: busy ? null : () => perform(send),
                child: const Text('核对同次操作'))
        ]),
        if (pending != null) const Notice('上次操作结果待确认，请核对同次请求。'),
        const SectionTitle('运行计划'),
        FinanceRows(plans,
            builder: (p) => ExpansionTile(
                    key: ValueKey(p['id']),
                    initiallyExpanded: '${p['id']}' == widget.query['schedule'],
                    title: Text(
                        '${object(p['config'])['name']} · ${scheduleLabels[p['status']] ?? p['status']}'),
                    subtitle: Text(
                        '#${p['id']} · v${p['version']} · 下次 ${p['next_run_at'] == null ? '未安排' : businessTimeText(context, p['next_run_at'], zone: '${object(p['config'])['timezone']}')}'),
                    children: [
                      ScheduleConfigView(object(p['config'])),
                      Wrap(spacing: 8, children: [
                        OutlinedButton(
                            onPressed: locked || p['status'] == 'revoked'
                                ? null
                                : () => edit(p),
                            child: const Text('修改计划')),
                        OutlinedButton(
                            onPressed: locked || p['status'] != 'active'
                                ? null
                                : () => act(p, 'check'),
                            child: const Text('立即执行一次')),
                        OutlinedButton(
                            onPressed: locked || p['status'] != 'active'
                                ? null
                                : () => act(p, 'pause'),
                            child: const Text('暂停')),
                        OutlinedButton(
                            onPressed: locked || p['status'] != 'paused'
                                ? null
                                : () => act(p, 'resume'),
                            child: const Text('恢复')),
                        OutlinedButton(
                            onPressed: locked || p['status'] == 'revoked'
                                ? null
                                : () => act(p, 'revoke'),
                            child: const Text('撤销')),
                      ])
                    ])),
        const SectionTitle('应用内通知与运行历史'),
        SwitchListTile(
            value: unread,
            onChanged: locked
                ? null
                : (v) {
                    setState(() => unread = v);
                    perform(refresh);
                  },
            title: const Text('只看已到通知时间的未读记录')),
        FinanceRows(history,
            builder: (item) => Column(children: [
                  OccurrenceView(widget.app, item),
                  if (item['read_at'] == null)
                    TextButton(
                        onPressed: locked
                            ? null
                            : () => perform(() async {
                                  await widget.app.api.post(
                                      path('/history/${item['id']}/read'));
                                  await refresh();
                                }),
                        child: const Text('标记已读'))
                ])),
        if (history.length >= 50)
          OutlinedButton(
              onPressed: locked
                  ? null
                  : () => perform(() async {
                        final data = rows(await widget.app.api
                            .get(path('/history'), query: {
                          'unread': unread,
                          'before': history.last['id']
                        }));
                        if (mounted) setState(() => history = data);
                      }),
              child: const Text('更早记录')),
      ]));
}

class ScheduleEditor extends StatefulWidget {
  const ScheduleEditor(this.app, {super.key, this.initial});
  final AppState app;
  final Json? initial;
  @override
  State<ScheduleEditor> createState() => _ScheduleEditorState();
}

class _ScheduleEditorState extends BusinessPageState<ScheduleEditor> {
  final fields = {
    for (final key in [
      'name',
      'timezone',
      'local_time',
      'weekday',
      'month_day',
      'lookback_days',
      'currency',
      'max_age_hours',
      'min_quantity',
      'max_margin_percent',
      'quiet_start',
      'quiet_end'
    ])
      key: TextEditingController()
  };
  String task = 'operations',
      frequency = 'daily',
      identity = 'user_import',
      channel = 'generic';
  Set<String> reportCurrencies = {};
  Json? rule, pending, current;
  bool quiet = false, confirmed = false, uncertainEdit = false;
  bool get locked => busy || pending != null || uncertainEdit;
  @override
  void initState() {
    super.initState();
    current = widget.initial;
    restore(widget.initial?['config'] == null
        ? {
            'name': '每日运营检查',
            'timezone': widget.app.shop?['timezone'] ?? 'Asia/Shanghai',
            'local_time': '09:00',
            'weekday': 0,
            'month_day': 1,
            'lookback_days': 7,
            'currency': widget.app.shop?['currency'] ?? 'USD',
            'max_age_hours': 24,
            'min_quantity': 1,
            'max_margin_percent': '20',
            'quiet_start': null,
            'quiet_end': null
          }
        : object(widget.initial!['config']));
    Future.microtask(() => perform(readRule));
  }

  void restore(Json c) {
    for (final key in fields.keys) {
      fields[key]!.text =
          '${c[key] ?? (key == 'quiet_start' ? 22 : key == 'quiet_end' ? 8 : '')}';
    }
    task = '${c['task'] ?? 'operations'}';
    frequency = '${c['frequency'] ?? 'daily'}';
    identity = '${c['data_identity'] ?? 'user_import'}';
    channel = '${c['channel'] ?? 'generic'}';
    quiet = c['quiet_start'] != null;
    reportCurrencies =
        (c['report_currencies'] as List? ?? []).map((e) => '$e').toSet();
    confirmed = false;
    rule = null;
  }

  Future<void> readRule() async {
    confirmed = false;
    rule = null;
    if (task == 'report') {
      channel = 'generic';
      fields['weekday']!.text = '0';
      fields['month_day']!.text = '1';
      return;
    }
    final value = object(await widget.app.api.get(
        widget.app.shopPath('/business-rules'),
        query: {'channel': channel, 'data_identity': identity}));
    if (!mounted) return;
    setState(() {
      rule = value;
      if (value['active'] == true) {
        final v = object(value['values']);
        for (final key in [
          'max_age_hours',
          'min_quantity',
          'max_margin_percent'
        ]) {
          fields[key]!.text = '${v[key]}';
        }
      }
    });
  }

  Json config() {
    if (task == 'operations' && rule == null) {
      throw const FormatException('请先读取当前经营规则。');
    }
    final time = fields['local_time']!.text.trim();
    if (!RegExp(r'^([01]\d|2[0-3]):[0-5]\d$').hasMatch(time)) {
      throw const FormatException('当地运行时间须为 HH:mm。');
    }
    final start = quiet
        ? integerInput(fields['quiet_start']!.text, '免打扰开始小时', 0, 23)
        : null;
    final end = quiet
        ? integerInput(fields['quiet_end']!.text, '免打扰结束小时', 0, 23)
        : null;
    if (quiet && start == end) throw const FormatException('免打扰起止小时不能相同。');
    return {
      'name': requiredText(fields['name']!.text, '计划名称', 80),
      'task': task,
      'report_currencies': reportCurrencies.toList(),
      'timezone': requiredText(fields['timezone']!.text, '运行时区', 64),
      'frequency': frequency,
      'local_time': time,
      'weekday': task == 'report'
          ? 0
          : integerInput(fields['weekday']!.text, '星期（周一为0）', 0, 6),
      'month_day': task == 'report'
          ? 1
          : integerInput(fields['month_day']!.text, '每月日期', 1, 28),
      'lookback_days':
          integerInput(fields['lookback_days']!.text, '回看天数', 1, 365),
      'channel': task == 'report' ? 'generic' : channel,
      'data_identity': identity,
      'currency': requiredText(fields['currency']!.text, '币种', 3).toUpperCase(),
      'rule_revision_id': task == 'report' ? 0 : rule!['version'],
      'max_age_hours':
          integerInput(fields['max_age_hours']!.text, '库存有效小时', 1, 720),
      'min_quantity':
          integerInput(fields['min_quantity']!.text, '最低销量', 1, 1000000),
      'max_margin_percent': marginInput(fields['max_margin_percent']!.text),
      'quiet_start': start,
      'quiet_end': end
    };
  }

  Future<void> save() => perform(() async {
        if (pending == null) {
          if (!confirmed) return;
          final c = config();
          pending = current == null
              ? {'request_id': newRequestId(), 'config': c, 'confirmed': true}
              : {
                  'version': current!['version'],
                  'action': 'edit',
                  'config': c,
                  'confirmed': true
                };
        }
        try {
          await widget.app.api.post(
              widget.app.shopPath(
                  '/schedules${current == null ? '' : '/${current!['id']}'}'),
              pending);
          if (mounted) Navigator.pop(context);
        } on ApiFailure catch (e) {
          if (current != null) {
            uncertainEdit = true;
            pending = null;
          } else if (e.status >= 400 && e.status < 500 && e.status != 408) {
            pending = null;
            confirmed = false;
          }
          rethrow;
        }
      });
  Future<void> reread() => perform(() async {
        final data =
            rows(await widget.app.api.get(widget.app.shopPath('/schedules')));
        final value = data.where((p) => p['id'] == current?['id']).firstOrNull;
        if (value == null) throw const FormatException('未找到当前计划，请返回列表核对。');
        if (mounted) {
          setState(() {
            current = value;
            restore(object(value['config']));
            uncertainEdit = false;
            pending = null;
          });
        }
        await readRule();
      });
  @override
  void dispose() {
    for (final c in fields.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => EditGuard(
      app: widget.app,
      controllers: fields.values.toList(),
      cleanKey: current,
      stateValue:
          '$task:$frequency:$identity:$channel:$quiet:$reportCurrencies',
      busy: busy,
      pending: pending != null,
      child: Scaffold(
          appBar: AppBar(
              title:
                  Text(current == null ? '新建计划' : '修改计划 #${current!['id']}')),
          body: PageBody(children: [
            ...feedback,
            if (uncertainEdit) ...[
              const Notice('请回读当前计划，核对上次修改结果。'),
              OutlinedButton(
                  onPressed: busy ? null : reread,
                  child: const Text('回读计划并替换表单'))
            ],
            Form(
                onChanged: () => setState(() => confirmed = false),
                child: Column(children: [
                  FormInput('计划名称', fields['name']!, enabled: !locked),
                  ChoiceField(
                      '计划内容',
                      task,
                      const {
                        'operations': '运营巡检 · 候选逐次审批',
                        'report': '经营报表 · 按期保存摘要'
                      },
                      locked
                          ? null
                          : (v) {
                              setState(() => task = v);
                              perform(readRule);
                            }),
                  BusinessZoneField('运行时区', fields['timezone']!,
                      enabled: !locked),
                  ChoiceField(
                      '周期',
                      frequency,
                      const {'daily': '每天', 'weekly': '每周', 'monthly': '每月'},
                      locked
                          ? null
                          : (v) => setState(() {
                                frequency = v;
                                confirmed = false;
                              })),
                  FormInput('当地运行时间 HH:mm', fields['local_time']!,
                      enabled: !locked),
                  if (task == 'operations' && frequency == 'weekly')
                    ChoiceField(
                        '星期',
                        fields['weekday']!.text,
                        const {
                          '0': '周一',
                          '1': '周二',
                          '2': '周三',
                          '3': '周四',
                          '4': '周五',
                          '5': '周六',
                          '6': '周日'
                        },
                        locked
                            ? null
                            : (v) => setState(() {
                                  fields['weekday']!.text = v;
                                  confirmed = false;
                                })),
                  if (task == 'operations' && frequency == 'monthly')
                    FormInput('每月日期（1–28）', fields['month_day']!,
                        enabled: !locked),
                  if (task == 'operations')
                    FormInput('订单回看天数（每一天为24小时）', fields['lookback_days']!,
                        enabled: !locked),
                  ChoiceField(
                      '数据身份',
                      identity,
                      importIdentities,
                      locked
                          ? null
                          : (v) {
                              setState(() => identity = v);
                              perform(readRule);
                            }),
                  if (task == 'operations')
                    ChoiceField(
                        '渠道',
                        channel,
                        importChannels,
                        locked
                            ? null
                            : (v) {
                                setState(() => channel = v);
                                perform(readRule);
                              }),
                  FormInput('基础币种', fields['currency']!, enabled: !locked),
                  if (task == 'report') ...[
                    const Text(
                        '日报汇总前一自然日，周报每周一汇总上个完整周，月报每月1日汇总上个自然月，并对比上一期。覆盖全部导入渠道。'),
                    const Text('报表币种：不选时按全部币种分别统计'),
                    Wrap(spacing: 8, children: [
                      for (final c in moneyCurrencies)
                        FilterChip(
                            label: Text(c),
                            selected: reportCurrencies.contains(c),
                            onSelected: locked
                                ? null
                                : (v) => setState(() {
                                      v
                                          ? reportCurrencies.add(c)
                                          : reportCurrencies.remove(c);
                                      confirmed = false;
                                    }))
                    ]),
                  ],
                  if (task == 'operations') ...[
                    FactLine(
                        '绑定经营规则',
                        rule == null
                            ? '尚未读取'
                            : '#${rule!['version']} · ${rule!['active'] == true ? '使用有效阈值' : '可设置本次阈值'}'),
                    OutlinedButton(
                        onPressed: locked ? null : () => perform(readRule),
                        child: const Text('读取当前经营规则'))
                  ],
                  for (final e in const {
                    'max_age_hours': '库存有效小时（1–720）',
                    'min_quantity': '最低销量',
                    'max_margin_percent': '低毛利率上限 %'
                  }.entries)
                    FormInput(e.value, fields[e.key]!,
                        enabled: !locked &&
                            !(task == 'operations' && rule?['active'] == true)),
                  SwitchListTile(
                      value: quiet,
                      onChanged: locked
                          ? null
                          : (v) => setState(() {
                                quiet = v;
                                confirmed = false;
                              }),
                      title: const Text('应用内通知免打扰')),
                  if (quiet) ...[
                    FormInput('免打扰开始小时（0–23）', fields['quiet_start']!,
                        enabled: !locked),
                    FormInput('免打扰结束小时（0–23）', fields['quiet_end']!,
                        enabled: !locked),
                  ],
                  const Text('夏令时重复时刻只运行第一次，不存在的时刻跳过。免打扰推迟通知，执行记录仍可回查。'),
                  CheckboxListTile(
                      value: confirmed,
                      onChanged: locked
                          ? null
                          : (v) => setState(() => confirmed = v ?? false),
                      title: const Text('已核对计划范围、当地运行时间、规则与应用内通知')),
                ])),
            FilledButton(
                onPressed:
                    busy || uncertainEdit || (!confirmed && pending == null)
                        ? null
                        : save,
                child: Text(pending == null ? '保存计划' : '核对同次创建')),
          ])));
}

class ScheduleConfigView extends StatelessWidget {
  const ScheduleConfigView(this.config, {super.key});
  final Json config;
  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        FactLine('内容', config['task'] == 'report' ? '经营报表' : '运营巡检'),
        FactLine('运行时刻',
            '${scheduleLabels[config['frequency']]} ${config['local_time']} · ${config['timezone']}'),
        if (config['frequency'] == 'weekly')
          FactLine(
              '星期',
              [
                '周一',
                '周二',
                '周三',
                '周四',
                '周五',
                '周六',
                '周日'
              ][config['weekday'] as int]),
        if (config['frequency'] == 'monthly')
          FactLine('每月日期', config['month_day']),
        FactLine(
            '身份 / 渠道', '${config['data_identity']} / ${config['channel']}'),
        FactLine(
            '币种',
            config['task'] == 'report'
                ? (config['report_currencies'] as List).join('、')
                : config['currency']),
        FactLine('回看天数', config['lookback_days']),
        FactLine('规则版本', config['rule_revision_id']),
        FactLine('库存有效小时', config['max_age_hours']),
        FactLine('最低销量', config['min_quantity']),
        FactLine('低毛利率上限 %', config['max_margin_percent']),
        FactLine(
            '通知免打扰',
            config['quiet_start'] == null
                ? '关闭'
                : '${config['quiet_start']}:00 → ${config['quiet_end']}:00'),
      ]);
}

class OccurrenceView extends StatelessWidget {
  const OccurrenceView(this.app, this.item, {super.key});
  final AppState app;
  final Json item;
  @override
  Widget build(BuildContext context) => ExpansionTile(
          title: Text(
              '周期 #${item['id']} · ${scheduleLabels[item['status']] ?? item['status']}'),
          subtitle: Text(
              '计划 #${item['schedule_id']} v${item['schedule_version']} · ${item['scheduled_at']}'),
          children: [
            FactLine('触发方式', item['trigger'] == 'manual' ? '手动' : '自动周期'),
            FactLine('创建时间', item['created_at']),
            FactLine('通知时间', item['notify_at']),
            FactLine('已读时间', item['read_at']),
            FactLine('合并周期起点', item['coalesced_from']),
            if (item['reason'] != '')
              FactLine(
                  '运行说明', scheduleReasons[item['reason']] ?? item['reason']),
            if (item['execution_id'] != null)
              OutlinedButton(
                  onPressed: () => openBusinessPath(
                      context, app, '/agent?execution=${item['execution_id']}'),
                  child: const Text('查看运行进度与审批')),
            if (item['report_id'] != null)
              OutlinedButton(
                  onPressed: () => openBusinessPath(
                      context, app, '/overview?report=${item['report_id']}'),
                  child: const Text('查看报表与依据')),
          ]);
}
