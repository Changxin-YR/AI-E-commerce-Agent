import '../../ui/edit_guard.dart';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/business_navigation.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/finance_inputs.dart';
import '../finance/finance_common.dart' show FinanceRows;
import '../imports/import_repository.dart';

const mailLabels = {
  'not_configured': '未配置',
  'disconnected': '尚未连接',
  'verifying': '等待邮箱验证码',
  'active': '已验证 / 有效',
  'configuration_changed': '配置已变化',
  'domain_unverified': '发送域未验证',
  'sender_unverified': '发送账号验证未通过',
  'smtp_accepted': 'SMTP已接受',
  'expired': '已过期',
  'locked': '验证次数用尽',
  'revoked': '已撤销',
  'draft': '等待审批',
  'sending': '提交中',
  'unknown': '结果未知，请回查',
  'accepted': '通道已接受',
  'rejected': '已拒绝',
  'cancelled': '已取消',
  'used': '已消耗',
  'invalidated': '已失效',
  'channel_unavailable': '通道不可用',
  'current': '当前来源',
  'stale': '来源已变化',
  'cleared': '正文已清除',
  'submitted': '已取得回执',
  'sent': '通道已发出',
  'delivered': '通道报告送达',
  'bounced': '退信',
  'failed': '发送失败',
  'complained': '投诉',
  'delivery_delayed': '投递延迟'
};
String mailLabel(dynamic value) => mailLabels[value] ?? '$value';

class OutboundPage extends StatefulWidget {
  const OutboundPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<OutboundPage> createState() => _OutboundPageState();
}

class _OutboundPageState extends BusinessPageState<OutboundPage> {
  late String identity = widget.query['identity'] ?? 'user_import',
      sourceChannel = widget.query['channel'] ?? 'generic';
  final code = TextEditingController(), recipient = TextEditingController();
  List<Json> messages = [], runs = [];
  Json? channel;
  int? cursor, runId;
  bool confirmed = false, uncertain = false;
  String path(String tail) => widget.app.shopPath('/outbound$tail');
  @override
  void initState() {
    super.initState();
    Future.microtask(() => perform(() async {
          await refresh();
          final id = int.tryParse(widget.query['mail'] ?? '');
          if (id != null && mounted) await open(id);
        }));
  }

  Future<void> refresh() async {
    final data = await Future.wait([
      widget.app.api.get(path('/channel')),
      widget.app.api.get(path('/messages')),
      widget.app.api.get(widget.app.shopPath('/operations/runs'),
          query: {'data_identity': identity, 'channel': sourceChannel})
    ]);
    if (!mounted) return;
    setState(() {
      channel = object(data[0]);
      recipient.text = '${channel!['recipient']}';
      final page = object(data[1]);
      messages = rows(page['items']);
      cursor = page['next_before_id'] as int?;
      runs =
          rows(data[2]).where((r) => r['source_status'] == 'current').toList();
      runId = runs.firstOrNull?['id'] as int?;
      confirmed = false;
      uncertain = false;
      code.clear();
    });
  }

  Future<void> channelAction(String action) => perform(() async {
        try {
          dynamic data;
          if (action == 'connect') {
            if (!confirmed) return;
            data = await widget.app.api
                .post(path('/channel/connect'), {'confirmed': true});
          } else if (action == 'verify') {
            if (!RegExp(r'^\d{8}$').hasMatch(code.text.trim())) {
              throw const FormatException('请填写8位验证码。');
            }
            data = await widget.app.api.post(
                path('/channel/${channel!['id']}/verify'),
                {'code': code.text.trim()});
          } else {
            data = await widget.app.api
                .post(path('/channel/${channel!['id']}/revoke'));
          }
          if (mounted) {
            setState(() {
              channel = object(data);
              confirmed = false;
              code.clear();
            });
          }
        } catch (e) {
          uncertain = true;
          confirmed = false;
          rethrow;
        }
      });
  Future<void> open(int id) async {
    await Navigator.of(context).push<void>(
        MaterialPageRoute(builder: (_) => OutboundMailPage(widget.app, id)));
  }

