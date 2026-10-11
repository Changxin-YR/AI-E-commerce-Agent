import 'business_time_fields.dart';
import 'package:flutter/material.dart';
import '../core/app_state.dart';
import '../features/imports/import_repository.dart';
import 'business_widgets.dart';
import 'common.dart';

/// The API owns business timezone interpretation. Timestamps keep an explicit offset.
class BusinessScope extends ChangeNotifier {
  BusinessScope(AppState app, [Map<String, String> query = const {}]) {
    final now = DateTime.now().toUtc();
    start.text = query['start_at'] ??
        now.subtract(const Duration(days: 7)).toIso8601String();
    end.text = query['end_at'] ?? now.toIso8601String();
    zone.text =
        query['timezone'] ?? '${app.shop?['timezone'] ?? 'Asia/Shanghai'}';
    currency.text = query['currency'] ?? '${app.shop?['currency'] ?? 'USD'}';
    identity = query['identity'] ?? 'user_import';
    channel = query['channel'] ?? 'generic';
    quantity.text = query['min_quantity'] ?? '1';
    margin.text = query['max_margin_percent'] ?? '20';
    age.text = query['max_age_hours'] ?? '24';
    for (final c in controllers) {
      c.addListener(notifyListeners);
    }
  }
  final start = TextEditingController(),
      end = TextEditingController(),
      zone = TextEditingController(),
      currency = TextEditingController(),
      quantity = TextEditingController(text: '1'),
      margin = TextEditingController(text: '20'),
      age = TextEditingController(text: '24');
  String identity = 'user_import', channel = 'generic';
  Json? rule;
  bool _closed = false;
  List<TextEditingController> get controllers =>
      [start, end, zone, currency, quantity, margin, age];
  void select({String? dataIdentity, String? sourceChannel}) {
    identity = dataIdentity ?? identity;
    channel = sourceChannel ?? channel;
    rule = null;
    notifyListeners();
  }

  Future<void> readRule(AppState app) async {
    final requestedIdentity = identity, requestedChannel = channel;
    final value = object(await app.api.get(app.shopPath('/business-rules'),
        query: {'channel': channel, 'data_identity': identity}));
    if (_closed ||
        requestedIdentity != identity ||
        requestedChannel != channel) {
      return;
    }
    rule = value;
    final values = object(value['values']);
    age.text = '${values['max_age_hours']}';
    quantity.text = '${values['min_quantity']}';
    margin.text = '${values['max_margin_percent']}';
    notifyListeners();
  }

  void restore(Json value) {
    start.text = '${value['start_at']}';
    end.text = '${value['end_at']}';
    zone.text = '${value['timezone']}';
    currency.text = '${value['currency']}';
    identity = '${value['data_identity']}';
    channel = '${value['channel'] ?? 'generic'}';
    quantity.text = '${value['min_quantity'] ?? 1}';
    margin.text = '${value['max_margin_percent'] ?? 20}';
    age.text = '${value['max_age_hours'] ?? 24}';
    rule = null;
    notifyListeners();
  }

  Json payload({bool sevenDays = false, bool requireRule = true}) {
    final to = awareDate(end.text, '结束时间', required: true)!;
    final from = sevenDays
        ? DateTime.parse(to)
            .toUtc()
            .subtract(const Duration(days: 7))
            .toIso8601String()
        : awareDate(start.text, '开始时间', required: true)!;
    final span = DateTime.parse(to).difference(DateTime.parse(from));
    if (span <= Duration.zero || span > const Duration(days: 366)) {
      throw const FormatException('统计时间窗须大于 0 且不超过 366 天。');
    }
    final q = int.tryParse(quantity.text), a = int.tryParse(age.text);
    if (q == null || q < 1 || q > 1000000 || a == null || a < 1 || a > 720) {
      throw const FormatException('最低销量须为正整数，库存有效期须为 1–720 小时。');
    }
    if (!RegExp(r'^-?\d+(\.\d{1,2})?$').hasMatch(margin.text.trim())) {
      throw const FormatException('请填写有效的毛利百分比。');
    }
    if (num.parse(margin.text) < -1000 || num.parse(margin.text) > 100) {
      throw const FormatException('毛利百分比须为 -1000 至 100。');
    }
    if (requireRule && rule == null) {
      throw const FormatException('请先读取当前范围的经营规则。');
    }
    return {
      'start_at': from,
      'end_at': to,
      'timezone': zone.text.trim(),
      'currency': currency.text.trim().toUpperCase(),
      'data_identity': identity,
      'channel': channel,
      'intent': 'low_margin',
      'cost_mode': 'current_estimate',
      'min_quantity': q,
      'max_margin_percent': margin.text.trim(),
      'max_age_hours': a,
      'rule_revision_id': rule?['version'] ?? 0
    };
  }

  @override
  void dispose() {
    _closed = true;
    for (final c in controllers) {
      c.dispose();
    }
    super.dispose();
  }
}

class ScopeFields extends StatelessWidget {
  const ScopeFields(this.scope,
      {super.key,
      this.enabled = true,
      this.sevenDays = false,
      this.operation = true,
      required this.onReadRule});
  final BusinessScope scope;
  final bool enabled, sevenDays, operation;
  final VoidCallback onReadRule;
  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        ChoiceField('数据身份', scope.identity, importIdentities,
            enabled ? (v) => scope.select(dataIdentity: v) : null),
        ChoiceField(
            '渠道',
            scope.channel,
            {if (!operation) '': '全部渠道', ...importChannels},
            enabled ? (v) => scope.select(sourceChannel: v) : null),
        BusinessZoneField('业务时区', scope.zone, enabled: enabled),
        FormInput('币种', scope.currency, enabled: enabled),
        if (!sevenDays)
          BusinessDateTimeField('开始时间', scope.start,
              zone: scope.zone, enabled: enabled),
        BusinessDateTimeField('结束时间（不含终点）', scope.end,
            zone: scope.zone, enabled: enabled),
        if (sevenDays) const Text('开始时间自动取结束时间前精确 7 天。'),
        FormInput('最低销量', scope.quantity,
            enabled: enabled, type: TextInputType.number),
        FormInput('低毛利率上限 %', scope.margin,
            enabled: enabled, type: TextInputType.number),
        if (operation)
          FormInput('库存有效小时数', scope.age,
              enabled: enabled, type: TextInputType.number),
        if (operation && scope.rule != null)
          FactLine('采用规则',
              '#${scope.rule!['version']} · ${scope.rule!['active'] == true ? '已启用' : '默认值'}'),
        if (operation)
          OutlinedButton(
              onPressed: enabled ? onReadRule : null,
              child: const Text('读取当前经营规则')),
      ]);
}
