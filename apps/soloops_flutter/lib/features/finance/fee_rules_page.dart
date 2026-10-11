import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/api_client.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/finance_inputs.dart';
import '../../ui/source_evidence.dart';
import 'finance_common.dart';

class FeeRulesPage extends StatefulWidget {
  const FeeRulesPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<FeeRulesPage> createState() => _FeeRulesPageState();
}

class _FeeRulesPageState extends BusinessPageState<FeeRulesPage> {
  late final scope = FinanceScope(widget.app, widget.query);
  final name = TextEditingController(), reason = TextEditingController();
  String category = 'platform';
  List<Json> items = [];
  int? cursor;
  Json? record, preview, draft, pending;
  String? pendingPath;
  bool confirmed = false, restoring = false;
  bool get locked => busy || pending != null;
  String path(String tail) => widget.app.shopPath('/fee-rules$tail');
  @override
  void initState() {
    super.initState();
    scope.addListener(scopeChanged);
    name.addListener(invalidate);
    reason.addListener(invalidate);
    Future.microtask(() => perform(() async {
          await load();
          final id = int.tryParse(widget.query['rule'] ?? '');
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
      record = null;
      items = [];
      cursor = null;
    });
    invalidate();
  }

  Future<void> load({bool more = false}) async {
    final data = object(await widget.app.api.get(path(''),
        query: {...scope.partition, if (more) 'before': cursor}));
    if (mounted) {
      setState(() {
        items = more ? [...items, ...rows(data['items'])] : rows(data['items']);
        cursor = data['next_cursor'] as int?;
      });
    }
  }

  void restore(Json value) {
    restoring = true;
    record = value;
    scope.identity = '${value['data_identity']}';
    scope.channel = '${value['channel']}';
    final content = object(value['content'] ?? {});
    name.text = '${content['fee_name'] ?? ''}';
    reason.text = '${content['reason'] ?? ''}';
    category = '${content['category'] ?? 'platform'}';
    preview = null;
    draft = null;
    confirmed = false;
    restoring = false;
  }

  Future<void> read(int id) async {
    final value = object(await widget.app.api.get(path('/$id')));
    if (mounted) setState(() => restore(value));
  }

  Future<void> calculate() => perform(() async {
        final input = {
          'scope': scope.input(),
          'rule_id': record?['id'],
          'version': record?['version'] ?? 0,
          'content': {
            'fee_name': requiredText(name.text, '账单费用名称', 120),
            'category': category,
            'reason': requiredText(reason.text, '映射依据', 500)
          }
        };
        final value =
            object(await widget.app.api.post(path('/preview'), input));
        if (mounted) {
          setState(() {
            preview = value;
            draft = input;
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
      success = '费用映射记录已回读。';
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
        !await confirmAction(context, action == 'clear' ? '清除映射正文' : '撤销映射规则',
            action == 'clear' ? '清除规则及历史正文，无法恢复。' : '撤销该规则后，账单分类须按当前规则重新核对。')) {
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
    name.dispose();
    reason.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('费用映射规则')),
      body: PageBody(children: [
        ...feedback,
        FinanceScopeFields(scope, enabled: !locked),
        const Text('用账单中的费用名称映射类别。预览只比较所选期间；保存的规则作用于相同身份与渠道。'),
        if (record != null) ...[
          FactLine('当前规则',
              '#${record!['id']} · v${record!['version']} · ${recordStatuses[record!['status']]}'),
          OutlinedButton(
              onPressed: locked
                  ? null
                  : () => perform(() => read(record!['id'] as int)),
              child: const Text('回读最新规则')),
        ],
        FormInput('账单费用名称（按服务端标准化后精确匹配）', name, enabled: !locked),
        ChoiceField(
            '归入类别',
            category,
            expenseCategories,
            locked
                ? null
                : (v) {
                    setState(() => category = v);
                    invalidate();
                  }),
        FormInput('分类与修订依据', reason, lines: 3, enabled: !locked),
        Wrap(spacing: 8, children: [
          FilledButton(
              onPressed: locked ? null : calculate,
              child: const Text('预览映射变化')),
          OutlinedButton(
              onPressed: locked
                  ? null
                  : () {
                      setState(() {
                        record = null;
                        name.clear();
                        reason.clear();
                      });
                      invalidate();
                    },
              child: const Text('新建另一规则')),
        ]),
        if (preview != null) ...[
          const SectionTitle('待确认的分类变化'),
          FactLine('当前来源修订', preview!['source_revision']),
          FactLine('账单行数', preview!['statement_count']),
          FactLine(
              '原规则',
              preview!['previous'] == null
                  ? '无'
                  : feeRuleDescription(object(preview!['previous']))),
          FactLine('拟保存规则', feeRuleDescription(object(preview!['proposed']))),
          FinanceRows(rows(preview!['changes']),
              builder: (change) => ExpansionTile(
                  title: Text(
                      '账单行 #${change['statement_id']} · ${change['fee_name']}'),
                  subtitle: Text(
                      '${mappingDescription(object(change['before']))}\n→ ${mappingDescription(object(change['after']))}'),
                  children: [SourceEvidence(widget.app, object(change['source']))])),
          CheckboxListTile(
              value: confirmed,
              onChanged:
                  locked ? null : (v) => setState(() => confirmed = v ?? false),
              title: const Text('已核对受影响的账单、类别与依据')),
        ],
        if (pending != null) const Notice('写入结果待确认。使用同一请求回查保存结果。'),
        FilledButton(
            onPressed: busy || (!confirmed && pending == null) ? null : save,
            child: Text(pending == null ? '保存已预览规则' : '核对同次写入')),
        if (record != null && record!['status'] != 'cleared')
          Wrap(spacing: 8, children: [
            OutlinedButton(
                onPressed: locked ? null : () => control('withdraw'),
                child: const Text('撤销规则')),
            OutlinedButton(
                onPressed: locked ? null : () => control('clear'),
                child: const Text('清除规则正文')),
          ]),
        if (record != null)
          ExpansionTile(title: const Text('规则版本历史'), children: [
            for (final h in rows(record!['history']))
              ListTile(
                  title: Text(
                      'v${h['version']} · ${h['action']} · ${h['created_at']}'),
                  subtitle: Text(h['content'] == null
                      ? '正文已清除'
                      : feeRuleDescription(object(h['content']))))
          ]),
        const SectionTitle('范围内的规则记录'),
        OutlinedButton(
            onPressed: locked ? null : () => perform(load),
            child: const Text('刷新规则列表')),
        FinanceRows(items,
            builder: (e) => ListTile(
                title: Text(
                    '#${e['id']} ${object(e['content'] ?? {})['fee_name'] ?? '正文已清除'}'),
                subtitle:
                    Text('${recordStatuses[e['status']]} · v${e['version']}'),
                onTap:
                    locked ? null : () => perform(() => read(e['id'] as int)))),
        if (cursor != null)
          OutlinedButton(
              onPressed: locked ? null : () => perform(() => load(more: true)),
              child: const Text('加载更多规则'))
      ]));
}

String feeRuleDescription(Json c) =>
    '${c['fee_name']} → ${expenseCategories[c['category']]}\n${c['reason']}';
String mappingDescription(Json m) =>
    '${mappingStatuses[m['status']] ?? m['status']} · ${expenseCategories[m['category']] ?? '待分类'}'
    '${m['rule_id'] == null ? '' : ' · 规则 #${m['rule_id']} v${m['rule_version']}'}';
