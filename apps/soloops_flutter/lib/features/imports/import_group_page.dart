import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import 'csv_split.dart';
import 'import_repository.dart';
import 'import_batch_page.dart';

class ImportGroupPage extends StatefulWidget {
  const ImportGroupPage(this.app, this.options, {super.key, this.groupId});
  final AppState app;
  final Json options;
  final int? groupId;
  @override
  State<ImportGroupPage> createState() => _ImportGroupPageState();
}

class _ImportGroupPageState extends BusinessPageState<ImportGroupPage> {
  late final repository = ImportRepository(widget.app.api, widget.app.shopId!);
  Json? group, importedManifest;
  PreparedCsv? prepared;
  CsvSplitJob? job;
  StreamSubscription<Json>? subscription;
  Json? progress;
  @override
  void initState() {
    super.initState();
    if (widget.groupId != null) reload();
  }

  @override
  void dispose() {
    subscription?.cancel();
    job?.cancel();
    prepared = null;
    super.dispose();
  }

  Future<void> reload() => perform(() async {
        final id = group?['id'] as int? ?? widget.groupId;
        if (id == null) return;
        final value = await repository.group(id);
        if (mounted) group = value;
      });
  Future<void> pickSource() => perform(() async {
        final file = await widget.app.device.pickFile();
        if (file == null || !mounted) return;
        prepared = null;
        progress = {
          'bytes': 0,
          'totalBytes': (file['bytes'] as Uint8List).length,
          'rows': 0
        };
        final current =
            CsvSplitJob(file['name'] as String, file['bytes'] as Uint8List);
        job = current;
        subscription = current.progress.listen((p) {
          if (mounted) setState(() => progress = p);
        });
        try {
          final result = await current.result;
          if (!mounted) return;
          if (group != null &&
              !sameManifest(result.manifest, object(group!['manifest']))) {
            throw const FormatException('原文件的名称、指纹或分片与当前组不一致。请选择建组时的原文件。');
          }
          prepared = result;
          importedManifest = null;
          success =
              '本机文件已就绪：${result.manifest['total_rows']} 条记录，${result.parts.length} 片。';
        } finally {
          await subscription?.cancel();
          subscription = null;
          job = null;
          if (mounted) progress = null;
        }
      });
  Future<void> create() => perform(() async {
        final manifest = prepared?.manifest ?? importedManifest;
        if (manifest == null) return;
        final value = await repository.createGroup(widget.options, manifest);
        if (mounted) group = value;
      }, message: '导入组已建立，请逐片上传、预览并确认。');
  Future<void> inspectBatch(int id) async {
    await Navigator.push<void>(context,
        MaterialPageRoute(builder: (_) => ImportBatchPage(widget.app, id)));
    if (mounted) await reload();
  }

  Future<void> upload(int index, {Uint8List? selectedBytes}) =>
      perform(() async {
        final g = group!;
        final part = rows(g['manifest']['parts'])[index];
        final bytes = selectedBytes ?? prepared!.parts[index];
        if (bytes.length != part['bytes'] ||
            sha256.convert(bytes).toString() != part['sha256']) {
          throw const FormatException('此分片字节或指纹与清单不一致，请使用原分片。');
        }
        final sourceOptions = object(g['options'])
          ..removeWhere((k, v) => v == null);
        final batch = await repository.upload(part['filename'] as String, bytes,
            {...sourceOptions, 'group_id': g['id'], 'group_part': index + 1});
        if (!mounted) return;
        group = await repository.group(g['id'] as int);
        if (!mounted) return;
        await Navigator.push<void>(
            context,
            MaterialPageRoute(
                builder: (_) =>
                    ImportBatchPage(widget.app, batch['id'] as int)));
        if (!mounted) return;
        group = await repository.group(g['id'] as int);
      });
  Future<void> selectPart() async {
    Uint8List? bytes;
    var index = -1;
    await perform(() async {
      final file = await widget.app.device.pickFile();
      if (file == null) return;
      index = rows(group!['manifest']['parts'])
          .indexWhere((p) => p['filename'] == file['name']);
      if (index < 0) throw const FormatException('文件名不在当前清单中，请选择原分片。');
      bytes = file['bytes'] as Uint8List;
    });
    if (bytes != null && mounted) await upload(index, selectedBytes: bytes);
  }

