import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/business_navigation.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/source_evidence.dart';

const taskLabels = {
  'pending_approval': '待审批',
  'open': '待处理',
  'deferred': '已延期',
  'completed': '已完成核对',
  'ignored': '已忽略',
  'rejected': '已拒绝',
  'none': '尚未创建'
};
const businessLabels = {
  'pending_review': '待核对',
  'checked_pending': '已核对待外部处理',
  'evidence_recorded': '已登记操作证据',
  'awaiting_source': '待来源更新复检',
  'resolved': '新有效证据支持已解决',
  'still_anomalous': '新来源仍显示异常',
  'ignored': '已忽略或不适用',
  'cleared': '来源已清除'
};
const sourceLabels = {'current': '来源有效', 'stale': '需重新检查', 'cleared': '来源已清除'};
const taskActions = {
  'approve': '批准并创建待办',
  'reject': '拒绝候选',
  'ignore': '忽略此事项',
  'defer': '延期至截止时间',
  'complete': '完成核对',
  'reopen': '重新打开待办',
  'edit': '保存处理记录',
  'record_evidence': '登记操作证据',
  'wait_source': '等待来源更新',
  'recheck': '按原事项复检'
};

String? awareDate(String value, String label, {bool required = false}) {
  if (value.trim().isEmpty) {
    if (required) throw FormatException('请填写$label。');
    return null;
  }
  if (!RegExp(r'(Z|[+-]\d{2}:\d{2})$').hasMatch(value.trim()) ||
      DateTime.tryParse(value.trim()) == null) {
    throw FormatException('$label须包含时区偏移，例如 2026-10-11T09:00:00+08:00。');
  }
  return value.trim();
}

class OperationTaskPage extends StatefulWidget {
  const OperationTaskPage(this.app, this.id, {super.key});
  final AppState app;
  final int id;
  @override
  State<OperationTaskPage> createState() => _OperationTaskPageState();
}

class _OperationTaskPageState extends BusinessPageState<OperationTaskPage> {
  Json? task;
  final note = TextEditingController(), due = TextEditingController();
  final description = TextEditingController(),
      evidenceRef = TextEditingController(),
      occurred = TextEditingController();
  bool confirmed = false;
  String get path => widget.app.shopPath('/operations/tasks/${widget.id}');
  bool get noteDirty =>
      note.text != (task?['note'] ?? '') || due.text != (task?['due_at'] ?? '');
  bool get evidenceDirty =>
      description.text.isNotEmpty ||
      evidenceRef.text.isNotEmpty ||
      occurred.text.isNotEmpty ||
      confirmed;
  @override
  void initState() {
    super.initState();
    note.addListener(changed);
    due.addListener(changed);
    for (final c in [description, evidenceRef, occurred]) {
      c.addListener(evidenceChanged);
    }
    load();
  }

  void changed() {
    if (mounted) setState(() {});
  }

  void evidenceChanged() {
    if (mounted) setState(() => confirmed = false);
  }

  @override
  void dispose() {
    for (final c in [note, due, description, evidenceRef, occurred]) {
      c.dispose();
    }
    super.dispose();
  }

  void clearEvidence() {
    description.clear();
    evidenceRef.clear();
    occurred.clear();
    confirmed = false;
  }

  void adopt(Json value) {
    task = value;
    note.text = '${value['note'] ?? ''}';
    due.text = '${value['due_at'] ?? ''}';
    clearEvidence();
  }

