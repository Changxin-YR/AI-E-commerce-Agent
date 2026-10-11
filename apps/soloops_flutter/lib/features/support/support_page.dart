import '../../ui/business_time_fields.dart';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/business_navigation.dart';
import '../../ui/business_widgets.dart';
import '../../ui/common.dart';
import '../../ui/content_evidence.dart';
import '../../ui/reviewed_delivery.dart';
import 'policies_page.dart';
import 'manual_message_page.dart';

class SupportPage extends StatefulWidget {
  const SupportPage(this.app,
      {super.key, this.query = const {}, this.embedded = false});
  final AppState app;
  final Map<String, String> query;
  final bool embedded;
  @override
  State<SupportPage> createState() => _SupportPageState();
}

class _SupportPageState extends BusinessPageState<SupportPage> {
  final search = TextEditingController(),
      reply = TextEditingController(),
      occurred = TextEditingController(),
      method = TextEditingController(),
      evidence = TextEditingController(),
      note = TextEditingController();
  List<Json> messages = [], history = [], manual = [];
  Json? workspace, draft;
  int offset = 0;
  bool orderVerified = false,
      reviewConfirmed = false,
      actionConfirmed = false,
      manualMore = false,
      manualLoaded = false;
  String language = '';
  String? requestId;
  final policyIds = <int>{};
  String path(String suffix) => widget.app.shopPath('/support$suffix');
  Json get snapshot => mapValue(draft?['snapshot']);
  bool get replyDirty =>
      draft != null && reply.text != '${snapshot['reply'] ?? ''}';
  bool get manualDirty =>
      [occurred, method, evidence, note].any((c) => c.text.isNotEmpty) ||
      actionConfirmed;
  bool get dirty => replyDirty || manualDirty || reviewConfirmed;
  bool get live => draft?['source_status'] == 'current';
  bool get reviewed =>
      live &&
      draft?['reviewed_at'] != null &&
      draft?['reviewed_version'] == draft?['version'];
  @override
  void initState() {
    super.initState();
    reply.addListener(replyChanged);
    for (final c in [occurred, method, evidence, note]) {
      c.addListener(actionChanged);
    }
    if (widget.embedded) widget.app.beforeNavigation = leaveEdit;
    load(initial: true);
  }

  @override
  void dispose() {
    if (widget.app.beforeNavigation == leaveEdit) {
      widget.app.beforeNavigation = null;
    }
    for (final c in [search, reply, occurred, method, evidence, note]) {
      c.dispose();
    }
    super.dispose();
  }

  void replyChanged() {
    if (mounted) setState(() => reviewConfirmed = false);
  }

  void actionChanged() {
    if (mounted) {
      setState(() {
        actionConfirmed = false;
        requestId = null;
      });
    }
  }

  void resetEvidence() {
    orderVerified = false;
    policyIds.clear();
  }

  void clearManual() {
    for (final c in [occurred, method, evidence, note]) {
      c.clear();
    }
    actionConfirmed = false;
    requestId = null;
  }

  void accept(Json value, {bool keepManual = false}) {
    draft = value;
    reply.text = '${mapValue(value['snapshot'])['reply'] ?? ''}';
    language =
        '${value['reviewed_language'] ?? mapValue(mapValue(value['snapshot'])['message'])['language'] ?? ''}';
    if (!['en', 'zh'].contains(language)) language = '';
    reviewConfirmed = false;
    if (!keepManual) clearManual();
    manual = [];
    manualMore = false;
    manualLoaded = false;
  }

  Future<bool> leaveEdit() async {
    if (busy) {
      if (mounted) setState(() => error = '当前请求处理中，请等待结果后再切换。');
      return false;
    }
    if (!dirty) return true;
    return await confirmAction(
        context, '放弃未保存修改', '回复正文、审阅确认或人工操作表单尚未保存。已保存记录仍保留。');
  }

