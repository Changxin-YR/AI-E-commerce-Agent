import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/business_navigation.dart';
import '../../ui/common.dart';
import '../../ui/business_widgets.dart';
import '../../ui/source_evidence.dart';
import '../imports/import_repository.dart';

class InventoryPage extends StatefulWidget {
  const InventoryPage(this.app, {super.key, this.query = const {}});
  final AppState app;
  final Map<String, String> query;
  @override
  State<InventoryPage> createState() => _InventoryPageState();
}

class _InventoryPageState extends BusinessPageState<InventoryPage> {
  late final search = TextEditingController(text: widget.query['sku'] ?? '');
  late final age =
      TextEditingController(text: widget.query['max_age_hours'] ?? '24');
  late String identity = widget.query['identity'] ?? 'user_import',
      channel = widget.query['channel'] ?? 'generic';
  Json? result;
  List<Json> tasks = [];
  int offset = 0, taskOffset = 0;
  bool moreTasks = false;
  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    search.dispose();
    age.dispose();
    super.dispose();
  }

  Future<void> load({int page = 0}) => perform(() async {
        final hours = int.tryParse(age.text);
        if (hours == null ||
            hours < 1 ||
            hours > 720 ||
            search.text.length > 120) {
          throw const FormatException('有效时长须为 1–720 小时，SKU 搜索最多 120 字。');
        }
        final value = object(
            await widget.app.api.get(widget.app.shopPath('/inventory'), query: {
          'data_identity': identity,
          'channel': channel,
          'max_age_hours': hours,
          'search': search.text.trim(),
          'offset': page,
        }));
        if (!mounted) return;
        result = value;
        offset = page;
        tasks = [];
        taskOffset = 0;
        await readTasks();
      });
  Future<void> readTasks({bool more = false}) async {
    final savedScope = result!['scope'];
    final page = object(await widget.app.api
        .get(widget.app.shopPath('/operations/tasks'), query: {
      'data_identity': savedScope['data_identity'],
      'channel': savedScope['channel'],
      'offset': more ? taskOffset + 50 : 0,
    }));
    if (!mounted) return;
    taskOffset = more ? taskOffset + 50 : 0;
    final items =
        rows(page['items']).where((t) => t['kind'] == 'low_inventory').toList();
    tasks = more ? [...tasks, ...items] : items;
    moreTasks = page['has_more'] == true;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('库存快照')),
      body: RefreshIndicator(
          onRefresh: () => load(page: offset),
          child: PageBody(children: [
            ...feedback,
            const Text('各渠道分别核对快照。没有快照的 SKU 库存未知，订单不会自动扣减本地快照。'),
            ChoiceField('数据身份', identity, importIdentities,
                busy ? null : (v) => setState(() => identity = v)),
            ChoiceField('来源渠道', channel, importChannels,
                busy ? null : (v) => setState(() => channel = v)),
            FormInput('快照有效小时数', age,
                enabled: !busy, type: TextInputType.number),
            FormInput('搜索 SKU', search, required: false, enabled: !busy),
            FilledButton(
                onPressed: busy ? null : () => load(),
                child: const Text('核对库存')),
            TextButton(
                onPressed: busy
                    ? null
                    : () => openBusinessPath(context, widget.app, '/imports', {
                          ...widget.query,
                          'kind': 'inventory',
                          'identity': identity,
                          'channel': channel,
                        }),
                child: const Text('导入库存 / 更新安全阈值')),
            if (result != null) ...[
              FactLine('核对时间 / 来源版本',
                  '${result!['checked_at']} / ${result!['source_revision']}'),
              FactLine('本次依据',
                  '${result!['scope']['data_identity']} · ${result!['scope']['channel']} · ${result!['scope']['max_age_hours']} 小时'),
              FactLine('说明', result!['note']),
              if (rows(result!['items']).isEmpty)
                const Notice('库存未知 / 未检查：此范围没有可用快照。'),
              for (final item in rows(result!['items'])) ...[
                SectionTitle('${item['sku']} · ${const {
                      'low': '低于安全阈值',
                      'above_threshold': '未低于安全阈值',
                      'unknown': '当前库存未知'
                    }[item['status']] ?? item['status']}'),
                FactLine('快照可售数量 / 安全阈值',
                    '${item['available']} / ${item['safety_threshold']}'),
                FactLine('判断依据', item['reason']),
                FactLine('快照时间 / 有效至',
                    '${item['snapshot_at']} / ${item['valid_until']}'),
                SourceEvidence(widget.app, object(item['source'])),
                for (final task in tasks.where(
                    (t) => t['snapshot']?['object_label'] == item['sku']))
                  TextButton(
                      onPressed: () => openBusinessPath(
                          context, widget.app, '/', {'task': '${task['id']}'}),
                      child: Text(
                          '关联待办 #${task['id']} · ${task['status']} · ${task['business_state']}')),
              ],
              Wrap(spacing: 12, children: [
                if (offset > 0)
                  TextButton(
                      onPressed: busy ? null : () => load(page: offset - 50),
                      child: const Text('上一页快照')),
                if (result!['has_more'] == true)
                  TextButton(
                      onPressed: busy ? null : () => load(page: offset + 50),
                      child: const Text('下一页快照')),
                if (moreTasks)
                  TextButton(
                      onPressed: busy
                          ? null
                          : () => perform(() => readTasks(more: true)),
                      child: const Text('继续查找关联待办')),
              ]),
              OutlinedButton(
                  onPressed: busy
                      ? null
                      : () => openBusinessPath(context, widget.app, '/', {
                            ...widget.query,
                            'identity': '${result!['scope']['data_identity']}',
                            'channel': '${result!['scope']['channel']}',
                            'max_age_hours':
                                '${result!['scope']['max_age_hours']}',
                          }),
                  child: const Text('进入运营巡检，生成或复查低库存待办')),
              if (widget.query['return_task'] != null)
                TextButton(
                    onPressed: () => openBusinessPath(context, widget.app, '/',
                        {'task': widget.query['return_task']!}),
                    child: const Text('返回来源待办')),
            ],
          ])));
}
