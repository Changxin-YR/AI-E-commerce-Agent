import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/api_client.dart';
import '../../core/business_navigation.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/source_evidence.dart';
import '../finance/finance_common.dart' show FinanceRows;
import '../imports/import_repository.dart';

class ProductQualityPage extends StatefulWidget {
  const ProductQualityPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<ProductQualityPage> createState() => _ProductQualityPageState();
}

class _ProductQualityPageState extends BusinessPageState<ProductQualityPage> {
  late String identity = widget.query['identity'] ?? 'user_import',
      channel = widget.query['channel'] ?? '';
  late final prefix = TextEditingController(text: widget.query['sku'] ?? '');
  Json? result, saved, pending;
  List<Json> history = [];
  int? cursor;
  bool confirmed = false, restoring = false;
  bool get locked => busy || pending != null;
  String path(String tail) => widget.app.shopPath('/product-quality$tail');
  @override
  void initState() {
    super.initState();
    prefix.addListener(changed);
    Future.microtask(() => perform(() async {
          await list();
          final id = int.tryParse(widget.query['report'] ?? '');
          if (id != null) await read(id);
        }));
  }

  void changed() {
    if (!restoring && mounted) {
      setState(() {
        result = null;
        saved = null;
        confirmed = false;
      });
    }
  }

  Future<void> list({bool more = false}) async {
    final value = object(await widget.app.api
        .get(path('/reports'), query: {if (more) 'before': cursor}));
    if (mounted) {
      setState(() {
        history =
            more ? [...history, ...rows(value['items'])] : rows(value['items']);
        cursor = value['next_cursor'] as int?;
      });
    }
  }

  void accept(Json value) {
    restoring = true;
    saved = value;
    result = value['snapshot'] == null ? null : object(value['snapshot']);
    final scope = object(value['scope']);
    identity = '${scope['data_identity']}';
    channel = '${scope['channel'] ?? ''}';
    prefix.text = '${scope['sku_prefix']}';
    confirmed = false;
    restoring = false;
  }

  Future<void> read(int id) async {
    final value = object(await widget.app.api.get(path('/reports/$id')));
    if (mounted) setState(() => accept(value));
  }

  Future<void> check() => perform(() async {
        if (prefix.text.trim().length > 120) {
          throw const FormatException('SKU 前缀最多 120 字符。');
        }
        final value = object(await widget.app.api.post(path('/preview'), {
          'data_identity': identity,
          'channel': channel.isEmpty ? null : channel,
          'sku_prefix': prefix.text.trim()
        }));
        if (mounted) {
          setState(() {
            result = value;
            saved = null;
            confirmed = false;
          });
        }
      });
  Future<void> save() => perform(() async {
        if (pending == null) {
          if (result == null || !confirmed) return;
          pending = {
            'scope': result!['scope'],
            'expected_revision': result!['source_revision'],
            'expected_preview_hash': result!['preview_hash'],
            'request_id': newRequestId(),
            'confirm': true
          };
        }
        try {
          final value =
              object(await widget.app.api.post(path('/reports'), pending));
          if (mounted) {
            setState(() {
              pending = null;
              accept(value);
            });
          }
          await list();
        } on ApiFailure catch (e) {
          if (e.status >= 400 && e.status < 500 && e.status != 408) {
            pending = null;
            confirmed = false;
            if (e.status == 409) {
              result = null;
              saved = null;
            }
          }
          rethrow;
        }
      });
  Future<void> clear() async {
    if (saved == null ||
        !await confirmAction(context, '清除质量报告', '清除报告正文、SKU 前缀与来源依赖，无法恢复。')) {
      return;
    }
    await perform(() async {
      final value = object(await widget.app.api
          .post(path('/reports/${saved!['id']}/clear'), {'confirm': true}));
      if (mounted) setState(() => accept(value));
      await list();
    });
  }

