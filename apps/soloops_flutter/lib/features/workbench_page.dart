import 'package:flutter/material.dart';
import '../core/app_state.dart';
import '../core/business_navigation.dart';
import '../ui/common.dart';
import '../ui/business_widgets.dart';
import 'imports/import_repository.dart';
import 'operations/operation_task_page.dart';

const workKinds = {
  'operation_task': '运营待办',
  'agent': 'Agent 执行',
  'listing': 'Listing 草稿',
  'reply': '客服草稿',
  'analysis_todo': '分析核对待办',
  'operation_run': '运营检查',
  'analysis': '分析报告',
  'overview': '经营摘要',
  'authorization': 'R1 预授权',
  'outbound': 'R2 测试邮件'
};
const workBuckets = {
  'pending': '待处理',
  'approval': '待审阅',
  'failed': '失败 / 阻断',
  'unknown': '结果未知',
  'stale': '需更新来源',
  'history': '存档 / 已记录'
};

class WorkbenchPage extends StatefulWidget {
  const WorkbenchPage(this.app, {super.key, this.tasksOnly = false});
  final AppState app;
  final bool tasksOnly;
  @override
  State<WorkbenchPage> createState() => _WorkbenchPageState();
}

class _WorkbenchPageState extends BusinessPageState<WorkbenchPage> {
  Json? data, onboarding;
  final items = <Json>[];
  String? view;
  String identity = '', channel = '', kind = '', bucket = '';
  @override
  void initState() {
    super.initState();
    view = widget.tasksOnly ? 'attention' : null;
    load();
  }

