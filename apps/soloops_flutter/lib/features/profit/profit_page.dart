import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/finance_inputs.dart';

const profitFees = {
  'inbound': '头程物流',
  'outbound': '尾程物流',
  'platform': '平台费用',
  'storage': '仓储',
  'packaging': '包装',
  'advertising': '广告',
  'refund': '退款损失',
  'tax': '税费',
  'other': '其他及分摊费用'
};
const moneyCurrencies = [
  'USD',
  'CNY',
  'EUR',
  'GBP',
  'JPY',
  'CAD',
  'AUD',
  'HKD',
  'SGD'
];

class FeeDraft {
  FeeDraft(this.kind, [Json? data])
      : mode = '${data?['mode'] ?? 'fixed'}',
        value = TextEditingController(text: '${data?['value'] ?? ''}'),
        basis = TextEditingController(text: '${data?['basis'] ?? ''}');
  final String kind;
  String mode;
  final TextEditingController value, basis;
  Json input() {
    final amount = value.text.trim().isEmpty
        ? null
        : decimalInput(value.text, profitFees[kind]!,
            max: mode == 'percent' ? '100' : '100000000');
    return {
      'kind': kind,
      'mode': mode,
      'value': amount,
      'basis': amount == null
          ? basis.text.trim()
          : requiredText(basis.text, '${profitFees[kind]}依据', 300)
    };
  }

  void dispose() {
    value.dispose();
    basis.dispose();
  }
}

class ScenarioDraft {
  ScenarioDraft(String label, [Json? data])
      : name = TextEditingController(text: '${data?['name'] ?? label}'),
        price = TextEditingController(text: '${data?['price'] ?? ''}'),
        cost = TextEditingController(text: '${data?['purchase_cost'] ?? ''}'),
        basis = TextEditingController(text: '${data?['basis'] ?? ''}'),
        fees = [
          for (final key in profitFees.keys)
            FeeDraft(key,
                rows(data?['fees']).where((e) => e['kind'] == key).firstOrNull)
        ];
  final TextEditingController name, price, cost, basis;
  final List<FeeDraft> fees;
  Json raw() => {
        'name': name.text,
        'price': price.text,
        'purchase_cost': cost.text,
        'basis': basis.text,
        'fees': [
          for (final f in fees)
            {
              'kind': f.kind,
              'mode': f.mode,
              'value': f.value.text,
              'basis': f.basis.text
            }
        ]
      };
  Json input() => {
        'name': requiredText(name.text, '方案名称', 80),
        'price': decimalInput(price.text, '候选售价', max: '100000000'),
        'purchase_cost': decimalInput(cost.text, '采购成本', max: '100000000'),
        'basis': requiredText(basis.text, '售价与成本依据', 500),
        'fees': fees.map((e) => e.input()).toList()
      };
  void dispose() {
    for (final c in [name, price, cost, basis]) {
      c.dispose();
    }
    for (final f in fees) {
      f.dispose();
    }
  }
}

class ProfitPage extends StatefulWidget {
  const ProfitPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<ProfitPage> createState() => _ProfitPageState();
}

