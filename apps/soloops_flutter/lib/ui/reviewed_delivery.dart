import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/app_state.dart';

Future<String> deliverArtifact(
    AppState app, Json artifact, String action) async {
  if (action == 'copy') {
    await Clipboard.setData(
        ClipboardData(text: artifact['plain_text'] as String));
    return '完整文案、版本与来源已复制，请在原渠道核对后使用。';
  }
  final bytes = Uint8List.fromList(utf8.encode(artifact['csv_text'] as String));
  final filename = artifact['filename'] as String;
  if (action == 'share') {
    await app.device.shareFile(filename, bytes);
    return '已打开系统分享，请核对接收目标。';
  }
  final saved = await app.device.saveFile(filename, bytes);
  return saved ? '通用 CSV 已保存。' : '已取消保存。';
}

class DeliveryButtons extends StatelessWidget {
  const DeliveryButtons(
      {super.key, required this.enabled, required this.onAction});
  final bool enabled;
  final void Function(String) onAction;
  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('交付文件包含完整文案、版本和来源。每次操作前重新核对当前版本；外部状态保持未提交。'),
        Wrap(spacing: 12, children: [
          for (final e in const {
            'copy': '复制全文',
            'save': '保存 CSV',
            'share': '分享 CSV'
          }.entries)
            OutlinedButton(
                onPressed: enabled ? () => onAction(e.key) : null,
                child: Text(e.value)),
        ]),
        const Text('CSV 使用服务端提供的公式防护标记；在电子表格中再次保存时请核对标记。'),
      ]);
}
