import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/edit_guard.dart';
import 'import_repository.dart';

class ImportBatchPage extends StatefulWidget {
  const ImportBatchPage(this.app, this.batchId, {super.key});
  final AppState app;
  final int batchId;
  @override
  State<ImportBatchPage> createState() => _ImportBatchPageState();
}

class _ImportBatchPageState extends BusinessPageState<ImportBatchPage> {
  late final repository = ImportRepository(widget.app.api, widget.app.shopId!);
  Json? batch, catalog;
  Json mapping = {}, corrections = {};
  List<Json> templates = [];
  final reviewed = <String>{};
  bool dirty = false, allowUpdates = false, errorsOnly = false;
  int page = 0, revision = 0;
  final templateName = TextEditingController();
  bool get editable => ['draft', 'preview'].contains(batch?['status']);
  List<Json> get fields => rows(catalog?[batch?['kind']]);
  bool get canCommit =>
      batch?['status'] == 'preview' &&
      !dirty &&
      (batch!['errors'] as List).isEmpty &&
      batch!['error_rows'] == 0 &&
      rows(batch!['required_reviews'])
          .every((r) => reviewed.contains(r['field'])) &&
      (batch!['updated_rows'] == 0 || allowUpdates);

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    templateName.dispose();
    super.dispose();
  }

  void adopt(Json value) {
    batch = value;
    mapping = object(value['mapping']);
    corrections = {
      for (final row in rows(value['rows']))
        '${row['row_number']}': object(row['corrections'])
    };
    reviewed.clear();
    dirty = false;
    allowUpdates = false;
    page = 0;
    revision++;
  }

  Future<void> load() => perform(() async {
        final results = await Future.wait([
          repository.batch(widget.batchId),
          repository.catalog(),
          repository.templates()
        ]);
        if (!mounted) return;
        adopt(object(results[0]));
        catalog = object(results[1]);
        templates = rows(results[2]);
      });

  void markDirty() {
    dirty = true;
    allowUpdates = false;
    reviewed.clear();
  }

  void applyMapping(Json candidate) => setState(() {
        mapping = Map.fromEntries(candidate.entries
            .where((e) => (batch!['headers'] as List).contains(e.value)));
        corrections = {};
        revision++;
        markDirty();
      });

  Future<void> preview() => perform(() async {
        final result = await repository.preview(batch!, mapping, corrections);
        if (mounted) adopt(result);
      }, message: '预览已更新，请核对结果和关键字段含义。');

  Future<void> commit() async {
    if (!canCommit) return;
    if (!await confirmAction(context, '确认导入',
        '本次新增 ${batch!['new_rows']} 行，更新 ${batch!['updated_rows']} 行。确认后写入当前店铺业务记录。')) {
      return;
    }
    await perform(() async {
      final result = await repository.commit(batch!, allowUpdates, reviewed);
      if (mounted) adopt(result);
    }, message: '批次已导入，可继续核对源行与转换结果。');
  }

  Future<void> withdraw(String action) async {
    final clear = action == 'clear';
    if (!await confirmAction(
        context,
        clear ? '清除批次' : '撤销批次',
        clear
            ? '将撤销本批次影响并清除源行资料；操作后无法恢复本批次的原始明细。'
            : '将撤销本批次及其衍生来源，按剩余有效批次恢复业务版本。')) {
      return;
    }
    await perform(() async {
      final result = await repository.withdraw(batch!, action);
      if (mounted) adopt(result);
    }, message: '批次状态已更新，业务记录已按剩余来源重新确定。');
  }

  Future<void> exportErrors({bool share = false}) => perform(() async {
        final bytes = await widget.app.api.send(
            'GET', '/imports/${widget.batchId}/errors.csv',
            rawResponse: true) as Uint8List;
        final name = 'import-${widget.batchId}-errors.csv';
        if (share) {
          await widget.app.device.shareFile(name, bytes);
        } else {
          final saved = await widget.app.device.saveFile(name, bytes);
          if (mounted) success = saved ? '错误报告已保存。' : '已取消保存。';
        }
      });

  Future<void> editRow(Json row) async {
    final result = await Navigator.push<Json>(
        context,
        MaterialPageRoute(
            builder: (_) => ImportRowEditor(
                row, fields, object(corrections['${row['row_number']}'] ?? {}),
                mapping: mapping, app: widget.app)));
    if (result != null && mounted) {
      setState(() {
        corrections['${row['row_number']}'] = result;
        markDirty();
      });
    }
  }

  Widget sourceRow(Json row) {
    final raw = object(row['raw']);
    final normalized = object(row['normalized']);
    final previous = row['previous'] == null ? null : object(row['previous']);
    final rowCorrections = object(corrections['${row['row_number']}'] ?? {});
    return Card(
        child: ExpansionTile(
      key: ValueKey('${batch!['id']}:$revision:${row['row_number']}'),
      title: Text(
          '源行 ${row['row_number']} · ${rowActions[row['action']] ?? row['action']}'),
      subtitle: Text(
          '${normalized['message_id'] ?? normalized['sku'] ?? normalized['order_id'] ?? '标识待补充'}'),
      childrenPadding: const EdgeInsets.all(16),
      expandedCrossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final issue in rows(row['errors']))
          Notice('${issue['field']}：${issue['message']}'),
        for (final warning in (row['warnings'] as List)) Text('$warning'),
        for (final field in fields) ...[
          Text('${field['label']}',
              style: Theme.of(context).textTheme.titleSmall),
          FactLine('源值', raw[mapping[field['key']]]),
          if (rowCorrections.containsKey(field['key']))
            FactLine('修正值', rowCorrections[field['key']]),
          FactLine('转换后', normalized[field['key']]),
          if (previous != null) FactLine('当前旧值', previous[field['key']]),
          const Divider(),
        ],
        if (editable)
          OutlinedButton.icon(
              onPressed: busy ? null : () => editRow(row),
              icon: const Icon(Icons.edit_outlined),
              label: const Text('修正此行')),
      ],
    ));
  }

  @override
  Widget build(BuildContext context) {
    final b = batch;
    final filtered = rows(b?['rows'])
        .where((r) => !errorsOnly || (r['errors'] as List).isNotEmpty)
        .toList();
    final pages = (filtered.length / 20).ceil().clamp(1, 100000);
    final suitable = templates
        .where((t) =>
            t['kind'] == b?['kind'] &&
            t['source_channel'] == b?['source_channel'])
        .toList();
    return Scaffold(
        appBar: AppBar(title: Text('导入批次 #${widget.batchId}'), actions: [
          IconButton(
              tooltip: '刷新批次',
              onPressed: busy
                  ? null
                  : () async {
                      if (dirty &&
                          !await confirmAction(
                              context, '重新读取批次', '当前未预览的修改会丢失。')) {
                        return;
                      }
                      await load();
                    },
              icon: const Icon(Icons.refresh))
        ]),
        body: PageBody(children: [
          ...feedback,
          if (b == null && !busy)
            OutlinedButton(onPressed: load, child: const Text('重新加载')),
          if (b != null) ...[
            Text('${b['filename']}',
                style: Theme.of(context).textTheme.headlineSmall),
            FactLine('状态', batchStatuses[b['status']] ?? b['status']),
            FactLine('来源',
                '${importKinds[b['kind']]} · ${importChannels[b['source_channel']]} · ${importIdentities[b['data_identity']]}'),
            FactLine('归属店铺 / 批次版本', '${b['shop_id']} / ${b['version']}'),
            if (b['group_id'] != null)
              FactLine('导入组 / 分片', '${b['group_id']} / ${b['group_part']}'),
            FactLine('文件时区', b['timezone']),
            FactLine('来源导出时间', b['exported_at']),
            FactLine('源记录覆盖',
                '${b['coverage_start'] ?? '未知'} — ${b['coverage_end'] ?? '未知'}'),
            FactLine('暂存过期时间（UTC）', b['expires_at']),
            FactLine('币种', (b['currencies'] as List).join(' / ')),
            Text(
                '总计 ${b['total_rows']} · 有效 ${b['valid_rows']} · 错误 ${b['error_rows']}\n'
                '新增 ${b['new_rows']} · 更新 ${b['updated_rows']} · 相同 ${b['unchanged_rows']} · 重复 ${b['duplicate_rows'] ?? 0}'),
            for (final issue in (b['errors'] as List)) Notice('$issue'),
            if (b['suggested_kind'] != b['kind'])
              Notice('文件疑似 ${importKinds[b['suggested_kind']]}，请核对所选报表类型。'),
            if (editable) ...[
              const SectionTitle('字段映射'),
              const Text('逐项核对源列与业务含义。金额保持原精度，缺失字段会在预览中提示。'),
              for (final preset in rows(b['presets']))
                Card(
                    child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('${preset['name']}',
                                  style:
                                      Theme.of(context).textTheme.titleMedium),
                              for (final note in (preset['notes'] as List))
                                Text('$note'),
                              FactLine('核验日期', preset['verified_on']),
                              FactLine('参考来源', preset['reference_url']),
                              TextButton(
                                  onPressed: busy
                                      ? null
                                      : () => applyMapping(
                                          object(preset['mapping'])),
                                  child: const Text('使用候选映射'))
                            ]))),
              if (suitable.isNotEmpty)
                ChoiceField(
                    '使用个人模板',
                    null,
                    {for (final t in suitable) '${t['id']}': '${t['name']}'},
                    busy
                        ? null
                        : (id) => applyMapping(object(suitable.firstWhere(
                            (t) => '${t['id']}' == id)['mapping']))),
              for (final field in fields) ...[
                ChoiceField(
                    '${field['label']}${field['required'] == true ? ' *' : ''}',
                    '${mapping[field['key']] ?? ''}',
                    {
                      '': '不映射',
                      for (final h in b['headers'] as List) '$h': '$h'
                    },
                    busy
                        ? null
                        : (v) => setState(() {
                              mapping[field['key'] as String] = v;
                              corrections = {};
                              revision++;
                              markDirty();
                            }),
                    help: '${field['data_type']} · ${field['help']}'),
                if (mapping[field['key']] != null &&
                    mapping[field['key']] != '')
                  FactLine('原始示例', b['examples'][mapping[field['key']]]),
                for (final suggestion in rows(b['suggestions']).where((s) =>
                    s['field'] == field['key'] &&
                    s['column'] == mapping[field['key']]))
                  Text(suggestion['confidence'] == 'exact'
                      ? '标准字段匹配'
                      : '别名候选，请核对口径'),
                const SizedBox(height: 12),
              ],
              FormInput('个人映射模板名称', templateName,
                  enabled: !busy, required: false),
              OutlinedButton(
                  onPressed: busy
                      ? null
                      : () => perform(() async {
                            if (templateName.text.trim().isEmpty) {
                              throw const FormatException('请填写模板名称。');
                            }
                            await repository.saveMapping(
                                b, templateName.text.trim(), mapping);
                            templates = await repository.templates();
                          }, message: '个人映射模板已保存；每次导入仍须核对字段含义。'),
                  child: const Text('保存映射模板')),
              const SizedBox(height: 12),
              FilledButton(
                  onPressed: busy ? null : preview,
                  child: Text(dirty ? '重新校验预览' : '校验并预览')),
            ],
            const SectionTitle('源行与转换结果'),
            CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('只看错误行'),
                value: errorsOnly,
                onChanged: (v) => setState(() {
                      errorsOnly = v ?? false;
                      page = 0;
                    })),
            if (filtered.isEmpty) const Text('当前筛选没有源行。'),
            for (final row in filtered.skip(page * 20).take(20)) sourceRow(row),
            if (filtered.isNotEmpty)
              Wrap(
                  spacing: 12,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    TextButton(
                        onPressed:
                            page > 0 ? () => setState(() => page--) : null,
                        child: const Text('上一页')),
                    Text('第 ${page + 1} / $pages 页'),
                    TextButton(
                        onPressed: page + 1 < pages
                            ? () => setState(() => page++)
                            : null,
                        child: const Text('下一页'))
                  ]),
            if (editable) ...[
              const SectionTitle('核对后确认'),
              if (dirty) const Notice('映射或修正值已变化，请重新预览后再确认。'),
              if (rows(b['required_reviews']).isNotEmpty)
                const Text('按原报表说明核对金额和稳定标识。整单退款不能直接当作行退款。'),
              for (final review in rows(b['required_reviews']))
                CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text('${review['column']} → ${review['label']}'),
                    subtitle: Text('${review['meaning']}'),
                    value: reviewed.contains(review['field']),
                    onChanged: busy || dirty
                        ? null
                        : (v) => setState(() {
                              if (v == true) {
                                reviewed.add(review['field'] as String);
                              } else {
                                reviewed.remove(review['field']);
                              }
                            })),
              if (b['updated_rows'] != 0)
                CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text('允许更新 ${b['updated_rows']} 条现有记录'),
                    subtitle: const Text('请在源行明细中比较转换后与当前旧值。'),
                    value: allowUpdates,
                    onChanged: busy || dirty
                        ? null
                        : (v) => setState(() => allowUpdates = v ?? false)),
              FilledButton(
                  onPressed: busy || !canCommit ? null : commit,
                  child: const Text('确认导入')),
            ],
            const SizedBox(height: 16),
            Wrap(spacing: 8, runSpacing: 8, children: [
              OutlinedButton(
                  onPressed: busy ? null : exportErrors,
                  child: const Text('保存错误报告')),
              OutlinedButton(
                  onPressed: busy ? null : () => exportErrors(share: true),
                  child: const Text('分享错误报告')),
              if (!['revoked', 'cleared', 'expired'].contains(b['status']))
                OutlinedButton(
                    onPressed: busy ? null : () => withdraw('revoke'),
                    child: const Text('撤销批次')),
              if (b['status'] != 'cleared')
                OutlinedButton(
                    onPressed: busy ? null : () => withdraw('clear'),
                    child: const Text('清除批次')),
            ]),
          ]
        ]));
  }
}