class _ProfitPageState extends BusinessPageState<ProfitPage> {
  final form = GlobalKey<FormState>();
  final title = TextEditingController();
  List<ScenarioDraft> scenarios = [ScenarioDraft('方案 1')];
  late String currency = '${widget.app.shop?['currency'] ?? 'USD'}';
  String identity = 'manual_assumption', requestKey = newRequestId();
  Json? result;
  int? savedId;
  List<Json> saved = [];
  int offset = 0;
  bool editing = true;
  String path(String p) => widget.app.shopPath('/profit$p');
  @override
  void initState() {
    super.initState();
    Future.microtask(() => perform(() async {
          await history();
          final id = int.tryParse(
              widget.query['saved'] ?? widget.query['study'] ?? '');
          if (id != null) await read(id);
        }));
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      result = null;
      savedId = null;
      requestKey = newRequestId();
      success = null;
    });
  }

  Json input() {
    final list = scenarios.map((e) => e.input()).toList();
    if (list.map((e) => e['name']).toSet().length != list.length) {
      throw const FormatException('方案名称不能重复。');
    }
    return {
      'title': requiredText(title.text, '试算名称', 120),
      'currency': currency,
      'data_identity': identity,
      'scenarios': list
    };
  }

  Future<void> history([int? next]) async {
    final page = next ?? offset;
    final data =
        rows(await widget.app.api.get(path('/saved'), query: {'offset': page}));
    if (mounted) {
      setState(() {
        saved = data;
        offset = page;
      });
    }
  }

  Future<void> read(int id) async {
    final record = object(await widget.app.api.get(path('/saved/$id')));
    if (!mounted) return;
    final value = object(record['result']);
    final fields = object(value['input']);
    setState(() {
      for (final s in scenarios) {
        s.dispose();
      }
      scenarios =
          rows(fields['scenarios']).map((e) => ScenarioDraft('', e)).toList();
      title.text = '${fields['title']}';
      currency = '${fields['currency']}';
      identity = '${fields['data_identity']}';
      result = value;
      savedId = id;
      editing = false;
      requestKey = newRequestId();
    });
  }

  Future<void> calculate() => perform(() async {
        if (!form.currentState!.validate()) return;
        final data = input();
        final value =
            object(await widget.app.api.post(path('/calculate'), data));
        if (mounted) {
          setState(() {
            result = value;
            savedId = null;
            editing = false;
          });
        }
      });
  Future<void> save() => perform(() async {
        if (result == null || savedId != null) return;
        final record = object(await widget.app.api.post(path('/saved'),
            {...object(result!['input']), 'request_key': requestKey}));
        if (!mounted) return;
        setState(() {
          result = object(record['result']);
          savedId = record['id'] as int;
        });
        success = '已保存试算 #$savedId。修改输入后重新计算，可另存记录。';
        await history(0);
      });
  Future<void> clear() async {
    if (savedId == null ||
        !await confirmAction(
            context, '清除已存试算', '清除试算 #$savedId 的名称、金额、假设和依据。此操作无法恢复。')) {
      return;
    }
    await perform(() async {
      await widget.app.api.send('DELETE', path('/saved/$savedId'));
      if (!mounted) return;
      setState(() {
        result = null;
        savedId = null;
        requestKey = newRequestId();
        editing = true;
      });
      await history(0);
      success = '已清除存档；表单保留当前输入，可继续编辑。';
    });
  }

  void add(bool copy) {
    var n = 1;
    while (scenarios.any((s) => s.name.text == '方案 $n')) {
      n++;
    }
    final data = copy ? scenarios.last.raw() : null;
    if (data != null) data['name'] = '方案 $n';
    setState(() => scenarios.add(ScenarioDraft('方案 $n', data)));
    changed();
  }

  Future<void> exchange(ScenarioDraft scenario) async {
    final value = await showDialog<Json>(
        context: context, builder: (_) => ExchangeDialog(currency));
    if (value == null || !mounted) return;
    final combined = '${scenario.basis.text.trim()}\n${value['basis']}'.trim();
    if (combined.length > 500) {
      setState(() => error = '依据超过 500 字，请缩短原依据后再换算。');
      return;
    }
    scenario.cost.text = '${value['amount']}';
    scenario.basis.text = combined;
    changed();
  }

  @override
  void dispose() {
    title.dispose();
    for (final s in scenarios) {
      s.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('新品利润测算')),
      body: PageBody(children: [
        ...feedback,
        const Text('比较售价与单件成本。金额使用所选结算币种；固定费用填单件分摊额，费率按售价计算。'),
        SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('编辑试算输入'),
            value: editing,
            onChanged: busy ? null : (v) => setState(() => editing = v)),
        if (editing)
          Form(
              key: form,
              onChanged: changed,
              child: Column(children: [
                FormInput('试算名称', title, enabled: !busy),
                ChoiceField(
                    '结算币种',
                    currency,
                    {for (final c in moneyCurrencies) c: c},
                    busy
                        ? null
                        : (v) {
                            setState(() => currency = v);
                            changed();
                          },
                    help: '更改币种后请重新核对金额。换算辅助需手工确认汇率。'),
                ChoiceField(
                    '假设来源',
                    identity,
                    const {'manual_assumption': '手工假设', 'synthetic': '合成测试'},
                    busy
                        ? null
                        : (v) {
                            setState(() => identity = v);
                            changed();
                          }),
                for (final s in scenarios)
                  Column(
                      key: ObjectKey(s),
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SectionTitle('方案 ${scenarios.indexOf(s) + 1}'),
                        FormInput('方案名称', s.name, enabled: !busy),
                        DecimalField('售价（$currency / 件）', s.price,
                            max: '100000000', enabled: !busy),
                        DecimalField('采购成本（$currency / 件）', s.cost,
                            max: '100000000', enabled: !busy),
                        OutlinedButton(
                            onPressed: busy ? null : () => exchange(s),
                            child: const Text('用手工汇率换算采购成本')),
                        FormInput('售价、采购成本与换算依据', s.basis,
                            lines: 3, enabled: !busy),
                        const Text('空白费用表示未知；填写 0 表示明确为零，也须填写依据。'),
                        for (final f in s.fees)
                          ExpansionTile(
                              key: ObjectKey(f),
                              maintainState: true,
                              title: Text(profitFees[f.kind]!),
                              subtitle: Text(f.value.text.isEmpty
                                  ? '未填 · 未计入'
                                  : '${f.value.text} ${f.mode == 'percent' ? '%' : currency}'),
                              children: [
                                ChoiceField(
                                    '计费方式',
                                    f.mode,
                                    {
                                      'fixed': '$currency / 件',
                                      'percent': '售价比例 %'
                                    },
                                    busy
                                        ? null
                                        : (v) {
                                            setState(() => f.mode = v);
                                            changed();
                                          }),
                                DecimalField('费用数值', f.value,
                                    optional: true,
                                    max: f.mode == 'percent'
                                        ? '100'
                                        : '100000000',
                                    enabled: !busy),
                                FormInput('费用依据（已填费用必填）', f.basis,
                                    required: false, lines: 2, enabled: !busy)
                              ]),
                        if (scenarios.length > 1)
                          TextButton(
                              onPressed: busy
                                  ? null
                                  : () {
                                      setState(() => scenarios.remove(s));
                                      s.dispose();
                                      changed();
                                    },
                              child: const Text('移除此方案')),
                      ]),
                Wrap(spacing: 8, children: [
                  OutlinedButton(
                      onPressed: busy || scenarios.length >= 5
                          ? null
                          : () => add(false),
                      child: const Text('新增方案')),
                  OutlinedButton(
                      onPressed: busy || scenarios.length >= 5
                          ? null
                          : () => add(true),
                      child: const Text('复制末个方案'))
                ]),
                FilledButton(
                    onPressed: busy ? null : calculate,
                    child: const Text('计算并比较'))
              ])),
        if (result != null) ...[
          ProfitResultView(result!),
          if (savedId != null) FactLine('已存档记录', savedId),
          if (savedId == null)
            FilledButton(
                onPressed: busy ? null : save,
                child: const Text('保存本次方案 / 核对同次保存')),
          if (savedId != null)
            OutlinedButton(
                onPressed: busy ? null : clear, child: const Text('清除本次存档')),
        ],
        const SectionTitle('试算历史'),
        OutlinedButton(
            onPressed: busy ? null : () => perform(() => history(0)),
            child: const Text('刷新历史')),
        if (saved.isEmpty && !busy) const Text('暂无试算记录。计算完成后可保存。'),
        for (final item in saved)
          ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('${item['title']}'),
              subtitle: Text(
                  '${item['currency']} · ${item['data_identity']} · ${item['created_at']}'),
              trailing: const Icon(Icons.chevron_right),
              onTap:
                  busy ? null : () => perform(() => read(item['id'] as int))),
        Wrap(spacing: 8, children: [
          OutlinedButton(
              onPressed: busy || offset == 0
                  ? null
                  : () => perform(() => history(offset - 50)),
              child: const Text('上一页')),
          Text('第 ${offset ~/ 50 + 1} 页'),
          OutlinedButton(
              onPressed: busy || saved.length < 50
                  ? null
                  : () => perform(() => history(offset + 50)),
              child: const Text('下一页'))
        ])
      ]));
}

