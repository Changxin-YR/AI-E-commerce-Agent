import 'package:flutter/material.dart';
import '../core/app_state.dart';
import '../ui/common.dart';

class WorkbenchPage extends StatefulWidget {
  const WorkbenchPage(this.app, {super.key, this.tasksOnly = false});
  final AppState app;
  final bool tasksOnly;
  @override
  State<WorkbenchPage> createState() => _WorkbenchPageState();
}

class _WorkbenchPageState extends State<WorkbenchPage> {
  Json? data;
  final items = <Json>[];
  String? view;
  String? error;
  bool busy = false;
  @override
  void initState() {
    super.initState();
    view = widget.tasksOnly ? 'attention' : null;
    load();
  }

  Future<void> load({bool more = false}) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final next = object(await widget.app.api.get('/workbench', query: {
        'shop_id': widget.app.shopId,
        'view': view,
        if (more) 'cursor': data?['next_cursor']
      }));
      if (!mounted) return;
      setState(() {
        data = next;
        if (!more) items.clear();
        items.addAll(objects(next['items']));
      });
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => RefreshIndicator(
      onRefresh: load,
      child: PageBody(children: [
        Text(widget.tasksOnly ? '待办事项' : '今天，从一件事开始',
            style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 12),
        if (data != null) Text('最近同步 ${data!['read_at']}'),
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
                    : (selected) {
                        setState(() => view = selected ? entry.key : null);
                        load();
                      })
        ]),
        if (error != null) Notice(error!, onRetry: () => load()),
        if (busy) const LinearProgressIndicator(),
        if (items.isEmpty && !busy && error == null)
          const Padding(
              padding: EdgeInsets.symmetric(vertical: 40),
              child: Text('当前没有符合条件的事项。导入报表并运行运营检查后，这里会显示待办和审批记录。')),
        for (final item in items)
          Card(
              child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${item['label']}',
                            style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: 8),
                        Text('${item['detail']}'),
                        const SizedBox(height: 8),
                        Text(
                            '${item['shop_name']} · ${item['source_status'] == 'current' ? '来源有效' : '来源需核对'}',
                            style: Theme.of(context).textTheme.bodySmall)
                      ]))),
        if (data?['next_cursor'] != null)
          TextButton(
              onPressed: busy ? null : () => load(more: true),
              child: const Text('加载更多'))
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
