import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'synthetic_transfer.dart';

const m0Channel = MethodChannel('soloops/m0');
const syntheticText = 'SoloOps M0 synthetic file\n';

void closureEvent(String name, String status, [Object? detail]) =>
    debugPrint('SOLOOPS_M0C ${jsonEncode({
          'name': name,
          'status': status,
          if (detail != null) 'detail': detail
        })}');

Future<T?> native<T>(String method, [Map<String, Object>? arguments]) =>
    m0Channel.invokeMethod<T>(method, arguments);
void requireM0(bool value) {
  if (!value) throw StateError('M0 assertion failed');
}

class ClosurePage extends StatefulWidget {
  const ClosurePage({super.key});
  @override
  State<ClosurePage> createState() => _ClosurePageState();
}

class _ClosurePageState extends State<ClosurePage> {
  final results = <String, String>{};
  bool busy = false;
  Uint8List? selected;
  Future<void> check(String name, Future<void> Function() action) async {
    try {
      await action();
      results[name] = 'PASS';
    } catch (error) {
      results[name] = 'FAIL';
      closureEvent('${name}_error', 'FAIL', error.runtimeType.toString());
    }
    closureEvent(name, results[name]!);
    if (mounted) setState(() {});
  }

  Future<void> storeChecks() async {
    await check('secure_roundtrip_overwrite', () async {
      await native<bool>('secureClear');
      await native<bool>('secureWrite', {'value': 'm0-synthetic-v1'});
      requireM0(await native<String>('secureRead') == 'm0-synthetic-v1');
      await native<bool>('secureWrite', {'value': 'm0-synthetic-v2'});
      requireM0(await native<String>('secureRead') == 'm0-synthetic-v2');
      final info = await native<Map>('secureInfo');
      requireM0(
          info?['nonExportable'] == true && info?['backupExcluded'] == true);
      closureEvent('secure_metadata', 'PASS', info);
    });
    for (final method in ['secureTamper', 'secureDropKey']) {
      await check(method, () async {
        await native<bool>('secureWrite', {'value': 'm0-synthetic-fault'});
        await native<bool>(method);
        var rejected = false;
        try {
          await native<String>('secureRead');
        } on PlatformException {
          rejected = true;
        }
        requireM0(rejected);
        requireM0(await native<bool>('secureClear') == true);
        requireM0(await native<String>('secureRead') == null);
      });
    }
    await check('cache_scopes_and_clear', () async {
      await native<bool>('cacheClear');
      await native<bool>(
          'cacheWrite', {'scope': 'synthetic-a', 'value': 'dark'});
      await native<bool>(
          'cacheWrite', {'scope': 'synthetic-b', 'value': 'light'});
      requireM0(await native<String>('cacheRead', {'scope': 'synthetic-a'}) ==
          'dark');
      requireM0(await native<String>('cacheRead', {'scope': 'synthetic-b'}) ==
          'light');
      await native<bool>('cacheClear');
      requireM0(
          await native<String>('cacheRead', {'scope': 'synthetic-a'}) == null);
    });
    await check('uri_permission_denied', () async {
      requireM0(await native<bool>('uriDenied') == true);
    });
    await check('share_size_rejected', () async {
      var rejected = false;
      try {
        await native<String>(
            'share', {'bytes': Uint8List(SyntheticTransfer.limit + 1)});
      } on PlatformException {
        rejected = true;
      }
      requireM0(rejected && await native<bool>('shareClear') == true);
    });
    await check('localized_dates', () async {
      final instant = DateTime.parse('2026-10-10T16:30:00Z');
      final civil = instant.add(const Duration(hours: 8));
      final zh = await GlobalMaterialLocalizations.delegate
          .load(const Locale('zh', 'CN'));
      final en = await GlobalMaterialLocalizations.delegate
          .load(const Locale('en', 'US'));
      requireM0(instant.isUtc && civil.day == 11 && civil.hour == 0);
      final chinese = zh.formatFullDate(civil);
      final english = en.formatFullDate(civil);
      requireM0(chinese.contains('2026') &&
          chinese.contains('10月11日') &&
          english.contains('October 11, 2026'));
      closureEvent('date_samples', 'PASS', {
        'utc': instant.toIso8601String(),
        'zone': 'Asia/Shanghai',
        'zh_CN': chinese,
        'en_US': english
      });
    });
    await check('restart_prepared', () async {
      await native<bool>('secureWrite', {'value': 'm0-synthetic-restart'});
      await native<bool>(
          'cacheWrite', {'scope': 'synthetic-a', 'value': 'restart-dark'});
    });
  }

