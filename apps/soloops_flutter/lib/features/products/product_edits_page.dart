import '../../ui/edit_guard.dart';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/api_client.dart';
import '../../core/business_navigation.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/finance_inputs.dart';
import '../../ui/source_evidence.dart';
import '../imports/import_repository.dart';
import '../finance/finance_common.dart' show FinanceRows;

const editStatuses = {
  'draft': '待审批',
  'applied': '已应用',
  'failed': '应用失败',
  'rejected': '已拒绝',
  'stale': '来源变化',
  'revoked': '已撤销',
  'cleared': '正文已清除'
};

class ProductEditDraft {
  ProductEditDraft(this.source)
      : name = TextEditingController(text: '${source['name']}'),
        facts = TextEditingController(text: '${source['facts']}');
  final Json source;
  final TextEditingController name, facts;
  bool selected = false;
  bool get changed =>
      name.text != source['name'] || facts.text != source['facts'];
  void dispose() {
    name.dispose();
    facts.dispose();
  }
}

class ProductEditsPage extends StatefulWidget {
  const ProductEditsPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<ProductEditsPage> createState() => _ProductEditsPageState();
}

class _ProductEditsPageState extends BusinessPageState<ProductEditsPage> {
  late String identity = widget.query['identity'] ?? 'user_import',
      channel = widget.query['channel'] ?? 'generic';
  late final sku = TextEditingController(text: widget.query['sku'] ?? '');
  final reason = TextEditingController(),
      prefix = TextEditingController(),
      append = TextEditingController();
  List<ProductEditDraft> products = [];
  List<Json> history = [];
  Json? catalog, record, pending;
  int page = 0;
  int? cursor;
  bool approved = false, uncertain = false;
  bool get locked => busy || pending != null || uncertain;
  String path(String tail) => widget.app.shopPath('/product-edits$tail');
  @override
  void initState() {
    super.initState();
    Future.microtask(() => perform(() async {
          await list();
          final id = int.tryParse(widget.query['edit'] ?? '');
          if (id != null) await read(id);
        }));
  }

  void clearCatalog() {
    for (final p in products) {
      p.dispose();
    }
    products = [];
    catalog = null;
    page = 0;
  }

  Future<void> list({bool more = false}) async {
    final value = object(await widget.app.api
        .get(path(''), query: {if (more) 'before': cursor}));
    if (mounted) {
      setState(() {
        history =
            more ? [...history, ...rows(value['items'])] : rows(value['items']);
        cursor = value['next_cursor'] as int?;
      });
    }
  }

  Future<void> load() => perform(() async {
        if (sku.text.trim().length > 120) {
          throw const FormatException('SKU 前缀最多120字符。');
        }
        final value = object(await widget.app.api.post(
            widget.app.shopPath('/product-quality/preview'), {
          'data_identity': identity,
          'channel': channel,
          'sku_prefix': sku.text.trim()
        }));
        if (mounted) {
          setState(() {
            clearCatalog();
            catalog = value;
            record = null;
            approved = false;
            products =
                rows(value['products']).map(ProductEditDraft.new).toList();
          });
        }
      });
  Future<void> read(int id) async {
    final value = object(await widget.app.api.get(path('/$id')));
    if (mounted) {
      setState(() {
        record = value;
        approved = false;
        uncertain = false;
        clearCatalog();
      });
    }
  }

