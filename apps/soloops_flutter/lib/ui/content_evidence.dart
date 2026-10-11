import 'package:flutter/material.dart';
import '../core/app_state.dart';
import 'business_widgets.dart';
import 'common.dart';
import 'source_evidence.dart';

Json mapValue(dynamic value) => value is Map ? object(value) : {};
String words(dynamic value) =>
    value is List ? value.join('、') : '${value ?? ''}';
List<Json> sourceReferences(dynamic value) {
  final found = <String, Json>{};
  void walk(dynamic item) {
    if (item is List) {
      for (final child in item) {
        walk(child);
      }
    }
    if (item is Map) {
      if (item['row_id'] != null &&
          item['batch_id'] != null &&
          item['filename'] != null) {
        found['${item['row_id']}'] = object(item);
      }
      for (final child in item.values) {
        walk(child);
      }
    }
  }

  walk(value);
  return found.values.toList();
}

class EvidenceSources extends StatefulWidget {
  const EvidenceSources(this.app, this.value, {super.key, this.shopId});
  final AppState app;
  final dynamic value;
  final int? shopId;
  @override
  State<EvidenceSources> createState() => _EvidenceSourcesState();
}

class _EvidenceSourcesState extends State<EvidenceSources> {
  List<Json>? sources;
  int offset = 0;
  @override
  void didUpdateWidget(covariant EvidenceSources old) {
    super.didUpdateWidget(old);
    if (!identical(old.value, widget.value)) {
      sources = null;
      offset = 0;
    }
  }

  @override
  Widget build(BuildContext context) => ExpansionTile(
          title: Text(sources == null ? '展开事实来源' : '事实来源（${sources!.length}）'),
          onExpansionChanged: (expanded) {
            if (expanded && sources == null)
              setState(() => sources = sourceReferences(widget.value));
          },
          children: [
            if (sources != null) ...[
              if (sources!.isEmpty) const Text('此部分没有可展开的导入来源。'),
              for (final s in sources!.skip(offset).take(30))
                SourceEvidence(widget.app, s,
                    key: ValueKey(s['row_id']), shopId: widget.shopId),
              Wrap(spacing: 12, children: [
                if (offset > 0)
                  TextButton(
                      onPressed: () => setState(() => offset -= 30),
                      child: const Text('上一页来源')),
                if (offset + 30 < sources!.length)
                  TextButton(
                      onPressed: () => setState(() => offset += 30),
                      child: const Text('下一页来源')),
              ]),
            ],
          ]);
}

class ProductEvidence extends StatelessWidget {
  const ProductEvidence(this.app, this.product, {super.key});
  final AppState app;
  final Json product;
  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        FactLine('SKU', product['sku']),
        FactLine('商品名称', product['name']),
        FactLine('完整参数', product['facts']),
        EvidenceSources(app, product),
      ]);
}

class ListingComparison extends StatelessWidget {
  const ListingComparison(this.before, this.after, {super.key});
  final Json before, after;
  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const SectionTitle('版本差异'),
        for (final e in const {'title': '标题', 'description': '描述'}.entries) ...[
          Text('${e.value} · ${before[e.key] == after[e.key] ? '保持原值' : '有变更'}',
              style: Theme.of(context).textTheme.titleSmall),
          FactLine('原值', before[e.key] ?? '无'),
          FactLine('新值', after[e.key] ?? '无'),
        ],
      ]);
}

class PolicyEvidence extends StatelessWidget {
  const PolicyEvidence(this.policy, {super.key});
  final Json policy;
  @override
  Widget build(BuildContext context) {
    final data = mapValue(policy['data']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      FactLine('政策',
          '#${policy['id']} · ${data['title'] ?? '内容已清除'} · v${policy['number']}'),
      FactLine('适用范围',
          '${data['market']} · ${data['channel']} · ${data['language']} · ${data['data_identity']}'),
      FactLine('主题 / 状态',
          '${data['topic']} · ${policy['availability'] ?? policy['status']}'),
      FactLine('全文', data['text']),
      FactLine('出处', data['source']),
      FactLine('来源版本', data['source_version']),
      FactLine('出处已核对', data['source_confirmed']),
      FactLine('有效区间',
          '${data['valid_from']} 至 ${data['valid_until'] ?? '长期'}（结束不含）'),
    ]);
  }
}

