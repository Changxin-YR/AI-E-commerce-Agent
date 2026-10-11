import '../../core/business_time.dart';
import '../../ui/business_time_fields.dart';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/business_navigation.dart';
import '../../ui/business_widgets.dart';
import '../../ui/common.dart';
import '../../ui/content_evidence.dart';
import '../imports/import_repository.dart';

class OverviewPage extends StatefulWidget {
  const OverviewPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<OverviewPage> createState() => _OverviewPageState();
}

class _OverviewPageState extends BusinessPageState<OverviewPage> {
  final start = TextEditingController(),
      end = TextEditingController(),
      compareStart = TextEditingController(),
      compareEnd = TextEditingController(),
      zone = TextEditingController(),
      age = TextEditingController(text: '24'),
      quantity = TextEditingController(text: '1'),
      margin = TextEditingController(text: '20');
  final shopIds = <int>{}, currencies = <String>{};
  String identity = 'user_import', platform = '', market = '';
  bool customCompare = false, stale = false;
  Json? result, saved;
  List<Json> history = [];
  int? cursor;
  String? requestId;
  List<TextEditingController> get controllers =>
      [start, end, compareStart, compareEnd, zone, age, quantity, margin];
  @override
  void initState() {
    super.initState();
    zone.text = '${widget.app.shop?['timezone'] ?? 'Asia/Shanghai'}';
    final today = BusinessTime.inZone(DateTime.now().toUtc(), zone.text);
    end.text = BusinessTime.day(today);
    start.text = BusinessTime.day(
        DateTime.utc(today.year, today.month, today.day)
            .subtract(const Duration(days: 7)));
    shopIds.addAll(widget.app.shops.take(20).map((s) => s['id'] as int));
    for (final c in controllers) {
      c.addListener(invalidate);
    }
    load(initial: true);
  }

  @override
  void dispose() {
    for (final c in controllers) {
      c.dispose();
    }
    super.dispose();
  }

  void invalidate() {
    if (mounted) {
      setState(() {
        result = null;
        saved = null;
        stale = false;
        requestId = null;
      });
    }
  }

