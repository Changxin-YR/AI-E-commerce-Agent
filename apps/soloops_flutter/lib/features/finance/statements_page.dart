import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/business_navigation.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/source_evidence.dart';
import 'finance_common.dart';
import 'fee_rules_page.dart';
import 'review_panel.dart';

class StatementsPage extends StatefulWidget {
  const StatementsPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<StatementsPage> createState() => _StatementsPageState();
}

class _StatementsPageState extends BusinessPageState<StatementsPage> {
  late final scope = FinanceScope(widget.app, widget.query);
  Json? result, queriedScope;
  @override
  void initState() {
    super.initState();
    scope.addListener(changed);
  }

  void changed() {
    if (mounted) {
      setState(() {
        result = null;
        queriedScope = null;
      });
    }
  }

  @override
  void dispose() {
    scope.dispose();
    super.dispose();
  }

  Future<void> calculate() => perform(() async {
        final input = scope.input();
        final value = object(await widget.app.api
            .post(widget.app.shopPath('/statements/reconcile'), input));
        if (mounted) {
          setState(() {
            result = value;
            queriedScope = input;
          });
        }
      });
  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('渠道账单与费用核对')),
      body: PageBody(children: [
        ...feedback,
        FinanceScopeFields(scope, enabled: !busy),
        Wrap(spacing: 8, children: [
          FilledButton(
              onPressed: busy ? null : calculate, child: const Text('核对账单与费用')),
          OutlinedButton(
              onPressed: busy
                  ? null
                  : () => openBusinessPath(context, widget.app,
                      '/imports?kind=statements&identity=${scope.identity}&channel=${scope.channel}'),
              child: const Text('导入渠道账单')),
          OutlinedButton(
              onPressed: busy
                  ? null
                  : () => openBusinessPath(context, widget.app,
                      '/fee-rules?identity=${scope.identity}&channel=${scope.channel}'),
              child: const Text('费用映射规则')),
          OutlinedButton(
              onPressed: busy
                  ? null
                  : () => openBusinessPath(
                      context, widget.app, '/statements/order-reconciliation'),
              child: const Text('订单与账单核对')),
        ]),
        if (result != null) StatementResultView(widget.app, result!),
        ReviewPanel(widget.app,
            scope: queriedScope,
            initialId: int.tryParse(widget.query['review'] ?? ''),
            resultBuilder: (value) => StatementResultView(widget.app, value)),
      ]));
}

class StatementResultView extends StatelessWidget {
  const StatementResultView(this.app, this.result, {super.key});
  final AppState app;
  final Json result;
  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const SectionTitle('账单核对依据'),
        FactLine('数据范围',
            '${object(result['scope'])['data_identity']} · ${object(result['scope'])['channel']}'),
        FactLine('期间',
            '${object(result['scope'])['start_at']} → ${object(result['scope'])['end_at']}'),
        FactLine('业务时区', object(result['scope'])['timezone']),
        FactLine('来源 / 映射规则修订',
            '${result['source_revision']} / ${result['rule_revision']}'),
        FactLine('核对时间', result['calculated_at']),
        FactLine('待重核费用', result['stale_expenses']),
        FactLine('撤销费用', result['withdrawn_expenses']),
        for (final check in result['checks'] as List) Text('$check'),
        const SectionTitle('分币种、分类型金额'),
        for (final total in rows(result['totals']))
          ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('${total['amount']} ${total['currency']}'),
              subtitle: Text(
                  '${entryTypes[total['entry_type']]} · ${total['count']} 行')),
        const SectionTitle('费用凭据匹配'),
        FinanceRows(rows(result['comparisons']),
            builder: (c) => ExpansionTile(
                    title: Text(
                        '${c['evidence_ref']} · ${comparisonStatuses[c['status']]}'),
                    subtitle: Text('金额差异：${c['difference'] ?? '无法确定'}'),
                    children: [
                      for (final e in rows(c['expenses']))
                        ListTile(
                            title: Text(
                                '${e['label']} · ${e['amount']} ${e['currency']}'),
                            subtitle: Text(
                                '${expenseCategories[e['category']]} · ${e['allocation'] == 'shop' ? '店铺未分摊' : '订单行费用'}\n${e['evidence_ref']} · ${e['occurred_at']} · v${e['version']}'),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () => openBusinessPath(
                                context, app, '/expenses?expense=${e['id']}')),
                      for (final statement in rows(result['statements']).where(
                          (s) =>
                              (c['statement_ids'] as List).contains(s['id'])))
                        StatementEvidence(app, statement),
                    ])),
        const SectionTitle('费用类别映射'),
        FinanceRows(rows(result['mappings']),
            builder: (m) => ListTile(
                title: Text('账单行 #${m['statement_id']}'),
                subtitle: Text(mappingDescription(m)),
                onTap: m['rule_id'] == null
                    ? null
                    : () => openBusinessPath(
                        context, app, '/fee-rules?rule=${m['rule_id']}'))),
        const SectionTitle('全部账单明细与源行'),
        FinanceRows(rows(result['statements']),
            builder: (s) => StatementEvidence(app, s)),
      ]);
}

class StatementEvidence extends StatelessWidget {
  const StatementEvidence(this.app, this.value, {super.key});
  final AppState app;
  final Json value;
  @override
  Widget build(BuildContext context) => ExpansionTile(
          title: Text(
              '${entryTypes[value['entry_type']]} · ${value['amount']} ${value['currency']}'),
          subtitle: Text(
              '${value['statement_id']} / ${value['line_id']} · #${value['id']}'),
          children: [
            for (final e in const {
              'occurred_at': '发生时间',
              'evidence_ref': '凭据编号',
              'fee_name': '费用名称',
              'settlement_id': '结算编号',
              'order_id': '订单号',
              'note': '备注'
            }.entries)
              FactLine(e.value, value[e.key]),
            if (value.containsKey('in_window'))
              FactLine('所选期间内', value['in_window'] == true ? '是' : '否 · 跨期关联'),
            SourceEvidence(app, object(value['source']))
          ]);
}
