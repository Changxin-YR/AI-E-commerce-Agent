import '../../ui/edit_guard.dart';
import '../../ui/business_time_fields.dart';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/api_client.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/finance_inputs.dart';
import 'finance_common.dart';
import 'statements_page.dart';

class SettlementsPage extends StatefulWidget {
  const SettlementsPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<SettlementsPage> createState() => _SettlementsPageState();
}

class _SettlementsPageState extends BusinessPageState<SettlementsPage> {
  late final scope = FinanceScope(widget.app, widget.query);
  final statement = TextEditingController(), note = TextEditingController();
  List<Json> receipts = [], items = [];
  Json? record, preview, draft, pending, current, shownHistory;
  String? pendingPath;
  int? cursor;
  bool confirmed = false, restoring = false;
  bool get locked => busy || pending != null;
  String path(String tail) => widget.app.shopPath('/settlements$tail');
  @override
  void initState() {
    super.initState();
    scope.addListener(scopeChanged);
    statement.addListener(invalidate);
    note.addListener(invalidate);
    Future.microtask(() => perform(() async {
          await load();
          final id = int.tryParse(widget.query['settlement'] ?? '');
          if (id != null) await read(id);
        }));
  }

  void invalidate() {
    if (!restoring && mounted) {
      setState(() {
        preview = null;
        draft = null;
        confirmed = false;
      });
    }
  }

  void scopeChanged() {
    if (restoring || !mounted) return;
    setState(() {
      items = [];
      cursor = null;
    });
    invalidate();
  }

  Future<void> load({bool more = false}) async {
    final value = object(await widget.app.api.get(path(''),
        query: {...scope.partition, if (more) 'before': cursor}));
    if (mounted) {
      setState(() {
        items =
            more ? [...items, ...rows(value['items'])] : rows(value['items']);
        cursor = value['next_cursor'] as int?;
      });
    }
  }

  void restore(Json value) {
    restoring = true;
    record = value;
    preview = null;
    draft = null;
    current = null;
    shownHistory = null;
    confirmed = false;
    final snapshot = object(value['snapshot'] ?? {}),
        content = object(snapshot['content'] ?? {});
    if (snapshot['scope'] != null) scope.restore(object(snapshot['scope']));
    statement.text = '${content['statement_id'] ?? ''}';
    note.text = '${content['note'] ?? ''}';
    receipts = rows(content['receipts']);
    restoring = false;
  }

  Future<void> read(int id) async {
    final value = object(await widget.app.api.get(path('/$id')));
    if (mounted) setState(() => restore(value));
  }

  Future<void> editReceipt([int? index]) async {
    final value = await Navigator.of(context).push<Json>(MaterialPageRoute(
        builder: (_) => ReceiptEditor(
            timezone: scope.zone.text,
            currency: '${widget.app.shop?['currency'] ?? 'USD'}',
            initial: index == null ? null : receipts[index])));
    if (value == null || !mounted) return;
    setState(() {
      if (index == null) {
        receipts.add(value);
      } else {
        receipts[index] = value;
      }
    });
    invalidate();
  }

  Future<void> calculate() => perform(() async {
        final input = {
          'scope': scope.input(),
          'settlement_id': record?['id'],
          'version': record?['version'] ?? 0,
          'content': {
            'statement_id': requiredText(statement.text, '原账单号', 120),
            'note': requiredText(note.text, '结算说明', 1000),
            'receipts':
                receipts.map((e) => Map<String, dynamic>.from(e)).toList()
          }
        };
        final value =
            object(await widget.app.api.post(path('/preview'), input));
        if (mounted) {
          setState(() {
            draft = input;
            preview = value;
            confirmed = false;
          });
        }
      });
  Future<void> send() async {
    try {
      final value = object(await widget.app.api.post(pendingPath!, pending));
      if (!mounted) return;
      setState(() {
        pending = null;
        pendingPath = null;
        restore(value);
      });
      success = '结算记录与到账登记已回读。';
      await load();
    } on ApiFailure catch (e) {
      if (e.status >= 400 && e.status < 500 && e.status != 408) {
        pending = null;
        pendingPath = null;
        if (e.status == 409) {
          preview = null;
          draft = null;
          confirmed = false;
        }
      }
      rethrow;
    }
  }