class ImportRowEditor extends StatefulWidget {
  const ImportRowEditor(this.row, this.fields, this.corrections,
      {super.key, required this.mapping, this.app});
  final Json row, corrections, mapping;
  final AppState? app;
  final List<Json> fields;
  @override
  State<ImportRowEditor> createState() => _ImportRowEditorState();
}

class _ImportRowEditorState extends State<ImportRowEditor> {
  late final Map<String, TextEditingController> inputs;
  late final Map<String, String> initial;
  bool saved = false;

  @override
  void initState() {
    super.initState();
    initial = {
      for (final f in widget.fields)
        f['key'] as String:
            '${widget.corrections[f['key']] ?? widget.row['raw'][widget.mapping[f['key']]] ?? ''}'
    };
    inputs = {
      for (final e in initial.entries)
        e.key: TextEditingController(text: e.value)
    };
  }

  @override
  void dispose() {
    for (final c in inputs.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => EditGuard(
      app: widget.app,
      controllers: inputs.values.toList(),
      dirty: () =>
          !saved && inputs.entries.any((e) => e.value.text != initial[e.key]),
      child: Scaffold(
          appBar: AppBar(title: Text('修正源行 ${widget.row['row_number']}')),
          body: PageBody(children: [
            const Text('修正只用于当前批次。保存后须重新预览并确认导入。'),
            const SizedBox(height: 16),
            for (final f in widget.fields) ...[
              FormInput('${f['label']}', inputs[f['key']]!,
                  required: false,
                  lines: f['key'] == 'body' || f['key'] == 'note' ? 4 : 1),
              Text('${f['help']}'),
              const SizedBox(height: 12),
            ],
            FilledButton(
                onPressed: () {
                  final result = {...widget.corrections};
                  for (final e in inputs.entries) {
                    if (e.value.text != initial[e.key]) {
                      result[e.key] = e.value.text;
                    }
                  }
                  setState(() => saved = true);
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    if (mounted) Navigator.pop(context, result);
                  });
                },
                child: const Text('保存修正，返回预览')),
          ])));
}