  Future<void> create() => perform(() async {
        if (pending == null) {
          final selected =
              products.where((p) => p.selected && p.changed).toList();
          if (selected.isEmpty || selected.length > 50) {
            throw const FormatException('请选择 1–50 个有修改的商品。');
          }
          final changes = <Json>[];
          for (final p in selected) {
            if (p.facts.text.length > 2000) {
              throw FormatException('${p.source['sku']} 的参数最多 2000 字符。');
            }
            changes.add({
              'product_id': p.source['product_id'],
              'expected_source_row_id': object(p.source['source'])['row_id'],
              'name': requiredText(p.name.text, '${p.source['sku']} 名称', 240),
              'facts': p.facts.text
            });
          }
          pending = {
            'data_identity': object(catalog!['scope'])['data_identity'],
            'channel': object(catalog!['scope'])['channel'],
            'reason': requiredText(reason.text, '修订依据', 500),
            'changes': changes,
            'request_id': newRequestId()
          };
        }
        try {
          final value = object(await widget.app.api.post(path(''), pending));
          if (mounted) {
            setState(() {
              pending = null;
              record = value;
              approved = false;
              clearCatalog();
            });
          }
          await list();
        } on ApiFailure catch (e) {
          if (e.status >= 400 && e.status < 500 && e.status != 408) {
            pending = null;
          }
          rethrow;
        }
      });
  Future<void> decide(String action) async {
    if (record == null) return;
    if (action != 'approve' &&
        !await confirmAction(
            context,
            {
              'reject': '拒绝修订',
              'withdraw': '撤销本地修订',
              'clear': '清除修订正文'
            }[action]!,
            action == 'clear'
                ? '清除差异正文与依据；已生效修订还会清除对应导入批次并回退其当前商品影响，无法恢复已清除正文。'
                : '按当前版本处理修订 #${record!['id']}，完成后回读结果。')) {
      return;
    }
    await perform(() async {
      try {
        final value = object(
            await widget.app.api.post(path('/${record!['id']}/$action'), {
          'version': record!['version'],
          'confirm': true,
          if (action == 'approve')
            'expected_preview_hash': record!['preview_hash']
        }));
        if (mounted) {
          setState(() {
            record = value;
            approved = false;
          });
        }
        await list();
      } catch (e) {
        uncertain = true;
        approved = false;
        rethrow;
      }
    });
  }

  void bulk() {
    setState(() {
      for (final p in products.where((p) => p.selected)) {
        p.name.text = prefix.text + p.name.text;
        if (append.text.isNotEmpty) {
          p.facts.text =
              [p.facts.text, append.text].where((s) => s.isNotEmpty).join('\n');
        }
      }
      prefix.clear();
      append.clear();
    });
  }

