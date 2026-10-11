import 'package:flutter/material.dart';
import 'app_state.dart';

typedef BusinessRoute = Widget Function(
    AppState app, Map<String, String> query);
final businessRoutes = <String, BusinessRoute>{};

Future<void> openBusinessPath(BuildContext context, AppState app, String path,
    [Map<String, String> query = const {}]) async {
  final uri = Uri.tryParse(path);
  final local = uri != null &&
      !uri.hasScheme &&
      !uri.hasAuthority &&
      uri.path.startsWith('/');
  final builder = local ? businessRoutes[uri.path] : null;
  if (builder == null) {
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('无法识别此业务链接，请从业务工具打开。')));
    return;
  }
  final parameters = {...uri!.queryParameters, ...query};
  final shop = int.tryParse(parameters['shop'] ?? '');
  if (shop != null && shop != app.shopId) {
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('请先切换到此记录所属店铺，再打开记录。')));
    return;
  }
  if (!await app.canNavigate() || !context.mounted) return;
  await Navigator.push<void>(
      context, MaterialPageRoute(builder: (_) => builder(app, parameters)));
}
