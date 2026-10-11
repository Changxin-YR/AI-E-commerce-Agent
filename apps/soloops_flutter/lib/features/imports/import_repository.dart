import 'dart:typed_data';
import '../../core/api_client.dart';
import '../../core/app_state.dart';

const importKinds = {
  'products': '商品',
  'orders': '订单行',
  'messages': '客服消息',
  'inventory': '库存快照',
  'statements': '渠道账单'
};
const importChannels = {
  'generic': '通用 / 自建表',
  'shopify': 'Shopify 风格候选',
  'amazon': 'Amazon 风格候选',
  'other': '其他来源'
};
const importIdentities = {'user_import': '用户导入文件', 'synthetic': '合成测试数据'};
const batchStatuses = {
  'draft': '待映射',
  'preview': '待确认',
  'committed': '已导入',
  'revoked': '已撤销',
  'cleared': '已清除',
  'expired': '已过期'
};
const rowActions = {
  'new': '新增',
  'update': '更新',
  'unchanged': '相同记录',
  'error': '需修正'
};

class ImportRepository {
  ImportRepository(this.api, this.shopId);
  final ApiClient api;
  final int shopId;
  Future<Json> catalog() async => object(await api.get('/imports/catalog'));
  Future<List<Json>> templates() async =>
      objects(await api.get('/imports/mappings'));
  Future<List<Json>> history() async =>
      objects(await api.get('/shops/$shopId/imports'));
  Future<Json> batch(int id) async => object(await api.get('/imports/$id'));
  Future<Json> upload(String name, Uint8List bytes, Json options) async =>
      object(await api.send('POST', '/shops/$shopId/imports',
          query: {...options, 'filename': name}, bytes: bytes));
  Future<Json> preview(Json batch, Json mapping, Json corrections) async =>
      object(await api.post('/imports/${batch['id']}/preview', {
        'version': batch['version'],
        'mapping': mapping,
        'corrections': corrections
      }));
  Future<Json> commit(Json batch, bool updates, Set<String> reviews) async =>
      object(await api.post('/imports/${batch['id']}/commit', {
        'version': batch['version'],
        'allow_updates': updates,
        'reviewed_fields': reviews.toList()
      }));
  Future<Json> withdraw(Json batch, String action) async => object(await api
      .post('/imports/${batch['id']}/$action', {'version': batch['version']}));
  Future<void> saveMapping(Json batch, String name, Json mapping) async {
    await api.post('/imports/mappings', {
      'name': name,
      'kind': batch['kind'],
      'source_channel': batch['source_channel'],
      'mapping': Map.fromEntries(mapping.entries.where((e) => e.value != ''))
    });
  }

  Future<List<Json>> groups({int? before}) async => objects(
      await api.get('/shops/$shopId/import-groups', query: {'before': before}));
  Future<Json> group(int id) async =>
      object(await api.get('/import-groups/$id'));
  Future<Json> createGroup(Json options, Json manifest) async =>
      object(await api.post('/shops/$shopId/import-groups', {
        'options': {...options, 'filename': manifest['source_filename']},
        'manifest': manifest
      }));
  Future<Json> revokeGroup(Json group) async => object(await api.post(
      '/import-groups/${group['id']}/revoke', {'version': group['version']}));
}