  Future<void> restartCheck() => check('restart_read_clear', () async {
        requireM0(await native<String>('secureRead') == 'm0-synthetic-restart');
        requireM0(await native<String>('cacheRead', {'scope': 'synthetic-a'}) ==
            'restart-dark');
        requireM0(await native<bool>('secureClear') == true);
        await native<bool>('cacheClear');
        requireM0(await native<String>('secureRead') == null);
        requireM0(await native<String>('cacheRead', {'scope': 'synthetic-a'}) ==
            null);
      });

  Future<void> pick() async {
    try {
      final value = await native<Map>('pick');
      if (value?['status'] == 'cancelled') {
        selected = null;
        closureEvent('picker_cancelled', 'PASS');
        results['picker_cancelled'] = 'PASS';
      } else {
        final bytes = value?['bytes'] as Uint8List;
        // Only the known synthetic fixture may enter the network probe.
        requireM0(value?['name'] == 'soloops-m0-small.txt' &&
            value?['scheme'] == 'content' &&
            value?['mime'] == 'text/plain' &&
            listEquals(bytes, utf8.encode(syntheticText)));
        selected = bytes;
        results['picker_selected'] = 'PASS';
        closureEvent('picker_selected', 'PASS', {
          'name': value?['name'],
          'mime': value?['mime'],
          'scheme': value?['scheme'],
          'size': bytes.length,
          'sha256': value?['sha256']
        });
      }
    } on PlatformException catch (error) {
      selected = null;
      final expected = error.code == 'FILE_TOO_LARGE';
      results['picker_size_limit'] = expected ? 'PASS' : 'FAIL';
      closureEvent(
          'picker_size_limit', results['picker_size_limit']!, error.code);
    } catch (error) {
      selected = null;
      results['picker_selected'] = 'FAIL';
      closureEvent('picker_selected', 'FAIL', error.runtimeType.toString());
    }
  }