class ExchangeDialog extends StatefulWidget {
  const ExchangeDialog(this.currency, {super.key});
  final String currency;
  @override
  State<ExchangeDialog> createState() => _ExchangeDialogState();
}

class _ExchangeDialogState extends State<ExchangeDialog> {
  final amount = TextEditingController(),
      rate = TextEditingController(),
      basis = TextEditingController();
  String from = 'CNY';
  String? error, converted;
  @override
  void dispose() {
    amount.dispose();
    rate.dispose();
    basis.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
          title: const Text('采购成本换算'),
          content: SingleChildScrollView(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
            ChoiceField(
                '原币种',
                from,
                {for (final c in moneyCurrencies) c: c},
                (v) => setState(() {
                      from = v;
                      converted = null;
                    })),
            Form(
                onChanged: () => setState(() => converted = null),
                child: Column(children: [
                  DecimalField('原币金额', amount, max: '100000000'),
                  DecimalField('1 $from 对应 ${widget.currency}', rate,
                      places: 8, positive: true, max: '100000000'),
                  FormInput('汇率来源、日期与报价依据', basis, lines: 3)
                ])),
            const Text('按手工汇率换算，四舍五入到 4 位小数；确认后会替换采购成本并追加依据。'),
            if (error != null) Notice(error!),
            if (converted != null)
              FactLine('换算金额', '$converted ${widget.currency}')
          ])),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('取消')),
            OutlinedButton(
                onPressed: () {
                  try {
                    requiredText(basis.text, '换算依据', 300);
                    setState(() {
                      converted = convertedMoney(amount.text, rate.text);
                      error = null;
                    });
                  } catch (e) {
                    setState(() => error = '$e');
                  }
                },
                child: const Text('预览换算')),
            FilledButton(
                onPressed: converted == null
                    ? null
                    : () => Navigator.pop(context, {
                          'amount': converted,
                          'basis':
                              '换算：${amount.text.trim()} $from × ${rate.text.trim()} ${widget.currency}/$from = $converted ${widget.currency}；${basis.text.trim()}'
                        }),
                child: const Text('确认采用'))
          ]);
}

