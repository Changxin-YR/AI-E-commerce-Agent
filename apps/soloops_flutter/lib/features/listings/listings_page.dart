import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/business_navigation.dart';
import '../../ui/business_widgets.dart';
import '../../ui/common.dart';
import '../../ui/content_evidence.dart';
import '../../ui/reviewed_delivery.dart';

class ListingsPage extends StatefulWidget {
  const ListingsPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<ListingsPage> createState() => _ListingsPageState();
}

class _ListingsPageState extends BusinessPageState<ListingsPage> {
  final search = TextEditingController(),
      title = TextEditingController(),
      description = TextEditingController();
  List<Json> products = [], history = [];
  Json? workspace, selected;
  int offset = 0;
  bool confirmed = false;
  String path(String suffix) => widget.app.shopPath('/listings$suffix');
  Json get snapshot => mapValue(selected?['snapshot']);
  bool get dirty =>
      selected != null &&
      snapshot.isNotEmpty &&
      (title.text != snapshot['proposed']['title'] ||
          description.text != snapshot['proposed']['description']);
  bool get live => selected?['source_status'] == 'current';
  @override
  void initState() {
    super.initState();
    title.addListener(edited);
    description.addListener(edited);
    load(initial: true);
  }

  @override
  void dispose() {
    search.dispose();
    title.dispose();
    description.dispose();
    super.dispose();
  }

  void edited() {
    if (mounted) setState(() => confirmed = false);
  }

  void accept(Json item) {
    selected = item;
    confirmed = false;
    final proposed = mapValue(mapValue(item['snapshot'])['proposed']);
    title.text = '${proposed['title'] ?? ''}';
    description.text = '${proposed['description'] ?? ''}';
  }

  Future<bool> leaveEdit() async =>
      !dirty ||
      await confirmAction(context, '放弃未保存的文案', '未保存的标题与描述将被放弃。已保存版本仍保留。');
  Future<void> lists() async {
    final values = await Future.wait([
      widget.app.api.get(path('/products'),
          query: {'q': search.text.trim(), 'offset': offset}),
      widget.app.api.get(path('/versions')),
    ]);
    if (mounted) {
      products = rows(values[0]);
      history = rows(values[1]);
    }
  }

  Future<void> readSelected(int id) async {
    final item = object(await widget.app.api.get(path('/versions/$id')));
    if (!mounted) return;
    accept(item);
    workspace = null;
    if (item['source_status'] == 'current' && item['snapshot'] != null) {
      final w = object(await widget.app.api
          .get(path('/products/${item['snapshot']['product']['product_id']}')));
      if (mounted) workspace = w;
    }
  }

  Future<void> load({bool initial = false}) async {
    if (!initial && !await leaveEdit()) return;
    await perform(() async {
      await lists();
      if (!mounted) return;
      final id = initial
          ? int.tryParse(widget.query['listing'] ?? '')
          : selected?['id'] as int?;
      if (id != null) {
        await readSelected(id);
      } else {
        final p = initial
            ? int.tryParse(widget.query['product'] ?? '')
            : workspace?['product']['product_id'] as int?;
        if (p != null)
          workspace = object(await widget.app.api.get(path('/products/$p')));
      }
    });
  }

  Future<void> inspect(int id) async {
    if (!await leaveEdit()) return;
    await perform(() => readSelected(id));
  }

  Future<void> choose(int id) async {
    if (!await leaveEdit()) return;
    await perform(() async {
      final w = object(await widget.app.api.get(path('/products/$id')));
      if (mounted) {
        workspace = w;
        selected = null;
      }
    });
  }