  Future<void> create() => perform(() async {
        if (runId == null) throw const FormatException('请选择当前来源的运营检查。');
        final value = object(await widget.app.api.post(path('/messages'), {
          'run_id': runId,
          if (channel?['provider'] == 'qq_smtp')
            'recipient': requiredText(recipient.text, '收件邮箱', 254)
        }));
        if (mounted) await open(value['id'] as int);
        if (mounted) await refresh();
      });
  @override
  void dispose() {
    code.dispose();
    recipient.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('测试外发管理')),
      body: PageBody(children: [
        ...feedback,
        ChoiceField(
            '摘要数据身份',
            identity,
            importIdentities,
            busy
                ? null
                : (v) {
                    setState(() => identity = v);
                    perform(refresh);
                  }),
        ChoiceField(
            '摘要来源渠道',
            sourceChannel,
            importChannels,
            busy
                ? null
                : (v) {
                    setState(() => sourceChannel = v);
                    perform(refresh);
                  }),
        OutlinedButton(
            onPressed: busy ? null : () => perform(refresh),
            child: const Text('刷新通道与记录')),
        if (uncertain) const Notice('操作结果待回读，请刷新通道后继续。'),
        if (channel != null) ...[
          const SectionTitle('发送通道'),
          FactLine('配置', channel!['configured'] == true ? '已配置' : '尚未配置'),
          FactLine('通道', channel!['provider']),
          FactLine('状态', mailLabel(channel!['status'])),
          FactLine('发件地址', channel!['sender']),
          FactLine('测试收件地址', channel!['recipient']),
          FactLine('验证有效期', channel!['verification_expires_at']),
          FactLine('完成验证时间', channel!['verified_at']),
          if (channel!['configured'] != true)
            const Text('由部署者为当前账号与店铺配置发送通道、凭据和测试收件邮箱。'),
          if (channel!['configured'] == true &&
              channel!['status'] != 'active') ...[
            FactLine('验证邮件主题', channel!['verification_subject']),
            FactLine('验证邮件模板', channel!['verification_template']),
            CheckboxListTile(
                value: confirmed,
                onChanged: busy || uncertain
                    ? null
                    : (v) => setState(() => confirmed = v ?? false),
                title: const Text('确认向上述测试邮箱提交一封验证邮件')),
            FilledButton(
                onPressed: busy || uncertain || !confirmed
                    ? null
                    : () => channelAction('connect'),
                child: const Text('连接并请求验证邮件')),
            if (channel!['id'] != null) ...[
              FormInput('邮箱验证码（8位）', code,
                  secret: true, enabled: !busy && !uncertain),
              OutlinedButton(
                  onPressed:
                      busy || uncertain ? null : () => channelAction('verify'),
                  child: const Text('验证测试邮箱')),
            ],
          ],
          if (channel!['id'] != null)
            OutlinedButton(
                onPressed: busy || uncertain
                    ? null
                    : () async {
                        if (await confirmAction(
                            context, '撤销发送通道', '撤销后停止新的提交；已开始的邮件提交仍可能送达。')) {
                          await channelAction('revoke');
                        }
                      },
                child: const Text('撤销通道')),
          const SectionTitle('创建待审摘要'),
          ChoiceField(
              '当前来源的运营检查',
              runId?.toString(),
              {
                for (final r in runs)
                  '${r['id']}': '检查 #${r['id']} · ${r['created_at']}'
              },
              busy ? null : (v) => setState(() => runId = int.parse(v))),
          if (runId != null)
            OutlinedButton(
                onPressed: () =>
                    openBusinessPath(context, widget.app, '/?run=$runId'),
                child: const Text('回读选中检查与依据')),
          if (channel!['provider'] == 'qq_smtp')
            FormInput('收件邮箱', recipient, enabled: !busy),
          FilledButton(
              onPressed: busy || channel!['status'] != 'active' ? null : create,
              child: const Text('创建摘要并审阅全文')),
        ],
        const SectionTitle('发送记录'),
        FinanceRows(messages,
            builder: (m) => ListTile(
                title: Text('#${m['id']} · ${m['subject'] ?? '正文已清除'}'),
                subtitle: Text('${mailLabel(m['status'])} · ${m['recipient']}'),
                onTap: busy ? null : () => open(m['id'] as int))),
        if (cursor != null)
          OutlinedButton(
              onPressed: busy
                  ? null
                  : () => perform(() async {
                        final value = object(await widget.app.api.get(
                            path('/messages'),
                            query: {'before_id': cursor}));
                        if (mounted) {
                          setState(() {
                            messages = [...messages, ...rows(value['items'])];
                            cursor = value['next_before_id'] as int?;
                          });
                        }
                      }),
              child: const Text('加载更多发送记录'))
      ]));
}

class OutboundMailPage extends StatefulWidget {
  const OutboundMailPage(this.app, this.id, {super.key});
  final AppState app;
  final int id;
  @override
  State<OutboundMailPage> createState() => _OutboundMailPageState();
}

