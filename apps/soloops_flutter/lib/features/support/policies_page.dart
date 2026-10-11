import '../../ui/business_time_fields.dart';
import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../ui/business_widgets.dart';
import '../../ui/common.dart';
import '../../ui/content_evidence.dart';
import '../imports/import_repository.dart';

class PoliciesPage extends StatefulWidget {
  const PoliciesPage(this.app, {super.key});
  final AppState app;
  @override
  State<PoliciesPage> createState() => _PoliciesPageState();
}

class _PoliciesPageState extends BusinessPageState<PoliciesPage> {
  final search = TextEditingController();
  final fields = <String, TextEditingController>{
    for (final k in [
      'code',
      'title',
      'text',
      'market',
      'source',
      'source_version',
      'valid_from',
      'valid_until'
    ])
      k: TextEditingController()
  };
  final formKey = GlobalKey<FormState>();
  List<Json> policies = [];
  int offset = 0;
  int? expected;
  bool editing = false, confirmed = false, saved = false;
  String topic = 'faq',
      channel = 'generic',
      language = 'en',
      identity = 'user_import';
  String path([String suffix = '']) =>
      widget.app.shopPath('/support/policies$suffix');
  @override
  void initState() {
    super.initState();
    for (final c in fields.values) {
      c.addListener(invalidate);
    }
    load();
  }

  @override
  void dispose() {
    search.dispose();
    for (final c in fields.values) {
      c.dispose();
    }
    super.dispose();
  }

  void invalidate() {
    if (mounted) setState(() => confirmed = false);
  }

  Future<void> read() async {
    final value = rows(await widget.app.api
        .get(path(), query: {'q': search.text.trim(), 'offset': offset}));
    if (mounted) policies = value;
  }

  Future<void> load() => perform(read);
  Future<void> edit([Json? policy]) async {
    if (editing && !await confirmAction(context, '放弃未保存政策', '将重新填写此政策表单。')) {
      return;
    }
    final data = mapValue(policy?['data']);
    setState(() {
      expected = policy?['id'] as int?;
      editing = true;
      for (final e in fields.entries) {
        e.value.text = '${data[e.key] ?? ''}';
      }
      fields['market']!.text =
          '${data['market'] ?? widget.app.shop?['market'] ?? ''}';
      topic = '${data['topic'] ?? 'faq'}';
      channel = '${data['channel'] ?? 'generic'}';
      language = '${data['language'] ?? 'en'}';
      identity = '${data['data_identity'] ?? 'user_import'}';
      confirmed = false;
    });
  }

  Future<void> save() async {
    if (!formKey.currentState!.validate()) return;
    await perform(() async {
      final data = <String, dynamic>{
        for (final e in fields.entries) e.key: e.value.text.trim()
      };
      for (final e in const {
        'code': 80,
        'title': 120,
        'text': 4000,
        'source': 400,
        'source_version': 80
      }.entries) {
        if ((data[e.key] as String).length > e.value) {
          throw FormatException('${e.key} 最多 ${e.value} 字。');
        }
      }
      data['market'] = (data['market'] as String).toUpperCase();
      if (!RegExp(r'^[A-Z]{2}$').hasMatch(data['market'] as String)) {
        throw const FormatException('市场须为两位国家代码。');
      }
      data['valid_from'] =
          awareDate(data['valid_from'] as String, '生效时间', required: true);
      data['valid_until'] = awareDate(data['valid_until'] as String, '结束时间');
      data.addAll({
        'topic': topic,
        'channel': channel,
        'language': language,
        'data_identity': identity,
        'source_confirmed': confirmed
      });
      await widget.app.api
          .post(path(), {'expected_policy_id': expected, 'data': data});
      if (!mounted) return;
      editing = false;
      saved = true;
      await read();
    }, message: '政策新版本已保存，已有草稿需重新核对政策。');
  }

  Future<void> clear(Json policy) async {
    if (!await confirmAction(
        context, '清除政策 #${policy['id']}', '此政策版本及引用它的客服草稿正文将被擦除，保留编号与状态记录。')) {
      return;
    }
    await perform(() async {
      await widget.app.api.post(path('/${policy['id']}/clear'), {});
      saved = true;
      if (mounted) await read();
    }, message: '政策版本与依赖正文已清除。');
  }

