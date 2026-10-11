import '../../ui/business_time_fields.dart';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import '../../core/app_state.dart';
import '../../core/business_navigation.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/source_evidence.dart';
import '../imports/import_repository.dart';
import 'operation_task_page.dart';

class OperationsPage extends StatefulWidget {
  const OperationsPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<OperationsPage> createState() => _OperationsPageState();
}

class _OperationsPageState extends BusinessPageState<OperationsPage> {
  late final start = TextEditingController(
      text: widget.query['start_at'] ??
          DateTime.now()
              .toUtc()
              .subtract(const Duration(days: 7))
              .toIso8601String());
  late final end = TextEditingController(
      text: widget.query['end_at'] ?? DateTime.now().toUtc().toIso8601String());
  late final zone = TextEditingController(
      text: widget.query['timezone'] ??
          '${widget.app.shop?['timezone'] ?? 'Asia/Shanghai'}');
  late final currency = TextEditingController(
      text: widget.query['currency'] ??
          '${widget.app.shop?['currency'] ?? 'USD'}');
  final quantity = TextEditingController(text: '1'),
      margin = TextEditingController(text: '20'),
      age = TextEditingController(text: '24');
  late String identity = importIdentities.containsKey(widget.query['identity'])
      ? widget.query['identity']!
      : 'user_import';
  late String channel = importChannels.containsKey(widget.query['channel'])
      ? widget.query['channel']!
      : 'generic';
  Json? rule, preview, run;
  List<Json> history = [], tasks = [];
  int offset = 0;
  bool hasMore = false, scopeDirty = false;
  String? requestId;
  String base(String suffix) => widget.app.shopPath('/operations$suffix');
  @override
  void initState() {
    super.initState();
    for (final c in [start, end, zone, currency, quantity, margin, age]) {
      c.addListener(invalidatePreview);
    }
    load(initial: true);
  }

  @override
  void dispose() {
    for (final c in [start, end, zone, currency, quantity, margin, age]) {
      c.dispose();
    }
    super.dispose();
  }

  void invalidatePreview() {
    if (mounted) {
      setState(() {
        preview = null;
        requestId = null;
        scopeDirty = true;
      });
    }
  }

  Json scope() {
    final from = awareDate(start.text, '开始时间', required: true)!;
    final to = awareDate(end.text, '结束时间', required: true)!;
    final duration = DateTime.parse(to).difference(DateTime.parse(from));
    if (duration <= Duration.zero || duration > const Duration(days: 366)) {
      throw const FormatException('时间窗须为正且不超过 366 天；结束时间不包含在范围内。');
    }
    final minQuantity = int.tryParse(quantity.text);
    final maxAge = int.tryParse(age.text);
    if (minQuantity == null ||
        minQuantity < 1 ||
        maxAge == null ||
        maxAge < 1 ||
        maxAge > 720) {
      throw const FormatException('最少件数须为正整数，库存有效小时数须为 1–720。');
    }
    if (num.tryParse(margin.text) == null) {
      throw const FormatException('请填写有效的低毛利百分比。');
    }
    if (rule == null) throw const FormatException('请先读取当前经营规则。');
    return {
      'start_at': from,
      'end_at': to,
      'timezone': zone.text.trim(),
      'currency': currency.text.trim().toUpperCase(),
      'data_identity': identity,
      'channel': channel,
      'intent': 'low_margin',
      'cost_mode': 'current_estimate',
      'max_age_hours': maxAge,
      'min_quantity': minQuantity,
      'max_margin_percent': margin.text.trim(),
      'rule_revision_id': rule!['version']
    };
  }

  Future<void> readRule() async {
    final value = object(await widget.app.api.get(
        widget.app.shopPath('/business-rules'),
        query: {'channel': channel, 'data_identity': identity}));
    if (!mounted) return;
    rule = value;
    age.text = '${value['values']['max_age_hours']}';
    quantity.text = '${value['values']['min_quantity']}';
    margin.text = '${value['values']['max_margin_percent']}';
  }

  Future<void> readLists() async {
    final loaded = await Future.wait([
      widget.app.api.get(base('/runs'),
          query: {'data_identity': identity, 'channel': channel}),
      widget.app.api.get(base('/tasks'), query: {
        'data_identity': identity,
        'channel': channel,
        'offset': offset
      })
    ]);
    if (!mounted) return;
    history = rows(loaded[0]);
    final page = object(loaded[1]);
    tasks = rows(page['items']);
    hasMore = page['has_more'] == true;
  }