  Future<void> transfers() async {
    await check('selected_upload', () async {
      requireM0(selected != null);
      final client = SyntheticTransfer();
      try {
        final value = await client.upload(selected!);
        requireM0(value['size'] == selected!.length &&
            value['sha256'] ==
                'e38cd77fac72367b4dcc2a811ef86af583be9706b4849d2305d4b944964e7a06');
      } finally {
        client.close();
      }
    });
    await check('upload_2mib_boundary', () async {
      final client = SyntheticTransfer();
      try {
        final value = await client.upload(
            Uint8List.fromList(List.filled(SyntheticTransfer.limit, 77)));
        requireM0(value['size'] == SyntheticTransfer.limit &&
            value['sha256'] ==
                '34af56de4c2b7216ce832be471c791eb350248683cb91924eefdcfc67738f296');
      } finally {
        client.close();
      }
    });
    await check('upload_oversize_rejected', () async {
      final client = SyntheticTransfer();
      try {
        var rejected = false;
        try {
          await client.upload(Uint8List(SyntheticTransfer.limit + 1));
        } on FormatException {
          rejected = true;
        }
        requireM0(rejected);
      } finally {
        client.close();
      }
    });
    await check('upload_server_failure', () async {
      final client = SyntheticTransfer();
      try {
        var rejected = false;
        try {
          await client.upload(Uint8List.fromList(utf8.encode(syntheticText)),
              path: '/_m0c/fail');
        } on HttpException catch (error) {
          rejected = error.message == 'status 503';
        }
        requireM0(rejected);
      } finally {
        client.close();
      }
    });
    await check('upload_cancelled', () async {
      final client = SyntheticTransfer();
      final timer = Timer(const Duration(milliseconds: 150), client.cancel);
      try {
        var rejected = false;
        try {
          await client.upload(Uint8List(SyntheticTransfer.limit),
              path: '/_m0c/upload-slow', slow: true);
        } on HttpException {
          rejected = true;
        } on SocketException {
          rejected = true;
        }
        requireM0(rejected && client.cancelled);
      } finally {
        timer.cancel();
        client.close();
      }
    });
    for (final path in [
      '/_m0c/download',
      '/_m0c/download-large',
      '/_m0c/fail',
      '/_m0c/download-slow'
    ]) {
      await check('download_${path.split('/').last}', () async {
        final client = SyntheticTransfer();
        final directory =
            await Directory.systemTemp.createTemp('soloops-m0-transfer-');
        final timer = path.endsWith('-slow')
            ? Timer(const Duration(milliseconds: 550), client.cancel)
            : null;
        try {
          if (path == '/_m0c/download') {
            final file = await client.download(directory, path: path);
            requireM0(listEquals(
                await file.readAsBytes(), List<int>.filled(131072, 77)));
            requireM0(!await File('${directory.path}/download.part').exists());
          } else {
            var rejected = false;
            try {
              await client.download(directory, path: path);
            } on HttpException {
              rejected = true;
            } on SocketException {
              rejected = true;
            } on FormatException {
              rejected = true;
            }
            requireM0(rejected && await directory.list().isEmpty);
          }
        } finally {
          timer?.cancel();
          client.close();
          await directory.delete(recursive: true);
        }
      });
    }
    await check('response_timeout', () async {
      final client = SyntheticTransfer();
      try {
        var rejected = false;
        try {
          await client.delayedRequest(timeout: true);
        } on TimeoutException {
          rejected = true;
        }
        requireM0(rejected);
      } finally {
        client.close();
      }
    });
    await check('redirect_not_followed', () async {
      final client = SyntheticTransfer();
      try {
        final request = await client.open('GET', '/_m0c/redirect');
        final response = await request.close();
        requireM0(response.statusCode == 302 && response.redirects.isEmpty);
        await response.drain<void>();
      } finally {
        client.close();
      }
    });
    await check('transfer_error_recovery', () async {
      final client = SyntheticTransfer();
      try {
        final value =
            await client.upload(Uint8List.fromList(utf8.encode(syntheticText)));
        requireM0(value['sha256'] ==
            'e38cd77fac72367b4dcc2a811ef86af583be9706b4849d2305d4b944964e7a06');
      } finally {
        client.close();
      }
    });
    closureEvent('transfers_complete',
        results.values.every((v) => v == 'PASS') ? 'PASS' : 'FAIL');
  }

  Future<void> action(Future<void> Function() run) async {
    setState(() => busy = true);
    try {
      await run();
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('M0 技术验收')),
        body: SafeArea(
            child: ListView(padding: const EdgeInsets.all(16), children: [
          const Text('合成资料 · 安全存储 / 文件 / 传输'),
          const Text('先准备存储，结束进程后核对。文件上限 2 MiB。'),
          for (final entry in <String, Future<void> Function()>{
            '存储与重启准备': storeChecks,
            '重启读回并清除': restartCheck,
            '选择合成文件': pick,
            '传输与网络边界': transfers,
            '打开合成分享面板': () => check('share_panel', () async {
                  requireM0(await native<String>('share', {
                        'bytes': Uint8List.fromList(utf8.encode(syntheticText))
                      }) ==
                      'panel_opened');
                }),
            '清理分享文件': () => check('share_cleanup', () async {
                  requireM0(await native<bool>('shareClear') == true);
                }),
            '打开本机外链': () => check('external_browser', () async {
                  requireM0(
                      await native<String>('external') == 'browser_opened');
                }),
          }.entries)
            Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: FilledButton(
                    onPressed: busy ? null : () => action(entry.value),
                    child: Text(entry.key))),
          const Text('分享面板可取消。渠道接收结果须另行核验。'),
          for (final entry in results.entries)
            Text('${entry.key}: ${entry.value}'),
        ])),
      );
}
