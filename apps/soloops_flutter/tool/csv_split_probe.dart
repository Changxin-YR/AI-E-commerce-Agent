import 'dart:convert';
import 'dart:io';
import 'package:soloops_flutter/features/imports/csv_split.dart';

/// Local differential check input/output, never part of the app build.
void main(List<String> args) {
  final inputs = jsonDecode(File(args.single).readAsStringSync()) as List;
  final output = <Map<String, dynamic>>[];
  for (final item in inputs) {
    try {
      final result = splitCsv(
          item['name'] as String, base64Decode(item['bytes'] as String));
      output.add({
        'manifest': result.manifest,
        'parts': result.parts.map(base64Encode).toList()
      });
    } on FormatException {
      output.add({'rejected': true});
    }
  }
  stdout.write(jsonEncode(output));
}
