import 'dart:convert';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'api_client.dart';
import 'device_bridge.dart';

typedef Json = Map<String, dynamic>;
Json object(dynamic value) => Map<String, dynamic>.from(value as Map);
List<Json> objects(dynamic value) => (value as List).map(object).toList();
String newRequestId() {
  final random = Random.secure();
  final bytes = List.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  final h = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${h.substring(0, 8)}-${h.substring(8, 12)}-${h.substring(12, 16)}-${h.substring(16, 20)}-${h.substring(20)}';
}

class AppState extends ChangeNotifier {
  final api = ApiClient();
  final device = DeviceBridge();
  Json? session;
  List<Json> shops = [];
  int? shopId;
  bool loading = true;
  String? notice;
  Json? get shop => shops.where((s) => s['id'] == shopId).firstOrNull;
  String shopPath(String path) {
    if (shopId == null) throw const ApiFailure('请先创建或选择一家店铺。');
    return '/shops/$shopId$path';
  }

  AppState() {
    api.onExpired = _expire;
  }
  Future<void> initialize() async {
    try {
      final settings = await device.settings();
      api.configure('${settings['baseUrl'] ?? api.baseUrl}');
      shopId = settings['shopId'] as int?;
      final stored = await device.readSession();
      if (stored != null) {
        final saved = object(jsonDecode(stored));
        if (saved['baseUrl'] == api.baseUrl) {
          api.token = saved['token'] as String?;
          session = object(await api.get('/mobile/auth/session'));
          await loadShops();
        }
      }
    } catch (error) {
      notice = '$error';
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> login(String url, String username, String password) async {
    api.token = null;
    session = null;
    api.configure(url);
    final result = object(await api.post('/mobile/auth/login', {
      'username': username.trim(),
      'password': password,
      'client_type': 'ohos'
    }));
    api.token = result['access_token'] as String;
    try {
      await device.writeSession(
          jsonEncode({'baseUrl': api.baseUrl, 'token': api.token}));
    } catch (_) {
      try {
        await api.post('/mobile/auth/logout');
      } catch (_) {}
      api.token = null;
      throw const ApiFailure('设备凭据未能安全保存，请重试登录。');
    }
    session = {...result}..remove('access_token');
    notice = null;
    await loadShops();
    notifyListeners();
  }

  Future<void> loadShops() async {
    final epoch = api.generation;
    final data = objects(await api.get('/shops'));
    if (epoch != api.generation) return;
    shops = data;
    if (!shops.any((s) => s['id'] == shopId))
      shopId = shops.firstOrNull?['id'] as int?;
    await device.saveSettings(api.baseUrl, shopId);
    notifyListeners();
  }

  Future<void> selectShop(int id) async {
    if (shopId == id) return;
    api.invalidate();
    shopId = id;
    notifyListeners();
    await device.saveSettings(api.baseUrl, shopId);
  }

  Future<void> logout({bool all = false}) async {
    await api.post(all ? '/mobile/auth/logout-all' : '/mobile/auth/logout');
    await device.clearSession();
    api.invalidate();
    api.token = null;
    session = null;
    shops = [];
    shopId = null;
    notifyListeners();
  }

  void _expire() {
    api.token = null;
    session = null;
    shops = [];
    shopId = null;
    notice = '登录已过期，请重新登录。';
    device.clearSession().catchError((Object _) {});
    notifyListeners();
  }

  @override
  void dispose() {
    api.dispose();
    super.dispose();
  }
}