  Future<void> revoke() async {
    if (!await confirmAction(
        context, '撤销整个导入组', '将撤销本组所有分片及其衍生来源，按剩余有效批次恢复其他版本。')) {
      return;
    }
    await perform(() async {
      final result = await repository.revokeGroup(group!);
      if (mounted) {
        group = result;
        prepared = null;
      }
    }, message: '整组已撤销。');
  }

  Future<void> pickManifest() => perform(() async {
        final file = await widget.app.device.pickFile();
        if (file == null || !mounted) return;
        final bytes = file['bytes'] as Uint8List;
        if (bytes.length > 65536) {
          throw const FormatException('分片清单不能超过 64 KiB。');
        }
        final raw = jsonDecode(utf8.decode(bytes));
        if (raw is! Map) throw const FormatException('请选择 JSON 分片清单。');
        final value = object(raw);
        final parts = rows(value['parts']);
        final fingerprint = RegExp(r'^[0-9a-f]{64}$');
        if (value['format'] != 'soloops-split-v1' ||
            value['source_filename'] is! String ||
            (value['source_filename'] as String).isEmpty ||
            (value['source_filename'] as String).length > 240 ||
            !fingerprint.hasMatch('${value['source_sha256']}') ||
            parts.isEmpty ||
            parts.length > 20 ||
            value['total_rows'] is! int ||
            (value['total_rows'] as int) < 1 ||
            (value['total_rows'] as int) > 40000) {
          throw const FormatException('清单格式、指纹、总记录数或分片数无效。');
        }
        var total = 0;
        final names = <String>{};
        for (final part in parts) {
          final name = part['filename'];
          if (name is! String ||
              name.length > 120 ||
              !RegExp(r'^[^/\\]+\.csv$').hasMatch(name) ||
              !names.add(name) ||
              !fingerprint.hasMatch('${part['sha256']}') ||
              part['rows'] is! int ||
              (part['rows'] as int) < 1 ||
              (part['rows'] as int) > 2000 ||
              part['bytes'] is! int ||
              (part['bytes'] as int) < 1 ||
              (part['bytes'] as int) > 2097152) {
            throw const FormatException('清单分片的文件名、记录数、大小或指纹无效。');
          }
          total += part['rows'] as int;
        }
        if (total != value['total_rows']) {
          throw const FormatException('分片记录总数与清单不一致。');
        }
        prepared = null;
        importedManifest = value;
        success = '清单已读取，请核对来源并建组，再选择对应分片。相同清单与来源可回读已建组。';
      });
  Future<void> saveManifest() => perform(() async {
        final manifest =
            group?['manifest'] ?? prepared?.manifest ?? importedManifest;
        final saved = await widget.app.device.saveFile(
            'manifest.json',
            Uint8List.fromList(utf8
                .encode(const JsonEncoder.withIndent('  ').convert(manifest))));
        if (mounted) success = saved ? '分片清单已保存。' : '已取消保存。';
      });
  @override
  Widget build(BuildContext context) {
    final g = group;
    final manifest = g == null
        ? (prepared?.manifest ?? importedManifest)
        : object(g['manifest']);
    final source = g == null ? widget.options : object(g['options']);
    var start = 1;
    final partWidgets = <Widget>[];
    final parts = rows(manifest?['parts']);
    for (var i = 0; i < parts.length; i++) {
      final index = i;
      final part = parts[i];
      final batchList =
          rows(g?['batches']).where((b) => b['group_part'] == i + 1);
      partWidgets.add(Card(
          child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('第 ${i + 1} 片 · ${part['filename']}',
                        style: Theme.of(context).textTheme.titleMedium),
                    Text(
                        '原数据记录 $start — ${start + (part['rows'] as int) - 1} · ${part['bytes']} 字节'),
                    if (batchList.isEmpty) const Text('尚未上传'),
                    for (final b in batchList)
                      ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(
                              '批次 #${b['id']} · ${batchStatuses[b['status']]}'),
                          trailing: const Icon(Icons.chevron_right),
                          onTap:
                              busy ? null : () => inspectBatch(b['id'] as int)),
                    if (g?['status'] == 'active' && prepared != null)
                      OutlinedButton(
                          onPressed: busy ? null : () => upload(index),
                          child: Text('上传 / 恢复第 ${i + 1} 片')),
                  ]))));
      start += part['rows'] as int;
    }
    return Scaffold(
        appBar: AppBar(
            title: Text(g == null ? '大 CSV 分批导入' : '导入组 #${g['id']}'),
            actions: [
              if (g != null)
                IconButton(
                    tooltip: '刷新导入组',
                    onPressed: busy ? null : reload,
                    icon: const Icon(Icons.refresh))
            ]),
        body: PageBody(children: [
          ...feedback,
          FactLine('所属店铺', widget.app.shop?['name']),
          FactLine('报表来源',
              '${importKinds[source['kind']]} · ${importChannels[source['source_channel']]} · ${importIdentities[source['data_identity']]}'),
          FactLine('文件时区 / 导出时间',
              '${source['timezone']} / ${source['exported_at'] ?? '未知'}'),
          const Text('选择原始 UTF-8 CSV，最多 40 MiB、40000 条记录、20 片。多行字段按一条记录处理。'
              '返回后可用同一原文件恢复已保存的组；尚未确认的分片不会计入业务记录。'),
          const SizedBox(height: 16),
          if (g == null && widget.groupId != null && !busy)
            OutlinedButton(onPressed: reload, child: const Text('重新加载导入组')),
          if (g == null || g['status'] == 'active')
            OutlinedButton.icon(
                onPressed: busy ? null : pickSource,
                icon: const Icon(Icons.attach_file),
                label: Text(g == null ? '选择原始 CSV' : '选择同一原文件以恢复')),
          if (g == null && widget.groupId == null)
            OutlinedButton(
                onPressed: busy ? null : pickManifest,
                child: const Text('选择已有 manifest.json 清单')),
          if (job != null) ...[
            LinearProgressIndicator(
                value: progress == null || progress!['totalBytes'] == 0
                    ? null
                    : (progress!['bytes'] as num) /
                        (progress!['totalBytes'] as num)),
            Text('已处理 ${progress?['rows'] ?? 0} 条记录'),
            TextButton(
                onPressed: () => job?.cancel(), child: const Text('取消拆分'))
          ],
          if (prepared != null && !busy)
            TextButton(
                onPressed: () => setState(() {
                      prepared = null;
                      success = '已释放本机文件；服务端记录仍保留。';
                    }),
                child: const Text('释放本机文件')),
          if (manifest != null) ...[
            const SectionTitle('来源与完整性'),
            FactLine('原文件', manifest['source_filename']),
            FactLine('SHA-256', manifest['source_sha256']),
            FactLine('总记录 / 分片', '${manifest['total_rows']} / ${parts.length}'),
            if (g != null) ...[
              FactLine(
                  '状态',
                  g['status'] == 'revoked'
                      ? '已整组撤销'
                      : g['complete'] == true
                          ? '分片全部完成'
                          : '部分覆盖 / 数据不足'),
              FactLine('已提交片数', '${g['committed_parts']} / ${parts.length}'),
              FactLine('已提交源记录',
                  '${g['committed_rows']} / ${manifest['total_rows']}'),
              FactLine(
                  '去重 / 跨片重叠', '${g['unique_rows']} / ${g['overlap_rows']}'),
              if (g['complete'] != true && g['status'] == 'active')
                const Notice('汇总与完整性判断暂停，请补齐所有分片或撤销整组。'),
            ],
            OutlinedButton(
                onPressed: busy ? null : saveManifest,
                child: const Text('保存分片清单')),
            if (g == null && widget.groupId == null)
              FilledButton(
                  onPressed: busy ? null : create,
                  child: const Text('按当前来源建立导入组')),
            const SectionTitle('逐片核对'),
            const Text('下方范围为原文件数据记录序号，不含表头；批次明细的源行号为分片内物理行号。'),
            ...partWidgets,
            if (g?['status'] == 'active') ...[
              OutlinedButton(
                  onPressed: busy ? null : selectPart,
                  child: const Text('选择已有分片 CSV 并上传')),
              OutlinedButton(
                  onPressed: busy ? null : revoke,
                  child: const Text('撤销整个导入组')),
            ]
          ],
        ]));
  }
}
