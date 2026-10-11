import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';

/// Loopback-only M0 transfer client. Caps both known and streamed body sizes.
class SyntheticTransfer {
  static const limit = 2 * 1024 * 1024;
  final HttpClient client;
  final Uri base;
  HttpClientRequest? active;
  bool cancelled = false;

  SyntheticTransfer._(this.client, this.base);
  factory SyntheticTransfer() {
    const endpoint = String.fromEnvironment('M0B_API_BASE');
    const certificate = String.fromEnvironment('M0B_CA_BASE64');
    final base = Uri.parse(endpoint);
    if (!kDebugMode || base.scheme != 'https' || base.host != '127.0.0.1') {
      throw StateError('Debug loopback fixture required');
    }
    final context = SecurityContext(withTrustedRoots: true)
      ..setTrustedCertificatesBytes(base64Decode(certificate));
    return SyntheticTransfer._(
        HttpClient(context: context)
          ..connectionTimeout = const Duration(seconds: 2),
        base);
  }

  void cancel() {
    cancelled = true;
    active?.abort(const HttpException('M0 cancelled'));
    client.close(force: true);
  }

  Future<HttpClientRequest> open(String method, String path) async {
    if (cancelled) throw const HttpException('M0 cancelled');
    final request = await client.openUrl(method, base.resolve(path));
    active = request;
    request.followRedirects = false;
    request.headers.set('x-m0-synthetic', 'true');
    if (cancelled) {
      request.abort();
      throw const HttpException('M0 cancelled');
    }
    return request;
  }

  Future<Uint8List> body(HttpClientResponse response,
      {int maximum = limit}) async {
    if (response.statusCode != 200) {
      throw HttpException('status ${response.statusCode}');
    }
    if (response.contentLength > maximum) throw const FormatException('size');
    final builder = BytesBuilder(copy: false);
    await for (final chunk in response.timeout(const Duration(seconds: 3))) {
      if (cancelled) throw const HttpException('M0 cancelled');
      if (builder.length + chunk.length > maximum) {
        throw const FormatException('size');
      }
      builder.add(chunk);
    }
    return builder.takeBytes();
  }

  Future<Map<String, dynamic>> upload(Uint8List bytes,
      {String path = '/_m0c/upload', bool slow = false}) async {
    if (bytes.length > limit) throw const FormatException('size');
    final request = await open('POST', path);
    // Chunked transfer also exercises server accounting without Content-Length.
    await request.addStream(Stream<Uint8List>.multi((controller) async {
      for (var offset = 0; offset < bytes.length; offset += 65536) {
        if (cancelled) break;
        final end = (offset + 65536).clamp(0, bytes.length);
        controller.add(Uint8List.sublistView(bytes, offset, end));
        if (slow) await Future<void>.delayed(const Duration(milliseconds: 40));
      }
      controller.close();
    }));
    final response = await request.close().timeout(const Duration(seconds: 5));
    return jsonDecode(utf8.decode(await body(response, maximum: 4096)))
        as Map<String, dynamic>;
  }

  Future<File> download(Directory directory,
      {String path = '/_m0c/download'}) async {
    final partial = File('${directory.path}/download.part');
    final complete = File('${directory.path}/synthetic.bin');
    IOSink? sink;
    try {
      final request = await open('GET', path);
      final response =
          await request.close().timeout(const Duration(seconds: 3));
      if (response.statusCode != 200) {
        throw HttpException('status ${response.statusCode}');
      }
      if (response.contentLength > limit) throw const FormatException('size');
      sink = partial.openWrite();
      var size = 0;
      await for (final chunk in response.timeout(const Duration(seconds: 3))) {
        if (cancelled) throw const HttpException('M0 cancelled');
        size += chunk.length;
        if (size > limit) throw const FormatException('size');
        sink.add(chunk);
        await sink.flush();
      }
      await sink.close();
      sink = null;
      return await partial.rename(complete.path);
    } catch (_) {
      await sink?.close();
      if (await partial.exists()) await partial.delete();
      rethrow;
    }
  }

  Future<void> delayedRequest({bool timeout = false}) async {
    final request = await open('GET', '/_m0c/slow');
    try {
      final response = await request
          .close()
          .timeout(Duration(milliseconds: timeout ? 150 : 4000), onTimeout: () {
        request.abort(const HttpException('M0 timeout'));
        throw TimeoutException('M0 response deadline');
      });
      await body(response);
    } finally {
      active = null;
    }
  }

  void close() => client.close(force: true);
}