  DateTime date(String value) {
    final parsed = DateTime.tryParse('${value.trim()}T00:00:00Z');
    if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value.trim()) ||
        parsed == null ||
        parsed.toIso8601String().substring(0, 10) != value.trim()) {
      throw const FormatException('请填写 YYYY-MM-DD 形式的有效业务日期。');
    }
    return parsed;
  }

  String day(DateTime value) => value.toIso8601String().substring(0, 10);
  Future<void> preset(int days) => perform(() async {
        final to = date(end.text);
        start.text = day(to.subtract(Duration(days: days)));
      });
  Json payload() {
    final from = date(start.text), to = date(end.text);
    final span = to.difference(from).inDays;
    if (span < 1 || span > 366 || shopIds.isEmpty || shopIds.length > 20) {
      throw const FormatException('请选择 1–20 家店铺和 1–366 天的时间窗。');
    }
    final a = int.tryParse(age.text), q = int.tryParse(quantity.text);
    if (a == null ||
        a < 1 ||
        a > 720 ||
        q == null ||
        q < 1 ||
        q > 1000000 ||
        !RegExp(r'^-?\d+(\.\d{1,2})?$').hasMatch(margin.text) ||
        num.parse(margin.text) < -1000 ||
        num.parse(margin.text) > 100) {
      throw const FormatException('请核对库存小时数、最低销量与毛利率阈值。');
    }
    return {
      'shop_ids': shopIds.toList(),
      'start_date': day(from),
      'end_date': day(to),
      'timezone': zone.text.trim(),
      'data_identity': identity,
      'currencies': currencies.toList(),
      'max_age_hours': a,
      'min_quantity': q,
      'max_margin_percent': margin.text,
      'comparison_start': customCompare ? day(date(compareStart.text)) : null,
      'comparison_end': customCompare ? day(date(compareEnd.text)) : null
    };
  }

  Future<void> readHistory({bool more = false}) async {
    final page = object(await widget.app.api.get('/overview/reports',
        query: more && cursor != null ? {'before': cursor} : {}));
    if (mounted) {
      history =
          more ? [...history, ...rows(page['items'])] : rows(page['items']);
      cursor = page['next_cursor'] as int?;
    }
  }

  void adopt(Json report) {
    saved = report;
    result = report['snapshot'] == null ? null : object(report['snapshot']);
    stale = report['status'] != 'current';
    requestId = null;
  }

  Future<void> load({bool initial = false}) => perform(() async {
        await readHistory();
        if (!mounted) return;
        final id = initial
            ? int.tryParse(widget.query['report'] ?? '')
            : saved?['id'] as int?;
        if (id != null) {
          final report =
              object(await widget.app.api.get('/overview/reports/$id'));
          if (mounted) adopt(report);
        } else if (result != null) {
          final current = result!;
          for (final shop in rows(current['shops'])) {
            final revision = await widget.app.api
                .get('/shops/${shop['shop_id']}/analytics/revision');
            if (!mounted) return;
            if (revision != shop['source_revision']) stale = true;
          }
          if (current['valid_until'] != null &&
              !DateTime.parse('${current['valid_until']}')
                  .isAfter(DateTime.now().toUtc())) {
            stale = true;
          }
          if (stale) {
            result = null;
            success = '来源或库存时效已变化，请重新生成。';
          }
        }
      });
  Future<void> calculate({Json? scope}) => perform(() async {
        final value = object(await widget.app.api
            .post('/overview/calculate', scope ?? payload()));
        if (mounted) {
          result = value;
          saved = null;
          stale = false;
          requestId = newRequestId();
        }
      });
  Future<void> save() => perform(() async {
        requestId ??= newRequestId();
        final value = object(await widget.app.api.post('/overview/reports', {
          'request_id': requestId,
          'scope': result!['scope'],
          'expected_revisions': {
            for (final s in rows(result!['shops']))
              '${s['shop_id']}': s['source_revision']
          },
        }));
        if (mounted) {
          adopt(value);
          await readHistory();
        }
      }, message: '跨店摘要已保存，库存按保存时刻再次核验。');
  Future<void> inspect(int id) => perform(() async {
        final value = object(await widget.app.api.get('/overview/reports/$id'));
        if (mounted) adopt(value);
      });
  Future<void> clear() async {
    if (!await confirmAction(
        context, '清除摘要 #${saved!['id']}', '摘要正文与来源依赖将被清除，保留范围、状态和审计记录。')) {
      return;
    }
    await perform(() async {
      final value = object(await widget.app.api
          .post('/overview/reports/${saved!['id']}/clear', {'confirm': true}));
      if (mounted) {
        adopt(value);
        await readHistory();
      }
    }, message: '摘要正文已清除。');
  }

  Widget period(Json value, String name, int shopId) =>
      ExpansionTile(title: Text(name), children: [
        FactLine('订单数 / 待履约订单',
            '${value['orders'] ?? '未知'} / ${value['pending_orders'] ?? '未知'}'),
        FactLine('退款 / 已知退款 / 已知行数',
            '${value['refunds'] ?? '未知'} / ${value['known_refunds']} / ${value['refund_known_lines']}'),
        FactLine('未知履约行数', value['unknown_fulfillment_lines']),
        FactLine('购买数量前五 SKU', words(value['top_skus'])),
        AnalysisEvidence(widget.app, object(value['analysis']), shopId: shopId),
        EvidenceSources(widget.app, value['pending_sources'], shopId: shopId),
      ]);
  void filterShops() {
    shopIds.clear();
    final today = BusinessTime.inZone(DateTime.now().toUtc(), zone.text);
    end.text = BusinessTime.day(today);
    start.text = BusinessTime.day(
        DateTime.utc(today.year, today.month, today.day)
            .subtract(const Duration(days: 7)));
    shopIds.addAll(widget.app.shops
        .where((s) =>
            (platform.isEmpty || s['platform'] == platform) &&
            (market.isEmpty || s['market'] == market))
        .take(20)
        .map((s) => s['id'] as int));
    invalidate();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('跨店经营总览')),
      body: RefreshIndicator(
          onRefresh: load,
          child: PageBody(children: [
            ...feedback,
            const Text('按业务时区的日历日期统计，结束日不计入。各币种分别汇总，保留未知项。'),
            ExpansionTile(
                title: const Text('店铺与统计范围'),
                initiallyExpanded: result == null && saved == null,
                children: [
                  ChoiceField(
                      '筛选平台',
                      platform,
                      {
                        '': '全部平台',
                        for (final s in widget.app.shops)
                          '${s['platform']}': '${s['platform']}'
                      },
                      busy
                          ? null
                          : (v) => setState(() {
                                platform = v;
                                filterShops();
                              })),
                  ChoiceField(
                      '筛选市场',
                      market,
                      {
                        '': '全部市场',
                        for (final s in widget.app.shops)
                          '${s['market']}': '${s['market']}'
                      },
                      busy
                          ? null
                          : (v) => setState(() {
                                market = v;
                                filterShops();
                              })),
                  for (final s in widget.app.shops.where((s) =>
                      (platform.isEmpty || s['platform'] == platform) &&
                      (market.isEmpty || s['market'] == market)))
                    CheckboxListTile(
                        title: Text('${s['name']} · ${s['currency']}'),
                        value: shopIds.contains(s['id']),
                        onChanged: busy
                            ? null
                            : (v) => setState(() {
                                  if (v!) {
                                    shopIds.add(s['id'] as int);
                                  } else {
                                    shopIds.remove(s['id']);
                                  }
                                  invalidate();
                                })),
                  ChoiceField(
                      '数据身份',
                      identity,
                      importIdentities,
                      busy
                          ? null
                          : (v) => setState(() {
                                identity = v;
                                invalidate();
                              })),
                  BusinessZoneField('业务时区', zone, enabled: !busy),
                  BusinessDateField('开始日期', start, enabled: !busy),
                  BusinessDateField('结束日期（不含此日）', end, enabled: !busy),
                  Wrap(spacing: 12, children: [
                    for (final e
                        in const {1: '日摘要', 7: '周摘要', 30: '30 日摘要'}.entries)
                      OutlinedButton(
                          onPressed: busy ? null : () => preset(e.key),
                          child: Text(e.value)),
                  ]),
                  const Text('快捷摘要以填写的结束日期为截止日，向前取 1、7 或 30 天。'),
                  SwitchListTile(
                      value: customCompare,
                      onChanged: busy
                          ? null
                          : (v) => setState(() {
                                customCompare = v;
                                invalidate();
                              }),
                      title: const Text('自选对比区间'),
                      subtitle: const Text('关闭时使用紧邻本期之前的等长区间')),
                  if (customCompare) ...[
                    BusinessDateField('对比开始日期', compareStart, enabled: !busy),
                    BusinessDateField('对比结束日期', compareEnd, enabled: !busy),
                  ],
                  const Text('币种（不选则读取数据中的全部币种）'),
                  Wrap(spacing: 8, children: [
                    for (final c in const [
                      'USD',
                      'CNY',
                      'EUR',
                      'GBP',
                      'JPY',
                      'CAD',
                      'AUD',
                      'HKD',
                      'SGD'
                    ])
                      FilterChip(
                          label: Text(c),
                          selected: currencies.contains(c),
                          onSelected: busy
                              ? null
                              : (v) => setState(() {
                                    if (v) {
                                      currencies.add(c);
                                    } else {
                                      currencies.remove(c);
                                    }
                                    invalidate();
                                  })),
                  ]),
                  FormInput('库存有效小时数', age,
                      enabled: !busy, type: TextInputType.number),
                  FormInput('最低销量', quantity,
                      enabled: !busy, type: TextInputType.number),
                  FormInput('毛利率上限 %', margin,
                      enabled: !busy, type: TextInputType.number),
                  FilledButton(
                      onPressed: busy ? null : () => calculate(),
                      child: const Text('生成跨店摘要')),
                ]),
            if (saved != null) ...[
              SectionTitle('摘要 #${saved!['id']} · ${saved!['status']}'),
              FactLine('保存时间', saved!['created_at']),
              Wrap(spacing: 12, children: [
                OutlinedButton(
                    onPressed: busy
                        ? null
                        : () => calculate(scope: object(saved!['scope'])),
                    child: const Text('按原范围重算')),
                if (saved!['status'] != 'cleared')
                  TextButton(
                      onPressed: busy ? null : clear,
                      child: const Text('清除摘要正文')),
              ]),
            ],
            if (stale) const Notice('此报告依赖来源或库存时效已变化，请重新生成。'),
            if (result != null) ...[
              FactLine(
                  '本期 / 对比',
                  '${result!['scope']['start_date']} → ${result!['scope']['end_date']} / '
                      '${result!['scope']['comparison_start']} → ${result!['scope']['comparison_end']}'),
              FactLine('计算时间 / 有效至',
                  '${result!['calculated_at']} / ${result!['valid_until'] ?? '按来源版本判断'}'),
              for (final total in rows(result!['totals'])) ...[
                SectionTitle('${total['currency']} 汇总'),
                FactLine('覆盖店铺', words(total['shop_ids'])),
                for (final e in const {
                  'sales': '销售额',
                  'known_sales': '已知销售小计',
                  'comparison_sales': '对比销售额',
                  'sales_change': '销售变化',
                  'sales_change_percent': '销售变化率 %',
                  'gross_profit': '商品毛利',
                  'known_gross_profit': '已知毛利小计',
                  'refunds': '退款',
                  'known_refunds': '已知退款小计',
                  'observed_orders': '观测订单数'
                }.entries)
                  FactLine(e.value, total[e.key]),
                FactLine('覆盖说明', words(total['warnings'])),
              ],
              const SectionTitle('经营摘要'),
              for (final line in result!['summary'] as List)
                Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Text('$line')),
              FactLine('口径与未获取项', words(result!['limitations'])),
              for (final shop in rows(result!['shops']))
                ExpansionTile(
                    title: Text(
                        '${shop['shop_name']} · ${shop['platform']} · ${shop['market']}'),
                    children: [
                      FactLine('来源版本', shop['source_revision']),
                      for (final group in rows(shop['currencies'])) ...[
                        SectionTitle('${group['currency']}'),
                        FactLine('销售变化 / 变化率',
                            '${group['sales_change'] ?? '未知'} / ${group['sales_change_percent'] ?? '未知'}%'),
                        period(object(group['current']), '本期金额与订单依据',
                            shop['shop_id'] as int),
                        period(object(group['comparison']), '对比期金额与订单依据',
                            shop['shop_id'] as int),
                      ],
                      FactLine('低库存数 / 未知数',
                          '${shop['inventory_low'] ?? '未知'} / ${shop['inventory_unknown']}'),
                      for (final stock in rows(shop['inventory']))
                        FactLine('库存 ${stock['sku']}',
                            '${stock['available']} / 阈值 ${stock['safety_threshold']} · ${stock['status']} · ${stock['reason']} · ${stock['snapshot_at']}'),
                      FactLine('消息数', shop['message_count']),
                      for (final msg in rows(shop['messages']))
                        FactLine('消息 ${msg['message_id']}',
                            '${msg['channel']} · ${msg['sent_at']}'),
                      for (final task in rows(shop['tasks']))
                        TextButton(
                            onPressed: () => openBusinessPath(
                                    context, widget.app, '/', {
                                  'shop': '${shop['shop_id']}',
                                  'task': '${task['id']}'
                                }),
                            child: Text(
                                '待办 #${task['id']} · ${task['kind']} · ${task['status']} · ${task['source_status']}')),
                      if (shop['tasks_has_more'] == true)
                        const Text('还有更多待办，切换到该店后可在待办入口查看。'),
                      EvidenceSources(widget.app, shop,
                          shopId: shop['shop_id'] as int),
                    ]),
              FilledButton(
                  onPressed: busy || stale ? null : save,
                  child: const Text('保存持久摘要')),
            ],
            const SectionTitle('历史摘要'),
            OutlinedButton(
                onPressed: busy ? null : load, child: const Text('刷新状态')),
            if (history.isEmpty && !busy) const Text('暂无已保存摘要。'),
            for (final h in history)
              ListTile(
                  title: Text('#${h['id']} · ${h['status']}'),
                  subtitle: Text(
                      '${h['scope']['start_date']} → ${h['scope']['end_date']} · ${h['scope']['timezone']}'),
                  onTap: busy ? null : () => inspect(h['id'] as int)),
            if (cursor != null)
              TextButton(
                  onPressed: busy
                      ? null
                      : () => perform(() => readHistory(more: true)),
                  child: const Text('加载更早摘要')),
          ])));
}
