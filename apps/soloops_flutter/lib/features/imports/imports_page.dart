import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import 'import_repository.dart';
import 'import_batch_page.dart';
import 'import_group_page.dart';

class ImportsPage extends StatefulWidget {
  const ImportsPage(this.app,
      {super.key,
      this.kind = 'products',
      this.identity = 'user_import',
      this.channel = 'generic',
      this.batchId});
  final AppState app;
  final String kind, identity, channel;
  final int? batchId;
  @override
  State<ImportsPage> createState() => _ImportsPageState();
}

class _ImportsPageState extends BusinessPageState<ImportsPage> {
  late final repository = ImportRepository(widget.app.api, widget.app.shopId!);
  late String kind =
      importKinds.containsKey(widget.kind) ? widget.kind : 'products';
  late String identity = importIdentities.containsKey(widget.identity)
      ? widget.identity
      : 'user_import';
  late String channel =
      importChannels.containsKey(widget.channel) ? widget.channel : 'generic';
  String format = 'csv';
  late final timezone = TextEditingController(
      text: '${widget.app.shop?['timezone'] ?? 'Asia/Shanghai'}');
  final exportedAt = TextEditingController();
  final formKey = GlobalKey<FormState>();
  Json? catalog, file;
  List<Json> history = [], groups = [];
  int? olderCursor;
  bool _opened = false;
  Json get options {
    final value = exportedAt.text.trim();
    if (value.isNotEmpty &&
        (!RegExp(r'(Z|[+-]\d{2}:\d{2})$').hasMatch(value) ||
            DateTime.tryParse(value) == null)) {
      throw const FormatException('导出时间须包含时区偏移，例如 2026-10-11T09:00:00+08:00。');
    }
    if (timezone.text.trim().isEmpty) throw const FormatException('请填写文件时区。');
    return {
      'kind': kind,
      'source_channel': channel,
      'data_identity': identity,
      'timezone': timezone.text.trim(),
      if (value.isNotEmpty) 'exported_at': value
    };
  }

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    timezone.dispose();
    exportedAt.dispose();
    super.dispose();
  }

  Future<void> load() => perform(() async {
        final loaded = await Future.wait(
            [repository.catalog(), repository.history(), repository.groups()]);
        if (!mounted) return;
        catalog = object(loaded[0]);
        history = rows(loaded[1]);
        groups = rows(loaded[2]);
        olderCursor = groups.length == 20 ? groups.last['id'] as int : null;
        if (!_opened && widget.batchId != null) {
          _opened = true;
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) openBatch(widget.batchId!);
          });
        }
      });
  Future<void> openBatch(int id) async {
    await Navigator.push<void>(context,
        MaterialPageRoute(builder: (_) => ImportBatchPage(widget.app, id)));
    if (mounted) await load();
  }

  Future<void> openGroup({int? id}) async {
    Json sourceOptions;
    try {
      sourceOptions = options;
    } catch (e) {
      setState(() => error = '$e');
      return;
    }
    await Navigator.push<void>(
        context,
        MaterialPageRoute(
            builder: (_) =>
                ImportGroupPage(widget.app, sourceOptions, groupId: id)));
    if (mounted) await load();
  }

  Future<void> upload() => perform(() async {
        if (!(formKey.currentState?.validate() ?? false) || file == null)
          return;
        final bytes = file!['bytes'] as Uint8List;
        if (bytes.length > (catalog?['max_bytes'] as int? ?? 2097152)) {
          throw const FormatException(
              '文件超过单批次上限，请使用“大 CSV 分批导入”；Excel 先将目标工作表另存为 CSV UTF-8。');
        }
        final result =
            await repository.upload(file!['name'] as String, bytes, options);
        file = null;
        if (!mounted) return;
        // Lifecycle remains locked while upload result is inspected.
        await Navigator.push<void>(
            context,
            MaterialPageRoute(
                builder: (_) =>
                    ImportBatchPage(widget.app, result['id'] as int)));
        history = await repository.history();
      });
  Future<void> template() => perform(() async {
        final bytes = await widget.app.api.send(
            'GET', '/imports/templates/$kind',
            query: {'format': format}, rawResponse: true) as Uint8List;
        final saved =
            await widget.app.device.saveFile('soloops-$kind.$format', bytes);
        if (mounted) success = saved ? '模板已保存。' : '已取消保存。';
      });

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('文件导入'), actions: [
        IconButton(
            tooltip: '刷新',
            onPressed: busy ? null : load,
            icon: const Icon(Icons.refresh))
      ]),
      body: PageBody(children: [
        Text('把业务数据，整理成依据', style: Theme.of(context).textTheme.headlineSmall),
        FactLine('所属店铺', widget.app.shop?['name']),
        const Text('数据截至文件导出时间，用于本地分析与草稿。请移除顾客姓名、地址、电话与邮箱。'
            '文件暂存 24 小时，确认后只保留映射字段及修正记录。'),
        ...feedback,
        if (catalog == null && !busy)
          OutlinedButton(onPressed: load, child: const Text('重新加载')),
        const SectionTitle('选择来源'),
        Form(
            key: formKey,
            child: Column(children: [
              ChoiceField('报表类型', kind, importKinds,
                  busy ? null : (v) => setState(() => kind = v)),
              ChoiceField('来源渠道', channel, importChannels,
                  busy ? null : (v) => setState(() => channel = v),
                  help: '平台别名为映射候选，请按自己的报表核对。'),
              ChoiceField('数据身份', identity, importIdentities,
                  busy ? null : (v) => setState(() => identity = v)),
              FormInput('文件时间使用的时区', timezone, enabled: !busy),
              FormInput('导出时间（可选，须含时区偏移）', exportedAt,
                  enabled: !busy, required: false),
              const Text('时间示例：2026-10-11T09:00:00+08:00'),
            ])),
        if (kind == 'statements')
          const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text(
                  '账单以 sale / refund / fee / payout 区分含义，金额填写正数；费用行须有凭据费用行编号与原始收费项名称。')),
        const SectionTitle('单批次导入'),
        Text(
            'UTF-8 CSV 或单工作表 XLSX。单批最多 ${catalog?['max_rows'] ?? 2000} 行、2 MiB、64 列；'
            '金额最多四位小数。不接受宏、公式及外部链接。'),
        const SizedBox(height: 12),
        ChoiceField('模板格式', format, const {'csv': 'CSV', 'xlsx': 'Excel'},
            busy ? null : (v) => setState(() => format = v)),
        OutlinedButton.icon(
            onPressed: busy ? null : template,
            icon: const Icon(Icons.download_outlined),
            label: Text('下载${importKinds[kind]}模板')),
        OutlinedButton.icon(
            onPressed: busy
                ? null
                : () => perform(() async {
                      final selected = await widget.app.device.pickFile();
                      if (mounted && selected != null) file = selected;
                    }),
            icon: const Icon(Icons.attach_file),
            label: const Text('选择 CSV / XLSX')),
        if (file != null)
          FactLine('已选文件',
              '${file!['name']} · ${(file!['bytes'] as Uint8List).length} 字节'),
        FilledButton(
            onPressed: busy || file == null || catalog == null ? null : upload,
            child: const Text('上传并查看映射')),
        const SectionTitle('大 CSV 分批导入'),
        const Text('最多 40 MiB、40000 条记录、20 片。按完整 CSV 记录拆分，逐片预览确认。'
            '组内全部分片完成后才具备完整来源；经营分析单次范围仍最多 10000 行。'),
        const SizedBox(height: 12),
        OutlinedButton(
            onPressed: busy || catalog == null ? null : () => openGroup(),
            child: const Text('选择原始 CSV，建立导入组')),
        for (final group in groups)
          Card(
              child: ListTile(
                  title: Text(
                      '#${group['id']} · ${group['manifest']['source_filename']}'),
                  subtitle: Text(
                      '${group['status'] == 'revoked' ? '已整组撤销' : group['complete'] == true ? '分片全部完成' : '部分覆盖 / 数据不足'}'
                      ' · ${group['committed_parts']} / ${(group['manifest']['parts'] as List).length} 片'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap:
                      busy ? null : () => openGroup(id: group['id'] as int))),
        if (olderCursor != null)
          TextButton(
              onPressed: busy
                  ? null
                  : () => perform(() async {
                        final result =
                            await repository.groups(before: olderCursor);
                        groups.addAll(result.where(
                            (g) => !groups.any((old) => old['id'] == g['id'])));
                        olderCursor = result.length == 20
                            ? result.last['id'] as int
                            : null;
                      }),
              child: const Text('加载更早的导入组')),
        const SectionTitle('批次历史'),
        if (history.isEmpty && !busy) const Text('尚未导入文件。可以先下载一份模板。'),
        for (final b in history)
          Card(
              child: ListTile(
                  title: Text('#${b['id']} · ${b['filename']}'),
                  subtitle: Text(
                      '${batchStatuses[b['status']]} · ${importKinds[b['kind']]} · ${importIdentities[b['data_identity']]}\n'
                      '${b['total_rows']} 行 · ${b['created_at']}'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: busy ? null : () => openBatch(b['id'] as int))),
      ]));
}
