import '../../ui/edit_guard.dart';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/business_navigation.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/finance_inputs.dart';
import '../finance/finance_common.dart';

class BusinessRulesPage extends StatefulWidget {
  const BusinessRulesPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<BusinessRulesPage> createState() => _BusinessRulesPageState();
}

class _BusinessRulesPageState extends BusinessPageState<BusinessRulesPage> {
  late final scope = FinanceScope(widget.app, widget.query);
  final fields = {
    for (final key in [
      'max_age_hours',
      'min_quantity',
      'max_margin_percent',
      'advertising_daily_budget',
      'currency',
      'basis',
      'target_site',
      'warehouse',
      'logistics',
      'brand_voice',
      'support_wording'
    ])
      key: TextEditingController()
  };
  Json? current, selected;
  List<Json> history = [];
  bool confirmed = false, uncertain = false;
  String path(String tail) => widget.app.shopPath('/business-rules$tail');
  @override
  void initState() {
    super.initState();
    scope.addListener(scopeChanged);
    Future.microtask(() => perform(load));
  }

  void scopeChanged() {
    if (mounted) {
      setState(() {
        current = null;
        selected = null;
        history = [];
        confirmed = false;
      });
    }
  }

  void restore(Json value) {
    current = value;
    final values = object(value['values']), notes = object(values['notes']);
    for (final key in fields.keys) {
      fields[key]!.text = '${values[key] ?? notes[key] ?? ''}';
    }
    confirmed = false;
    uncertain = false;
  }

  Future<void> load() async {
    final value =
        object(await widget.app.api.get(path(''), query: scope.partition));
    final list = rows(
        await widget.app.api.get(path('/history'), query: scope.partition));
    if (mounted) {
      setState(() {
        restore(value);
        history = list;
      });
    }
  }

  Json values() => {
        'max_age_hours':
            integerInput(fields['max_age_hours']!.text, '库存有效小时', 1, 720),
        'min_quantity':
            integerInput(fields['min_quantity']!.text, '最低销量', 1, 1000000),
        'max_margin_percent': marginInput(fields['max_margin_percent']!.text),
        'advertising_daily_budget': fields['advertising_daily_budget']!
                .text
                .trim()
                .isEmpty
            ? null
            : decimalInput(fields['advertising_daily_budget']!.text, '广告日预算',
                max: '100000000'),
        'currency':
            requiredText(fields['currency']!.text, '币种', 3).toUpperCase(),
        'basis': requiredText(fields['basis']!.text, '规则依据', 500),
        'automation': 'manual_only',
        'notes': {
          for (final e in const {
            'target_site': 200,
            'warehouse': 200,
            'logistics': 500,
            'brand_voice': 1000,
            'support_wording': 1000
          }.entries)
            e.key: optionalNote(fields[e.key]!.text, e.value)
        }
      };
  String optionalNote(String value, int max) {
    if (value.trim().length > max) throw FormatException('经营备注最多 $max 个字符。');
    return value.trim();
  }

  Future<void> change(String action, {int? version}) async {
    if (current == null) return;
    if (action != 'save' &&
        !await confirmAction(
            context,
            {
              'revoke': '停用经营规则',
              'reset': '重置检查口径',
              'restore': '恢复历史规则'
            }[action]!,
            action == 'restore'
                ? '将历史版本 #$version 作为新的有效规则，后续巡检需重新读取。'
                : '此操作会生成新版本，后续巡检需读取当前规则。')) {
      return;
    }
    await perform(() async {
      final data = {
        ...scope.partition,
        'expected_version': current!['version'],
        'action': action,
        if (action == 'save') 'values': values(),
        if (version != null) 'restore_version': version
      };
      try {
        final value = object(await widget.app.api.post(path(''), data));
        if (mounted) setState(() => restore(value));
        success = '经营规则已更新。';
        final list = rows(
            await widget.app.api.get(path('/history'), query: scope.partition));
        if (mounted) setState(() => history = list);
      } catch (e) {
        uncertain = true;
        confirmed = false;
        rethrow;
      }
    });
  }