  Future<void> mutate(String action) => perform(() async {
        Json item;
        if (action == 'generate') {
          item = object(await widget.app.api.post(path('/generate'), {
            'product_id': workspace!['product']['product_id'],
            'expected_source_row_id': workspace!['product']['source']['row_id'],
            'expected_active_id': workspace!['active_id'],
          }));
        } else if (action == 'revise') {
          if (title.text.trim().isEmpty ||
              title.text.length > 240 ||
              description.text.length > 4000) {
            throw const FormatException('标题须为 1–240 字，描述不超过 4000 字。');
          }
          item = object(await widget.app.api
              .post(path('/versions/${selected!['id']}/revise'), {
            'expected_version': selected!['version'],
            'expected_active_id': workspace!['active_id'],
            'content': {'title': title.text, 'description': description.text},
          }));
        } else {
          if (dirty || (action == 'approve' && !confirmed))
            throw const FormatException('请先保存文案并核对当前版本。');
          item = object(await widget.app.api
              .post(path('/versions/${selected!['id']}/decision'), {
            'expected_version': selected!['version'],
            'decision': action,
            'facts_confirmed': confirmed,
          }));
        }
        if (!mounted) return;
        accept(item);
        if (item['snapshot'] != null)
          workspace = object(await widget.app.api.get(
              path('/products/${item['snapshot']['product']['product_id']}')));
        if (mounted) await lists();
      },
          message: action == 'approve'
              ? '此版本已在本地生效。'
              : action == 'reject'
                  ? '版本已拒绝，历史保留。'
                  : '待审版本已保存。');
  Future<void> deliver(String action) => perform(() async {
        final item = selected!;
        final artifact = object(await widget.app.api.get(
            path('/versions/${item['id']}/delivery'),
            query: {'expected_version': item['version']}));
        if (!mounted || dirty || selected?['version'] != item['version'])
          return;
        success = await deliverArtifact(widget.app, artifact, action);
      });
  @override
  Widget build(BuildContext context) => PopScope(
      canPop: !dirty,
      onPopInvokedWithResult: (didPop, _) async {
        if (!didPop && await leaveEdit() && context.mounted)
          Navigator.pop(context);
      },
      child: Scaffold(
        appBar: AppBar(title: const Text('Listing')),
        body: RefreshIndicator(
            onRefresh: load,
            child: PageBody(children: [
              ...feedback,
              const Text('从导入商品事实建立候选，审阅差异后批准本地版本。'),
              FormInput('查找 SKU / 商品名', search,
                  required: false, enabled: !busy),
              OutlinedButton(
                  onPressed: busy
                      ? null
                      : () => perform(() async {
                            offset = 0;
                            await lists();
                          }),
                  child: const Text('搜索')),
              if (products.isEmpty && !busy)
                TextButton(
                    onPressed: () => openBusinessPath(
                        context, widget.app, '/imports', {'kind': 'products'}),
                    child: const Text('没有匹配商品，导入商品文件')),
              for (final p in products)
                ListTile(
                    title: Text('${p['sku']} · ${p['name']}'),
                    subtitle: Text(
                        '${p['source']['data_identity']} · 批次 #${p['source']['batch_id']}'),
                    onTap: busy ? null : () => choose(p['product_id'] as int)),
              Wrap(spacing: 12, children: [
                if (offset > 0)
                  TextButton(
                      onPressed: busy
                          ? null
                          : () => perform(() async {
                                offset -= 50;
                                await lists();
                              }),
                      child: const Text('上一页')),
                if (products.length == 50)
                  TextButton(
                      onPressed: busy
                          ? null
                          : () => perform(() async {
                                offset += 50;
                                await lists();
                              }),
                      child: const Text('下一页')),
              ]),
              if (workspace != null) ...[
                const SectionTitle('当前商品'),
                ProductEvidence(widget.app, object(workspace!['product'])),
                FactLine('本地已批准版本', workspace!['active_id']),
                FilledButton(
                    onPressed: busy || dirty ? null : () => mutate('generate'),
                    child: const Text('从商品事实生成草稿')),
                TextButton(
                    onPressed: busy || dirty
                        ? null
                        : () =>
                            openBusinessPath(context, widget.app, '/agent', {
                              ...widget.query,
                              'shop': '${widget.app.shopId}',
                              'mode': 'listing_model',
                              'product':
                                  '${workspace!['product']['product_id']}',
                              'identity':
                                  '${workspace!['product']['source']['data_identity']}',
                            }),
                    child: const Text('生成 AI Listing 候选')),
                for (final v in rows(workspace!['versions']))
                  ListTile(
                      title: Text('版本 ${v['number']} · ${v['status']}'),
                      onTap: busy ? null : () => inspect(v['id'] as int)),
              ],
              if (selected != null) ...[
                SectionTitle(
                    '版本 #${selected!['id']} · v${selected!['number']}'),
                FactLine('状态 / 来源',
                    '${selected!['status']} / ${selected!['source_status']}'),
                FactLine('生成方式', selected!['engine']),
                FactLine('创建 / 审批',
                    '${selected!['created_at']} / ${selected!['decided_at']}'),
                const Text('影响本店此 SKU 的本地文案，R1，外部费用 0。恢复可将有效历史文案另存待审版本。'),
                if (snapshot.isNotEmpty) ...[
                  ListingComparison(mapValue(snapshot['before']),
                      mapValue(snapshot['proposed'])),
                  ProductEvidence(widget.app, object(snapshot['product'])),
                  FactLine('缺失项', words(snapshot['missing'])),
                  FactLine('阻断项', words(snapshot['blockers'])),
                  if (live && workspace != null) ...[
                    FormInput('拟议标题', title, enabled: !busy),
                    FormInput('拟议描述', description,
                        lines: 7, required: false, enabled: !busy),
                    const Text('标题保留完整商品名；描述可调整完整参数行顺序。新增事实须先补充导入来源。'),
                    OutlinedButton(
                        onPressed: busy ? null : () => mutate('revise'),
                        child: Text(selected!['status'] == 'draft'
                            ? '保存修改为待审版本'
                            : '另存待审版本 / 恢复历史文案')),
                    if (dirty)
                      TextButton(
                          onPressed: busy
                              ? null
                              : () => setState(() => accept(selected!)),
                          child: const Text('放弃未保存修改')),
                  ],
                  if (selected!['status'] == 'draft') ...[
                    CheckboxListTile(
                        value: confirmed,
                        onChanged: busy || dirty || !live
                            ? null
                            : (v) => setState(() => confirmed = v!),
                        title: const Text('已逐项核对来源真实性、文案差异和平台适用性')),
                    Wrap(spacing: 12, children: [
                      FilledButton(
                          onPressed: busy ||
                                  dirty ||
                                  !live ||
                                  !confirmed ||
                                  (snapshot['blockers'] as List).isNotEmpty
                              ? null
                              : () => mutate('approve'),
                          child: const Text('批准本地生效')),
                      OutlinedButton(
                          onPressed: busy || dirty || !live
                              ? null
                              : () => mutate('reject'),
                          child: const Text('拒绝版本')),
                    ]),
                  ],
                  DeliveryButtons(
                      enabled: !busy &&
                          !dirty &&
                          live &&
                          selected!['status'] == 'approved',
                      onAction: deliver),
                ] else
                  const Text('相关来源已清除，版本正文已擦除。'),
                OutlinedButton(
                    onPressed: busy ? null : load,
                    child: const Text('回读当前版本与来源')),
              ],
              const SectionTitle('全部版本历史'),
              if (history.isEmpty && !busy) const Text('尚无 Listing 版本。'),
              for (final v in history)
                ListTile(
                    title: Text(
                        '#${v['id']} · ${v['snapshot']?['proposed']?['title'] ?? '内容已清除'}'),
                    subtitle: Text(
                        '${v['status']} · ${v['source_status']} · ${v['created_at']}'),
                    onTap: busy ? null : () => inspect(v['id'] as int)),
            ])),
      ));
}
