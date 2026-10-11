import '../../ui/edit_guard.dart';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/api_client.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/finance_inputs.dart';
import 'finance_common.dart';

const reviewOutcomes = {
  'consistent': '所选口径内一致',
  'differences_recorded': '金额差异已说明 · 待跟进',
  'pending': '仍待核对'
};

/// Both review domains expose versioned evidence snapshots; results keep their own business UI.
class ReviewPanel extends StatefulWidget {
  const ReviewPanel(this.app,
      {super.key,
      required this.scope,
      required this.resultBuilder,
      this.initialId,
      this.orders = false});
  final AppState app;
  final Json? scope;
  final int? initialId;
  final bool orders;
  final Widget Function(Json) resultBuilder;
  @override
  State<ReviewPanel> createState() => _ReviewPanelState();
}

class _ReviewPanelState extends BusinessPageState<ReviewPanel> {
  final note = TextEditingController(),
      identity = TextEditingController(text: 'user_import'),
      channel = TextEditingController(text: 'generic');
  String outcome = 'pending';
  Json? record, preview, draft, pending, currentEvidence, historyRecord;
  String? pendingPath;
  List<Json> items = [];
  int? cursor;
  bool confirmed = false, restoring = false;
  bool get locked => busy || pending != null;
  String path(String tail) => widget.app.shopPath(
      '${widget.orders ? '/order-statement-reviews' : '/statement-reviews'}$tail');
  @override
  void initState() {
    super.initState();
    note.addListener(invalidate);
    Future.microtask(() => perform(() async {
          if (widget.initialId != null) await read(widget.initialId!);
          await load();
        }));
  }