  @override
  void dispose() {
    scope.dispose();
    for (final c in fields.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => EditGuard(
      app: widget.app,
      controllers: fields.values.toList(),
      cleanKey: current,
      busy: busy,
      child: Scaffold(
          appBar: AppBar(title: const Text('经营规则与授权')),
          body: PageBody(children: [
            ...feedback,
            FinanceScopeFields(scope, enabled: !busy, partitionOnly: true),
            FilledButton(
                onPressed: busy ? null : () => perform(load),
                child: const Text('读取当前规则与历史')),
            const Text(
                '按店铺、渠道和数据身份使用规则。有效规则的阈值优先，巡检与计划须绑定当前版本；默认或停用时可使用本次输入阈值。'),
            if (uncertain) const Notice('请先回读最新规则，核对上次操作结果后再修改。'),
            if (current != null) ...[
              FactLine('当前版本',
                  '#${current!['version']} · ${current!['active'] == true ? '已启用' : '默认 / 已停用'}'),
              RuleEvidence(current!),
              Form(
                  onChanged: () => setState(() => confirmed = false),
                  child: Column(children: [
                    for (final e in const {
                      'max_age_hours': '库存有效小时（1–720）',
                      'min_quantity': '最低销量（1–1000000）',
                      'max_margin_percent': '低毛利率上限 %',
                      'currency': '预算币种',
                      'basis': '规则依据',
                      'target_site': '目标站点',
                      'warehouse': '仓库说明',
                      'logistics': '物流说明',
                      'brand_voice': '品牌表达',
                      'support_wording': '客服措辞'
                    }.entries)
                      FormInput(e.value, fields[e.key]!,
                          required: false,
                          lines: [
                            'basis',
                            'logistics',
                            'brand_voice',
                            'support_wording'
                          ].contains(e.key)
                              ? 3
                              : 1,
                          enabled: !busy && !uncertain),
                    DecimalField('广告日预算', fields['advertising_daily_budget']!,
                        optional: true,
                        max: '100000000',
                        enabled: !busy && !uncertain),
                    CheckboxListTile(
                        value: confirmed,
                        onChanged: busy || uncertain
                            ? null
                            : (v) => setState(() => confirmed = v ?? false),
                        title: const Text('已核对规则作用范围、阈值、预算与依据')),
                  ])),
              Wrap(spacing: 8, children: [
                FilledButton(
                    onPressed: busy || uncertain || !confirmed
                        ? null
                        : () => change('save'),
                    child: const Text('保存并启用规则')),
                OutlinedButton(
                    onPressed:
                        busy || uncertain ? null : () => change('revoke'),
                    child: const Text('停用规则')),
                OutlinedButton(
                    onPressed: busy || uncertain ? null : () => change('reset'),
                    child: const Text('重置默认口径'))
              ])
            ],
            const SectionTitle('内部运营授权'),
            const Text(
                '在 AI 运营的每日候选预览中创建有限次数授权，核对范围、期限和消耗记录，并可撤销授权或撤回消耗产生的候选。'),
            OutlinedButton(
                onPressed: busy
                    ? null
                    : () => openBusinessPath(
                        context, widget.app, '/agent?mode=daily'),
                child: const Text('管理 AI 运营授权')),
            const SectionTitle('规则版本历史'),
            for (final h in history)
              ListTile(
                  title: Text('#${h['version']} · ${h['action']}'),
                  subtitle: Text('${h['created_at']}'),
                  onTap: busy
                      ? null
                      : () => perform(() async {
                            final value = object(await widget.app.api
                                .get(path('/${h['version']}')));
                            if (mounted) setState(() => selected = value);
                          })),
            if (history.length >= 50)
              OutlinedButton(
                  onPressed: busy
                      ? null
                      : () => perform(() async {
                            final list = rows(await widget.app.api
                                .get(path('/history'), query: {
                              ...scope.partition,
                              'before': history.last['version']
                            }));
                            if (mounted) setState(() => history = list);
                          }),
                  child: const Text('更早版本')),
            if (selected != null) ...[
              RuleEvidence(selected!),
              if (selected!['active'] == true)
                OutlinedButton(
                    onPressed: busy || uncertain || current == null
                        ? null
                        : () => change('restore',
                            version: selected!['version'] as int),
                    child: Text('恢复历史 #${selected!['version']} 为新版本'))
            ]
          ])));
}

class RuleEvidence extends StatelessWidget {
  const RuleEvidence(this.value, {super.key});
  final Json value;
  @override
  Widget build(BuildContext context) {
    final values = object(value['values']), notes = object(values['notes']);
    return ExpansionTile(
        title: Text(
            '规则 #${value['version']} · ${value['active'] == true ? '有效' : '默认 / 停用'}'),
        children: [
          FactLine('范围', '${value['data_identity']} / ${value['channel']}'),
          FactLine('前一版本', value['previous_version']),
          FactLine('恢复来源版本', value['restored_from']),
          FactLine('生效时间', value['created_at']),
          for (final e in const {
            'max_age_hours': '库存有效小时',
            'min_quantity': '最低销量',
            'max_margin_percent': '低毛利率上限 %',
            'advertising_daily_budget': '广告日预算',
            'currency': '预算币种',
            'basis': '规则依据'
          }.entries)
            FactLine(e.value, values[e.key]),
          for (final e in const {
            'target_site': '目标站点',
            'warehouse': '仓库',
            'logistics': '物流',
            'brand_voice': '品牌表达',
            'support_wording': '客服措辞'
          }.entries)
            FactLine(e.value, notes[e.key]),
          const Text('经营规则提供本地检查口径；执行权限由对应业务审批或授权决定。')
        ]);
  }
}