  Future<void> save() => perform(() async {
        if (pending == null) {
          if (preview == null || draft == null || !confirmed) return;
          pendingPath = path('');
          pending = {
            ...draft!,
            'preview_hash': preview!['preview_hash'],
            'request_id': newRequestId(),
            'confirm': true
          };
        }
        await send();
      });
  Future<void> control(String action) async {
    if (record == null ||
        !await confirmAction(context, action == 'clear' ? '清除结算正文' : '撤销结算记录',
            action == 'clear' ? '清除登记与历史快照的正文及依据，无法恢复。' : '撤销本次人工结算记录，保留历史。')) {
      return;
    }
    await perform(() async {
      pendingPath = path('/${record!['id']}/$action');
      pending = {
        'version': record!['version'],
        'request_id': newRequestId(),
        'confirm': true
      };
      await send();
    });
  }

  @override
  void dispose() {
    scope.dispose();
    statement.dispose();
    note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => EditGuard(
      app: widget.app,
      controllers: [statement, note],
      cleanKey: record,
      stateValue: receipts.toString(),
      busy: busy,
      pending: pending != null,
      child: Scaffold(
          appBar: AppBar(title: const Text('结算回款')),
          body: PageBody(children: [
            ...feedback,
            FinanceScopeFields(scope, enabled: !locked),
            if (record != null) ...[
              FactLine('结算记录',
                  '#${record!['id']} · v${record!['version']} · ${recordStatuses[record!['status']]}'),
              Wrap(spacing: 8, children: [
                OutlinedButton(
                    onPressed: locked
                        ? null
                        : () => perform(() => read(record!['id'] as int)),
                    child: const Text('回读最新存档')),
                OutlinedButton(
                    onPressed: locked
                        ? null
                        : () => perform(() async {
                              final value = object(await widget.app.api
                                  .get(path('/${record!['id']}/current')));
                              if (mounted) {
                                setState(() => current =
                                    value['preview'] == null
                                        ? null
                                        : object(value['preview']));
                              }
                            }),
                    child: const Text('核对当前来源'))
              ]),
              if (record!['snapshot'] != null)
                ExpansionTile(title: const Text('保存时完整依据'), children: [
                  SettlementResultView(widget.app, object(record!['snapshot']))
                ]),
              if (current != null)
                ExpansionTile(title: const Text('当前回读依据'), children: [
                  SettlementResultView(widget.app, object(current!['snapshot']))
                ]),
            ],
            FormInput('原始账单号', statement, enabled: !locked),
            FormInput('结算周期与核查说明', note, lines: 3, enabled: !locked),
            const SectionTitle('卖家人工到账登记'),
            const Text('按平台回款凭据号逐笔关联；人工登记的银行到账仍须核验银行证据。'),
            for (var i = 0; i < receipts.length; i++)
              ExpansionTile(
                  title: Text(
                      '${receipts[i]['receipt_ref']} · ${receipts[i]['amount']} ${receipts[i]['currency']}'),
                  subtitle: Text('回款 ${receipts[i]['payout_ref']}'),
                  children: [
                    ReceiptEvidence(receipts[i]),
                    Wrap(spacing: 8, children: [
                      OutlinedButton(
                          onPressed: locked ? null : () => editReceipt(i),
                          child: const Text('修改登记')),
                      TextButton(
                          onPressed: locked
                              ? null
                              : () {
                                  setState(() => receipts.removeAt(i));
                                  invalidate();
                                },
                          child: const Text('移除本条'))
                    ])
                  ]),
            OutlinedButton(
                onPressed: locked || receipts.length >= 50
                    ? null
                    : () => editReceipt(),
                child: Text('添加到账登记（${receipts.length}/50）')),
            Wrap(spacing: 8, children: [
              FilledButton(
                  onPressed: locked ? null : calculate,
                  child: const Text('预览逐笔回款核对')),
              OutlinedButton(
                  onPressed: locked
                      ? null
                      : () => setState(() {
                            record = null;
                            current = null;
                            shownHistory = null;
                            receipts = [];
                            statement.clear();
                            note.clear();
                            preview = null;
                            draft = null;
                            confirmed = false;
                          }),
                  child: const Text('新建结算记录'))
            ]),
            if (preview != null) ...[
              SettlementResultView(widget.app, object(preview!['snapshot'])),
              CheckboxListTile(
                  value: confirmed,
                  onChanged: locked
                      ? null
                      : (v) => setState(() => confirmed = v ?? false),
                  title: const Text('已核对逐笔关联、币种、金额、跨期项与到账登记依据'))
            ],
            if (pending != null) const Notice('结果待确认，请核对同次保存请求。'),
            FilledButton(
                onPressed:
                    busy || (!confirmed && pending == null) ? null : save,
                child: Text(pending == null ? '保存结算版本' : '核对同次写入')),
            if (record != null && record!['status'] != 'cleared')
              Wrap(spacing: 8, children: [
                OutlinedButton(
                    onPressed: locked ? null : () => control('withdraw'),
                    child: const Text('撤销记录')),
                OutlinedButton(
                    onPressed: locked ? null : () => control('clear'),
                    child: const Text('清除正文'))
              ]),
            if (record != null)
              ExpansionTile(title: const Text('结算版本历史'), children: [
                for (final h in rows(record!['history']))
                  ListTile(
                      title: Text('v${h['version']} · ${h['action']}'),
                      subtitle: Text('${h['created_at']}'),
                      onTap: locked || h['has_content'] != true
                          ? null
                          : () => perform(() async {
                                final value = object(await widget.app.api.get(
                                    path('/${record!['id']}'),
                                    query: {'version': h['version']}));
                                if (mounted) {
                                  setState(() => shownHistory = value);
                                }
                              })),
                if (shownHistory?['snapshot'] != null)
                  SettlementResultView(
                      widget.app, object(shownHistory!['snapshot']))
              ]),
            const SectionTitle('结算存档'),
            OutlinedButton(
                onPressed: locked ? null : () => perform(load),
                child: const Text('刷新记录')),
            FinanceRows(items,
                builder: (e) => ListTile(
                    title: Text('结算 #${e['id']} · v${e['version']}'),
                    subtitle: Text(
                        '${recordStatuses[e['status']]} · ${e['created_at']}'),
                    onTap: locked
                        ? null
                        : () => perform(() => read(e['id'] as int)))),
            if (cursor != null)
              OutlinedButton(
                  onPressed:
                      locked ? null : () => perform(() => load(more: true)),
                  child: const Text('加载更多记录'))
          ])));
}

class ReceiptEditor extends StatefulWidget {
  const ReceiptEditor(
      {super.key,
      required this.timezone,
      required this.currency,
      this.initial});
  final String timezone, currency;
  final Json? initial;
  @override
  State<ReceiptEditor> createState() => _ReceiptEditorState();
}

class _ReceiptEditorState extends State<ReceiptEditor> {
  late final fields = {
    for (final key in [
      'payout_ref',
      'receipt_ref',
      'amount',
      'currency',
      'received_at',
      'timezone',
      'note'
    ])
      key: TextEditingController(
          text:
              '${widget.initial?[key] ?? (key == 'currency' ? widget.currency : key == 'timezone' ? widget.timezone : '')}')
  };
  String? error;
  void save() {
    try {
      final data = {
        'payout_ref': requiredText(fields['payout_ref']!.text, '平台回款凭据号', 120),
        'receipt_ref': requiredText(fields['receipt_ref']!.text, '到账凭据号', 120),
        'amount': decimalInput(fields['amount']!.text, '到账金额', positive: true),
        'currency':
            requiredText(fields['currency']!.text, '币种', 3).toUpperCase(),
        'received_at':
            awareDate(fields['received_at']!.text, '到账时间', required: true),
        'timezone': requiredText(fields['timezone']!.text, '业务时区', 64),
        'note': requiredText(fields['note']!.text, '到账证据说明', 500)
      };
      Navigator.pop(context, data);
    } catch (e) {
      setState(() => error = '$e');
    }
  }