  @override
  void didUpdateWidget(covariant ReviewPanel old) {
    super.didUpdateWidget(old);
    if (old.scope != widget.scope) {
      preview = null;
      draft = null;
      confirmed = false;
      if (widget.scope != null) {
        identity.text = '${widget.scope!['data_identity']}';
        channel.text = '${widget.scope!['channel']}';
        items = [];
        cursor = null;
      }
    }
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

  void restore(Json value) {
    restoring = true;
    record = value;
    historyRecord = null;
    currentEvidence = null;
    final conclusion =
        object(object(value['snapshot'] ?? {})['conclusion'] ?? {});
    note.text = '${conclusion['note'] ?? ''}';
    outcome = '${conclusion['outcome'] ?? 'pending'}';
    identity.text = '${value['data_identity']}';
    channel.text = '${value['channel']}';
    preview = null;
    draft = null;
    confirmed = false;
    restoring = false;
  }

  Future<void> read(int id) async {
    final value = object(await widget.app.api.get(path('/$id')));
    if (mounted) setState(() => restore(value));
  }

  Future<void> load({bool more = false}) async {
    final data = object(await widget.app.api.get(path(''), query: {
      'data_identity': identity.text,
      'channel': channel.text,
      if (more) 'before': cursor
    }));
    if (mounted) {
      setState(() {
        items = more ? [...items, ...rows(data['items'])] : rows(data['items']);
        cursor = data['next_cursor'] as int?;
      });
    }
  }

  Future<void> calculate() => perform(() async {
        final selectedScope = widget.scope ??
            (record?['snapshot'] == null
                ? null
                : object(object(record!['snapshot'])['result'])['scope']);
        if (selectedScope == null) {
          throw const FormatException('请先运行核对，或打开一个已有审阅记录。');
        }
        final input = {
          'scope': selectedScope,
          'review_id': record?['id'],
          'version': record?['version'] ?? 0,
          'conclusion': {
            'outcome': outcome,
            'note': requiredText(note.text, '审阅说明', 1000)
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
      success = '审阅记录与证据快照已回读。';
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
        !await confirmAction(context, action == 'clear' ? '清除审阅正文' : '撤销审阅',
            action == 'clear' ? '清除本记录及历史快照正文，无法恢复。' : '撤销人工结论；版本依据仍可回读。')) {
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

  Widget snapshot(Json value) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        FactLine(
            '审阅结论', reviewOutcomes[object(value['conclusion'])['outcome']]),
        FactLine('说明', object(value['conclusion'])['note']),
        for (final blocker in value['blockers'] as List) Notice('$blocker'),
        widget.resultBuilder(object(value['result']))
      ]);
  @override
  void dispose() {
    note.dispose();
    identity.dispose();
    channel.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => EditGuard(
      app: widget.app,
      controllers: [note],
      cleanKey: record,
      stateValue: outcome,
      pending: pending != null,
      busy: busy,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SectionTitle(widget.orders ? '订单核对审阅' : '费用核对审阅'),
        ...feedback,
        if (record != null) ...[
          FactLine('审阅记录',
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
                            setState(() => currentEvidence =
                                value['preview'] == null
                                    ? null
                                    : object(value['preview']));
                          }
                        }),
                child: const Text('用当前来源复核')),
          ]),
          if (record!['snapshot'] != null)
            ExpansionTile(
                title: const Text('保存时的完整证据'),
                children: [snapshot(object(record!['snapshot']))]),
          if (currentEvidence != null)
            ExpansionTile(
                title: const Text('当前来源回读 · 尚未重新确认'),
                children: [snapshot(object(currentEvidence!['snapshot']))]),
        ],
        ChoiceField(
            '结论',
            outcome,
            reviewOutcomes,
            locked
                ? null
                : (v) {
                    setState(() => outcome = v);
                    invalidate();
                  }),
        FormInput('人工审阅说明与差异依据', note, lines: 3, enabled: !locked),
        Wrap(spacing: 8, children: [
          FilledButton(
              onPressed: locked ? null : calculate,
              child: const Text('预览结论与证据')),
          OutlinedButton(
              onPressed: locked
                  ? null
                  : () => setState(() {
                        record = null;
                        preview = null;
                        draft = null;
                        confirmed = false;
                        historyRecord = null;
                        currentEvidence = null;
                      }),
              child: const Text('新建审阅记录')),
        ]),
        if (preview != null) ...[
          snapshot(object(preview!['snapshot'])),
          CheckboxListTile(
              value: confirmed,
              onChanged:
                  locked ? null : (v) => setState(() => confirmed = v ?? false),
              title: const Text('已核对以上金额、来源、差异与待核事项')),
        ],
        if (pending != null) const Notice('写入结果待确认，请核对同次请求。'),
        FilledButton(
            onPressed: busy || (!confirmed && pending == null) ? null : save,
            child: Text(pending == null ? '保存审阅版本' : '核对同次写入')),
        if (record != null && record!['status'] != 'cleared')
          Wrap(spacing: 8, children: [
            OutlinedButton(
                onPressed: locked ? null : () => control('withdraw'),
                child: const Text('撤销审阅')),
            OutlinedButton(
                onPressed: locked ? null : () => control('clear'),
                child: const Text('清除审阅正文')),
          ]),
        if (record != null)
          ExpansionTile(title: const Text('审阅版本历史'), children: [
            for (final h in rows(record!['history']))
              ListTile(
                  title: Text('v${h['version']} · ${h['action']}'),
                  subtitle: Text(
                      '${h['created_at']}\n${h['conclusion'] == null ? '无正文' : object(h['conclusion'])['note']}'),
                  onTap: locked || h['conclusion'] == null
                      ? null
                      : () => perform(() async {
                            final value = object(await widget.app.api.get(
                                path('/${record!['id']}'),
                                query: {'version': h['version']}));
                            if (mounted) setState(() => historyRecord = value);
                          })),
            if (historyRecord?['snapshot'] != null)
              snapshot(object(historyRecord!['snapshot']))
          ]),
        const SectionTitle('已保存的审阅'),
        FactLine('列表范围', '${identity.text} / ${channel.text}'),
        OutlinedButton(
            onPressed: locked ? null : () => perform(load),
            child: const Text('刷新审阅历史')),
        FinanceRows(items,
            builder: (item) => ListTile(
                title: Text('审阅 #${item['id']} · v${item['version']}'),
                subtitle: Text(
                    '${recordStatuses[item['status']]} · ${item['created_at']}'),
                onTap: locked
                    ? null
                    : () => perform(() => read(item['id'] as int)))),
        if (cursor != null)
          OutlinedButton(
              onPressed: locked ? null : () => perform(() => load(more: true)),
              child: const Text('加载更多审阅'))
      ]));
}