class _OutboundMailPageState extends BusinessPageState<OutboundMailPage> {
  final subject = TextEditingController(),
      body = TextEditingController(),
      hours = TextEditingController(text: '1'),
      receipt = TextEditingController(),
      evidence = TextEditingController();
  Json? mail;
  bool editing = false, confirmed = false, received = false, mustRead = false;
  String path(String tail) =>
      widget.app.shopPath('/outbound/messages/${widget.id}$tail');
  bool get editable =>
      mail?['status'] == 'draft' && mail?['source_status'] == 'current';
  bool get locked => busy || mustRead;
  Json? get grant => rows(mail?['approvals'])
      .where((a) => a['status'] == 'active')
      .firstOrNull;
  @override
  void initState() {
    super.initState();
    hours.addListener(reset);
    Future.microtask(() => perform(read));
  }

  void reset() {
    if (mounted) setState(() => confirmed = false);
  }

  void accept(Json value) {
    mail = value;
    subject.text = '${value['subject'] ?? ''}';
    body.text = '${value['body'] ?? ''}';
    editing = false;
    confirmed = false;
    received = false;
    mustRead = false;
    evidence.clear();
    receipt.clear();
  }

  Future<void> read() async {
    final value = object(await widget.app.api.get(path('')));
    if (mounted) setState(() => accept(value));
  }

  Future<void> mutate(String action, Json data, {String method = 'POST'}) =>
      perform(() async {
        try {
          final value = object(
              await widget.app.api.send(method, path(action), body: data));
          if (mounted) setState(() => accept(value));
        } catch (e) {
          mustRead = true;
          confirmed = false;
          received = false;
          rethrow;
        }
      });
  Future<void> approve(String mode) async {
    if (!confirmed || mail == null) return;
    await perform(() async {
      final duration = integerInput(hours.text, '授权有效小时', 1, 24);
      try {
        final value = object(await widget.app.api.post(path('/approve'), {
          'version': mail!['version'],
          'mode': mode,
          'valid_hours': duration,
          'confirmed': true
        }));
        if (mounted) setState(() => accept(value));
        success = '审批已保存，请核对有效授权后提交。';
      } catch (e) {
        mustRead = true;
        confirmed = false;
        rethrow;
      }
    });
  }

