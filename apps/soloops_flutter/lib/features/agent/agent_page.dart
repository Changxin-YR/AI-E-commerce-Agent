import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/api_client.dart';
import '../../ui/business_scope.dart';
import '../../ui/business_widgets.dart';
import '../../ui/common.dart';
import '../../ui/content_evidence.dart';
import 'agent_labels.dart';
import 'agent_run_view.dart';
import 'authorizations_panel.dart';

bool agentProductMatchesScope(Json candidate,
        {required String template,
        required String identity,
        required String channel}) =>
    candidate['source']?['data_identity'] == identity &&
    (template != 'margin_review' || candidate['source_channel'] == channel);

class AgentPage extends StatefulWidget {
  const AgentPage(this.app,
      {super.key, this.query = const {}, this.embedded = false});
  final AppState app;
  final Map<String, String> query;
  final bool embedded;
  @override
  State<AgentPage> createState() => _AgentPageState();
}

class _AgentPageState extends BusinessPageState<AgentPage> {
  late final scope = BusinessScope(widget.app, widget.query);
  late String template = templates.containsKey(widget.query['mode'])
      ? widget.query['mode']!
      : 'daily';
  String costMode = 'seller_history';
  final goal = TextEditingController(),
      search = TextEditingController(),
      steps = TextEditingController(text: '12'),
      seconds = TextEditingController(text: '120'),
      cost = TextEditingController(text: '0');
  List<Json> history = [], skills = [], products = [], messages = [];
  Json? model, run, product, supportContext, operationContext, pendingStart;
  int productOffset = 0, messageOffset = 0, controlEpoch = 0, driveEpoch = 0;
  bool productsMore = false,
      messagesMore = false,
      driving = false,
      controlling = false,
      orderVerified = false,
      allowModel = false,
      allowData = false;
  final policyIds = <int>{};
  static const templates = {
    'daily': '今日运营：检查与异常候选',
    'daily_model': 'AI 今日运营：检查与解释',
    'analysis': '销售与已知毛利',
    'margin_review': 'B1：最近 7 天低毛利复核',
    'question': 'AI 经营问数',
    'listing': '商品事实与 Listing 草稿',
    'listing_model': 'AI Listing 候选',
    'support': '客服人工接管草稿',
    'support_model': 'AI 客服候选',
    'natural': '自然语言目标',
  };
  bool get useModel => [
        'natural',
        'question',
        'listing_model',
        'support_model',
        'daily_model'
      ].contains(template);
  String path(String suffix) => widget.app.shopPath('/agent$suffix');
  @override
  void initState() {
    super.initState();
    scope.addListener(changed);
    for (final c in [goal, steps, seconds, cost]) {
      c.addListener(consentChanged);
    }
    load(initial: true);
  }

  @override
  void dispose() {
    driving = false;
    scope.dispose();
    for (final c in [goal, search, steps, seconds, cost]) {
      c.dispose();
    }
    super.dispose();
  }

  void consentChanged() {
    if (mounted) {
      setState(() {
        allowModel = false;
        allowData = false;
        pendingStart = null;
      });
    }
  }

  bool productInScope(Json candidate) => agentProductMatchesScope(candidate,
      template: template, identity: scope.identity, channel: scope.channel);

  void changed() {
    if (mounted) {
      setState(() {
        allowModel = false;
        allowData = false;
        operationContext = null;
        pendingStart = null;
        if (product != null && !productInScope(product!)) {
          product = null;
        }
        if (supportContext != null &&
            (supportContext!['message']['source']['data_identity'] !=
                    scope.identity ||
                supportContext!['message']['channel'] != scope.channel)) {
          supportContext = null;
          policyIds.clear();
          orderVerified = false;
        }
      });
    }
  }

  void accept(Json value) {
    if (!mounted || value['shop_id'] != widget.app.shopId) return;
    if (run == null ||
        (run!['id'] == value['id'] &&
            (value['version'] as int) >= (run!['version'] as int))) {
      setState(() => run = value);
    }
  }

  Future<void> refreshRuns() async {
    final value = rows(await widget.app.api.get(path('/runs')));
    if (!mounted) return;
    history = value;
    if (run != null) {
      accept(object(await widget.app.api.get(path('/runs/${run!['id']}'))));
    }
  }

