import 'dart:convert';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soloops_flutter/core/business_time.dart';
import 'package:soloops_flutter/features/imports/csv_split.dart';
import 'package:soloops_flutter/ui/finance_inputs.dart';

void main() {
  test('money preserves exact fractions and distinguishes unknown from zero',
      () {
    expect(decimalInput('99999999999998.9999', '金额'), '99999999999998.9999');
    expect(decimalInput('0.0000', '金额'), '0.0000');
    for (final input in [
      '',
      'NaN',
      '1e3',
      '-1',
      '1.00001',
      '100,000',
      '99999999999999.0001'
    ]) {
      expect(() => decimalInput(input, '金额'), throwsFormatException);
    }
    expect(
        () => decimalInput('0', '金额', positive: true), throwsFormatException);
  });
  test('exchange uses decimal half-up at four places and bounded output', () {
    expect(convertedMoney('0.0001', '0.5'), '0.0001');
    expect(convertedMoney('12345.6789', '1.23456789'), '15241.5788');
    expect(convertedMoney('100000000', '0.00000001'), '1.0000');
    expect(() => convertedMoney('100000000', '2'), throwsFormatException);
    expect(() => convertedMoney('1', '0'), throwsFormatException);
    expect(marginInput('-1000.00'), '-1000.00');
    expect(() => marginInput('100.01'), throwsFormatException);
  });
  test('strict date validation rejects rollover and missing offsets', () {
    expect(BusinessTime.instant('2024-02-29T09:05:06+08:00'),
        DateTime.utc(2024, 2, 29, 1, 5, 6));
    for (final input in [
      '2026-02-29T00:00Z',
      '2026-01-32T00:00Z',
      '2026-10-11T24:00Z',
      '2026-10-11T01:60Z',
      '2026-10-11T10:00',
      '2026-10-11T09:00+25:00'
    ]) {
      expect(() => BusinessTime.instant(input), throwsFormatException);
    }
  });
  test('business conversion ignores device timezone and crosses dates', () {
    final value = DateTime.utc(2026, 10, 11, 18, 30);
    expect(
        BusinessTime.iso(value, 'Asia/Shanghai'), '2026-10-12T02:30:00+08:00');
    expect(BusinessTime.iso(value, 'America/New_York'),
        '2026-10-11T14:30:00-04:00');
    expect(() => BusinessTime.location('invalid-zone'), throwsFormatException);
  });
  test('DST gap has no candidate, fold requires explicit offset', () {
    expect(
        BusinessTime.candidates(
            DateTime.utc(2026, 3, 8), 2, 30, 'America/New_York'),
        isEmpty);
    final values = BusinessTime.candidates(
        DateTime.utc(2026, 11, 1), 1, 30, 'America/New_York');
    expect(values,
        [DateTime.utc(2026, 11, 1, 5, 30), DateTime.utc(2026, 11, 1, 6, 30)]);
    expect(values.map((v) => BusinessTime.iso(v, 'America/New_York')),
        ['2026-11-01T01:30:00-04:00', '2026-11-01T01:30:00-05:00']);
  });
  test('half-hour DST transitions and skipped calendar date are explicit', () {
    expect(
        BusinessTime.candidates(
            DateTime.utc(2026, 10, 4), 2, 15, 'Australia/Lord_Howe'),
        isEmpty);
    expect(
        BusinessTime.candidates(
            DateTime.utc(2011, 12, 30), 12, 0, 'Pacific/Apia'),
        isEmpty);
    expect(
        BusinessTime.candidates(
            DateTime.utc(2026, 4, 5), 1, 45, 'Australia/Lord_Howe'),
        hasLength(2));
  });
  test('CSV logical records retain quoted newline and exact normalized bytes',
      () {
    final source = Uint8List.fromList(
        utf8.encode('\ufeffsku,facts\r\nS1,"第一行\n第二行,含逗号"\r\nS2,"a""b"\r\n'));
    final split = splitCsv('合成.csv', source);
    expect(split.manifest['total_rows'], 2);
    expect(split.manifest['source_sha256'], sha256.convert(source).toString());
    expect(utf8.decode(split.parts.single),
        'sku,facts\r\nS1,"第一行\n第二行,含逗号"\r\nS2,"a""b"\r\n');
    expect(split.parts.single.take(3), [239, 187, 191]);
    expect(split.manifest['parts'][0]['sha256'],
        sha256.convert(split.parts.single).toString());
  });
  test('CSV partitions at 2000 records, handles UTF8 spanning decode blocks',
      () {
    final text =
        'sku,facts\n${List.generate(2001, (i) => 'S$i,${'中' * 53}').join('\n')}';
    final split =
        splitCsv('synthetic.csv', Uint8List.fromList(utf8.encode(text)));
    expect(split.parts, hasLength(2));
    expect(split.manifest['parts'].map((dynamic p) => p['rows']), [2000, 1]);
    expect(split.manifest['total_rows'], 2001);
    expect(utf8.decode(split.parts.last), startsWith('sku,facts\r\nS2000,'));
  });
  test('CSV rejects malformed UTF8, unclosed quote and oversized field', () {
    expect(() => splitCsv('s.csv', Uint8List.fromList([0xff, 0x0a])),
        throwsFormatException);
    expect(
        () => splitCsv('s.csv', Uint8List.fromList(utf8.encode('sku\n"bad'))),
        throwsFormatException);
    expect(
        () => splitCsv(
            's.csv', Uint8List.fromList(utf8.encode('sku\n${'x' * 2001}'))),
        throwsFormatException);
  });
}