  Future<void> load() => perform(() async {
        final value = object(await widget.app.api.get(path));
        if (mounted) adopt(value);
      });
  Future<void> action(String action) async {
    if (busy || task == null) return;
    if (['approve', 'reject', 'ignore', 'complete', 'reopen']
            .contains(action) &&
        !await confirmAction(
            context,
            taskActions[action]!,
            action == 'complete'
                ? '将保存“已完成核对”状态。业务结果由新有效来源复检确定。'
                : '将更新此事项的本地处理状态，并保留操作历史。')) return;
    await perform(() async {
      final followUp =
          ['record_evidence', 'wait_source', 'recheck'].contains(action);
      final deadline = followUp ? task!['due_at'] : awareDate(due.text, '截止时间');
      if (action == 'defer' &&
          (deadline == null ||
              !DateTime.parse(deadline as String).isAfter(DateTime.now()))) {
        throw const FormatException('延期须设置未来截止时间。');
      }
      Json? evidence;
      if (action == 'record_evidence') {
        if (!confirmed ||
            description.text.trim().isEmpty ||
            evidenceRef.text.trim().isEmpty) {
          throw const FormatException('请补齐证据说明、凭据编号，并确认卖家自报。');
        }
        evidence = {
          'description': description.text.trim(),
          'evidence_ref': evidenceRef.text.trim(),
          'occurred_at': awareDate(occurred.text, '操作发生时间', required: true),
          'confirmed': true
        };
      }
      final result = object(await widget.app.api.post(path, {
        'version': task!['version'],
        'action': action,
        'note': followUp ? task!['note'] : note.text,
        'due_at': deadline,
        if (evidence != null) 'evidence': evidence
      }));
      if (mounted) adopt(result);
    }, message: '事项已更新并回读。');
  }

  List<Widget> reviewWidgets(Json review) {
    final evidence =
        review['evidence'] == null ? null : object(review['evidence']);
    final check = review['recheck'] == null ? null : object(review['recheck']);
    return [
      if (evidence != null) ...[
        FactLine('卖家自报操作', evidence['description']),
        FactLine('依据或凭据编号', evidence['evidence_ref']),
        FactLine('发生时间', evidence['occurred_at']),
        FactLine('登记人 / 登记时间',
            '${evidence['recorded_by']} / ${evidence['recorded_at']}'),
      ],
      if (check != null) ...[
        FactLine('存档复检结论', businessLabels[check['state']] ?? check['state']),
        FactLine('复检原因', check['reason']),
        FactLine('复检时间 / 来源版本',
            '${check['checked_at']} / ${check['source_revision']}'),
        FactLine('有效至', check['valid_until']),
        for (final e in object(check['facts'] ?? {}).entries)
          FactLine(e.key, e.value),
        for (final source in rows(check['sources']))
          SourceEvidence(widget.app, source),
      ],
    ];
  }