  Future<void> readOptions(
      {bool moreProducts = false, bool moreMessages = false}) async {
    final pOffset = moreProducts ? productOffset + 50 : 0;
    final mOffset = moreMessages ? messageOffset + 50 : 0;
    if (!moreMessages) {
      final p = rows(await widget.app.api.get(
          widget.app.shopPath('/listings/products'),
          query: {'q': search.text.trim(), 'offset': pOffset}));
      if (!mounted) return;
      products = moreProducts ? [...products, ...p] : p;
      productOffset = pOffset;
      productsMore = p.length == 50;
    }
    if (!moreProducts) {
      final m = rows(await widget.app.api.get(
          widget.app.shopPath('/support/messages'),
          query: {'q': search.text.trim(), 'offset': mOffset}));
      if (!mounted) return;
      messages = moreMessages ? [...messages, ...m] : m;
      messageOffset = mOffset;
      messagesMore = m.length == 50;
    }
    consentChanged();
  }

  Future<void> load({bool initial = false}) => perform(() async {
        final loaded = await Future.wait([
          widget.app.api.get(path('/skills')),
          widget.app.api.get(path('/model')),
        ]);
        if (!mounted) return;
        skills = rows(loaded[0]);
        model = object(loaded[1]);
        await scope.readRule(widget.app);
        if (!mounted) return;
        await refreshRuns();
        if (!mounted) return;
        await readOptions();
        if (!mounted) return;
        if (initial) {
          final id = int.tryParse(
              widget.query['execution'] ?? widget.query['run'] ?? '');
          if (id != null) {
            run = object(await widget.app.api.get(path('/runs/$id')));
          }
          if (!mounted) return;
          final p = int.tryParse(widget.query['product'] ?? '');
          if (p != null) {
            product = object((await widget.app.api
                .get(widget.app.shopPath('/listings/products/$p')))['product']);
          }
          final m = int.tryParse(widget.query['message'] ?? '');
          if (m != null) {
            supportContext = object(await widget.app.api
                .get(widget.app.shopPath('/support/messages/$m')));
          }
        }
      });
  Json budget() {
    final n = int.tryParse(steps.text), t = int.tryParse(seconds.text);
    if (n == null ||
        n < 1 ||
        n > 100 ||
        t == null ||
        t < 1 ||
        t > 3600 ||
        !RegExp(r'^\d+(\.\d{1,6})?$').hasMatch(cost.text.trim()) ||
        num.parse(cost.text) > 10) {
      throw const FormatException('预算须为 1–100 步、1–3600 秒、0–10 USD（最多 6 位小数）。');
    }
    return {'max_steps': n, 'max_seconds': t, 'max_cost_usd': cost.text.trim()};
  }

  Json startPayload() {
    if (useModel &&
        (goal.text.trim().isEmpty || goal.text.length > 500 || !allowModel)) {
      throw const FormatException('请填写 1–500 字目标，并核对本次模型数据授权。');
    }
    if (useModel && template != 'natural' && !allowData) {
      throw const FormatException('请核对本次业务数据发送范围。');
    }
    if (['listing', 'listing_model'].contains(template) && product == null) {
      throw const FormatException('请选择商品。');
    }
    if (['support', 'support_model'].contains(template) &&
        supportContext == null) {
      throw const FormatException('请选择消息。');
    }
    if (product != null && !productInScope(product!)) {
      throw const FormatException('商品不属于当前数据身份或复核渠道，请重新选择。');
    }
    if (supportContext != null &&
        (supportContext!['message']['source']['data_identity'] !=
                scope.identity ||
            supportContext!['message']['channel'] != scope.channel)) {
      throw const FormatException('消息身份或渠道不匹配。');
    }
    if (template == 'daily_model' && operationContext == null) {
      throw const FormatException('请先预览本次运营数据。');
    }
    if (policyIds.length > 10) throw const FormatException('最多选择 10 份政策。');
    return {
      'request_id': newRequestId(),
      'template': template,
      'margin_cost_mode': costMode,
      'scope': scope.payload(sevenDays: template == 'margin_review'),
      'goal': goal.text.trim(),
      'product_id': product?['product_id'],
      'message_id': supportContext?['message']['id'],
      'allow_model': useModel && allowModel,
      'allow_analysis_data': template == 'question' && allowData,
      'allow_listing_data': template == 'listing_model' && allowData,
      'allow_support_data': template == 'support_model' && allowData,
      'allow_operation_data': template == 'daily_model' && allowData,
      'expected_operation_hash': operationContext?['preview_hash'],
      'expected_product_source_row_id':
          template == 'listing_model' ? (product?['source']['row_id']) : null,
      'support_context': template == 'support_model' && supportContext != null
          ? {
              'expected_source_row_id': supportContext!['message']['source']
                  ['row_id'],
              'expected_order_row_ids': orderVerified
                  ? rows(supportContext!['orders'])
                      .map((o) => o['source']['row_id'])
                      .toList()
                  : [],
              'order_verified': orderVerified,
              'policy_ids': policyIds.toList(),
            }
          : null,
      'budget': budget()
    };
  }

