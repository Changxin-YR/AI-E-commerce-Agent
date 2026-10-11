import 'package:flutter/material.dart';
import '../../core/app_state.dart';
import '../../core/business_navigation.dart';
import '../../ui/business_widgets.dart';
import '../../ui/content_evidence.dart';
import '../../ui/common.dart';
import 'agent_labels.dart';

class AgentRunView extends StatelessWidget {
  const AgentRunView(this.app, this.run,
      {super.key,
      required this.busy,
      required this.controlling,
      required this.onAction,
      required this.onResume,
      required this.onRetry,
      this.returnContext = const {}});
  final AppState app;
  final Json run;
  final bool busy, controlling;
  final void Function(String) onAction;
  final VoidCallback onResume, onRetry;
  final Map<String, String> returnContext;
  Json output(String name) => mapValue(rows(run['steps'])
      .where((s) =>
          (s['node'] == name || s['skill'] == name) &&
          s['status'] == 'completed')
      .lastOrNull?['output']);
  @override
  Widget build(BuildContext context) {
    final input = mapValue(run['input']), scope = mapValue(input['scope']);
    final metrics = output('metrics'),
        margin = output('margin_evidence'),
        listing = output('compose_listing'),
        product = output('product_context'),
        support = output('compose_support'),
        message = output('message_context'),
        check = output('data_check');
    final records = [
      mapValue(run['result']),
      ...rows(run['steps'])
          .where((s) => s['node'] == 'verify' && s['status'] == 'completed')
          .map((s) => mapValue(s['output']))
    ];
    final links = <String, Json>{};
    for (final record in records) {
      if (record['record_id'] != null) {
        links['${record['record_type']}:${record['record_id']}'] = record;
      }
    }
    final approval = {
      'propose_tasks': '保存下列异常为工作台待审批候选。已有候选保留处理状态。',
      'analysis_todo': '保存当前分析快照，并创建一个销售与已知毛利核对待办。可在分析页完成或重开。',
      'listing_draft': '依据完整商品名称和参数保存本地 Listing 模板草稿；进入 Listing 页另行批准生效。',
      'listing_candidate': '将下方模型候选保存为待审 Listing；进入 Listing 页另行批准生效。',
      'support_candidate': '保存下方回复候选及人工接管原因；进入客服页编辑、审阅或存档。',
      'support_draft': '保存未核验订单、未选择政策的人工接管草稿；进入客服页继续核对。',
    };
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionTitle('执行 #${run['id']} · ${agentLabel(run['status'])}'),
      FactLine('流程 / 当前节点',
          '${agentLabel(run['template'])} / ${agentLabel(run['next_node'])}'),
      FactLine(
          '来源 / 修订号', '${run['source_status']} / ${run['source_revision']}'),
      FactLine('状态说明', agentReasons[run['reason']] ?? run['reason']),
      FactLine('保存范围',
          '${scope['data_identity']} · ${scope['channel']} · ${scope['currency']}'),
      FactLine('时间窗',
          '${scope['start_at']} 至 ${scope['end_at']}（结束不含，${scope['timezone']}）'),
      FactLine('目标', input['goal']),
      FactLine('商品 / 消息',
          '#${input['product_id'] ?? '无'} / #${input['message_id'] ?? '无'}'),
      FactLine('步数 / 秒数',
          '${run['steps_used']} / ${run['budget']['max_steps']} 步；${run['elapsed_ms']} ms / ${run['budget']['max_seconds']} 秒'),
      FactLine('USD 已用 / 预留 / 总预算',
          '${run['spent_usd']} / ${run['reserved_usd']} / ${run['budget']['max_cost_usd']}'),
      const Text('外部未提交。模型费用按部署费率估算，在途请求取消后仍可能计费。'),
      if (scope['rule_revision_id'] != null)
        TextButton(
            onPressed: () => openBusinessPath(context, app, '/rules', {
                  'shop': '${run['shop_id']}',
                  'channel': '${scope['channel']}',
                  'identity': '${scope['data_identity']}',
                  'version': '${scope['rule_revision_id']}'
                }),
            child: Text('查看适用经营规则 #${scope['rule_revision_id']}')),
      if (margin.isNotEmpty) ...[
        const SectionTitle('最近 7 天低毛利复核'),
        FactLine('成本口径', margin['cost_basis']),
        FactLine('纳入行数 / 候选数',
            '${margin['included_lines']} / ${margin['candidate_count']}'),
        FactLine('完整排行可用', margin['ranking_available']),
        FactLine('候选 SKU', words(margin['candidates'])),
        FactLine('数据缺口', words(margin['data_gaps'])),
        FactLine('费用缺口', words(margin['fee_gaps'])),
        const Text('商品毛利未扣完整费用，不能据此认定净利润。'),
        for (final r in rows(margin['recommendations'])) ...[
          FactLine('建议 · ${r['risk']}', r['title']),
          FactLine('依据', r['evidence']),
          FactLine('动作', r['action']),
        ],
        FactLine('独立内容检查', margin['listing_note']),
        if (margin['listing'] != null) ...[
          ProductEvidence(app, object(margin['listing']['product'])),
          FactLine('当前版本遗漏的参数', words(margin['listing']['missing_parameters'])),
          ListingComparison(object(margin['listing']['before']), {
            'title': margin['listing']['product']['name'],
            'description': margin['listing']['product']['facts']
          }),
        ],
      ],
      if (metrics.isNotEmpty) AnalysisEvidence(app, metrics),
      for (final name in ['explain_analysis', 'explain_operations']) ...[
        if (output(name)['explanation'] != null) ...[
          FactLine('模型组织说明', output(name)['explanation']['composition']),
          for (final obs in rows(output(name)['explanation']['observations']))
            FactLine('事实 ${obs['fact_id']}', obs['text']),
          for (final b in rows(output(name)['explanation']['branches']))
            FactLine('${b['name']} · ${b['status']}',
                '${b['count']} · ${b['reason']}'),
          for (final item
              in rows(output(name)['explanation']['candidate_counts']))
            FactLine('${item['label']}', item['count']),
          for (final item in rows(output(name)['explanation']['checks']))
            FactLine('待核对建议', item['text']),
        ],
      ],
      for (final b in rows(check['branches']))
        FactLine('${b['name']} · ${b['status']}',
            '${b['count']} 行 · ${b['reason']}'),
      for (final f in rows(check['findings']))
        ExpansionTile(
            title: Text('${f['title']} · ${f['object_label']}'),
            children: [
              FactLine('依据', f['basis']),
              FactLine('建议', f['advice']),
              FactLine('影响', f['impact']),
              for (final e in mapValue(f['facts']).entries)
                FactLine(e.key, e.value),
              EvidenceSources(app, f),
            ]),
      if (listing.isNotEmpty) ...[
        ProductEvidence(app, mapValue(listing['preparation']['product'])),
        ListingComparison(mapValue(listing['preparation']['before']),
            mapValue(listing['candidate'])),
      ] else if (product['product'] != null) ...[
        ProductEvidence(app, object(product['product'])),
        ListingComparison(mapValue(product['before']), {
          'title': product['product']['name'],
          'description': product['product']['facts']
        }),
      ],
      if (support['candidate'] != null)
        SupportEvidence(app, object(support['candidate'])),
      if (message['message'] != null) ...[
        FactLine('消息原文', message['message']['body']),
        EvidenceSources(app, message),
      ],
      if (run['status'] == 'waiting_approval') ...[
        const SectionTitle('审批当前内部写入 · R1 · 0 USD'),
        Text(approval[run['next_node']] ?? '请核对本节点的对象、依据和影响。'),
        if (run['template'] == 'margin_review')
          Text(run['next_node'] == 'analysis_todo'
              ? '本次批准只保存分析和核对待办。存在独立内容建议时，后续会再次请求批准。'
              : '本次批准保存独立内容草稿；之前已保存的分析保留。'),
        Wrap(spacing: 12, children: [
          FilledButton(
              onPressed:
                  !busy && !controlling && run['source_status'] == 'current'
                      ? () => onAction('approve')
                      : null,
              child: const Text('已核对，批准当前节点')),
          OutlinedButton(
              onPressed:
                  !busy && !controlling ? () => onAction('reject') : null,
              child: const Text('拒绝当前节点')),
        ]),
      ],
      Wrap(spacing: 12, children: [
        if (run['status'] == 'ready')
          FilledButton(
              onPressed: busy || controlling ? null : () => onAction('advance'),
              child: Text(run['reason'] == 'temporary_read_failure'
                  ? '重试安全读取步骤'
                  : '继续执行')),
        if (['ready', 'running'].contains(run['status']))
          OutlinedButton(
              onPressed: controlling ? null : () => onAction('pause'),
              child: const Text('暂停')),
        if (['paused', 'waiting_configuration'].contains(run['status']))
          OutlinedButton(
              onPressed: busy || controlling ? null : onResume,
              child: const Text('调整预算并恢复')),
        if ([
          'ready',
          'running',
          'paused',
          'waiting_configuration',
          'waiting_approval',
          'waiting_input'
        ].contains(run['status']))
          OutlinedButton(
              onPressed: controlling ? null : () => onAction('cancel'),
              child: const Text('取消任务')),
        OutlinedButton(
            onPressed:
                busy || controlling || run['input'] == null ? null : onRetry,
            child: const Text('按此范围重新填写')),
      ]),
      for (final record in links.values)
        Builder(builder: (context) {
          const entries = {
            'operations': ['/', 'run'],
            'listing': ['/listings', 'listing'],
            'support': ['/support', 'draft'],
            'analysis': ['/analytics', 'analysis']
          };
          final entry = entries[record['record_type']];
          if (entry == null) return const SizedBox.shrink();
          return TextButton(
              onPressed: () => openBusinessPath(context, app, entry[0], {
                    ...returnContext,
                    'shop': '${run['shop_id']}',
                    for (final k in [
                      'channel',
                      'currency',
                      'start_at',
                      'end_at',
                      'timezone'
                    ])
                      if (scope[k] != null) k: '${scope[k]}',
                    if (scope['data_identity'] != null)
                      'identity': '${scope['data_identity']}',
                    entry[1]: '${record['record_id']}',
                  }),
              child: Text(
                  '复查${agentLabel(record['record_type'])} #${record['record_id']}'));
        }),
      EvidenceSources(app, run['steps']),
      const SectionTitle('步骤与操作记录'),
      for (final step in rows(run['steps']))
        ListTile(
          title: Text(
              '${agentLabel(step['node'])} · ${agentLabel(step['status'])}'),
          subtitle: Text(
              '${step['skill']} v${step['skill_version']} · ${step['duration_ms']} ms\n'
              '${agentReasons[step['reason']] ?? step['reason']}\n${step['created_at']}'),
          isThreeLine: true,
        ),
    ]);
  }
}