  Future<void> load({bool initial = false, bool reset = false}) =>
      perform(() async {
        if (reset) {
          offset = 0;
          run = null;
          rule = null;
          preview = null;
          requestId = null;
        }
        await readRule();
        await readLists();
        if (!mounted) return;
        final requested =
            initial ? int.tryParse(widget.query['run'] ?? '') : null;
        if (requested != null || run != null) {
          final value = object(await widget.app.api
              .get(base('/runs/${requested ?? run!['id']}')));
          if (mounted) run = value;
        }
      });

  Future<void> previewCheck() => perform(() async {
        final requestedScope = scope();
        final result =
            object(await widget.app.api.post(base('/preview'), requestedScope));
        if (!mounted || !mapEquals(requestedScope, scope())) return;
        if (mounted) {
          preview = result;
          requestId = null;
          scopeDirty = false;
        }
      }, message: '已读取本次检查预览，请核对分支与候选，再保存检查。');

  Future<void> runCheck() async {
    if (preview == null) return;
    if (!await confirmAction(
        context, '保存本次运营检查', '将保存检查结果和候选事项。候选须批准后才成为本地待办。')) {
      return;
    }
    await perform(() async {
      requestId ??= newRequestId();
      final result = object(await widget.app.api.post(base('/runs'), {
        'scope': scope(),
        'request_id': requestId,
        'expected_preview_hash': preview!['preview_hash']
      }));
      if (!mounted) return;
      run = result;
      requestId = null;
      preview = null;
      offset = 0;
      await readLists();
    }, message: '检查已保存，已有事项的处理状态保留。');
  }

  Future<void> inspectRun(int id) => perform(() async {
        final result = object(await widget.app.api.get(base('/runs/$id')));
        if (mounted) run = result;
      });
  Future<void> inspectTask(int id) async {
    await Navigator.push<void>(context,
        MaterialPageRoute(builder: (_) => OperationTaskPage(widget.app, id)));
    if (mounted) await perform(readLists);
  }

