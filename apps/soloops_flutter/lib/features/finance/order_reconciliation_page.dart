import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/source_evidence.dart';
import '../../ui/finance_inputs.dart';
import 'finance_common.dart';
import 'statements_page.dart';
import 'review_panel.dart';

const orderReasons = {
  'missing_order_reference': '账单缺少来源订单号，需补充稳定关联编号。',
  'order_not_imported': '当前导入范围没有此订单，文件覆盖仍待核对。',
  'statement_not_imported': '当前导入范围没有此类型账单，需核查来源覆盖。',
  'multiple_order_lines': '订单有多行，账单未提供可核验的行归属。',
  'multiple_statement_lines': '同订单有多笔同类账单，拆分、重复或调整关系待核。',
  'outside_window': '存在期间外关联来源，请核实跨期关系。',
  'currency_mismatch': '两侧币种不同，缺少已确认换汇依据。',
  'order_status_uncomparable': '未付款、取消或测试状态不支持销售金额比较。',
  'refund_transaction_unknown': '累计行退款缺逐笔编号、时间、金额组成及支付状态，差额未知。',
  'refund_amount_unknown': '订单行退款金额未知。',
  'sale_basis_unknown': '销售款金额组成未知，需核实两侧原文件口径。',
  'discount_unknown': '订单行折扣未知，无法计算折后商品款。',
  'different_local_date': '账单与订单当地日期不同，时间归属待核。'
};

class OrderReconciliationPage extends StatefulWidget {
  const OrderReconciliationPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<OrderReconciliationPage> createState() =>
      _OrderReconciliationPageState();
}

class _OrderReconciliationPageState
    extends BusinessPageState<OrderReconciliationPage> {
  late final scope = FinanceScope(widget.app, widget.query);
  final basisNote = TextEditingController();
  String saleBasis = 'unknown';
  Json? result, queriedScope;
  @override
  void initState() {
    super.initState();
    scope.addListener(changed);
    basisNote.addListener(changed);
  }

  void changed() {
    if (mounted) {
      setState(() {
        result = null;
        queriedScope = null;
      });
    }
  }

  Future<void> calculate() => perform(() async {
        final input = {
          ...scope.input(),
          'sale_basis': saleBasis,
          'basis_note': saleBasis == 'unknown'
              ? basisNote.text.trim()
              : requiredText(basisNote.text, '销售口径依据', 500)
        };
        final value = object(await widget.app.api
            .post(widget.app.shopPath('/statements/orders/reconcile'), input));
        if (mounted) {
          setState(() {
            result = value;
            queriedScope = input;
          });
        }
      });
  @override
  void dispose() {
    scope.dispose();
    basisNote.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('订单账单核对')),
      body: PageBody(children: [
        ...feedback,
        FinanceScopeFields(scope, enabled: !busy),
        ChoiceField(
            '销售款可比口径',
            saleBasis,
            const {
              'unknown': '金额组成尚未确认',
              'merchandise_after_discount': '退款前折后商品款，不含运费、税费及其他调整'
            },
            busy
                ? null
                : (v) {
                    setState(() => saleBasis = v);
                    changed();
                  }),
        FormInput('两侧原文件金额组成依据', basisNote,
            lines: 3, required: false, enabled: !busy),
        FilledButton(
            onPressed: busy ? null : calculate, child: const Text('匹配订单与账单')),
        if (result != null) OrderReconciliationView(widget.app, result!),
        ReviewPanel(widget.app,
            orders: true,
            scope: queriedScope,
            initialId: int.tryParse(widget.query['review'] ?? ''),
            resultBuilder: (value) =>
                OrderReconciliationView(widget.app, value))
      ]));
}

class OrderReconciliationView extends StatelessWidget {
  const OrderReconciliationView(this.app, this.result, {super.key});
  final AppState app;
  final Json result;
  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const SectionTitle('订单与账单核对结果'),
        FactLine('数据范围',
            '${object(result['scope'])['data_identity']} · ${object(result['scope'])['channel']}'),
        FactLine('期间',
            '${object(result['scope'])['start_at']} → ${object(result['scope'])['end_at']}'),
        FactLine('业务时区', object(result['scope'])['timezone']),
        FactLine(
            '销售口径',
            object(result['scope'])['sale_basis'] == 'unknown'
                ? '尚未确认'
                : '退款前折后商品款'),
        FactLine('口径依据', object(result['scope'])['basis_note']),
        FactLine('来源修订', result['source_revision']),
        FactLine('计算时间', result['calculated_at']),
        FactLine('来源覆盖完整性',
            result['coverage'] == 'unknown' ? '未知' : result['coverage']),
        for (final check in result['checks'] as List) Text('$check'),
        const SectionTitle('匹配与差异'),
        FinanceRows(rows(result['comparisons']),
            builder: (c) => ExpansionTile(
                    title: Text(
                        '${c['order_id']} · ${entryTypes[c['entry_type']]}'),
                    subtitle: Text(
                        '${c['status'] == 'matched' ? '所选口径内金额相同' : comparisonStatuses[c['status']]} · 差异 ${c['difference'] ?? '未知'} ${c['currency'] ?? ''}'),
                    children: [
                      FactLine('订单可比金额', c['order_amount']),
                      for (final reason in c['reasons'] as List)
                        Notice(orderReasons[reason] ?? '$reason'),
                      for (final order in rows(result['orders']).where((o) =>
                          (c['order_line_ids'] as List).contains(o['id'])))
                        OrderEvidence(app, order),
                      for (final statement in rows(result['statements']).where(
                          (s) =>
                              (c['statement_ids'] as List).contains(s['id'])))
                        StatementEvidence(app, statement),
                    ])),
        ExpansionTile(
            title: Text('全部订单行 · ${rows(result['orders']).length}'),
            children: [
              FinanceRows(rows(result['orders']),
                  builder: (o) => OrderEvidence(app, o))
            ]),
        ExpansionTile(
            title: Text('全部销售 / 退款账单 · ${rows(result['statements']).length}'),
            children: [
              FinanceRows(rows(result['statements']),
                  builder: (s) => StatementEvidence(app, s))
            ]),
      ]);
}

class OrderEvidence extends StatelessWidget {
  const OrderEvidence(this.app, this.value, {super.key});
  final AppState app;
  final Json value;
  @override
  Widget build(BuildContext context) => ExpansionTile(
          title: Text(
              '${value['order_id']} / ${value['line_id']} · ${value['sku']}'),
          subtitle: Text(
              '${value['quantity']} 件 · ${value['currency']} · ${value['status']}'),
          children: [
            FactLine('下单时间', value['ordered_at']),
            FactLine('折扣前单价', value['unit_price']),
            FactLine('行折扣', value['discount']),
            FactLine('累计行退款', value['refund']),
            FactLine('履约状态', value['fulfillment_status']),
            FactLine('所选期间内', value['in_window'] == true ? '是' : '否 · 跨期关联'),
            SourceEvidence(app, object(value['source']))
          ]);
}
