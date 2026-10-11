import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../ui/business_widgets.dart';
import '../../ui/common.dart';
import '../../ui/content_evidence.dart';

class AuthorizationsPanel extends StatefulWidget {
  const AuthorizationsPanel(this.app,
      {super.key,
      this.run,
      this.focusId,
      required this.disabled,
      required this.onUse,
      required this.onStart,
      required this.onInspect});
  final AppState app;
  final Json? run;
  final int? focusId;
  final bool disabled;
  final void Function(int) onUse, onInspect;
  final void Function(Json) onStart;
  @override
  State<AuthorizationsPanel> createState() => _AuthorizationsPanelState();
}

class _AuthorizationsPanelState extends BusinessPageState<AuthorizationsPanel> {
  List<Json> grants = [];
  int? next;
  final count = TextEditingController(text: '1'),
      hours = TextEditingController(text: '24');
  bool confirmed = false;
  String? requestId;
  String path([String suffix = '']) =>
      widget.app.shopPath('/authorizations$suffix');
  bool get canCreate =>
      widget.run?['template'] == 'daily' &&
      widget.run?['status'] == 'waiting_approval' &&
      widget.run?['next_node'] == 'propose_tasks' &&
      widget.run?['source_status'] == 'current';
  @override
  void initState() {
    super.initState();
    count.addListener(reset);
    hours.addListener(reset);
    load();
  }

  void reset() {
    if (mounted)
      setState(() {
        confirmed = false;
        requestId = null;
      });
  }

  @override
  void didUpdateWidget(covariant AuthorizationsPanel old) {
    super.didUpdateWidget(old);
    if (old.run?['version'] != widget.run?['version'] ||
        old.run?['id'] != widget.run?['id']) reset();
  }

  @override
  void dispose() {
    count.dispose();
    hours.dispose();
    super.dispose();
  }

  Future<void> read({bool more = false}) async {
    final page = object(await widget.app.api
        .get(path(), query: more && next != null ? {'before_id': next} : {}));
    Json? focused;
    if (!more && widget.focusId != null) {
      focused = object(await widget.app.api.get(path('/${widget.focusId}')));
    }
    if (!mounted) return;
    grants = more ? [...grants, ...rows(page['items'])] : rows(page['items']);
    if (focused != null)
      grants = [focused, ...grants.where((g) => g['id'] != focused!['id'])];
    next = page['next_before_id'] as int?;
  }

  Future<void> load({bool more = false}) => perform(() => read(more: more));
  Future<void> create() => perform(() async {
        final n = int.tryParse(count.text), h = int.tryParse(hours.text);
        if (!canCreate ||
            !confirmed ||
            n == null ||
            n < 1 ||
            n > 20 ||
            h == null ||
            h < 1 ||
            h > 168) {
          throw const FormatException('请核对授权并填写 1–20 次、1–168 小时。');
        }
        requestId ??= newRequestId();
        await widget.app.api.post(path(), {
          'request_id': requestId,
          'execution_id': widget.run!['id'],
          'expected_version': widget.run!['version'],
          'max_uses': n,
          'valid_hours': h,
          'confirmed': true
        });
        if (!mounted) return;
        confirmed = false;
        requestId = null;
        await read();
      }, message: '有限范围授权已保存。');
  Future<void> change(Json grant, {Json? use}) async {
    if (!await confirmAction(
        context,
        use == null ? '撤销授权' : '撤回新增候选',
        use == null
            ? '已保存结果保留，后续执行不能再使用此授权。'
            : '本次新增且未被后续处理的候选将设为已拒绝；历史保留，额度不返还。任一项已变化时整批不撤回。')) return;
    await perform(() async {
      await widget.app.api.post(
          path(use == null
              ? '/${grant['id']}/revoke'
              : '/${grant['id']}/uses/${use['id']}/revert'),
          use == null ? {'version': grant['version']} : null);
      await read();
    }, message: use == null ? '授权已撤销。' : '新增候选已撤回，额度不返还。');
  }