  @override
  Widget build(BuildContext context) {
    final t = task;
    final snapshot = t?['snapshot'] == null ? null : object(t!['snapshot']);
    final available = snapshot != null && t!['source_status'] == 'current';
    final followUp = snapshot != null &&
        ['open', 'deferred', 'completed'].contains(t!['status']);
    final allowed = <String>[
      if (t?['status'] == 'pending_approval') ...['approve', 'reject'],
      if (['open', 'deferred'].contains(t?['status'])) ...['complete', 'defer'],
      if (['pending_approval', 'open', 'deferred'].contains(t?['status']))
        'ignore',
      if (['completed', 'ignored', 'rejected', 'deferred']
          .contains(t?['status']))
        'reopen',
      'edit'
    ];
    return Scaffold(
        appBar: AppBar(title: Text('运营事项 #${widget.id}'), actions: [
          IconButton(
              tooltip: '刷新事项',
              onPressed: busy
                  ? null
                  : () async {
                      if ((noteDirty || evidenceDirty) &&
                          !await confirmAction(
                              context, '刷新事项', '未保存的处理记录与证据将丢失。')) return;
                      await load();
                    },
              icon: const Icon(Icons.refresh))
        ]),
        body: PageBody(children: [
          ...feedback,
          if (t == null && !busy)
            OutlinedButton(onPressed: load, child: const Text('重新加载')),
          if (t != null) ...[
            FactLine('处理状态', taskLabels[t['status']]),
            FactLine('原异常来源', sourceLabels[t['source_status']]),
            FactLine('业务进展',
                businessLabels[t['business_state']] ?? t['business_state']),
            FactLine('负责人 / 版本', '${t['owner_id']} / ${t['version']}'),
            const Text('R1 内部操作 · 外部未提交 · 本地操作费用 0'),
            if (snapshot == null) const Notice('来源已清除，证据和处理备注已擦除，仅保留状态历史。'),
            if (snapshot != null) ...[
              const SizedBox(height: 16),
              Text('${snapshot['title']} · ${snapshot['object_label']}',
                  style: Theme.of(context).textTheme.headlineSmall),
              FactLine('依据', snapshot['basis']),
              FactLine('影响', snapshot['impact']),
              FactLine('建议', snapshot['advice']),
              FactLine('证据有效至', snapshot['valid_until']),
              for (final e in object(snapshot['facts'] ?? {}).entries)
                FactLine(e.key, e.value),
              if (!available)
                const Notice('原异常依据已变化或过期，可更新来源后复检；经营规则改变时须重新运行巡检。'),
              if (available && !noteDirty && !evidenceDirty)
                for (final destination in rows(t['destinations']))
                  OutlinedButton(
                      onPressed: busy
                          ? null
                          : () => openBusinessPath(
                              context,
                              widget.app,
                              destination['path'] as String,
                              object(destination['query'])
                                  .map((k, v) => MapEntry(k, '$v'))),
                      child: Text('${destination['label']}')),
              ExpansionTile(title: const Text('原始来源依据'), children: [
                for (final source in rows(snapshot['sources']))
                  SourceEvidence(widget.app, source)
              ]),
              const SectionTitle('处理记录'),
              FormInput('处理备注', note,
                  enabled: !busy, required: false, lines: 3),
              FormInput('截止时间（可选，须含时区偏移）', due,
                  enabled: !busy, required: false),
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final a in allowed)
                  OutlinedButton(
                      onPressed: busy ||
                              evidenceDirty ||
                              (!available &&
                                  !['reject', 'ignore', 'reopen']
                                      .contains(a)) ||
                              (a == 'edit' && !noteDirty)
                          ? null
                          : () => action(a),
                      child: Text(taskActions[a]!))
              ]),
              const SectionTitle('异常业务复核'),
              const Text('完成核对仅保存本地处理状态。复检固定原对象、渠道、身份、规则和范围，读取新导入依据。'),
              if (t['review'] != null) ...[
                if (t['review']['recheck'] != null &&
                    t['review_current'] != true)
                  const Notice('存档结论已因来源、规则变化或时效失效，请更新来源后复检。'),
                ...reviewWidgets(object(t['review'])),
              ],
              if (followUp) ...[
                FormInput('人工操作说明（卖家自报）', description,
                    enabled: !busy, required: false, lines: 3),
                FormInput('操作依据或凭据编号', evidenceRef,
                    enabled: !busy, required: false),
                FormInput('操作发生时间（须含时区偏移）', occurred,
                    enabled: !busy, required: false),
                CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('我确认这是人工自报记录，外部结果仍需有效来源复检'),
                    value: confirmed,
                    onChanged: busy
                        ? null
                        : (v) => setState(() => confirmed = v ?? false)),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  FilledButton(
                      onPressed: busy || noteDirty || !confirmed
                          ? null
                          : () => action('record_evidence'),
                      child: const Text('登记操作证据')),
                  OutlinedButton(
                      onPressed: busy || noteDirty || evidenceDirty
                          ? null
                          : () => action('wait_source'),
                      child: const Text('等待来源更新')),
                  OutlinedButton(
                      onPressed: busy || noteDirty || evidenceDirty
                          ? null
                          : () => action('recheck'),
                      child: const Text('按原事项复检')),
                  if (evidenceDirty)
                    TextButton(
                        onPressed: busy ? null : () => setState(clearEvidence),
                        child: const Text('清空未保存证据')),
                ])
              ] else
                const Text('批准或重新打开事项后，可以登记人工证据并复检。'),
            ],
            const SectionTitle('操作历史（最近 50 条）'),
            for (final event in rows(t['history']))
              Card(
                  child: ExpansionTile(
                      title: Text(
                          '${taskActions[event['action']] ?? event['action']} · v${event['version']}'),
                      subtitle: Text(
                          '${event['created_at']} · ${taskLabels[event['from_status']]} → ${taskLabels[event['to_status']]}'),
                      childrenPadding: const EdgeInsets.all(16),
                      expandedCrossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    FactLine('备注', event['note']),
                    FactLine('截止时间', event['due_at']),
                    if (event['review'] != null)
                      ...reviewWidgets(object(event['review'])),
                  ])),
          ],
        ]));
  }
}
