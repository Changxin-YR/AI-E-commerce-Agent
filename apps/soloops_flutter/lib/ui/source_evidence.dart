import 'package:flutter/material.dart';
import '../core/app_state.dart';
import 'business_widgets.dart';
import 'common.dart';

class SourceEvidence extends StatefulWidget {
  const SourceEvidence(this.app, this.source, {super.key, this.shopId});
  final AppState app;
  final Json source;
  final int? shopId;
  @override
  State<SourceEvidence> createState() => _SourceEvidenceState();
}

class _SourceEvidenceState extends State<SourceEvidence> {
  Json? detail;
  String? error;
  bool busy = false, expanded = false;
  int epoch = 0;
  @override
  void didUpdateWidget(covariant SourceEvidence old) {
    super.didUpdateWidget(old);
    if (old.source['row_id'] != widget.source['row_id'] ||
        old.shopId != widget.shopId) {
      epoch++;
      detail = null;
      error = null;
      busy = false;
      if (expanded) load();
    }
  }

  Future<void> load() async {
    if (busy || detail != null) return;
    final token = ++epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final value = object(await widget.app.api.get(
          '/shops/${widget.shopId ?? widget.app.shopId}/analytics/sources/${widget.source['row_id']}'));
      if (mounted && token == epoch) setState(() => detail = value);
    } catch (e) {
      if (mounted && token == epoch) setState(() => error = '$e');
    } finally {
      if (mounted && token == epoch) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Card(
          child: ExpansionTile(
        title: Text(
            '${widget.source['filename']} · 源行 ${widget.source['row_number']}'),
        subtitle: Text(
            '批次 #${widget.source['batch_id']} · ${widget.source['data_identity']}'),
        childrenPadding: const EdgeInsets.all(16),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        onExpansionChanged: (value) {
          expanded = value;
          if (expanded) load();
        },
        children: [
          FactLine('来源导出时间', widget.source['exported_at']),
          FactLine('导入时间', widget.source['imported_at']),
          if (busy) const LinearProgressIndicator(),
          if (error != null) Notice(error!, onRetry: load),
          if (detail != null) ...[
            FactLine('批次状态', detail!['batch_status']),
            for (final section in const {
              'raw': '源值',
              'corrections': '修正值',
              'normalized': '转换后'
            }.entries) ...[
              Text(section.value,
                  style: Theme.of(context).textTheme.titleSmall),
              for (final e in object(detail![section.key] ?? {}).entries)
                FactLine(e.key, e.value),
            ]
          ]
        ],
      ));
}
