import 'dart:async';
import 'dart:convert';
import 'dart:isolate';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';

typedef SplitMap = Map<String, dynamic>;

class PreparedCsv {
  const PreparedCsv(this.manifest, this.parts);
  final SplitMap manifest;
  final List<Uint8List> parts;
}

/// Owns one bounded worker. Cancellation terminates parsing and releases input.
class CsvSplitJob {
  final _port = ReceivePort();
  final _result = Completer<PreparedCsv>();
  final _progress = StreamController<SplitMap>.broadcast();
  Isolate? _worker;
  bool _closed = false;
  Future<PreparedCsv> get result => _result.future;
  Stream<SplitMap> get progress => _progress.stream;

  CsvSplitJob(String name, Uint8List bytes) {
    _port.listen((dynamic message) {
      if (_closed) return;
      if (message == null || message is List) {
        _finishError(const FormatException('本机拆分意外结束，请缩小文件范围后重试。'));
        return;
      }
      final event = Map<String, dynamic>.from(message as Map);
      if (event['error'] != null) {
        _finishError(FormatException(event['error'] as String));
      } else if (event['manifest'] != null) {
        final parts = (event['parts'] as List)
            .map(
                (p) => (p as TransferableTypedData).materialize().asUint8List())
            .toList();
        _result.complete(PreparedCsv(
            Map<String, dynamic>.from(event['manifest'] as Map), parts));
        _close();
      } else {
        _progress.add(event);
      }
    });
    _start(name, bytes);
  }

  Future<void> _start(String name, Uint8List bytes) async {
    try {
      final worker = await Isolate.spawn(
          _splitWorker,
          [
            _port.sendPort,
            name,
            TransferableTypedData.fromList([bytes])
          ],
          onError: _port.sendPort,
          onExit: _port.sendPort,
          errorsAreFatal: true);
      if (_closed) {
        worker.kill(priority: Isolate.immediate);
      } else {
        _worker = worker;
      }
    } catch (error) {
      _finishError(error);
    }
  }

  void cancel() => _finishError(const FormatException('已取消本机拆分。'));
  void _finishError(Object error) {
    if (_closed) return;
    _result.completeError(error);
    _close();
  }

  void _close() {
    _closed = true;
    _worker?.kill(priority: Isolate.immediate);
    _port.close();
    _progress.close();
  }
}

void _splitWorker(List<dynamic> args) {
  final port = args[0] as SendPort;
  try {
    final prepared = splitCsv(args[1] as String,
        (args[2] as TransferableTypedData).materialize().asUint8List(),
        onProgress: port.send);
    Isolate.exit(port, {
      'manifest': prepared.manifest,
      'parts': prepared.parts
          .map((p) => TransferableTypedData.fromList([p]))
          .toList()
    });
  } catch (error) {
    port.send({'error': error is FormatException ? error.message : '$error'});
  }
}

bool sameManifest(SplitMap left, SplitMap right) {
  for (final key in [
    'format',
    'source_filename',
    'source_sha256',
    'total_rows'
  ]) {
    if (left[key] != right[key]) return false;
  }
  final a = left['parts'] as List;
  final b = right['parts'] as List;
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    for (final key in ['filename', 'sha256', 'rows', 'bytes']) {
      if (a[i][key] != b[i][key]) return false;
    }
  }
  return true;
}