  @override
  void didUpdateWidget(covariant WorkbenchPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.tasksOnly != widget.tasksOnly) {
      view = widget.tasksOnly ? 'attention' : null;
      identity = channel = kind = bucket = '';
      data = null;
      items.clear();
      load();
    }
  }

  Future<void> load({bool more = false}) => perform(() async {
        final next = object(await widget.app.api.get('/workbench', query: {
          'shop_id': widget.app.shopId,
          'view': view,
          'data_identity': identity,
          'channel': channel,
          'kind': kind,
          'bucket': bucket,
          if (more) 'cursor': data?['next_cursor']
        }));
        if (!mounted) return;
        data = next;
        if (!more) items.clear();
        final keys = items.map((i) => '${i['kind']}:${i['id']}').toSet();
        items.addAll(rows(next['items'])
            .where((i) => keys.add('${i['kind']}:${i['id']}')));
        if (!widget.tasksOnly) {
          final setup = object(await widget.app.api.get('/onboarding'));
          if (mounted) onboarding = setup;
        }
      });
  void filter(VoidCallback change) {
    setState(() {
      change();
      data = null;
      items.clear();
    });
    load();
  }

  Future<void> open(String path, [Map<String, String> query = const {}]) async {
    await openBusinessPath(context, widget.app, path, query);
    if (mounted) await load();
  }

  Widget itemCard(Json item) => Card(
      child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: busy
              ? null
              : () => open(item['path'] as String,
                  object(item['query']).map((k, v) => MapEntry(k, '$v'))),
          child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${item['label']}',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    Text('${item['detail']}'),
                    FactLine('类型 / 处理分组',
                        '${workKinds[item['kind']]} / ${workBuckets[item['bucket']]}'),
                    FactLine(
                        '来源状态',
                        sourceLabels[item['source_status']] ??
                            item['source_status']),
                    if (item['business_state'] != null)
                      FactLine(
                          '业务进展',
                          businessLabels[item['business_state']] ??
                              item['business_state']),
                    FactLine('所属店铺', item['shop_name']),
                    FactLine('记录时间', item['created_at']),
                    if (item['due_at'] != null)
                      FactLine('截止时间', item['due_at']),
                    if (item['source_status'] != 'current')
                      const Text('先核对来源时效，再继续业务操作。'),
                    const Align(
                        alignment: Alignment.centerRight,
                        child: Icon(Icons.chevron_right)),
                  ]))));

  @override
  Widget build(BuildContext context) => RefreshIndicator(
      onRefresh: load,
      child: PageBody(children: [
        Text(widget.tasksOnly ? '待办事项' : '今天，从一件事开始',
            style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 12),
        if (data != null) FactLine('读取截至', data!['read_at']),
        if (!widget.tasksOnly) ...[
          Wrap(spacing: 8, runSpacing: 8, children: [
            OutlinedButton.icon(
                onPressed: busy ? null : () => open('/imports'),
                icon: const Icon(Icons.upload_file),
                label: const Text('导入业务文件')),
            FilledButton.icon(
                onPressed: busy ? null : () => open('/'),
                icon: const Icon(Icons.fact_check_outlined),
                label: const Text('今日运营检查')),
          ]),
          if (onboarding != null &&
              (onboarding!['profile_complete'] != true ||
                  onboarding!['shop_count'] == 0))
            Card(
                child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('准备经营资料',
                              style: Theme.of(context).textTheme.titleMedium),
                          FactLine(
                              '经营档案',
                              onboarding!['profile_complete'] == true
                                  ? '已完成'
                                  : '待完善'),
                          FactLine('店铺数量', onboarding!['shop_count']),
                          const Text('填写经营档案、添加店铺记录，再导入一类报表即可开始。'),
                          TextButton(
                              onPressed: () => open('/settings'),
                              child: const Text('完善经营资料'))
                        ]))),
        ],
        const SizedBox(height: 20),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final entry in const {
            'attention': '待我处理',
            'ai_completed': 'AI 已完成',
            'update_data': '需要更新数据'
          }.entries)
            ChoiceChip(
                selected: view == entry.key,
                label: Text(
                    '${entry.value}  ${data?['view_counts']?[entry.key] ?? '—'}'),
                onSelected: busy
                    ? null
                    : (selected) =>
                        filter(() => view = selected ? entry.key : null))
        ]),
        ExpansionTile(title: const Text('筛选事项'), children: [
          ChoiceField('数据身份', identity, {'': '全部身份', ...importIdentities},
              busy ? null : (v) => filter(() => identity = v)),
          ChoiceField('来源渠道', channel, {'': '全部渠道', ...importChannels},
              busy ? null : (v) => filter(() => channel = v)),
          ChoiceField('业务类型', kind, {'': '全部类型', ...workKinds},
              busy ? null : (v) => filter(() => kind = v)),
          ChoiceField('处理分组', bucket, {'': '全部分组', ...workBuckets},
              busy ? null : (v) => filter(() => bucket = v)),
        ]),
        ...feedback,
        if (error != null)
          TextButton(onPressed: busy ? null : load, child: const Text('刷新事项')),
        if (data?['counts'] != null)
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final e in object(data!['counts']).entries)
              Text('${workBuckets[e.key] ?? e.key} ${e.value}')
          ]),
        if (items.isEmpty && !busy && error == null)
          const Padding(
              padding: EdgeInsets.symmetric(vertical: 40),
              child: Text('当前没有符合条件的事项。导入报表并运行运营检查后，这里会显示待办和审批记录。')),
        for (final item in items) itemCard(item),
        if (data?['next_cursor'] != null)
          TextButton(
              onPressed: busy ? null : () => load(more: true),
              child: const Text('加载更多')),
        if (!widget.tasksOnly && rows(data?['recent_runs']).isNotEmpty) ...[
          const SectionTitle('最近执行'),
          for (final item in rows(data?['recent_runs'])) itemCard(item),
        ],
      ]));
}

class RecordListPage extends StatefulWidget {
  const RecordListPage(this.app,
      {super.key,
      required this.path,
      required this.title,
      required this.empty,
      required this.titleKeys,
      required this.detailKeys});
  final AppState app;
  final String path, title, empty;
  final List<String> titleKeys, detailKeys;
  @override
  State<RecordListPage> createState() => _RecordListPageState();
}

class _RecordListPageState extends State<RecordListPage> {
  List<Json> records = [];
  String? error;
  bool busy = false;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result =
          objects(await widget.app.api.get(widget.app.shopPath(widget.path)));
      if (mounted) setState(() => records = result);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  String text(Json item, List<String> keys) => keys
      .map((k) => item[k])
      .where((v) => v != null && v.toString().isNotEmpty)
      .join(' · ');
  @override
  Widget build(BuildContext context) => RefreshIndicator(
      onRefresh: load,
      child: PageBody(children: [
        Text(widget.title, style: Theme.of(context).textTheme.headlineSmall),
        if (busy) const LinearProgressIndicator(),
        if (error != null) Notice(error!, onRetry: load),
        if (!busy && error == null && records.isEmpty)
          Padding(
              padding: const EdgeInsets.symmetric(vertical: 32),
              child: Text(widget.empty)),
        for (final item in records)
          Card(
              child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(text(item, widget.titleKeys),
                            style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: 8),
                        Text(text(item, widget.detailKeys))
                      ])))
      ]));
}
