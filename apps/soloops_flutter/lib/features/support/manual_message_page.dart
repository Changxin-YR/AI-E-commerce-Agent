import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../ui/business_widgets.dart';
import '../../ui/common.dart';
import '../imports/import_repository.dart';
import '../imports/import_batch_page.dart';

class ManualMessagePage extends StatefulWidget {
  const ManualMessagePage(this.app, {super.key});
  final AppState app;
  @override
  State<ManualMessagePage> createState() => _ManualMessagePageState();
}

class _ManualMessagePageState extends BusinessPageState<ManualMessagePage> {
  final formKey = GlobalKey<FormState>();
  final id = TextEditingController(),
      sent = TextEditingController(),
      body = TextEditingController(),
      order = TextEditingController();
  String language = 'und', channel = 'generic', identity = 'user_import';
  int? batchId;
  @override
  void dispose() {
    for (final c in [id, sent, body, order]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> preview() async {
    if (!formKey.currentState!.validate()) return;
    await perform(() async {
      if (id.text.length > 120 ||
          order.text.length > 120 ||
          body.text.length > 2000) {
        throw const FormatException('消息/订单标识最多 120 字，原文最多 2000 字。');
      }
      final date = awareDate(sent.text, '消息时间', required: true)!;
      String escape(String value) => '"${value.replaceAll('"', '""')}"';
      final csv = 'message_id,sent_at,body,language,order_id\n'
          '${[
        id.text,
        date,
        body.text,
        language,
        order.text
      ].map(escape).join(',')}\n';
      final repo = ImportRepository(widget.app.api, widget.app.shopId!);
      final batch = await repo
          .upload('manual-message.csv', Uint8List.fromList(utf8.encode(csv)), {
        'kind': 'messages',
        'source_channel': channel,
        'data_identity': identity,
        'timezone': widget.app.shop?['timezone'] ?? 'Asia/Shanghai',
      });
      if (!mounted) return;
      batchId = batch['id'] as int;
    }, message: '消息已存为待核对批次。请在导入页审阅字段、旧值与新值，再提交。');
    if (mounted && error == null && batchId != null) await openBatch();
  }

  Future<void> openBatch() => Navigator.push<void>(context,
      MaterialPageRoute(builder: (_) => ImportBatchPage(widget.app, batchId!)));
  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('手工录入消息')),
      body: Form(
          key: formKey,
          child: PageBody(children: [
            ...feedback,
            FormInput('原消息标识', id, enabled: !busy),
            FormInput('消息时间（ISO，含时区偏移）', sent, enabled: !busy),
            ChoiceField('来源渠道', channel, importChannels,
                busy ? null : (v) => setState(() => channel = v)),
            ChoiceField('数据身份', identity, importIdentities,
                busy ? null : (v) => setState(() => identity = v)),
            ChoiceField(
                '消息语言',
                language,
                const {'und': '待人工确认 / 其他', 'en': 'English', 'zh': '中文'},
                busy ? null : (v) => setState(() => language = v)),
            FormInput('待核验订单号', order, required: false, enabled: !busy),
            FormInput('消息原文', body, lines: 8, enabled: !busy),
            FilledButton(
                onPressed: busy ? null : preview, child: const Text('创建待核对批次')),
            if (batchId != null)
              TextButton(
                  onPressed: busy ? null : openBatch,
                  child: Text('继续核对批次 #$batchId')),
          ])));
}