  List<Widget> branchWidgets(dynamic branches) => [
        for (final branch in rows(branches))
          Card(
              child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${branch['name']} · ${const {
                              'checked': '已检查',
                              'partial': '部分可核对',
                              'not_checked': '未检查'
                            }[branch['status']] ?? branch['status']}'),
                        FactLine('数量', branch['count']),
                        Text('${branch['reason']}')
                      ])))
      ];

  @override
  Widget build(BuildContext context) {
    final snapshot = run?['snapshot'] == null ? null : object(run!['snapshot']);
    final contextPreview =
        preview?['preview'] == null ? null : object(preview!['preview']);
    return Scaffold(
        appBar: AppBar(title: const Text('今日运营检查'), actions: [
          IconButton(
              tooltip: '刷新记录与规则',
              onPressed: busy ? null : load,
              icon: const Icon(Icons.refresh))
        ]),
        body: PageBody(children: [
          ...feedback,
          FactLine('所属店铺', widget.app.shop?['name']),
          const Text('按明确范围检查已导入数据，查看证据，再批准需要处理的候选。'),
          const SectionTitle('本次检查范围'),
          ChoiceField(
              '数据身份',
              identity,
              importIdentities,
              busy
                  ? null
                  : (v) {
                      setState(() => identity = v);
                      load(reset: true);
                    }),
          ChoiceField(
              '渠道',
              channel,
              importChannels,
              busy
                  ? null
                  : (v) {
                      setState(() => channel = v);
                      load(reset: true);
                    }),
          BusinessDateTimeField('开始时间（包含）', start, zone: zone, enabled: !busy),
          BusinessDateTimeField('结束时间（不含终点）', end, zone: zone, enabled: !busy),
          BusinessZoneField('业务时区', zone, enabled: !busy),
          FormInput('币种', currency, enabled: !busy),
          const Text('时间示例：2026-10-11T09:00:00+08:00；Z 表示 UTC。'),
          const SectionTitle('应用的经营规则'),
          if (rule != null) ...[
            FactLine('规则版本', rule!['version']),
            FactLine('状态', rule!['active'] == true ? '已应用经营规则' : '使用本次手填检查阈值'),
            FactLine('依据', rule!['values']['basis']),
          ] else
            const Notice('经营规则尚未加载，请刷新。'),
          if (rule?['active'] == true) ...[
            FactLine('库存有效期', '${age.text} 小时'),
            FactLine('最少件数', quantity.text),
            FactLine('低毛利阈值', '${margin.text}%'),
          ] else ...[
            FormInput('库存有效小时数', age,
                enabled: !busy, type: TextInputType.number),
            FormInput('最少件数', quantity,
                enabled: !busy, type: TextInputType.number),
            FormInput('低毛利阈值（%）', margin,
                enabled: !busy,
                type: const TextInputType.numberWithOptions(
                    decimal: true, signed: true)),
          ],
          FilledButton(
              onPressed: busy || rule == null ? null : previewCheck,
              child: const Text('预览检查')),
          if (contextPreview != null) ...[
            const SectionTitle('检查预览'),
            FactLine('来源版本', contextPreview['source_revision']),
            FactLine('有效至', contextPreview['valid_until']),
            ...branchWidgets(contextPreview['branches']),
            for (final finding in rows(contextPreview['findings']))
              Card(
                  child: ExpansionTile(
                      title: Text(
                          '${finding['title']} · ${finding['object_label']}'),
                      subtitle: Text('${finding['basis']}'),
                      childrenPadding: const EdgeInsets.all(16),
                      expandedCrossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    FactLine('建议', finding['advice']),
                    FactLine('影响', finding['impact']),
                    for (final fact in object(finding['facts'] ?? {}).entries)
                      FactLine(fact.key, fact.value),
                    for (final source in rows(finding['sources']))
                      SourceEvidence(widget.app, source)
                  ])),
            FilledButton(
                onPressed: busy ? null : runCheck,
                child: Text(requestId == null ? '保存检查与候选' : '核对同次检查结果')),
          ],
          if (run != null) ...[
            const SectionTitle('已保存检查'),
            FactLine('记录 / 时间', '#${run!['id']} / ${run!['created_at']}'),
            FactLine('来源状态',
                sourceLabels[run!['source_status']] ?? run!['source_status']),
            FactLine('有效至', run!['valid_until']),
            FactLine('范围',
                '${run!['scope']['start_at']} — ${run!['scope']['end_at']}'),
            FactLine('币种 / 时区',
                '${run!['scope']['currency']} / ${run!['scope']['timezone']}'),
            if (snapshot == null) const Text('来源正文已清除。'),
            if (snapshot != null) ...[
              FactLine('数据截至', snapshot['data_as_of']),
              FactLine('新增 / 复用候选',
                  '${snapshot['created_candidates']} / ${snapshot['reused_candidates']}'),
              ...branchWidgets(snapshot['branches']),
              for (final id in snapshot['task_ids'] as List)
                OutlinedButton(
                    onPressed: busy ? null : () => inspectTask(id as int),
                    child: Text('查看事项 #$id')),
              ExpansionTile(title: const Text('检查来源'), children: [
                for (final source in rows(snapshot['sources']))
                  SourceEvidence(widget.app, source)
              ])
            ]
          ],
          const SectionTitle('运营待办'),
          if (tasks.isEmpty && !busy) const Text('当前范围没有事项。'),
          for (final task in tasks)
            Card(
                child: ListTile(
                    title: Text('${task['snapshot']?['title'] ?? '来源已清除'}'),
                    subtitle: Text(
                        '#${task['id']} · ${taskLabels[task['status']]} · ${sourceLabels[task['source_status']]}'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: busy ? null : () => inspectTask(task['id'] as int))),
          Wrap(spacing: 12, children: [
            TextButton(
                onPressed: busy || offset == 0
                    ? null
                    : () {
                        offset = (offset - 50).clamp(0, 1000000).toInt();
                        perform(readLists);
                      },
                child: const Text('上一页')),
            TextButton(
                onPressed: busy || !hasMore
                    ? null
                    : () {
                        offset += 50;
                        perform(readLists);
                      },
                child: const Text('下一页')),
          ]),
          const SectionTitle('检查历史'),
          for (final item in history)
            ListTile(
                title: Text('检查 #${item['id']} · ${item['created_at']}'),
                subtitle: Text(
                    '${sourceLabels[item['source_status']] ?? item['source_status']}'),
                trailing: const Icon(Icons.chevron_right),
                onTap: busy ? null : () => inspectRun(item['id'] as int)),
          OutlinedButton(
              onPressed: busy
                  ? null
                  : () => openBusinessPath(context, widget.app, '/agent', {
                        'shop': '${widget.app.shopId}',
                        'identity': identity,
                        'channel': channel,
                        'mode': 'daily_model'
                      }),
              child: const Text('启动 AI 今日运营概览')),
        ]));
  }
}