  @override
  Widget build(BuildContext context) => PopScope(
      canPop: !editing,
      onPopInvokedWithResult: (didPop, _) async {
        if (!didPop &&
            await confirmAction(context, '放弃未保存政策', '表单内容尚未保存，确认返回。') &&
            context.mounted) {
          Navigator.pop(context);
        }
      },
      child: Scaffold(
          appBar: AppBar(title: const Text('政策与 FAQ')),
          body: PageBody(children: [
            ...feedback,
            const Text('按出处、市场、渠道、语言和有效期维护版本。保存新版本后重新核验已有草稿。'),
            FormInput('检索政策 / FAQ', search, required: false, enabled: !busy),
            Wrap(spacing: 12, children: [
              OutlinedButton(
                  onPressed: busy
                      ? null
                      : () => perform(() async {
                            offset = 0;
                            await read();
                          }),
                  child: const Text('检索')),
              FilledButton(
                  onPressed: busy ? null : () => edit(),
                  child: const Text('录入政策')),
            ]),
            if (editing)
              Form(
                  key: formKey,
                  child: Column(children: [
                    SectionTitle(
                        expected == null ? '录入新政策' : '政策 #$expected 新版本'),
                    FormInput('政策编号', fields['code']!,
                        enabled: !busy && expected == null),
                    FormInput('政策标题', fields['title']!, enabled: !busy),
                    ChoiceField(
                        '主题',
                        topic,
                        const {
                          'faq': '一般 FAQ',
                          'shipping': '物流',
                          'refund': '退款退货',
                          'warranty': '保修'
                        },
                        busy
                            ? null
                            : (v) => setState(() {
                                  topic = v;
                                  confirmed = false;
                                })),
                    FormInput('市场（两位国家代码）', fields['market']!, enabled: !busy),
                    ChoiceField(
                        '渠道',
                        channel,
                        importChannels,
                        busy
                            ? null
                            : (v) => setState(() {
                                  channel = v;
                                  confirmed = false;
                                })),
                    ChoiceField(
                        '语言',
                        language,
                        const {'en': 'English', 'zh': '中文'},
                        busy
                            ? null
                            : (v) => setState(() {
                                  language = v;
                                  confirmed = false;
                                })),
                    ChoiceField(
                        '数据身份',
                        identity,
                        importIdentities,
                        busy
                            ? null
                            : (v) => setState(() {
                                  identity = v;
                                  confirmed = false;
                                })),
                    FormInput('政策全文', fields['text']!,
                        lines: 7, enabled: !busy),
                    FormInput('出处', fields['source']!, enabled: !busy),
                    FormInput('来源版本', fields['source_version']!,
                        enabled: !busy),
                    BusinessDateTimeField('生效时间', fields['valid_from']!,
                        enabled: !busy),
                    BusinessDateTimeField(
                        '结束时间（不含终点，留空长期）', fields['valid_until']!,
                        required: false, enabled: !busy),
                    CheckboxListTile(
                        value: confirmed,
                        onChanged:
                            busy ? null : (v) => setState(() => confirmed = v!),
                        title: const Text('已核对政策出处与适用范围')),
                    Wrap(spacing: 12, children: [
                      FilledButton(
                          onPressed: busy ? null : save,
                          child: const Text('保存政策版本')),
                      OutlinedButton(
                          onPressed: busy
                              ? null
                              : () => setState(() => editing = false),
                          child: const Text('放弃修改')),
                    ]),
                  ])),
            if (policies.isEmpty && !busy) const Text('暂无匹配政策。'),
            for (final policy in policies)
              ExpansionTile(
                  title: Text(
                      '${policy['data']?['title'] ?? '内容已清除'} · v${policy['number']}'),
                  children: [
                    PolicyEvidence(policy),
                    if (policy['data'] != null)
                      Wrap(spacing: 12, children: [
                        TextButton(
                            onPressed: busy ? null : () => edit(policy),
                            child: const Text('编辑新版本')),
                        TextButton(
                            onPressed: busy ? null : () => clear(policy),
                            child: const Text('清除此政策版本')),
                      ]),
                  ]),
            Wrap(spacing: 12, children: [
              if (offset > 0)
                TextButton(
                    onPressed: busy
                        ? null
                        : () => perform(() async {
                              offset -= 50;
                              await read();
                            }),
                    child: const Text('上一页')),
              if (policies.length == 50)
                TextButton(
                    onPressed: busy
                        ? null
                        : () => perform(() async {
                              offset += 50;
                              await read();
                            }),
                    child: const Text('下一页')),
            ]),
          ])));
}
