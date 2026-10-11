import '../../ui/edit_guard.dart';
import '../../ui/business_time_fields.dart';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/api_client.dart';
import '../../core/business_navigation.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/finance_inputs.dart';
import '../../ui/source_evidence.dart';
import 'finance_common.dart';

class ExpensesPage extends StatefulWidget {
  const ExpensesPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<ExpensesPage> createState() => _ExpensesPageState();
}

class _ExpensesPageState extends BusinessPageState<ExpensesPage> {
  late final scope = FinanceScope(widget.app, widget.query);
  List<Json> items = [];
  int? cursor;
  Json? summary;
  @override
  void initState() {
    super.initState();
    scope.addListener(changed);
    Future.microtask(() => perform(() async {
          await load();
          final id = int.tryParse(widget.query['expense'] ?? '');
          if (id != null && mounted) await open(id);
        }));
  }

  void changed() {
    if (mounted) {
      setState(() {
        summary = null;
        items = [];
        cursor = null;
      });
    }
  }

  Future<void> load({bool more = false}) async {
    final data = object(await widget.app.api.get(
        widget.app.shopPath('/expenses'),
        query: {...scope.partition, if (more) 'before': cursor}));
    if (mounted) {
      setState(() {
        items = more ? [...items, ...rows(data['items'])] : rows(data['items']);
        cursor = data['next_cursor'] as int?;
      });
    }
  }

  Future<void> open(int? id) async {
    await Navigator.of(context).push<void>(MaterialPageRoute(
        builder: (_) => ExpenseEditor(widget.app,
            partition: scope.partition, expenseId: id)));
    if (mounted) await load();
  }

  @override
  void dispose() {
    scope.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('实际费用')),
      body: PageBody(children: [
        ...feedback,
        FinanceScopeFields(scope, enabled: !busy),
        Wrap(spacing: 8, children: [
          FilledButton(
              onPressed: busy ? null : () => perform(load),
              child: const Text('查询费用')),
          OutlinedButton(
              onPressed: busy ? null : () => perform(() => open(null)),
              child: const Text('录入费用')),
          OutlinedButton(
              onPressed: busy
                  ? null
                  : () => openBusinessPath(context, widget.app, '/fee-rules'),
              child: const Text('费用映射规则')),
          OutlinedButton(
              onPressed: busy
                  ? null
                  : () => perform(() async {
                        final data = object(await widget.app.api.post(
                            widget.app.shopPath('/expenses/summary'),
                            scope.input()));
                        if (mounted) setState(() => summary = data);
                      }),
              child: const Text('按期间汇总'))
        ]),
        if (summary != null) ...[
          const SectionTitle('期间费用 · 按币种分别汇总'),
          FactLine('有效笔数', summary!['included_count']),
          FactLine('来源变化笔数', summary!['stale_count']),
          FactLine('已撤销笔数', summary!['withdrawn_count']),
          for (final check in summary!['checks'] as List) Text('$check'),
          for (final row in rows(summary!['totals']))
            ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(
                    '${row['amount']} ${row['currency']} · ${expenseCategories[row['category']]}'),
                subtitle: Text(
                    '${row['allocation'] == 'shop' ? '店铺未分摊' : '订单行'} · ${row['count']} 笔'))
        ],
        const SectionTitle('费用记录'),
        FinanceRows(items, builder: (e) {
          final content = object(object(e['snapshot'] ?? {})['content'] ?? {});
          return ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('#${e['id']} ${content['label'] ?? '已清除'}'),
              subtitle: Text(
                  '${content['amount'] ?? '—'} ${content['currency'] ?? ''} · ${recordStatuses[e['status']]} · v${e['version']}'),
              onTap: busy ? null : () => perform(() => open(e['id'] as int)));
        }),
        if (cursor != null)
          OutlinedButton(
              onPressed: busy ? null : () => perform(() => load(more: true)),
              child: const Text('加载更多记录'))
      ]));
}

class ExpenseEditor extends StatefulWidget {
  const ExpenseEditor(this.app,
      {super.key, required this.partition, this.expenseId});
  final AppState app;
  final Json partition;
  final int? expenseId;
  @override
  State<ExpenseEditor> createState() => _ExpenseEditorState();
}

class _ExpenseEditorState extends BusinessPageState<ExpenseEditor> {
  final form = GlobalKey<FormState>();
  final fields = {
    for (final key in [
      'label',
      'amount',
      'currency',
      'occurred_at',
      'timezone',
      'evidence_ref',
      'evidence_note',
      'reason'
    ])
      key: TextEditingController()
  };
  final orderQuery = TextEditingController();
  Json? record, selected, pending;
  List<Json> orders = [];
  int? sourceRevision;
  String category = 'shipping', allocation = 'shop';
  String? pendingPath;
  bool confirmed = false;
  bool get locked => busy || pending != null;
  String path(String tail) => widget.app.shopPath('/expenses$tail');
  Json get partition => record == null
      ? widget.partition
      : {
          'data_identity': record!['data_identity'],
          'channel': record!['channel']
        };
  @override
  void initState() {
    super.initState();
    fields['currency']!.text = '${widget.app.shop?['currency'] ?? 'USD'}';
    fields['timezone']!.text =
        '${widget.app.shop?['timezone'] ?? 'Asia/Shanghai'}';
    orderQuery.addListener(unlink);
    if (widget.expenseId != null) Future.microtask(() => perform(read));
  }