  @override
  void dispose() {
    prefix.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('商品质量检查')),
      body: PageBody(children: [
        ...feedback,
        ChoiceField(
            '数据身份',
            identity,
            importIdentities,
            locked
                ? null
                : (v) {
                    setState(() => identity = v);
                    changed();
                  }),
        ChoiceField(
            '渠道',
            channel,
            {'': '全部渠道', ...importChannels},
            locked
                ? null
                : (v) {
                    setState(() => channel = v);
                    changed();
                  }),
        FormInput('SKU 前缀', prefix, required: false, enabled: !locked),
        FilledButton(
            onPressed: locked ? null : check, child: const Text('检查当前商品')),
        if (saved != null)
          FactLine(
              '已存报告',
              '#${saved!['id']} · ${saved!['status'] == 'current' ? '当前有效' : saved!['status'] == 'stale' ? '来源变化 · 待重查' : '正文已清除'}'),
        if (result != null) ...[
          QualityResultView(widget.app, result!),
          if (saved == null)
            CheckboxListTile(
                value: confirmed,
                onChanged: locked
                    ? null
                    : (v) => setState(() => confirmed = v ?? false),
                title: const Text('已核对检查范围、规则结果与未检查项')),
        ],
        if (saved == null)
          FilledButton(
              onPressed: busy || (!confirmed && pending == null) ? null : save,
              child: Text(pending == null ? '保存质量报告' : '核对同次保存')),
        if (saved != null)
          Wrap(spacing: 8, children: [
            OutlinedButton(
                onPressed: locked
                    ? null
                    : () => perform(() => read(saved!['id'] as int)),
                child: const Text('回读存档状态')),
            OutlinedButton(
                onPressed:
                    locked || saved!['status'] == 'cleared' ? null : clear,
                child: const Text('清除报告正文'))
          ]),
        const SectionTitle('质量报告历史'),
        OutlinedButton(
            onPressed: locked ? null : () => perform(list),
            child: const Text('刷新历史')),
        FinanceRows(history,
            builder: (h) => ListTile(
                title: Text('报告 #${h['id']} · ${h['status']}'),
                subtitle: Text('${h['created_at']}'),
                onTap:
                    locked ? null : () => perform(() => read(h['id'] as int)))),
        if (cursor != null)
          OutlinedButton(
              onPressed: locked ? null : () => perform(() => list(more: true)),
              child: const Text('加载更多'))
      ]));
}

class QualityResultView extends StatelessWidget {
  const QualityResultView(this.app, this.value, {super.key});
  final AppState app;
  final Json value;
  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const SectionTitle('质量报告'),
        FactLine('检查时间', value['checked_at']),
        FactLine('规则版本', value['rule_version']),
        FactLine('来源修订', value['source_revision']),
        FactLine('检查商品 / 受影响商品',
            '${value['product_count']} / ${value['affected_products']}'),
        FactLine('缺失 / 待审问题',
            '${value['missing_count']} / ${value['review_count']}'),
        for (final c in rows(value['coverage']))
          ListTile(
              title: Text(
                  '${c['label']} · ${c['status'] == 'checked' ? '已检查' : '未检查'}'),
              subtitle: Text('${c['reason']}')),
        for (final limitation in value['limitations'] as List)
          Text('$limitation'),
        FinanceRows(rows(value['products']),
            builder: (p) => ExpansionTile(
                    title: Text('${p['sku']} · ${p['name']}'),
                    subtitle: Text(
                        '${rows(p['issues']).length} 项问题 · ${p['channel']}'),
                    children: [
                      FactLine('参数与事实', p['facts']),
                      FactLine(
                          '售价', '${p['price'] ?? '未知'} ${p['currency'] ?? ''}'),
                      FactLine('采购成本',
                          '${p['unit_cost'] ?? '未知'} ${p['cost_currency'] ?? ''}'),
                      FactLine('相似SKU',
                          '${(p['similar_skus'] as List).join('、')} · 共 ${p['similar_sku_count']} 个'),
                      for (final issue in rows(p['issues']))
                        ListTile(
                            title: Text(
                                '${issue['status'] == 'missing' ? '缺失' : '待审'} · ${issue['field']}'),
                            subtitle: Text(
                                '${issue['reason']}\n建议：${issue['suggestion']}\n规则：${issue['code']}')),
                      SourceEvidence(app, object(p['source'])),
                      Wrap(spacing: 8, children: [
                        OutlinedButton(
                            onPressed: () => openBusinessPath(
                                context,
                                app,
                                Uri(path: '/product-edits', queryParameters: {
                                  'identity':
                                      '${object(value['scope'])['data_identity']}',
                                  'channel': '${p['channel']}',
                                  'sku': '${p['sku']}'
                                }).toString()),
                            child: const Text('修订名称与参数')),
                        OutlinedButton(
                            onPressed: () => openBusinessPath(context, app,
                                '/listings?product=${p['product_id']}'),
                            child: const Text('查看商品与文案'))
                      ])
                    ])),
      ]);
}