/// Mirrors the existing browser/Python split contract, including logical CSV rows.
PreparedCsv splitCsv(String name, Uint8List source,
    {void Function(SplitMap)? onProgress}) {
  const partLimit = 2 * 1024 * 1024;
  if (!name.toLowerCase().endsWith('.csv')) {
    throw const FormatException('请选择 UTF-8 CSV；Excel 请先将目标工作表另存为 CSV UTF-8。');
  }
  if (source.isEmpty || source.length > 40 * 1024 * 1024) {
    throw const FormatException('源文件须非空且不超过 40 MiB。');
  }
  if (name.runes.length > 240) throw const FormatException('文件名最多 240 字符。');
  final manifest = <String, dynamic>{
    'format': 'soloops-split-v1',
    'source_filename': name,
    'source_sha256': sha256.convert(source).toString(),
    'total_rows': 0,
    'parts': <SplitMap>[]
  };
  final parts = <Uint8List>[];
  Uint8List? header;
  var columns = 0, count = 0, total = 0;
  var output = BytesBuilder(copy: false);
  void flush() {
    if (parts.length == 20) throw const FormatException('最多 20 个分片，请缩小来源范围。');
    final bytes = output.takeBytes();
    (manifest['parts'] as List).add({
      'filename': 'part-${(parts.length + 1).toString().padLeft(3, '0')}.csv',
      'sha256': sha256.convert(bytes).toString(),
      'rows': count,
      'bytes': bytes.length
    });
    parts.add(bytes);
    output = BytesBuilder(copy: false)..add(header!);
    count = 0;
  }

  void accept(List<String> values) {
    if (header == null) {
      final names = values.map((v) => v.trim()).toList();
      if (names.isEmpty ||
          names.any((v) => v.isEmpty || v.runes.length > 120) ||
          names.toSet().length != names.length) {
        throw const FormatException('表头须非空且不重复，每列名称最多 120 字符。');
      }
      columns = names.length;
      header = Uint8List.fromList([239, 187, 191, ..._encodeRow(values)]);
      output.add(header!);
      return;
    }
    if (values.length > columns) {
      throw FormatException('源数据记录 ${total + 1} 列数超出表头。');
    }
    if (++total > 40000) throw const FormatException('最多 40000 个源记录，请缩小范围。');
    final row = _encodeRow(values);
    if (header!.length + row.length > partLimit) {
      throw const FormatException('单条记录超过 2 MiB，请修正原文件。');
    }
    if (count == 2000 || output.length + row.length > partLimit) flush();
    output.add(row);
    count++;
  }

  final parser = _CsvRecords(accept);
  final decoder = const Utf8Decoder(allowMalformed: false)
      .startChunkedConversion(_TextSink(parser.feed));
  for (var offset = 0; offset < source.length; offset += 65536) {
    final end = (offset + 65536).clamp(0, source.length).toInt();
    // Decoder keeps partial UTF-8 sequences between byte blocks.
    decoder.add(Uint8List.sublistView(source, offset, end));
    onProgress
        ?.call({'bytes': end, 'totalBytes': source.length, 'rows': total});
  }
  decoder.close();
  parser.finish();
  if (count == 0) throw const FormatException('源文件须有表头和至少一个数据记录。');
  flush();
  manifest['total_rows'] = total;
  return PreparedCsv(manifest, parts);
}

Uint8List _encodeRow(List<String> values) => Uint8List.fromList(utf8.encode(
    '${values.map((v) => RegExp('[,"\\r\\n]').hasMatch(v) || (values.length == 1 && v.isEmpty) ? '"${v.replaceAll('"', '""')}"' : v).join(',')}\r\n'));

class _TextSink implements Sink<String> {
  _TextSink(this.onText);
  final void Function(String) onText;
  @override
  void add(String data) => onText(data);
  @override
  void close() {}
}

class _CsvRecords {
  _CsvRecords(this.accept);
  final void Function(List<String>) accept;
  String state = 'start';
  StringBuffer field = StringBuffer();
  List<String> row = [];
  int length = 0;
  bool used = false, skipLf = false;
  void append(int rune) {
    if (rune == 0 || ++length > 2000) {
      throw const FormatException('单元格含无效字符或超过 2000 字符，请修正原文件。');
    }
    field.writeCharCode(rune);
  }

  void endField() {
    row.add(field.toString());
    if (row.length > 64) throw const FormatException('每条记录最多 64 列。');
    field = StringBuffer();
    length = 0;
    state = 'start';
  }

  void endRow() {
    if (used) endField();
    accept(row);
    row = [];
    used = false;
  }

  void feed(String text) {
    for (final rune in text.runes) {
      if (skipLf) {
        skipLf = false;
        if (rune == 10) continue;
      }
      if (state == 'quoted') {
        if (rune == 34) {
          state = 'closed';
        } else {
          append(rune);
        }
        continue;
      }
      if (state == 'closed' && rune == 34) {
        append(rune);
        state = 'quoted';
      } else if (rune == 13 || rune == 10) {
        skipLf = rune == 13;
        endRow();
      } else if (rune == 44) {
        used = true;
        endField();
      } else {
        if (state == 'closed') throw const FormatException('CSV 引号闭合后须为逗号或换行。');
        used = true;
        if (state == 'start' && rune == 34) {
          state = 'quoted';
        } else {
          append(rune);
          state = 'plain';
        }
      }
    }
  }

  void finish() {
    if (state == 'quoted') throw const FormatException('CSV 存在未闭合引号，请核对多行字段。');
    if (used) endRow();
  }
}
