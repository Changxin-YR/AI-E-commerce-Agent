import '../../ui/business_time_fields.dart';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../ui/business_widgets.dart';
import '../../ui/common.dart';

class OrderCostPage extends StatefulWidget {
  const OrderCostPage(this.app, this.rowId, {super.key});
  final AppState app;
  final int rowId;
  @override
  State<OrderCostPage> createState() => _OrderCostPageState();
}

class _OrderCostPageState extends BusinessPageState<OrderCostPage> {
  final unit = TextEditingController(),
      currency = TextEditingController(),
      evidence = TextEditingController(),
      at = TextEditingController();
  Json? data;
  bool confirmed = false, changed = false;
  String? requestId, pendingAction;
  String get path =>
      widget.app.shopPath('/analytics/order-costs/${widget.rowId}');
  @override
  void initState() {
    super.initState();
    for (final c in [unit, currency, evidence, at]) {
      c.addListener(invalidate);
    }
    load();
  }

  @override
  void dispose() {
    for (final c in [unit, currency, evidence, at]) {
      c.dispose();
    }
    super.dispose();
  }

  void invalidate() {
    if (mounted) {
      setState(() {
        confirmed = false;
        requestId = null;
        pendingAction = null;
      });
    }
  }

  Future<void> read() async {
    final value = object(await widget.app.api.get(path));
    if (!mounted) return;
    data = value;
    currency.text = '${value['currency']}';
    final current = rows(value['history'])
        .where((v) => v['status'] == 'active' && v['action'] == 'upsert')
        .firstOrNull;
    if (current != null) {
      unit.text = '${current['unit_cost']}';
      evidence.text = '${current['evidence_ref']}';
      at.text = '${current['evidence_at']}';
    }
    confirmed = false;
    requestId = null;
    pendingAction = null;
  }

  Future<void> load() => perform(read);
  Future<void> save(String action) async {
    if (action == 'revoke' &&
        !await confirmAction(
            context, '撤销订单行历史成本', '当前成本凭据将撤销，版本历史保留，采用该依据的分析需重算。')) {
      return;
    }
    await perform(() async {
      Json? content;
      if (action == 'upsert') {
        if (!confirmed ||
            !RegExp(r'^\d{1,14}(\.\d{1,4})?$').hasMatch(unit.text.trim()) ||
            evidence.text.trim().isEmpty ||
            evidence.text.length > 500) {
          throw const FormatException('请填写非负单位成本（最多 4 位小数）、凭据索引，并确认历史成本口径。');
        }
        content = {
          'unit_cost': unit.text.trim(),
          'currency': currency.text.trim().toUpperCase(),
          'evidence_ref': evidence.text.trim(),
          'evidence_at': awareDate(at.text, '凭据时间', required: true),
          'confirmed': true
        };
      }
      if (pendingAction != action) requestId = null;
      requestId ??= newRequestId();
      pendingAction = action;
      final value = object(await widget.app.api.post(path, {
        'request_id': requestId,
        'expected_version': data!['version'],
        'expected_revision': data!['source_revision'],
        'action': action,
        if (content != null) 'content': content,
      }));
      if (!mounted) return;
      data = value;
      changed = true;
      confirmed = false;
      requestId = null;
      pendingAction = null;
    }, message: '历史成本依据已更新，返回分析页后请重新计算。');
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('订单行历史成本')),
      body: PageBody(children: [
        ...feedback,
        if (data != null) ...[
          FactLine('订单 / 行 / SKU',
              '${data!['order_id']} / ${data!['line_id']} / ${data!['sku']}'),
          FactLine('来源批次 / 行 / 修订号',
              '${data!['source_batch_id']} / ${data!['source_row_id']} / ${data!['source_revision']}'),
          FactLine(
              '渠道 / 数据身份', '${data!['channel']} / ${data!['data_identity']}'),
          FactLine('当前来源有效', data!['source_current']),
          const Text('此成本是卖家提供的订单行历史单位采购成本；凭据变更后需重新计算。'),
          FormInput('单位采购成本', unit,
              enabled: !busy && data!['source_current'] == true,
              type: TextInputType.number),
          FormInput('币种', currency,
              enabled: !busy && data!['source_current'] == true),
          FormInput('凭据索引', evidence,
              enabled: !busy && data!['source_current'] == true),
          BusinessDateTimeField('凭据时间', at,
              enabled: !busy && data!['source_current'] == true),
          CheckboxListTile(
              value: confirmed,
              onChanged: busy || data!['source_current'] != true
                  ? null
                  : (v) => setState(() => confirmed = v!),
              title: const Text('确认这是卖家提供的订单行历史单位采购成本依据')),
          Wrap(spacing: 12, children: [
            FilledButton(
                onPressed: busy || !confirmed || data!['source_current'] != true
                    ? null
                    : () => save('upsert'),
                child: const Text('保存成本新版本')),
            OutlinedButton(
                onPressed: busy ||
                        data!['source_current'] != true ||
                        data!['version'] == 0
                    ? null
                    : () => save('revoke'),
                child: const Text('撤销当前凭据')),
            TextButton(
                onPressed: busy ? null : load, child: const Text('回读版本与来源')),
          ]),
          const SectionTitle('成本版本历史'),
          for (final v in rows(data!['history']))
            ExpansionTile(
                title:
                    Text('v${v['version']} · ${v['action']} · ${v['status']}'),
                children: [
                  FactLine('单位成本 / 币种', '${v['unit_cost']} / ${v['currency']}'),
                  FactLine('凭据索引', v['evidence_ref']),
                  FactLine('凭据时间', v['evidence_at']),
                  FactLine('登记时间', v['recorded_at']),
                ]),
        ],
      ]));
}
