import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/business_navigation.dart';
import '../../ui/business_widgets.dart';
import '../../ui/business_scope.dart';
import '../../ui/content_evidence.dart';
import '../../ui/common.dart';

import 'order_cost_page.dart';

class AnalyticsPage extends StatefulWidget {
  const AnalyticsPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<AnalyticsPage> createState() => _AnalyticsPageState();
}

class _AnalyticsPageState extends BusinessPageState<AnalyticsPage> {
  late final scope = BusinessScope(widget.app, widget.query);
  late String costMode = widget.query['cost_mode'] ?? 'current_estimate';
  String intent = 'summary';
  final question = TextEditingController(text: '查看销售与已知毛利');
  List<Json> history = [];
  Json? selected, result;
  bool outdated = false;
  int lineOffset = 0;
  String path(String suffix) => widget.app.shopPath('/analytics$suffix');
  @override
  void initState() {
    super.initState();
    if (!widget.query.containsKey('channel')) scope.channel = '';
    scope.addListener(invalidate);
    question.addListener(invalidate);
    load(initial: true);
  }

  @override
  void dispose() {
    scope.dispose();
    question.dispose();
    super.dispose();
  }

  void invalidate() {
    if (mounted) {
      setState(() {
        selected = null;
        result = null;
        outdated = false;
        lineOffset = 0;
      });
    }
  }

  Json payload() {
    final value = scope.payload(requireRule: false);
    value.remove('rule_revision_id');
    value.remove('max_age_hours');
    value['channel'] = scope.channel.isEmpty ? null : scope.channel;
    value['cost_mode'] = costMode;
    value['intent'] = intent;
    return value;
  }

  Future<void> readHistory() async {
    final value = rows(await widget.app.api.get(path('/saved')));
    if (mounted) history = value;
  }

  void adopt(Json saved) {
    final savedScope = object(saved['scope']);
    scope.restore(savedScope);
    scope.channel = '${savedScope['channel'] ?? ''}';
    costMode = '${savedScope['cost_mode'] ?? 'current_estimate'}';
    intent = '${savedScope['intent']}';
    question.text = const {
          'summary': '查看销售与已知毛利',
          'sales': '销量前五的 SKU',
          'low_margin': '哪些商品销量高但已知毛利低'
        }[intent] ??
        '';
    selected = saved;
    result = saved['snapshot'] == null ? null : object(saved['snapshot']);
    outdated = saved['status'] != 'current';
    lineOffset = 0;
  }

  Future<void> load({bool initial = false}) => perform(() async {
        await readHistory();
        if (!mounted) return;
        final id = initial
            ? int.tryParse(widget.query['analysis'] ?? '')
            : selected?['id'] as int?;
        if (id != null) {
          final saved = object(await widget.app.api.get(path('/saved/$id')));
          if (!mounted) return;
          adopt(saved);
        }
        if (result != null) {
          final revision = await widget.app.api.get(path('/revision'));
          if (mounted) {
            outdated = outdated || revision != result!['source_revision'];
          }
        }
      });
  Future<void> calculate({bool ask = false}) => perform(() async {
        final requested = payload();
        if (ask &&
            (question.text.trim().isEmpty || question.text.length > 200)) {
          throw const FormatException('受控问题须为 1–200 字。');
        }
        final value = object(await widget.app.api.post(
            path(ask ? '/ask' : '/calculate'),
            ask
                ? {'scope': requested, 'question': question.text.trim()}
                : requested));
        if (mounted) {
          result = value;
          selected = null;
          outdated = false;
          lineOffset = 0;
        }
      });
  Future<void> inspect(int id) => perform(() async {
        final saved = object(await widget.app.api.get(path('/saved/$id')));
        if (mounted) adopt(saved);
      });
  Future<void> save() => perform(() async {
        final value = object(await widget.app.api.post(path('/saved'), {
          'scope': result!['scope'],
          'expected_revision': result!['source_revision']
        }));
        if (mounted) {
          adopt(value);
          await readHistory();
        }
      }, message: '分析报告已保存。');
  Future<void> todo(String action) => perform(() async {
        final id = selected!['id'];
        final value = object(await widget.app.api.post(
            path(action == 'create'
                ? '/saved/$id/todo'
                : '/saved/$id/todo/action'),
            action == 'create'
                ? null
                : {
                    'expected_version': selected!['todo']['version'],
                    'action': action
                  }));
        if (mounted) {
          adopt(value);
          await readHistory();
        }
      }, message: '核对待办已保存。');
  Future<void> editCost(int rowId) async {
    await Navigator.push<void>(context,
        MaterialPageRoute(builder: (_) => OrderCostPage(widget.app, rowId)));
    if (mounted) await load();
  }

