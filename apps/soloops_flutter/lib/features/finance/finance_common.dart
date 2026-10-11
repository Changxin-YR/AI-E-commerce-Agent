import '../../ui/business_time_fields.dart';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../ui/business_widgets.dart';
import '../imports/import_repository.dart';

const expenseCategories = {
  'shipping': '物流',
  'packaging': '包装',
  'storage': '仓储',
  'platform': '平台服务',
  'advertising': '广告',
  'tax': '税费',
  'other': '其他费用'
};
const recordStatuses = {
  'active': '当前有效',
  'stale': '来源变化 · 待重核',
  'withdrawn': '已撤销',
  'cleared': '正文已清除'
};
const mappingStatuses = {
  'mapped': '已按规则分类 · 业务待核',
  'unmapped': '未匹配规则',
  'ambiguous': '重复凭据或规则',
  'currency_mismatch': '币种不一致',
  'category_conflict': '与人工费用类别冲突'
};
const entryTypes = {
  'sale': '账单销售款',
  'refund': '账单退款',
  'fee': '账单费用',
  'payout': '平台记载回款 · 到账待核'
};
const comparisonStatuses = {
  'matched': '编号与金额一致',
  'amount_difference': '金额差异',
  'statement_only': '仅账单有记录',
  'expense_only': '仅人工费用有记录',
  'receipt_only': '仅到账登记有记录',
  'ambiguous': '重复编号 · 待核',
  'currency_mismatch': '币种不一致',
  'missing_reference': '缺关联编号',
  'pending': '待核实'
};

class FinanceScope extends ChangeNotifier {
  FinanceScope(AppState app, [Map<String, String> query = const {}]) {
    final now = DateTime.now().toUtc();
    identity = query['identity'] ?? 'user_import';
    channel = query['channel'] ?? 'generic';
    start.text = query['start_at'] ??
        now.subtract(const Duration(days: 30)).toIso8601String();
    end.text = query['end_at'] ?? now.toIso8601String();
    zone.text =
        query['timezone'] ?? '${app.shop?['timezone'] ?? 'Asia/Shanghai'}';
    for (final c in [start, end, zone]) {
      c.addListener(notifyListeners);
    }
  }
  String identity = 'user_import', channel = 'generic';
  final start = TextEditingController(),
      end = TextEditingController(),
      zone = TextEditingController();
  Json get partition => {'data_identity': identity, 'channel': channel};
  Json input() {
    final from = awareDate(start.text, '开始时间', required: true)!,
        to = awareDate(end.text, '结束时间', required: true)!;
    final duration = DateTime.parse(to).difference(DateTime.parse(from));
    if (duration <= Duration.zero || duration > const Duration(days: 366)) {
      throw const FormatException('查询区间须大于零且不超过 366 天。');
    }
    if (zone.text.trim().isEmpty) throw const FormatException('请填写业务时区。');
    return {
      ...partition,
      'start_at': from,
      'end_at': to,
      'timezone': zone.text.trim()
    };
  }

  void restore(Json value) {
    identity = '${value['data_identity']}';
    channel = '${value['channel']}';
    start.text = '${value['start_at']}';
    end.text = '${value['end_at']}';
    zone.text = '${value['timezone']}';
    notifyListeners();
  }

  void select({String? dataIdentity, String? sourceChannel}) {
    identity = dataIdentity ?? identity;
    channel = sourceChannel ?? channel;
    notifyListeners();
  }

  @override
  void dispose() {
    start.dispose();
    end.dispose();
    zone.dispose();
    super.dispose();
  }
}

class FinanceScopeFields extends StatelessWidget {
  const FinanceScopeFields(this.scope,
      {super.key, this.enabled = true, this.partitionOnly = false});
  final FinanceScope scope;
  final bool enabled, partitionOnly;
  @override
  Widget build(BuildContext context) => Column(children: [
        ChoiceField('数据身份', scope.identity, importIdentities,
            enabled ? (v) => scope.select(dataIdentity: v) : null),
        ChoiceField('渠道', scope.channel, importChannels,
            enabled ? (v) => scope.select(sourceChannel: v) : null),
        if (!partitionOnly) ...[
          BusinessDateTimeField('开始时间', scope.start,
              zone: scope.zone, enabled: enabled),
          BusinessDateTimeField('结束时间（不含终点）', scope.end,
              zone: scope.zone, enabled: enabled),
          BusinessZoneField('业务时区', scope.zone, enabled: enabled),
        ]
      ]);
}

/// Local pagination bounds widgets while keeping every returned row accessible.
class FinanceRows extends StatefulWidget {
  const FinanceRows(this.items,
      {super.key, required this.builder, this.pageSize = 30});
  final List<Json> items;
  final Widget Function(Json) builder;
  final int pageSize;
  @override
  State<FinanceRows> createState() => _FinanceRowsState();
}

class _FinanceRowsState extends State<FinanceRows> {
  int page = 0;
  @override
  void didUpdateWidget(covariant FinanceRows old) {
    super.didUpdateWidget(old);
    if (page * widget.pageSize >= widget.items.length) page = 0;
  }

  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (widget.items.isEmpty) const Text('当前范围没有记录。'),
        ...widget.items
            .skip(page * widget.pageSize)
            .take(widget.pageSize)
            .map(widget.builder),
        if (widget.items.length > widget.pageSize)
          Wrap(
              spacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                TextButton(
                    onPressed: page == 0 ? null : () => setState(() => page--),
                    child: const Text('上一页')),
                Text('第 ${page + 1} 页 · 共 ${widget.items.length} 条'),
                TextButton(
                    onPressed:
                        (page + 1) * widget.pageSize >= widget.items.length
                            ? null
                            : () => setState(() => page++),
                    child: const Text('下一页'))
              ])
      ]);
}
