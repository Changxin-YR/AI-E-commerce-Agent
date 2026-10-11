import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';

class ApiFailure implements Exception {
  const ApiFailure(this.message,
      {this.status = 0, this.code = '', this.requestId = ''});
  final String message;
  final int status;
  final String code;
  final String requestId;
  @override
  String toString() => message;
}

class ApiClient {
  String baseUrl = const String.fromEnvironment('SOLOOPS_API_BASE',
      defaultValue: 'https://127.0.0.1:18443');
  String? token;
  int generation = 0;
  VoidCallback? onExpired;
  HttpClient? _client;
  final _active = <HttpClientRequest>{};

  void configure(String url) {
    final uri = Uri.tryParse(url.trim());
    final localDebug = kDebugMode &&
        uri != null &&
        ['127.0.0.1', 'localhost', '10.0.2.2'].contains(uri.host) &&
        uri.scheme == 'http';
    if (uri == null ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        (uri.path != '' && uri.path != '/') ||
        (uri.scheme != 'https' && !localDebug)) {
      throw const ApiFailure('请输入完整的 HTTPS 服务地址，例如 https://example.com');
    }
    baseUrl = uri.replace(path: '').toString().replaceFirst(RegExp(r'/$'), '');
    invalidate();
    _client?.close(force: true);
    final context = SecurityContext(withTrustedRoots: true);
    const ca = String.fromEnvironment('M0B_CA_BASE64');
    if (kDebugMode && uri.host == '127.0.0.1' && ca.isNotEmpty) {
      context.setTrustedCertificatesBytes(base64Decode(ca));
    }
    _client = HttpClient(context: context)
      ..connectionTimeout = const Duration(seconds: 10);
  }

  void invalidate() {
    generation++;
    for (final request in _active.toList()) {
      request.abort();
    }
    _active.clear();
  }

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) =>
      send('GET', path, query: query);
  Future<dynamic> post(String path, [Object? body]) =>
      send('POST', path, body: body);
  Future<dynamic> put(String path, Object body) =>
      send('PUT', path, body: body);
  Future<dynamic> send(String method, String path,
      {Object? body,
      Map<String, dynamic>? query,
      Uint8List? bytes,
      bool rawResponse = false}) async {
    if (!path.startsWith('/') || path.startsWith('//')) {
      throw const ApiFailure('请求地址无效');
    }
    final epoch = generation;
    final uri = Uri.parse('$baseUrl/api$path').replace(
        queryParameters: query == null
            ? null
            : {
                for (final e in query.entries)
                  if (e.value != null && e.value.toString().isNotEmpty)
                    e.key: e.value.toString()
              });
    _client ??= HttpClient()..connectionTimeout = const Duration(seconds: 10);
    HttpClientRequest? pending;
    final timer = Timer(
        const Duration(seconds: 45),
        () => pending
            ?.abort(const ApiFailure('请求超时；写入结果请刷新记录核对。', code: 'timeout')));
    try {
      final request = await _client!
          .openUrl(method, uri)
          .timeout(const Duration(seconds: 12));
      pending = request;
      if (epoch != generation) {
        request.abort();
        throw const ApiFailure('当前店铺或账号已变化，请刷新。', code: 'context_changed');
      }
      _active.add(request);
      request.followRedirects = false;
      request.headers.set('X-SoloOps-Client', 'mobile');
      if (token != null) {
        request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
      }
      if (bytes != null) {
        request.headers.contentType = ContentType.binary;
        request.contentLength = bytes.length;
        for (var offset = 0; offset < bytes.length; offset += 65536) {
          request.add(Uint8List.sublistView(
              bytes, offset, (offset + 65536).clamp(0, bytes.length).toInt()));
          await request.flush();
        }
      } else if (body != null) {
        request.headers.contentType = ContentType.json;
        request.write(jsonEncode(body));
      }
      final response = await request.close();
      final buffer = BytesBuilder(copy: false);
      await for (final chunk in response) {
        if (buffer.length + chunk.length > 8 * 1024 * 1024) {
          throw const ApiFailure('结果超过本次可读取范围，请缩小筛选条件。');
        }
        buffer.add(chunk);
      }
      if (epoch != generation) {
        throw const ApiFailure('当前店铺或账号已变化，请刷新。', code: 'context_changed');
      }
      final data = buffer.takeBytes();
      dynamic value;
      if (data.isNotEmpty && (!rawResponse || response.statusCode >= 400)) {
        try {
          value = jsonDecode(utf8.decode(data));
        } on FormatException {
          value = null;
        }
      }
      if (response.statusCode >= 300) {
        if (response.statusCode == 401) onExpired?.call();
        final error = value is Map ? value['error'] : null;
        throw ApiFailure(
            error is Map
                ? '${error['message'] ?? '请求未完成'}'
                : '请求未完成（${response.statusCode}）',
            status: response.statusCode,
            code: error is Map ? '${error['code'] ?? ''}' : '',
            requestId: error is Map ? '${error['request_id'] ?? ''}' : '');
      }
      if (response.statusCode == 204) return null;
      if (rawResponse) return data;
      if (value == null && data.isNotEmpty && utf8.decode(data) != 'null') {
        throw const ApiFailure('服务响应无法读取，请稍后重试。');
      }
      return value;
    } on ApiFailure {
      rethrow;
    } on HandshakeException {
      throw const ApiFailure('服务证书校验失败，请检查服务地址和证书。');
    } on TimeoutException {
      throw const ApiFailure('连接超时，请检查服务是否已启动。');
    } on IOException {
      throw ApiFailure(
          method == 'GET' ? '暂时无法连接服务，请刷新重试。' : '连接中断，结果尚未确认；请先刷新记录再操作。');
    } finally {
      timer.cancel();
      if (pending != null) _active.remove(pending);
    }
  }

  void dispose() {
    invalidate();
    _client?.close(force: true);
  }
}