  Future<void> lists() async {
    final values = await Future.wait([
      widget.app.api.get(path('/messages'),
          query: {'q': search.text.trim(), 'offset': offset}),
      widget.app.api.get(path('/drafts')),
    ]);
    if (mounted) {
      messages = rows(values[0]);
      history = rows(values[1]);
    }
  }

  Future<void> load({bool initial = false}) async {
    if (!initial && !await leaveEdit()) return;
    await perform(() async {
      await lists();
      if (!mounted) return;
      final id = initial
          ? int.tryParse(widget.query['draft'] ?? '')
          : draft?['id'] as int?;
      final mid = initial
          ? int.tryParse(widget.query['message'] ?? '')
          : workspace?['message']['id'] as int?;
      resetEvidence();
      if (id != null) {
        final value = object(await widget.app.api.get(path('/drafts/$id')));
        if (mounted) accept(value);
      }
      if (mid != null) {
        final value = object(await widget.app.api.get(path('/messages/$mid')));
        if (mounted) workspace = value;
      }
    });
  }

  Future<void> choose(int id) async {
    if (!await leaveEdit()) return;
    await perform(() async {
      final value = object(await widget.app.api.get(path('/messages/$id')));
      if (mounted) {
        workspace = value;
        draft = null;
        resetEvidence();
        clearManual();
        reviewConfirmed = false;
      }
    });
  }

  Future<void> inspect(int id) async {
    if (!await leaveEdit()) return;
    await perform(() async {
      final value = object(await widget.app.api.get(path('/drafts/$id')));
      if (mounted) {
        workspace = null;
        resetEvidence();
        accept(value);
      }
    });
  }

  Future<void> generate() => perform(() async {
        if (policyIds.length > 10) throw const FormatException('最多选择 10 份政策。');
        final w = workspace!;
        final value = object(await widget.app.api
            .post(path('/messages/${w['message']['id']}/generate'), {
          'expected_source_row_id': w['message']['source']['row_id'],
          'expected_order_row_ids': orderVerified
              ? rows(w['orders']).map((o) => o['source']['row_id']).toList()
              : [],
          'order_verified': orderVerified,
          'policy_ids': policyIds.toList(),
        }));
        if (mounted) {
          accept(value);
          await lists();
        }
      }, message: '候选回复与接管摘要已保存，请核对全部诉求和依据。');
  Future<void> mutate(String action) => perform(() async {
        Json value;
        if (action == 'edit') {
          if (reply.text.trim().isEmpty || reply.text.length > 6000) {
            throw const FormatException('回复须为 1–6000 字。');
          }
          value = object(await widget.app.api.post(
              path('/drafts/${draft!['id']}/edit'),
              {'expected_version': draft!['version'], 'reply': reply.text}));
        } else if (action == 'review') {
          if (!reviewConfirmed ||
              replyDirty ||
              manualDirty ||
              language.isEmpty) {
            throw const FormatException('请核对全文和目标语言。');
          }
          value = object(await widget.app.api
              .post(path('/drafts/${draft!['id']}/review'), {
            'expected_version': draft!['version'],
            'target_language': language,
            'confirmed': true
          }));
        } else {
          if (dirty) throw const FormatException('请先保存或放弃未完成修改。');
          value = object(await widget.app.api.post(
              path('/drafts/${draft!['id']}/action'),
              {'expected_version': draft!['version'], 'action': action}));
        }
        if (mounted) {
          accept(value);
          await lists();
        }
      }, message: '当前版本处理结果已保存。');
  Future<void> deliver(String action) => perform(() async {
        final current = draft!;
        final value = object(await widget.app.api.get(
            path('/drafts/${current['id']}/delivery'),
            query: {'expected_version': current['version']}));
        if (!mounted || dirty || draft?['version'] != current['version']) {
          return;
        }
        success = await deliverArtifact(widget.app, value, action);
      });
  Future<void> readManual({bool more = false}) async {
    final value = rows(await widget.app.api.get(
        path('/drafts/${draft!['id']}/manual-actions'),
        query: more && manual.isNotEmpty ? {'before': manual.last['id']} : {}));
    if (mounted) {
      manual = more ? [...manual, ...value] : value;
      manualMore = value.length == 50;
      manualLoaded = true;
    }
  }

