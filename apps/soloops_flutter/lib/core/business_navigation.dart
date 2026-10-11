import 'package:flutter/material.dart';
import 'app_state.dart';

typedef BusinessRoute = Widget Function(
    AppState app, Map<String, String> query);
final businessRoutes = <String, BusinessRoute>{};

Future<void> openBusinessPath(BuildContext context, AppState app, String path,
    [Map<String, String> query = const {}]) async {
  final builder = businessRoutes[path];
  if (builder == null) {
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('此业务页面正在接入中。')));
    return;
  }
  final shop = int.tryParse(query['shop'] ?? '');
  if (shop != null && shop != app.shopId) {
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('请先切换到此记录所属店铺，再打开记录。')));
    return;
  }
  await Navigator.push<void>(
      context, MaterialPageRoute(builder: (_) => builder(app, query)));
}