  @override
  void dispose() {
    for (final c in fields.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => EditGuard(
      controllers: fields.values.toList(),
      child: Scaffold(
          appBar: AppBar(title: const Text('人工到账登记')),
          body: PageBody(children: [
            if (error != null) Notice(error!),
            FormInput('平台回款凭据号', fields['payout_ref']!),
            FormInput('到账凭据号', fields['receipt_ref']!),
            DecimalField('到账金额', fields['amount']!, positive: true),
            FormInput('到账币种', fields['currency']!),
            BusinessDateTimeField('到账时间', fields['received_at']!,
                zone: fields['timezone']),
            BusinessZoneField('到账时区', fields['timezone']!),
            FormInput('银行证据来源与核对说明', fields['note']!, lines: 4),
            FilledButton(onPressed: save, child: const Text('采用本条登记'))
          ])));
}

class ReceiptEvidence extends StatelessWidget {
  const ReceiptEvidence(this.value, {super.key});
  final Json value;
  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        FactLine('人工登记凭据', value['receipt_ref']),
        FactLine('对应平台回款', value['payout_ref']),
        FactLine('人工到账金额', '${value['amount']} ${value['currency']}'),
        FactLine('到账时间', '${value['received_at']} · ${value['timezone']}'),
        FactLine('依据', value['note'])
      ]);
}

class SettlementResultView extends StatelessWidget {
  const SettlementResultView(this.app, this.result, {super.key});
  final AppState app;
  final Json result;
  @override
  Widget build(BuildContext context) {
    final content = object(result['content']),
        receipts = rows(content['receipts']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionTitle('原账单 ${content['statement_id']}'),
      FactLine('期间',
          '${object(result['scope'])['start_at']} → ${object(result['scope'])['end_at']}'),
      FactLine('业务时区', object(result['scope'])['timezone']),
      FactLine('来源修订', result['source_revision']),
      FactLine('核对时间', result['calculated_at']),
      FactLine('结算说明', content['note']),
      const Text('覆盖完整性未知 · 期初期末余额未知 · 银行证据待核验'),
      for (final total in rows(result['totals']))
        ListTile(
            title: Text('${total['amount']} ${total['currency']}'),
            subtitle: Text(
                '${total['entry_type'] == 'manual_receipt' ? '人工到账登记' : entryTypes[total['entry_type']]} · ${total['count']} 笔')),
      FactLine('周期外明细编号', (result['outside_cycle_ids'] as List).join('、')),
      const SectionTitle('逐笔回款比较 · 差额为平台减人工'),
      FinanceRows(rows(result['comparisons']),
          builder: (c) => ExpansionTile(
                  title: Text(
                      '${c['payout_ref'] == '' ? '凭据号未知' : c['payout_ref']} · ${comparisonStatuses[c['status']]}'),
                  subtitle: Text('差额：${c['difference'] ?? '无法确定'}'),
                  children: [
                    for (final s in rows(result['statements']).where(
                        (s) => (c['statement_ids'] as List).contains(s['id'])))
                      StatementEvidence(app, s),
                    for (final index in c['receipt_indexes'] as List)
                      ReceiptEvidence(receipts[index as int]),
                  ])),
      ExpansionTile(title: const Text('全部原账单行'), children: [
        FinanceRows(rows(result['statements']),
            builder: (s) => StatementEvidence(app, s))
      ]),
      ExpansionTile(title: const Text('全部人工到账登记'), children: [
        FinanceRows(receipts, builder: (r) => ReceiptEvidence(r))
      ]),
      for (final check in result['checks'] as List) Text('$check')
    ]);
  }
}