  void unlink() {
    if (mounted) {
      setState(() {
        selected = null;
        orders = [];
        sourceRevision = null;
        confirmed = false;
      });
    }
  }

  void restore(Json value) {
    record = value;
    final snapshot = object(value['snapshot'] ?? {}),
        content = object(snapshot['content'] ?? {});
    for (final key in fields.keys) {
      fields[key]!.text = '${content[key] ?? ''}';
    }
    category = '${content['category'] ?? 'shipping'}';
    allocation = '${content['allocation'] ?? 'shop'}';
    orderQuery.text = '${snapshot['order_id'] ?? ''}';
    selected = null;
    orders = [];
    sourceRevision = null;
    confirmed = false;
  }

  Future<void> read() async {
    final id = record?['id'] ?? widget.expenseId;
    if (id == null) return;
    final value = object(await widget.app.api.get(path('/$id')));
    if (mounted) setState(() => restore(value));
  }

  Future<void> findOrders() => perform(() async {
        selected = null;
        confirmed = false;
        final data = object(await widget.app.api.get(path('/orders'), query: {
          ...partition,
          'order_id': requiredText(orderQuery.text, '订单号', 120)
        }));
        if (mounted) {
          setState(() {
            orders = rows(data['items']);
            sourceRevision = data['source_revision'] as int;
          });
        }
      });
  Json content() {
    if (allocation == 'order_line' &&
        (selected == null || sourceRevision == null)) {
      throw const FormatException('请查询并重新选择当前订单行。');
    }
    return {
      'label': requiredText(fields['label']!.text, '费用名称', 100),
      'category': category,
      'amount': decimalInput(fields['amount']!.text, '费用金额', positive: true),
      'currency': requiredText(fields['currency']!.text, '币种', 3).toUpperCase(),
      'occurred_at':
          awareDate(fields['occurred_at']!.text, '发生时间', required: true),
      'timezone': requiredText(fields['timezone']!.text, '业务时区', 64),
      'evidence_ref': requiredText(fields['evidence_ref']!.text, '凭据编号', 120),
      'evidence_note':
          requiredText(fields['evidence_note']!.text, '凭据依据', 1000),
      'reason': requiredText(fields['reason']!.text, '录入或修订原因', 500),
      'allocation': allocation,
      'order_line_id': allocation == 'order_line' ? selected!['id'] : null,
      'expected_source_row_id': allocation == 'order_line'
          ? object(selected!['source'])['row_id']
          : null,
      'expected_source_revision':
          allocation == 'order_line' ? sourceRevision : null
    };
  }

  Future<void> sendPending() async {
    try {
      final value = object(await widget.app.api.post(pendingPath!, pending));
      if (!mounted) return;
      setState(() {
        pending = null;
        pendingPath = null;
        restore(value);
      });
      success = '费用记录已回读。';
    } on ApiFailure catch (e) {
      if (e.status >= 400 && e.status < 500 && e.status != 408) {
        pending = null;
        pendingPath = null;
        confirmed = false;
      }
      rethrow;
    }
  }

  Future<void> save() => perform(() async {
        if (pending != null) {
          await sendPending();
          return;
        }
        if (!form.currentState!.validate() || !confirmed) return;
        final id = record?['id'];
        pendingPath = path(id == null ? '' : '/$id');
        pending = {
          ...partition,
          'version': record?['version'] ?? 0,
          'confirm': true,
          'request_id': newRequestId(),
          'content': content()
        };
        await sendPending();
      });
  Future<void> control(String action) async {
    if (record == null ||
        !await confirmAction(context, action == 'clear' ? '清除费用正文' : '撤销费用',
            action == 'clear' ? '清除该费用及版本历史中的正文，无法恢复。' : '撤销当前费用；历史仍可回读。')) {
      return;
    }
    await perform(() async {
      pendingPath = path('/${record!['id']}/$action');
      pending = {
        'version': record!['version'],
        'request_id': newRequestId(),
        'confirm': true
      };
      await sendPending();
    });
  }