  Future<void> drive() async {
    final token = ++driveEpoch;
    driving = true;
    try {
      for (var i = 0;
          i < 100 &&
              mounted &&
              driving &&
              token == driveEpoch &&
              run?['status'] == 'ready';
          i++) {
        final current = run!;
        final value = object(await widget.app.api.post(
            path('/runs/${current['id']}'),
            {'version': current['version'], 'action': 'advance'}));
        accept(value);
      }
    } finally {
      if (token == driveEpoch) driving = false;
    }
  }

  Future<void> start({Json? grant}) => perform(() async {
        if (grant != null) {
          pendingStart = {
            'request_id': newRequestId(),
            'template': 'daily',
            'scope': grant['scope'],
            'authorization_id': grant['id'],
            'budget': budget(),
            'goal': '',
            'allow_model': false
          };
        } else {
          pendingStart ??= startPayload();
        }
        try {
          final value =
              object(await widget.app.api.post(path('/runs'), pendingStart));
          if (!mounted) return;
          setState(() {
            run = value;
            pendingStart = null;
          });
          await drive();
          if (mounted) await refreshRuns();
        } catch (e) {
          if (e is ApiFailure &&
              e.status >= 400 &&
              e.status < 500 &&
              e.status != 408) {
            pendingStart = null;
          }
          rethrow;
        }
      });
  Future<void> act(String action,
      {Json? newBudget, int? authorizationId}) async {
    if (run == null ||
        controlling ||
        (busy && !['pause', 'cancel'].contains(action))) {
      return;
    }
    final selected = run!, token = ++controlEpoch;
    driving = false;
    driveEpoch++;
    setState(() {
      controlling = true;
      error = null;
    });
    try {
      // Approval uses precisely the reviewed version; pause/cancel read the latest version.
      final current = ['pause', 'cancel'].contains(action)
          ? object(await widget.app.api.get(path('/runs/${selected['id']}')))
          : selected;
      final value =
          object(await widget.app.api.post(path('/runs/${current['id']}'), {
        'version': current['version'],
        'action': action,
        if (newBudget != null) 'budget': newBudget,
        if (authorizationId != null) 'authorization_id': authorizationId,
      }));
      accept(value);
      if (!mounted) return;
      setState(() => controlling = false);
      if (['approve', 'resume', 'advance', 'use_authorization']
          .contains(action)) {
        setState(() => busy = true);
        await drive();
      }
      if (mounted) await refreshRuns();
    } catch (e) {
      if (mounted && token == controlEpoch) {
        setState(() => error = '$e');
        try {
          await refreshRuns();
        } catch (_) {}
      }
    } finally {
      if (mounted && token == controlEpoch) {
        setState(() {
          controlling = false;
          if (!driving) busy = false;
        });
      }
    }
  }