  @override
  void dispose() {
    clearCatalog();
    for (final c in [sku, reason, prefix, append]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => EditGuard(
      app: widget.app,
      controllers: [
        reason,
        prefix,
        append,
        for (final p in products) ...[p.name, p.facts]
      ],
      dirty: () => products.any((p) => p.changed),
      busy: busy,
      pending: pending != null,
      child: Scaffold(
          appBar: AppBar(title: const Text('商品本地修订')),
          body: PageBody(children: [
            ...feedback,
            ChoiceField(
                '数据身份',
                identity,
                importIdentities,
                locked
                    ? null
                    : (v) => setState(() {
                          identity = v;
                          clearCatalog();
                        })),
            ChoiceField(
                '渠道',
                channel,
                importChannels,
                locked
                    ? null
                    : (v) => setState(() {
                          channel = v;
                          clearCatalog();
                        })),
            FormInput('SKU 前缀', sku, required: false, enabled: !locked),
            FilledButton(
                onPressed: locked ? null : load,
                child: const Text('读取当前商品与来源')),
            if (catalog != null) ...[
              FactLine('来源修订', catalog!['source_revision']),
              FactLine('已选择商品', products.where((p) => p.selected).length),
              FormInput('批量名称前缀', prefix, required: false, enabled: !locked),
              FormInput('批量追加参数', append,
                  required: false, lines: 3, enabled: !locked),
              OutlinedButton(
                  onPressed: locked ? null : bulk,
                  child: const Text('将输入应用到已选商品表单')),
              for (final p in products.skip(page * 20).take(20))
                ExpansionTile(
                    key: ObjectKey(p),
                    maintainState: true,
                    title: Text('${p.source['sku']} · ${p.source['name']}'),
                    children: [
                      CheckboxListTile(
                          value: p.selected,
                          onChanged: locked
                              ? null
                              : (v) => setState(() => p.selected = v ?? false),
                          title: const Text('选择此商品')),
                      FormInput('拟修订名称', p.name, enabled: !locked),
                      FormInput('拟修订参数与事实', p.facts,
                          lines: 5, required: false, enabled: !locked),
                      FactLine('原名称', p.source['name']),
                      FactLine('原参数', p.source['facts']),
                      SourceEvidence(widget.app, object(p.source['source']))
                    ]),
              Wrap(spacing: 8, children: [
                TextButton(
                    onPressed: locked || page == 0
                        ? null
                        : () => setState(() => page--),
                    child: const Text('上一页')),
                Text('第 ${page + 1} 页 · 共 ${products.length} 个商品'),
                TextButton(
                    onPressed: locked || (page + 1) * 20 >= products.length
                        ? null
                        : () => setState(() => page++),
                    child: const Text('下一页'))
              ]),
              FormInput('修订依据', reason, lines: 3, enabled: !locked),
            ],
            if (catalog != null || pending != null)
              FilledButton(
                  onPressed: busy ? null : create,
                  child: Text(pending == null ? '创建修订差异预览' : '核对同次创建')),
            if (record != null) ...[
              const SectionTitle('修订差异与应用结果'),
              FactLine('修订记录',
                  '#${record!['id']} · v${record!['version']} · ${editStatuses[record!['status']]}'),
              FactLine('当前有效商品数', record!['current_count']),
              FactLine('审批时间', record!['decided_at']),
              OutlinedButton(
                  onPressed: busy
                      ? null
                      : () => perform(() => read(record!['id'] as int)),
                  child: const Text('回读记录与当前状态')),
              if (uncertain) const Notice('请先回读记录，核对上次操作结果。'),
              if (record!['snapshot'] != null) ...[
                FactLine('修订依据', object(record!['snapshot'])['reason']),
                FactLine(
                    '来源修订', object(record!['snapshot'])['source_revision']),
                FinanceRows(rows(object(record!['snapshot'])['items']),
                    builder: (item) => ExpansionTile(
                            title: Text(
                                '${object(item['before'])['sku']} · ${item['result']}'),
                            subtitle: Text('${item['message']}'),
                            children: [
                              FactLine('原名称', object(item['before'])['name']),
                              FactLine('新名称', object(item['after'])['name']),
                              FactLine('原参数', object(item['before'])['facts']),
                              FactLine('新参数', object(item['after'])['facts']),
                              SourceEvidence(widget.app, object(item['source']))
                            ])),
              ],
              if (record!['status'] == 'draft') ...[
                CheckboxListTile(
                    value: approved,
                    onChanged: locked
                        ? null
                        : (v) => setState(() => approved = v ?? false),
                    title: const Text('已核对全部商品的前后差异，批准应用到本地商品数据')),
                FilledButton(
                    onPressed:
                        locked || !approved ? null : () => decide('approve'),
                    child: const Text('批准并应用本地修订')),
                OutlinedButton(
                    onPressed: locked ? null : () => decide('reject'),
                    child: const Text('拒绝修订')),
              ],
              if (record!['status'] == 'applied')
                OutlinedButton(
                    onPressed: locked ? null : () => decide('withdraw'),
                    child: const Text('撤销本次修订')),
              if (record!['status'] != 'cleared')
                OutlinedButton(
                    onPressed: locked ? null : () => decide('clear'),
                    child: const Text('清除差异正文')),
              if (record!['output_batch_id'] != null)
                OutlinedButton(
                    onPressed: () => openBusinessPath(context, widget.app,
                        '/imports?batch=${record!['output_batch_id']}'),
                    child: const Text('查看应用批次与行结果')),
            ],
            const SectionTitle('本地修订历史'),
            OutlinedButton(
                onPressed: busy ? null : () => perform(list),
                child: const Text('刷新历史')),
            FinanceRows(history,
                builder: (h) => ListTile(
                    title:
                        Text('修订 #${h['id']} · ${editStatuses[h['status']]}'),
                    subtitle: Text('${h['created_at']} · v${h['version']}'),
                    onTap: locked
                        ? null
                        : () => perform(() => read(h['id'] as int)))),
            if (cursor != null)
              OutlinedButton(
                  onPressed:
                      locked ? null : () => perform(() => list(more: true)),
                  child: const Text('加载更多修订'))
          ])));
}