  @override
  void dispose() {
    for (final c in fields.values) {
      c.dispose();
    }
    orderQuery.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => EditGuard(
      app: widget.app,
      controllers: fields.values.toList(),
      cleanKey: record,
      stateValue: '$category:$allocation:${selected?['id']}',
      busy: busy,
      pending: pending != null,
      child: Scaffold(
          appBar: AppBar(
              title: Text(record == null ? '录入费用' : '费用 #${record!['id']}')),
          body: PageBody(children: [
            ...feedback,
            FactLine('数据身份 / 渠道',
                '${partition['data_identity']} / ${partition['channel']}'),
            if (record != null) ...[
              FactLine('状态',
                  '${recordStatuses[record!['status']]} · v${record!['version']}'),
              OutlinedButton(
                  onPressed: locked ? null : () => perform(read),
                  child: const Text('回读最新版本（替换表单）')),
              if (record!['snapshot'] != null)
                ExpenseEvidence(widget.app, object(record!['snapshot'])),
            ],
            if (pending != null) const Notice('上次写入结果待确认，表单已锁定。核对同次请求后再修改。'),
            if (record?['status'] != 'cleared')
              Form(
                  key: form,
                  onChanged: () => setState(() => confirmed = false),
                  child: Column(children: [
                    FormInput('费用名称', fields['label']!, enabled: !locked),
                    ChoiceField(
                        '费用类别',
                        category,
                        expenseCategories,
                        locked
                            ? null
                            : (v) => setState(() {
                                  category = v;
                                  confirmed = false;
                                })),
                    DecimalField('费用总额', fields['amount']!,
                        positive: true, enabled: !locked),
                    FormInput('币种', fields['currency']!, enabled: !locked),
                    BusinessDateTimeField('发生时间', fields['occurred_at']!,
                        zone: fields['timezone'], enabled: !locked),
                    BusinessZoneField('发生时区', fields['timezone']!,
                        enabled: !locked),
                    FormInput('凭据唯一编号', fields['evidence_ref']!,
                        enabled: !locked),
                    FormInput('凭据内容与核查依据', fields['evidence_note']!,
                        lines: 3, enabled: !locked),
                    FormInput('录入或修订原因', fields['reason']!,
                        lines: 2, enabled: !locked),
                    ChoiceField(
                        '费用归属',
                        allocation,
                        const {'shop': '店铺费用 · 未分摊', 'order_line': '整笔归属单一订单行'},
                        locked
                            ? null
                            : (v) {
                                setState(() => allocation = v);
                                unlink();
                              }),
                    if (allocation == 'order_line') ...[
                      FormInput('订单号（精确匹配）', orderQuery, enabled: !locked),
                      OutlinedButton(
                          onPressed: locked ? null : findOrders,
                          child: const Text('查询当前订单行')),
                      FinanceRows(orders,
                          builder: (o) => RadioListTile<int>(
                              value: o['id'] as int,
                              groupValue: selected?['id'] as int?,
                              title: Text(
                                  '${o['order_id']} / ${o['line_id']} · ${o['sku']}'),
                              subtitle:
                                  Text('${o['currency']} · ${o['status']}'),
                              onChanged: locked
                                  ? null
                                  : (_) => setState(() {
                                        selected = o;
                                        confirmed = false;
                                      }))),
                      if (selected != null)
                        SourceEvidence(widget.app, object(selected!['source'])),
                    ],
                    CheckboxListTile(
                        value: confirmed,
                        onChanged: locked
                            ? null
                            : (v) => setState(() => confirmed = v ?? false),
                        title: const Text('已核对凭据、金额和费用归属；此人工记录尚需与账单核对')),
                    FilledButton(
                        onPressed: busy || (!confirmed && pending == null)
                            ? null
                            : save,
                        child: Text(pending == null ? '保存费用版本' : '核对同次写入')),
                  ])),
            if (record != null && record!['status'] != 'cleared')
              Wrap(spacing: 8, children: [
                OutlinedButton(
                    onPressed: locked ? null : () => control('withdraw'),
                    child: const Text('撤销费用')),
                OutlinedButton(
                    onPressed: locked ? null : () => control('clear'),
                    child: const Text('清除正文与依据')),
              ]),
            if (record != null) ...[
              const SectionTitle('版本与依据历史'),
              for (final h in rows(record!['history']))
                ExpansionTile(
                    title: Text('v${h['version']} · ${h['action']}'),
                    subtitle: Text('${h['created_at']}'),
                    children: [
                      if (h['snapshot'] != null)
                        ExpenseEvidence(widget.app, object(h['snapshot']))
                      else
                        const Text('正文已清除')
                    ])
            ]
          ])));
}

class ExpenseEvidence extends StatelessWidget {
  const ExpenseEvidence(this.app, this.snapshot, {super.key});
  final AppState app;
  final Json snapshot;
  @override
  Widget build(BuildContext context) {
    final c = object(snapshot['content']);
    return ExpansionTile(
        title: Text('${c['label']} · ${c['amount']} ${c['currency']}'),
        children: [
          FactLine('费用类别', expenseCategories[c['category']]),
          FactLine('发生时间', '${c['occurred_at']} · ${c['timezone']}'),
          FactLine('凭据编号', c['evidence_ref']),
          FactLine('凭据依据', c['evidence_note']),
          FactLine('修订原因', c['reason']),
          FactLine(
              '归属',
              c['allocation'] == 'shop'
                  ? '店铺未分摊'
                  : '订单 ${snapshot['order_id']} / ${snapshot['line_id']} · ${snapshot['sku']}'),
          FactLine('来源修订', c['expected_source_revision']),
          if (snapshot['source'] != null)
            SourceEvidence(app, object(snapshot['source']))
        ]);
  }
}
