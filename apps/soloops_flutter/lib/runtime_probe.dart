import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

void recordProbe(String event, Object value) {
  debugPrint('SOLOOPS_M0B ${jsonEncode({'event': event, 'value': value})}');
}

/// Synthetic, debug-only diagnostics. Never handles a user session or credential.
Future<Map<String, String>> runRuntimeProbe() async {
  final results = <String, String>{};
  if (!kDebugMode) return {'diagnostics': 'NOT_TESTED: debug builds only'};
  Future<void> check(String name, Future<void> Function() action) async {
    try {
      await action().timeout(const Duration(seconds: 12));
      results[name] = 'PASS';
    } catch (error) {
      results[name] = 'FAIL: ${error.runtimeType}';
    }
    recordProbe(name, results[name]!);
  }

  await check('sandbox_file', () async {
    final directory = await Directory.systemTemp.createTemp('soloops-m0b-');
    try {
      final file = File('${directory.path}/synthetic.txt');
      await file.writeAsString('SoloOps 合成资料 M0-B', flush: true);
      if (await file.readAsString() != 'SoloOps 合成资料 M0-B') {
        throw StateError('file round trip');
      }
    } finally {
      await directory.delete(recursive: true);
    }
  });
  await check('clipboard', () async {
    // Only read back our own synthetic value; do not capture prior clipboard data.
    await Clipboard.setData(const ClipboardData(text: 'SoloOps-M0B-synthetic'));
    final value = await Clipboard.getData(Clipboard.kTextPlain);
    if (value?.text != 'SoloOps-M0B-synthetic') throw StateError('clipboard');
  });

  const base = String.fromEnvironment('M0B_API_BASE');
  const ca = String.fromEnvironment('M0B_CA_BASE64');
  final uri = Uri.tryParse(base);
  if (uri == null ||
      uri.scheme != 'https' ||
      uri.host != '127.0.0.1' ||
      ca.isEmpty) {
    results['https'] = 'NOT_TESTED: local fixture not configured';
    return results;
  }
  final context = SecurityContext(withTrustedRoots: true)
    ..setTrustedCertificatesBytes(base64Decode(ca));
  final client = HttpClient(context: context)
    ..connectionTimeout = const Duration(seconds: 5);
  Future<int> get(String path, {bool syntheticHeaders = false}) async {
    final request = await client.getUrl(uri.resolve(path));
    if (syntheticHeaders) {
      request.cookies.add(Cookie('m0b_probe', 'synthetic'));
      request.headers
          .set(HttpHeaders.authorizationHeader, 'Bearer m0b-synthetic');
    }
    final response = await request.close();
    final body = await utf8.decoder.bind(response).join();
    if (syntheticHeaders && body != '{"cookie":true,"bearer":true}') {
      throw StateError('header echo');
    }
    return response.statusCode;
  }

  try {
    await check('https_health', () async {
      if (await get('/api/health/live') != 200) throw StateError('health');
    });
    await check('anonymous_rejected', () async {
      if (await get('/api/auth/session') != 401) throw StateError('auth');
    });
    await check('synthetic_headers', () async {
      if (await get('/_m0b/echo', syntheticHeaders: true) != 200) {
        throw StateError('headers');
      }
    });
    await check('untrusted_certificate_rejected', () async {
      final untrusted = HttpClient()
        ..connectionTimeout = const Duration(seconds: 5);
      try {
        try {
          final request =
              await untrusted.getUrl(uri.resolve('/api/health/live'));
          await (await request.close()).drain<void>();
        } on HandshakeException {
          return;
        }
        throw StateError('untrusted TLS was accepted');
      } finally {
        untrusted.close(force: true);
      }
    });
    await check('connection_failure_and_recovery', () async {
      try {
        final request = await client.getUrl(Uri.parse('https://127.0.0.1:1/'));
        await (await request.close()).drain<void>();
        throw StateError('port unexpectedly reachable');
      } on SocketException {
        if (await get('/api/health/live') != 200) throw StateError('recovery');
      }
    });
  } finally {
    client.close(force: true);
  }
  recordProbe('completed', results);
  return results;
}