class SupportEvidence extends StatelessWidget {
  const SupportEvidence(this.app, this.snapshot, {super.key});
  final AppState app;
  final Json snapshot;
  @override
  Widget build(BuildContext context) {
    final message = mapValue(snapshot['message']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      FactLine('客户消息', message['body']),
      FactLine('消息语言 / 渠道', '${message['language']} · ${message['channel']}'),
      FactLine('订单关联已人工核验', snapshot['order_verified']),
      for (final order in rows(snapshot['orders']))
        FactLine('订单 / 行 / SKU',
            '${order['order_id']} / ${order['line_id']} / ${order['sku']} · ${order['status']} · ${order['fulfillment_status']}'),
      FactLine('识别诉求', words(snapshot['intents'])),
      FactLine('人工接管原因', words(snapshot['reasons'])),
      FactLine('交接摘要', snapshot['handoff_summary']),
      FactLine('候选全文', snapshot['reply']),
      if (snapshot['model_facts'] != null)
        FactLine('模型引用事实', words(snapshot['model_facts'])),
      for (final p in rows(snapshot['policies']))
        ExpansionTile(
            title: Text('政策 #${p['id']}'), children: [PolicyEvidence(p)]),
      EvidenceSources(app, snapshot),
    ]);
  }
}

class AnalysisEvidence extends StatefulWidget {
  const AnalysisEvidence(this.app, this.result, {super.key, this.shopId});
  final AppState app;
  final Json result;
  final int? shopId;
  @override
  State<AnalysisEvidence> createState() => _AnalysisEvidenceState();
}

class _AnalysisEvidenceState extends State<AnalysisEvidence> {
  int skuPage = 0, linePage = 0;
  AppState get app => widget.app;
  Json get result => widget.result;
  @override
  void didUpdateWidget(covariant AnalysisEvidence old) {
    super.didUpdateWidget(old);
    if (!identical(old.result, widget.result)) {
      skuPage = 0;
      linePage = 0;
    }
  }

  Widget pages(String title, int count, int page, void Function(int) change) =>
      Wrap(
          spacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text('$title · 共 $count 项 · 第 ${page ~/ 50 + 1} 页'),
            if (page > 0)
              TextButton(
                  onPressed: () => setState(() => change(page - 50)),
                  child: const Text('上一页')),
            if (page + 50 < count)
              TextButton(
                  onPressed: () => setState(() => change(page + 50)),
                  child: const Text('下一页')),
          ]);
  List<Widget> metrics(Json value) => [
        FactLine('订单行 / 销量',
            '${value['line_count']} / ${value['purchased_quantity']}'),
        for (final e in const {
          'sales': '销售额',
          'cost': '成本',
          'gross_profit': '商品毛利',
          'margin_percent': '毛利率 %',
          'known_sales_subtotal': '已知销售小计',
          'known_cost_subtotal': '已知成本小计',
          'known_gross_subtotal': '已知毛利小计',
          'sales_known_lines': '销售已知行数',
          'cost_known_lines': '成本已知行数',
          'gross_known_lines': '毛利已知行数'
        }.entries)
          FactLine(e.value, value[e.key])
      ];
  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const SectionTitle('金额与计算依据'),
        FactLine('币种', mapValue(result['scope'])['currency']),
        FactLine('计算公式', result['formula']),
        FactLine('成本口径', result['cost_basis']),
        FactLine('费用缺口', words(result['fee_gaps'])),
        FactLine('数据提醒', words(result['warnings'])),
        FactLine('结论', result['answer']),
        FactLine('完整排行可用', result['ranking_available']),
        ...metrics(mapValue(result['summary'])),
        pages(
            'SKU 指标', rows(result['skus']).length, skuPage, (v) => skuPage = v),
        for (final sku in rows(result['skus']).skip(skuPage).take(50))
          ExpansionTile(
              title: Text('SKU ${sku['sku']}'), children: metrics(sku)),
        pages('订单行依据', rows(result['lines']).length, linePage,
            (v) => linePage = v),
        for (final line in rows(result['lines']).skip(linePage).take(50))
          ExpansionTile(
              title: Text(
                  '${line['order_id']} / ${line['line_id']} · ${line['sku']}'),
              subtitle: Text(line['included'] == true ? '计入统计' : '未计入统计'),
              children: [
                for (final e in const {
                  'ordered_at': '订单时间',
                  'status': '订单状态',
                  'currency': '币种',
                  'quantity': '数量',
                  'unit_price': '单价',
                  'discount': '折扣',
                  'refund': '退款',
                  'sales': '销售额',
                  'unit_cost': '单位成本',
                  'cost': '成本',
                  'gross_profit': '商品毛利'
                }.entries)
                  FactLine(e.value, line[e.key]),
                FactLine('缺口', words(line['gaps'])),
                if (line['historical_cost'] != null) ...[
                  FactLine('历史成本记录',
                      '#${line['historical_cost']['id']} · v${line['historical_cost']['version']}'),
                  FactLine('卖家成本依据', line['historical_cost']['evidence_ref']),
                  FactLine('依据时间', line['historical_cost']['evidence_at']),
                ],
                EvidenceSources(app, line, shopId: widget.shopId),
              ]),
      ]);
}