  @override
  Widget build(BuildContext context) => ExpansionTile(
          title: const Text('R1 内部有限次预授权'),
          initiallyExpanded: widget.focusId != null,
          children: [
            ...feedback,
            const Text(
                '只授权已核对范围内的异常候选保存，每次成功保存消耗 1 次，复用候选也计次；费用 0 USD。来源或规则变化后须重新核对。'),
            if (canCreate) ...[
              FactLine('当前依据',
                  '执行 #${widget.run!['id']} · 版本 ${widget.run!['version']}'),
              FactLine(
                  '授权范围',
                  '${widget.run!['input']['scope']['start_at']} 至 ${widget.run!['input']['scope']['end_at']} · '
                      '${widget.run!['input']['scope']['data_identity']} · ${widget.run!['input']['scope']['channel']}'),
              FormInput('最多使用次数', count,
                  enabled: !busy && !widget.disabled,
                  type: TextInputType.number),
              FormInput('有效小时数', hours,
                  enabled: !busy && !widget.disabled,
                  type: TextInputType.number),
              CheckboxListTile(
                  value: confirmed,
                  onChanged: busy || widget.disabled
                      ? null
                      : (v) => setState(() => confirmed = v!),
                  title: const Text('已核对上方全部候选、范围和撤回边界，同意有限次授权')),
              FilledButton(
                  onPressed:
                      busy || widget.disabled || !confirmed ? null : create,
                  child: const Text('保存预授权')),
            ],
            TextButton(
                onPressed: busy || widget.disabled ? null : load,
                child: const Text('刷新授权')),
            if (grants.isEmpty && !busy) const Text('暂无授权，可在今日运营流程的待审批候选下创建。'),
            for (final grant in grants)
              ExpansionTile(
                  key: ValueKey('${grant['id']}:${grant['version']}'),
                  initiallyExpanded: grant['id'] == widget.focusId,
                  title: Text('授权 #${grant['id']} · ${grant['status']}'),
                  subtitle: Text(
                      '已用 ${grant['used_count']} / ${grant['max_uses']} 次'),
                  children: [
                    FactLine('身份 / 渠道 / 币种',
                        '${grant['scope']['data_identity']} / ${grant['scope']['channel']} / ${grant['scope']['currency']}'),
                    FactLine('时间窗',
                        '${grant['scope']['start_at']} 至 ${grant['scope']['end_at']} · ${grant['scope']['timezone']}'),
                    FactLine('规则 / 来源版本',
                        '${grant['scope']['rule_revision_id']} / ${grant['source_revision']}'),
                    FactLine('阈值',
                        '库存 ${grant['scope']['max_age_hours']} 小时，最低销量 ${grant['scope']['min_quantity']}，毛利率 ≤ ${grant['scope']['max_margin_percent']}%'),
                    FactLine('绑定候选数', grant['candidate_count']),
                    FactLine('授权到期', grant['expires_at']),
                    FactLine('来源到期', grant['source_valid_until']),
                    Wrap(spacing: 12, children: [
                      TextButton(
                          onPressed: busy || widget.disabled
                              ? null
                              : () => widget.onInspect(
                                  grant['origin_execution_id'] as int),
                          child: const Text('查看原预览')),
                      if (grant['status'] == 'active') ...[
                        if (canCreate)
                          FilledButton(
                              onPressed: busy || widget.disabled
                                  ? null
                                  : () => widget.onUse(grant['id'] as int),
                              child: const Text('为当前候选使用授权')),
                        OutlinedButton(
                            onPressed: busy || widget.disabled
                                ? null
                                : () => widget.onStart(grant),
                            child: const Text('按授权范围运行')),
                      ],
                      if (grant['revoked_at'] == null)
                        TextButton(
                            onPressed: busy || widget.disabled
                                ? null
                                : () => change(grant),
                            child: const Text('撤销授权')),
                    ]),
                    for (final use in rows(grant['uses'])) ...[
                      FactLine('消耗',
                          '执行 #${use['execution_id']} → 巡检 #${use['operation_run_id']} · ${use['created_at']}'),
                      FactLine('新增 / 复用',
                          '${rows(use['changes']).length} / ${use['reused_count']}'),
                      for (final item in rows(use['changes']))
                        FactLine('候选 #${item['task_id']}',
                            '${item['before']} → ${item['after']} · 保存版本 ${item['version']}'),
                      if (use['reverted_at'] != null)
                        FactLine('撤回时间', use['reverted_at'])
                      else if (rows(use['changes']).isNotEmpty)
                        TextButton(
                            onPressed: busy || widget.disabled
                                ? null
                                : () => change(grant, use: use),
                            child: const Text('撤回本次新增候选')),
                    ],
                  ]),
            if (next != null)
              TextButton(
                  onPressed:
                      busy || widget.disabled ? null : () => load(more: true),
                  child: const Text('加载更早授权')),
          ]);
}