  @override
  Widget build(BuildContext context) {
    final lines = rows(result?['lines']);
    return Scaffold(
        appBar: AppBar(title: const Text('经营分析')),
        body: RefreshIndicator(
            onRefresh: load,
            child: PageBody(children: [
              ...feedback,
              const Text('按单店、单币种与明确时间窗计算。未知值和缺失费用单独保留。'),
              ChoiceField(
                  '采购成本口径',
                  costMode,
                  const {
                    'current_estimate': '当前商品成本回推估算',
                    'seller_history': '订单行历史成本依据'
                  },
                  busy
                      ? null
                      : (v) => setState(() {
                            costMode = v;
                            invalidate();
                          })),
              ChoiceField(
                  '分析范围',
                  intent,
                  const {
                    'summary': '销售与已知毛利汇总',
                    'sales': '购买数量前五 SKU',
                    'low_margin': '低毛利筛选'
                  },
                  busy
                      ? null
                      : (v) => setState(() {
                            intent = v;
                            invalidate();
                          })),
              ScopeFields(scope,
                  enabled: !busy, operation: false, onReadRule: () {}),
              Wrap(spacing: 12, children: [
                FilledButton(
                    onPressed: busy ? null : () => calculate(),
                    child: const Text('按范围计算')),
                TextButton(
                    onPressed: busy
                        ? null
                        : () => openBusinessPath(context, widget.app,
                            '/imports', {'kind': 'orders'}),
                    child: const Text('导入订单与成本来源')),
              ]),
              FormInput('受控经营问题（最多 200 字）', question, enabled: !busy),
              OutlinedButton(
                  onPressed: busy ? null : () => calculate(ask: true),
                  child: const Text('用本地规则回答')),
              if (scope.channel.isNotEmpty && costMode == 'current_estimate')
                TextButton(
                    onPressed: busy
                        ? null
                        : () {
                            openBusinessPath(context, widget.app, '/agent', {
                              ...widget.query,
                              'mode': 'question',
                              'channel': scope.channel,
                              'identity': scope.identity,
                              'currency': scope.currency.text,
                              'timezone': scope.zone.text,
                              'start_at': scope.start.text,
                              'end_at': scope.end.text,
                            });
                          },
                    child: const Text('进入 AI 经营问数并核对预算')),
              if (outdated) const Notice('来源或历史成本依据已变化，请重新计算后保存新的报告。'),
              if (selected != null) ...[
                SectionTitle(
                    '持久报告 #${selected!['id']} · ${selected!['status']}'),
                FactLine('保存时间', selected!['created_at']),
                if (selected!['snapshot'] == null)
                  const Text('依赖来源已清除，报告内容已擦除。'),
                FilledButton(
                    onPressed: busy ? null : () => calculate(),
                    child: const Text('按此报告范围重新计算')),
                if (selected!['todo'] != null) ...[
                  FactLine('核对待办 #${selected!['todo']['id']}',
                      '${selected!['todo']['title']} · ${selected!['todo']['status']}'),
                  OutlinedButton(
                      onPressed: busy || outdated
                          ? null
                          : () => todo(
                              selected!['todo']['status'] == 'completed'
                                  ? 'reopen'
                                  : 'complete'),
                      child: Text(selected!['todo']['status'] == 'completed'
                          ? '重开核对待办'
                          : '标记核对完成')),
                ] else
                  OutlinedButton(
                      onPressed:
                          busy || outdated || selected!['snapshot'] == null
                              ? null
                              : () => todo('create'),
                      child: const Text('创建关联核对待办')),
              ],
              if (result != null) ...[
                FactLine('结果范围',
                    '${result!['scope']['start_at']} 至 ${result!['scope']['end_at']} · ${result!['scope']['timezone']}'),
                FactLine('来源版本 / 计算版本 / 时间',
                    '${result!['source_revision']} / ${result!['calculation_version']} / ${result!['calculated_at']}'),
                AnalysisEvidence(widget.app, result!),
                FilledButton(
                    onPressed: busy || outdated ? null : save,
                    child: const Text('保存当前分析报告')),
                const SectionTitle('订单行历史成本录入'),
                for (final line in lines.skip(lineOffset).take(50))
                  ListTile(
                      title: Text(
                          '${line['order_id']} / ${line['line_id']} · ${line['sku']}'),
                      subtitle: Text(
                          '当前单位历史成本 ${line['historical_cost']?['unit_cost'] ?? '未登记'} · ${line['currency']}'),
                      trailing: const Icon(Icons.edit_outlined),
                      onTap: busy
                          ? null
                          : () => editCost(line['source']['row_id'] as int)),
                Wrap(spacing: 12, children: [
                  if (lineOffset > 0)
                    TextButton(
                        onPressed: () => setState(() => lineOffset -= 50),
                        child: const Text('上 50 行')),
                  if (lineOffset + 50 < lines.length)
                    TextButton(
                        onPressed: () => setState(() => lineOffset += 50),
                        child: const Text('下 50 行')),
                ]),
              ],
              const SectionTitle('报告历史'),
              OutlinedButton(
                  onPressed: busy ? null : load,
                  child: const Text('刷新报告与来源状态')),
              if (history.isEmpty && !busy) const Text('暂无已保存分析。'),
              for (final h in history)
                ListTile(
                    title: Text(
                        '报告 #${h['id']} · ${h['scope']['currency']} · ${h['status']}'),
                    subtitle: Text(
                        '${h['scope']['start_at']} 至 ${h['scope']['end_at']}'),
                    onTap: busy ? null : () => inspect(h['id'] as int)),
              if (widget.query['return_task'] != null)
                TextButton(
                    onPressed: () => openBusinessPath(context, widget.app, '/',
                        {'task': widget.query['return_task']!}),
                    child: const Text('返回来源待办')),
            ])));
  }
}