  Future<void> record() => perform(() async {
        if (!reviewed || replyDirty || reviewConfirmed || !actionConfirmed) {
          throw const FormatException('请先审阅版本并确认人工操作。');
        }
        if (method.text.trim().length < 2 ||
            method.text.length > 80 ||
            evidence.text.trim().length < 2 ||
            evidence.text.length > 500 ||
            note.text.length > 1000) {
          throw const FormatException('方式须为 2–80 字，证据索引 2–500 字，备注最多 1000 字。');
        }
        final at = awareDate(occurred.text, '人工操作时间', required: true);
        requestId ??= newRequestId();
        await widget.app.api
            .post(path('/drafts/${draft!['id']}/manual-actions'), {
          'request_id': requestId,
          'expected_version': draft!['version'],
          'occurred_at': at,
          'method': method.text.trim(),
          'evidence_ref': evidence.text.trim(),
          'note': note.text.trim(),
          'confirmed': true,
        });
        if (mounted) {
          clearManual();
          await readManual();
        }
      }, message: '人工操作自报已登记。此记录不等于平台回执，系统外部状态仍为未提交。');
  Future<void> openSupplement(bool policies) async {
    if (!await leaveEdit() || !mounted) return;
    if (dirty && draft != null) setState(() => accept(draft!));
    await Navigator.push<void>(
        context,
        MaterialPageRoute(
            builder: (_) => policies
                ? PoliciesPage(widget.app)
                : ManualMessagePage(widget.app)));
    if (mounted) await load();
  }