  Future<void> inspect(int id) => perform(() async {
        final value = object(await widget.app.api.get(path('/runs/$id')));
        if (mounted) run = value;
      });
  Future<void> restoreInput() => perform(() async {
        final input = mapValue(run?['input']);
        if (input.isEmpty) return;
        template = '${input['template']}';
        goal.text = '${input['goal'] ?? ''}';
        costMode = '${input['margin_cost_mode'] ?? 'seller_history'}';
        scope.restore(object(input['scope']));
        steps.text = '${run!['budget']['max_steps']}';
        seconds.text = '${run!['budget']['max_seconds']}';
        cost.text = '${run!['budget']['max_cost_usd']}';
        product = null;
        supportContext = null;
        operationContext = null;
        policyIds.clear();
        orderVerified = false;
        if (input['product_id'] != null) {
          product = object((await widget.app.api.get(widget.app.shopPath(
              '/listings/products/${input['product_id']}')))['product']);
        }
        if (input['message_id'] != null) {
          supportContext = object(await widget.app.api.get(
              widget.app.shopPath('/support/messages/${input['message_id']}')));
        }
        if (mounted) await scope.readRule(widget.app);
        consentChanged();
      }, message: '已按历史输入填入新任务表单并读取当前规则，请重新核对数据与授权。');
  Future<void> resume() async {
    final b = mapValue(run?['budget']);
    final n = TextEditingController(text: '${b['max_steps']}'),
        t = TextEditingController(text: '${b['max_seconds']}'),
        usd = TextEditingController(text: '${b['max_cost_usd']}');
    final value = await showDialog<Json>(
        context: context,
        builder: (context) => AlertDialog(
                title: const Text('恢复任务总预算'),
                content: SingleChildScrollView(
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Text('总预算包含已用费用。被丢弃的模型结果恢复时可能重新请求；未确认费用由服务器校验。'),
                  FormInput('总步数', n),
                  FormInput('总秒数', t),
                  FormInput('总 USD', usd),
                ])),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('返回')),
                  FilledButton(
                      onPressed: () {
                        final sn = int.tryParse(n.text),
                            st = int.tryParse(t.text);
                        if (sn == null ||
                            st == null ||
                            sn < (b['max_steps'] as int) ||
                            sn > 100 ||
                            st < (b['max_seconds'] as int) ||
                            st > 3600 ||
                            !RegExp(r'^\d+(\.\d{1,6})?$').hasMatch(usd.text) ||
                            num.parse(usd.text) <
                                num.parse('${b['max_cost_usd']}') ||
                            num.parse(usd.text) > 10) {
                          return;
                        }
                        Navigator.pop(context, {
                          'max_steps': sn,
                          'max_seconds': st,
                          'max_cost_usd': usd.text
                        });
                      },
                      child: const Text('确认并恢复')),
                ]));
    n.dispose();
    t.dispose();
    usd.dispose();
    if (value != null && mounted) await act('resume', newBudget: value);
  }

  @override
  Widget build(BuildContext context) {
    final locked = busy || controlling;
    final selectedProduct = product;
    final body = RefreshIndicator(
        onRefresh: () => load(),
        child: PageBody(children: [
          ...feedback,
          const SectionTitle('创建运营任务'),
          ChoiceField(
              '执行流程',
              template,
              templates,
              locked
                  ? null
                  : (v) => setState(() {
                        template = v;
                        if (product != null && !productInScope(product!)) {
                          product = null;
                        }
                        consentChanged();
                        operationContext = null;
                      })),
          ExpansionTile(
              title: const Text('范围与经营规则'),
              initiallyExpanded: true,
              children: [
                ScopeFields(scope,
                    enabled: !locked,
                    sevenDays: template == 'margin_review',
                    onReadRule: () =>
                        perform(() => scope.readRule(widget.app))),
              ]),
          if (template == 'margin_review')
            ChoiceField(
                '复核成本口径',
                costMode,
                const {
                  'seller_history': '卖家确认的订单行历史成本',
                  'current_estimate': '当前商品成本回推估算'
                },
                locked
                    ? null
                    : (v) => setState(() {
                          costMode = v;
                          consentChanged();
                        })),
          if ([
            'listing',
            'listing_model',
            'support',
            'support_model',
            'natural',
            'margin_review'
          ].contains(template)) ...[
            FormInput('商品或消息关键词', search, required: false, enabled: !locked),
            OutlinedButton(
                onPressed: locked ? null : () => perform(() => readOptions()),
                child: const Text('搜索商品与消息')),
            if (!['support', 'support_model'].contains(template)) ...[
              ChoiceField(
                  '目标商品',
                  product == null ? '' : '${product!['product_id']}',
                  {
                    '': '未选择',
                    for (final p in products.where(productInScope))
                      '${p['product_id']}': '${p['sku']} · ${p['name']}',
                    if (product != null)
                      '${product!['product_id']}':
                          '${product!['sku']} · ${product!['name']}',
                  },
                  locked
                      ? null
                      : (id) => perform(() async {
                            consentChanged();
                            product = id.isEmpty
                                ? null
                                : object((await widget.app.api.get(widget.app
                                    .shopPath(
                                        '/listings/products/$id')))['product']);
                          })),
              if (productsMore)
                TextButton(
                    onPressed: locked
                        ? null
                        : () => perform(() => readOptions(moreProducts: true)),
                    child: const Text('加载更多商品')),
              if (selectedProduct != null)
                ProductEvidence(widget.app, selectedProduct),
            ],
            if (!['listing', 'listing_model', 'margin_review']
                .contains(template)) ...[
              ChoiceField(
                  '目标消息',
                  supportContext == null
                      ? ''
                      : '${supportContext!['message']['id']}',
                  {
                    '': '未选择',
                    for (final m in messages.where((m) =>
                        m['source']['data_identity'] == scope.identity &&
                        m['channel'] == scope.channel))
                      '${m['id']}': '${m['message_id']} · ${m['body']}',
                    if (supportContext != null)
                      '${supportContext!['message']['id']}':
                          '${supportContext!['message']['body']}',
                  },
                  locked
                      ? null
                      : (id) => perform(() async {
                            consentChanged();
                            orderVerified = false;
                            policyIds.clear();
                            supportContext = id.isEmpty
                                ? null
                                : object(await widget.app.api.get(widget.app
                                    .shopPath('/support/messages/$id')));
                          })),
              if (messagesMore)
                TextButton(
                    onPressed: locked
                        ? null
                        : () => perform(() => readOptions(moreMessages: true)),
                    child: const Text('加载更多消息')),
              if (supportContext != null) ...[
                FactLine('消息全文', supportContext!['message']['body']),
                FactLine('标注语言', supportContext!['message']['language']),
                EvidenceSources(widget.app, supportContext!['message']),
                if (template == 'support_model') ...[
                  for (final o in rows(supportContext!['orders'])) ...[
                    FactLine('订单行',
                        '${o['order_id']} / ${o['line_id']} · ${o['sku']} · ${o['status']} · ${o['fulfillment_status']}'),
                    EvidenceSources(widget.app, o),
                  ],
                  CheckboxListTile(
                      value: orderVerified,
                      onChanged:
                          locked || rows(supportContext!['orders']).isEmpty
                              ? null
                              : (v) => setState(() {
                                    orderVerified = v!;
                                    consentChanged();
                                  }),
                      title: const Text('已人工核验客户与上述全部订单行的关联')),
                  const Text('选择适用政策，最多 10 份。订单号相同不能证明买家身份。'),
                  for (final p in rows(supportContext!['policies'])) ...[
                    CheckboxListTile(
                        value: policyIds.contains(p['id']),
                        title: Text('${p['data']?['title'] ?? '政策'}'),
                        onChanged: locked
                            ? null
                            : (v) => setState(() {
                                  if (v!) {
                                    policyIds.add(p['id'] as int);
                                  } else {
                                    policyIds.remove(p['id']);
                                  }
                                  consentChanged();
                                })),
                    PolicyEvidence(p),
                  ],
                ],
              ],
            ],
          ],
          if (useModel) ...[
            FormInput('运营目标（最多 500 字）', goal, lines: 3, enabled: !locked),
            if (template == 'daily_model') ...[
              OutlinedButton(
                  onPressed: locked
                      ? null
                      : () => perform(() async {
                            consentChanged();
                            final value = object(await widget.app.api.post(
                                widget.app.shopPath('/operations/preview'),
                                scope.payload()));
                            if (mounted) operationContext = value;
                          }),
                  child: const Text('预览将发送的运营聚合数据')),
              if (operationContext != null) ...[
                FactLine(
                    '来源版本', operationContext!['preview']['source_revision']),
                for (final b in rows(operationContext!['preview']['branches']))
                  FactLine('${b['name']} · ${b['status']}',
                      '${b['count']} 行 · ${b['reason']}'),
                for (final kind in [
                  'order_review',
                  'low_inventory',
                  'message_review',
                  'low_margin'
                ])
                  FactLine(
                      kind,
                      rows(operationContext!['preview']['findings'])
                          .where((f) => f['kind'] == kind)
                          .length),
              ],
            ],
            Text({
              'natural': '目标原文将发送给配置的模型，用于识别任务意图。',
              'question':
                  '目标原文、范围、匿名聚合指标、费用缺口及最多 20 个匿名 SKU 指标会发送；正常流程需两次模型请求。',
              'daily_model': '目标原文、范围、分支名称/状态/行数和四类候选数量会发送。',
              'listing_model': '目标、商品名称与全部参数会发送给模型，请核对原文中的信息。',
              'support_model':
                  '目标、消息原文及语言、选中政策全文/主题/核对状态和订单关联核验状态会发送。原文中的姓名、地址等也会随正文发送。',
            }[template]!),
            CheckboxListTile(
                value: allowModel,
                onChanged: locked
                    ? null
                    : (v) => setState(() {
                          allowModel = v!;
                          pendingStart = null;
                        }),
                title: Text(
                    '同意将本次目标文本发送至 ${model?['provider'] ?? '配置的模型'}，使用下方 USD 预算')),
            if (template != 'natural')
              CheckboxListTile(
                  value: allowData,
                  onChanged: locked ||
                          (template == 'daily_model' &&
                              operationContext == null)
                      ? null
                      : (v) => setState(() {
                            allowData = v!;
                            pendingStart = null;
                          }),
                  title: const Text('已核对上述业务数据，同意按所列范围发送')),
          ],
          FormInput('最多执行步数', steps,
              enabled: !locked, type: TextInputType.number),
          FormInput('最多执行秒数', seconds,
              enabled: !locked, type: TextInputType.number),
          FormInput('模型预算 USD', cost,
              enabled: !locked, type: TextInputType.number),
          FilledButton(
              onPressed: locked ? null : () => start(),
              child: Text(pendingStart == null ? '启动任务' : '核对并重试同次启动')),
          if (pendingStart != null)
            const Text('启动结果尚未确认；重试使用相同请求标识。更改输入将创建新的请求。'),
          if (run != null)
            AgentRunView(widget.app, run!,
                busy: busy,
                controlling: controlling,
                onAction: act,
                onResume: resume,
                onRetry: restoreInput,
                returnContext: widget.query),
          AuthorizationsPanel(widget.app,
              run: run,
              disabled: locked,
              focusId: int.tryParse(widget.query['authorization'] ?? ''),
              onInspect: inspect,
              onUse: (id) => act('use_authorization', authorizationId: id),
              onStart: (g) => start(grant: g)),
          const SectionTitle('执行历史'),
          OutlinedButton(
              onPressed: locked ? null : () => perform(refreshRuns),
              child: const Text('刷新运行状态')),
          if (history.isEmpty && !busy) const Text('尚无执行记录。'),
          for (final h in history)
            ListTile(
                title: Text('#${h['id']} · ${agentLabel(h['template'])}'),
                subtitle:
                    Text('${agentLabel(h['status'])} · ${h['created_at']}'),
                trailing: const Icon(Icons.chevron_right),
                onTap: locked ? null : () => inspect(h['id'] as int)),
          ExpansionTile(title: const Text('技能与模型状态'), children: [
            FactLine('提供方 / 模型', '${model?['provider']} / ${model?['model']}'),
            FactLine('可用状态', agentLabel(model?['status'])),
            FactLine('原因', model?['reason']),
            FactLine('输入 / 输出 USD 每百万 token',
                '${model?['input_usd_per_million']} / ${model?['output_usd_per_million']}'),
            FactLine('费用说明', model?['cost_note']),
            for (final s in skills)
              ExpansionTile(
                  title: Text('${s['name']} v${s['version']} · ${s['risk']}'),
                  children: [
                    for (final k in [
                      'purpose',
                      'read_scope',
                      'write_scope',
                      'idempotency',
                      'failure_policy',
                      'confirmation',
                      'max_attempts'
                    ])
                      FactLine(k, s[k]),
                    for (final k in [
                      'input_sources',
                      'permissions',
                      'tools',
                      'preconditions'
                    ])
                      FactLine(k, words(s[k])),
                  ]),
          ]),
        ]));
    return widget.embedded
        ? body
        : Scaffold(appBar: AppBar(title: const Text('AI 运营')), body: body);
  }
}