class ProfitResultView extends StatelessWidget {
  const ProfitResultView(this.result, {super.key});
  final Json result;
  @override
  Widget build(BuildContext context) {
    final input = object(result['input']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionTitle('${input['title']} · 假设估算'),
      FactLine('币种', input['currency']),
      FactLine('来源身份', input['data_identity']),
      FactLine('计算时间', result['calculated_at']),
      Text('${result['scope_note']}'),
      ExpansionTile(title: const Text('计算公式与规则版本'), children: [
        FactLine('公式', result['formula']),
        FactLine('规则版本', result['rule_version'])
      ]),
      for (final item in rows(result['scenarios'])) ...[
        SectionTitle('${object(item['assumption'])['name']}'),
        for (final entry in const {
          'purchase_gross': '采购毛利',
          'known_fees': '已填费用',
          'known_balance': '已知费用后余额',
          'margin_percent': '余额率 %',
          'break_even_price': '假设保本价'
        }.entries)
          FactLine(entry.value, item[entry.key]),
        Text('${item['break_even_reason']}'),
        if ((item['missing_fees'] as List).isNotEmpty)
          Notice('未计入：${(item['missing_fees'] as List).join('、')}'),
        ExpansionTile(title: const Text('原始输入与费用依据'), children: [
          FactLine('售价', object(item['assumption'])['price']),
          FactLine('采购成本', object(item['assumption'])['purchase_cost']),
          FactLine('依据', object(item['assumption'])['basis']),
          FactLine('固定费用合计', item['fixed_fees']),
          FactLine('售价费率合计 %', item['rate_percent']),
          for (final f in rows(item['fees']))
            ListTile(
                title: Text(
                    '${profitFees[object(f['assumption'])['kind']]}：${f['amount'] ?? '未知 · 未计入'}'),
                subtitle: Text(
                    '${object(f['assumption'])['value'] ?? '未知'} ${object(f['assumption'])['mode'] == 'percent' ? '%' : '/ 件'}\n${object(f['assumption'])['basis']}'))
        ]),
        ExpansionTile(title: const Text('售价与成本敏感性'), children: [
          for (final point in rows(item['sensitivity']))
            ListTile(
                title: Text('${point['label']}：余额 ${point['known_balance']}'),
                subtitle: Text(
                    '售价 ${point['price']} · 成本 ${point['purchase_cost']} · 余额率 ${point['margin_percent'] ?? '无法确定'}%'))
        ])
      ]
    ]);
  }
}