  @override
  Widget build(BuildContext context) {
    final editable = live && draft?['status'] != 'archived';
    final content = RefreshIndicator(
        onRefresh: load,
        child: PageBody(children: [
          ...feedback,
          Wrap(spacing: 12, children: [
            OutlinedButton(
                onPressed: busy ? null : () => openSupplement(false),
                child: const Text('手工录入消息')),
            OutlinedButton(
                onPressed: busy ? null : () => openSupplement(true),
                child: const Text('政策与 FAQ')),
          ]),
          FormInput('查找消息 / 订单号', search, required: false, enabled: !busy),
          OutlinedButton(
              onPressed: busy
                  ? null
                  : () => perform(() async {
                        offset = 0;
                        await lists();
                      }),
              child: const Text('搜索')),
          if (messages.isEmpty && !busy)
            TextButton(
                onPressed: () => openBusinessPath(
                    context, widget.app, '/imports', {'kind': 'messages'}),
                child: const Text('没有匹配消息，导入客服消息文件')),
          for (final m in messages)
            ListTile(
                title: Text('${m['message_id']} · ${m['body']}'),
                subtitle: Text(
                    '${m['channel']} · ${m['language']} · ${m['sent_at']}'),
                onTap: busy ? null : () => choose(m['id'] as int)),
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
            if (messages.length == 50)
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
            const SectionTitle('核对消息与订单'),
            FactLine('消息全文', workspace!['message']['body']),
            FactLine('消息语言 / 来源渠道',
                '${workspace!['message']['language']} / ${workspace!['message']['channel']}'),
            FactLine('消息时间 / 待核验订单',
                '${workspace!['message']['sent_at']} / ${workspace!['message']['order_id']}'),
            EvidenceSources(widget.app, workspace!['message']),
            for (final o in rows(workspace!['orders'])) ...[
              FactLine('订单行',
                  '${o['order_id']} / ${o['line_id']} · ${o['sku']} · ${o['status']} · ${o['fulfillment_status']}'),
              EvidenceSources(widget.app, o),
            ],
            const Text('订单号匹配不能证明客户身份。请在原渠道核验客户与全部订单行的关联。'),
            CheckboxListTile(
                value: orderVerified,
                onChanged: busy || rows(workspace!['orders']).isEmpty
                    ? null
                    : (v) => setState(() => orderVerified = v!),
                title: const Text('已人工核验客户与上述全部订单行的关联')),
            const SectionTitle('选择适用政策（最多 10 份）'),
            if (rows(workspace!['policies']).isEmpty)
              const Text('暂无适用政策，将保留人工核实提示。'),
            for (final p in rows(workspace!['policies'])) ...[
              CheckboxListTile(
                  value: policyIds.contains(p['id']),
                  title: Text('${p['data']?['title'] ?? '政策'}'),
                  onChanged: busy
                      ? null
                      : (v) => setState(() {
                            if (v!) {
                              policyIds.add(p['id'] as int);
                            } else {
                              policyIds.remove(p['id']);
                            }
                          })),
              PolicyEvidence(p),
            ],
            FilledButton(
                onPressed:
                    busy || dirty || policyIds.length > 10 ? null : generate,
                child: const Text('生成本地候选回复')),
            TextButton(
                onPressed: busy || dirty
                    ? null
                    : () => openBusinessPath(context, widget.app, '/agent', {
                          ...widget.query,
                          'shop': '${widget.app.shopId}',
                          'mode': 'support_model',
                          'message': '${workspace!['message']['id']}',
                          'identity':
                              '${workspace!['message']['source']['data_identity']}',
                          'channel': '${workspace!['message']['channel']}',
                        }),
                child: const Text('用 AI 组织客服候选')),
            for (final d in rows(workspace!['drafts']))
              ListTile(
                  title: Text('消息草稿 #${d['id']} · ${d['status']}'),
                  onTap: busy ? null : () => inspect(d['id'] as int)),
          ],
          if (draft != null) ...[
            SectionTitle('客服草稿 #${draft!['id']} · v${draft!['version']}'),
            FactLine('处理状态 / 来源',
                '${draft!['status']} / ${draft!['source_status']}'),
            FactLine(
                '生成方式 / 更新时间', '${draft!['engine']} / ${draft!['updated_at']}'),
            const Text('存档只记录处理状态，退款等原渠道业务仍须单独处理。系统外部未提交。'),
            if (snapshot.isNotEmpty) ...[
              SupportEvidence(widget.app, snapshot),
              FormInput('回复正文（最多 6000 字）', reply,
                  lines: 8, enabled: !busy && !manualDirty && editable),
              if (replyDirty) const Text('正文修改后须重新审阅当前版本。'),
              OutlinedButton(
                  onPressed: busy || manualDirty || !editable || !replyDirty
                      ? null
                      : () => mutate('edit'),
                  child: const Text('保存修改')),
              if (dirty)
                TextButton(
                    onPressed:
                        busy ? null : () => setState(() => accept(draft!)),
                    child: const Text('放弃未保存修改')),
              Wrap(spacing: 12, children: [
                if (draft!['status'] != 'human_review')
                  OutlinedButton(
                      onPressed: busy || dirty || !editable
                          ? null
                          : () => mutate('handoff'),
                      child: const Text('标记需要人工')),
                if (draft!['status'] != 'archived')
                  OutlinedButton(
                      onPressed: busy || dirty ? null : () => mutate('archive'),
                      child: const Text('存档处理记录'))
                else
                  OutlinedButton(
                      onPressed: busy || dirty || !live
                          ? null
                          : () => mutate('reopen'),
                      child: const Text('重开并转人工')),
              ]),
              const SectionTitle('审阅当前版本'),
              if (reviewed)
                FactLine('已审阅',
                    '${draft!['reviewed_at']} · ${draft!['reviewed_language']}'),
              ChoiceField(
                  '已核对目标语言',
                  language,
                  const {'': '请选择', 'en': 'English', 'zh': '中文'},
                  busy || replyDirty || manualDirty || !live
                      ? null
                      : (v) => setState(() {
                            language = v;
                            reviewConfirmed = false;
                          })),
              CheckboxListTile(
                  value: reviewConfirmed,
                  onChanged: busy || replyDirty || manualDirty || !live
                      ? null
                      : (v) => setState(() => reviewConfirmed = v!),
                  title: const Text('已审阅回复全文、订单关联、政策有效期、目标语言与全部接管提示')),
              FilledButton(
                  onPressed: busy ||
                          !reviewConfirmed ||
                          language.isEmpty ||
                          replyDirty ||
                          manualDirty ||
                          !live ||
                          reply.text.trim().isEmpty
                      ? null
                      : () => mutate('review'),
                  child: const Text('确认当前版本已审阅')),
              DeliveryButtons(
                  enabled: !busy && !dirty && reviewed, onAction: deliver),
              const SectionTitle('登记原渠道人工操作'),
              const Text('记录原渠道人工操作的自报证据；可填写证据编号或本机文件索引。此登记不等于平台回执。'),
              BusinessDateTimeField('操作时间', occurred,
                  enabled:
                      !busy && reviewed && !replyDirty && !reviewConfirmed),
              FormInput('操作方式', method,
                  enabled:
                      !busy && reviewed && !replyDirty && !reviewConfirmed),
              FormInput('证据索引', evidence,
                  enabled:
                      !busy && reviewed && !replyDirty && !reviewConfirmed),
              FormInput('备注', note,
                  lines: 3,
                  required: false,
                  enabled:
                      !busy && reviewed && !replyDirty && !reviewConfirmed),
              CheckboxListTile(
                  value: actionConfirmed,
                  onChanged: busy || !reviewed || replyDirty || reviewConfirmed
                      ? null
                      : (v) => setState(() => actionConfirmed = v!),
                  title: const Text('确认已在原渠道人工操作，本记录为本人自报')),
              FilledButton(
                  onPressed: busy ||
                          !reviewed ||
                          !actionConfirmed ||
                          replyDirty ||
                          reviewConfirmed
                      ? null
                      : record,
                  child: Text(requestId == null ? '登记人工操作' : '核对并重试同次登记')),
              TextButton(
                  onPressed: busy ? null : () => setState(clearManual),
                  child: const Text('清空未保存操作')),
            ] else
              const Text('关联来源已清除，正文与证据快照已擦除。'),
            TextButton(
                onPressed:
                    busy || dirty ? null : () => perform(() => readManual()),
                child: const Text('读取人工操作历史')),
            if (manualLoaded && manual.isEmpty) const Text('暂无人工操作记录。'),
            for (final r in manual)
              ExpansionTile(
                  title: Text('自报 #${r['id']} · 草稿 v${r['draft_version']}'),
                  children: [
                    FactLine('操作时间 / 登记时间',
                        '${r['occurred_at']} / ${r['recorded_at']}'),
                    if (r['details'] != null) ...[
                      FactLine('方式', r['details']['method']),
                      FactLine('证据索引', r['details']['evidence_ref']),
                      FactLine('备注', r['details']['note']),
                    ] else
                      const Text('相关来源已清除，证据内容已擦除。'),
                    const Text('卖家自报 · 系统外部未提交'),
                  ]),
            if (manualMore)
              TextButton(
                  onPressed: busy || dirty
                      ? null
                      : () => perform(() => readManual(more: true)),
                  child: const Text('加载更早人工记录')),
            OutlinedButton(
                onPressed: busy ? null : load, child: const Text('回读当前版本与来源')),
          ],
          const SectionTitle('客服处理历史'),
          if (history.isEmpty && !busy) const Text('尚无草稿记录。'),
          for (final d in history)
            ListTile(
                title: Text(
                    '#${d['id']} · ${d['snapshot']?['message']?['body'] ?? '内容已清除'}'),
                subtitle: Text(
                    '${d['status']} · ${d['source_status']} · ${d['updated_at']}'),
                onTap: busy ? null : () => inspect(d['id'] as int)),
        ]));
    final page = widget.embedded
        ? content
        : Scaffold(appBar: AppBar(title: const Text('客服')), body: content);
    return PopScope(
        canPop: !dirty && !busy,
        onPopInvokedWithResult: (didPop, _) async {
          if (!didPop && await leaveEdit() && context.mounted) {
            Navigator.pop(context);
          }
        },
        child: page);
  }
}