  @override
  void dispose() {
    for (final c in [subject, body, hours, receipt, evidence]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => EditGuard(
      app: widget.app,
      controllers: [subject, body, receipt, evidence],
      dirty: () =>
          (editing &&
              (subject.text != '${mail?['subject'] ?? ''}' ||
                  body.text != '${mail?['body'] ?? ''}')) ||
          evidence.text.isNotEmpty ||
          receipt.text.isNotEmpty,
      busy: busy,
      child: Scaffold(
          appBar: AppBar(title: Text('外发摘要 #${widget.id}')),
          body: PageBody(children: [
            ...feedback,
            OutlinedButton(
                onPressed: busy ? null : () => perform(read),
                child: const Text('回读当前发送记录')),
            if (mustRead) const Notice('请先回读状态。提交结果未知时使用回执核对，系统不会自动重发。'),
            if (mail != null) ...[
              FactLine('状态', mailLabel(mail!['status'])),
              FactLine('来源 / 通道',
                  '${mailLabel(mail!['source_status'])} / ${mailLabel(mail!['channel_status'])}'),
              FactLine('发件人', mail!['sender']),
              FactLine('收件人', mail!['recipient']),
              FactLine('内容版本', mail!['version']),
              OutlinedButton(
                  onPressed: () => openBusinessPath(
                      context, widget.app, '/?run=${mail!['run_id']}'),
                  child: const Text('查看来源运营检查')),
              const Text('每份摘要最多提交一封邮件。批准绑定当前地址、全文与来源；邮件提交后无法撤回。通道费用依服务配置而定。'),
              if (mail!['body'] != null) ...[
                SectionTitle('${mail!['subject']}'),
                SelectableText('${mail!['body']}'),
                FactLine('内容校验摘要', mail!['content_hash']),
              ] else
                const Text('来源正文已清除，提交状态和必要审计仍保留。'),
              if (editable)
                Wrap(spacing: 8, children: [
                  OutlinedButton(
                      onPressed: locked
                          ? null
                          : () => setState(() {
                                editing = !editing;
                                confirmed = false;
                              }),
                      child: Text(editing ? '取消编辑' : '编辑主题与全文')),
                  OutlinedButton(
                      onPressed: locked
                          ? null
                          : () =>
                              mutate('/reject', {'version': mail!['version']}),
                      child: const Text('拒绝此发送'))
                ]),
              if (editing) ...[
                FormInput('邮件主题', subject, enabled: !locked),
                FormInput('邮件全文', body, lines: 12, enabled: !locked),
                const Text('保存正文后，已有审批会失效。'),
                FilledButton(
                    onPressed: locked
                        ? null
                        : () async {
                            try {
                              final s = requiredText(subject.text, '邮件主题', 200),
                                  b = requiredText(body.text, '邮件正文', 12000);
                              if (RegExp(r'[\x00-\x1f\x7f]').hasMatch(s)) {
                                throw const FormatException('主题不能包含控制字符或换行。');
                              }
                              await mutate(
                                  '',
                                  {
                                    'version': mail!['version'],
                                    'subject': s,
                                    'body': b
                                  },
                                  method: 'PATCH');
                            } catch (e) {
                              if (mounted) setState(() => error = '$e');
                            }
                          },
                    child: const Text('保存正文版本')),
              ],
              if (editable &&
                  !editing &&
                  mail!['channel_status'] == 'active') ...[
                FormInput('预授权有效小时（1–24）', hours, enabled: !locked),
                CheckboxListTile(
                    value: confirmed,
                    onChanged: locked
                        ? null
                        : (v) => setState(() => confirmed = v ?? false),
                    title: const Text('已审阅地址与完整正文，确认一次邮件提交及通道费用')),
                Wrap(spacing: 8, children: [
                  FilledButton(
                      onPressed:
                          locked || !confirmed ? null : () => approve('once'),
                      child: const Text('保存单次批准')),
                  OutlinedButton(
                      onPressed: locked || !confirmed
                          ? null
                          : () => approve('preauthorized'),
                      child: const Text('创建限一次预授权'))
                ]),
              ],
              if (grant != null && !editing) ...[
                FactLine('有效审批',
                    '#${grant!['id']} · 限1次 · 到期 ${grant!['expires_at']}'),
                Wrap(spacing: 8, children: [
                  FilledButton(
                      onPressed: locked
                          ? null
                          : () => mutate('/send', {
                                'version': mail!['version'],
                                'approval_id': grant!['id']
                              }),
                      child: const Text('按有效授权提交一次')),
                  OutlinedButton(
                      onPressed: locked
                          ? null
                          : () =>
                              mutate('/approvals/${grant!['id']}/revoke', {}),
                      child: const Text('撤销此授权'))
                ])
              ],
              if (mail!['dispatch_at'] != null) ...[
                const SectionTitle('提交与回执'),
                FactLine('提交时间', mail!['dispatch_at']),
                FactLine('Message-ID', mail!['smtp_message_id']),
                FactLine('通道回执', mail!['receipt_id']),
                FactLine('通道事件', mailLabel(mail!['provider_event'])),
                FactLine('上次回查时间', mail!['checked_at']),
                if (mail!['provider'] == 'qq_smtp')
                  const Text(
                      'SMTP 不提供通道回执查询。请核对收件箱或垃圾箱中的地址、主题、全文与 Message-ID，再填写实际收件证据。')
                else if (mail!['body'] != null) ...[
                  FormInput('通道后台邮件ID（可选，UUID）', receipt,
                      required: false, enabled: !busy),
                  OutlinedButton(
                      onPressed: busy || mail!['status'] == 'sending'
                          ? null
                          : () => mutate('/reconcile', {
                                'receipt_id': receipt.text.trim().isEmpty
                                    ? null
                                    : receipt.text.trim()
                              }),
                      child: const Text('只读回查发送结果')),
                ],
                const Text('通道接受或报告送达仍需核实实际收件。'),
                if (mail!['body'] != null &&
                    (mail!['status'] == 'accepted' ||
                        (mail!['provider'] == 'qq_smtp' &&
                            mail!['status'] == 'unknown'))) ...[
                  FormInput('实际收件证据', evidence, lines: 4, enabled: !locked),
                  CheckboxListTile(
                      value: received,
                      onChanged: locked
                          ? null
                          : (v) => setState(() => received = v ?? false),
                      title: const Text('已核对实际收件，此项为人工证据声明')),
                  OutlinedButton(
                      onPressed: locked || !received
                          ? null
                          : () async {
                              try {
                                final note =
                                    requiredText(evidence.text, '实际收件证据', 500);
                                if (note.length < 5) {
                                  throw const FormatException('证据至少5字符。');
                                }
                                await mutate('/receipt',
                                    {'confirmed': true, 'evidence': note});
                              } catch (e) {
                                if (mounted) setState(() => error = '$e');
                              }
                            },
                      child: const Text('记录人工收件证据')),
                ],
                FactLine('人工收件声明时间', mail!['received_at']),
                FactLine('收件证据', mail!['receipt_evidence']),
              ],
              const SectionTitle('审批与消耗历史'),
              for (final a in rows(mail!['approvals']))
                ListTile(
                    title: Text(
                        '#${a['id']} · ${a['mode'] == 'once' ? '单次批准' : '预授权'} · ${mailLabel(a['status'])}'),
                    subtitle: Text(
                        '已用 ${a['used_count']} / ${a['max_uses']} 次\n创建 ${a['created_at']}\n到期 ${a['expires_at']}')),
            ]
          ])));
}
