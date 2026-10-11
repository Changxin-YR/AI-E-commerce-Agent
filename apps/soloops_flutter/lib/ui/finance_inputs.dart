import 'package:flutter/material.dart';

/// Decimal strings stay exact through validation and transport.
String decimalInput(String raw, String label,
    {int places = 4, String max = '99999999999999', bool positive = false}) {
  final value = raw.trim();
  if (!RegExp('^[0-9]+(\\.[0-9]{1,$places})?\$').hasMatch(value) ||
      value.length > 32) {
    throw FormatException('$label须为非负数字，最多 $places 位小数。');
  }
  BigInt scaled(String input) {
    final parts = input.split('.');
    return BigInt.parse(parts[0]) * BigInt.from(10).pow(places) +
        BigInt.parse((parts.length == 1 ? '' : parts[1]).padRight(places, '0'));
  }

  final number = scaled(value);
  if (number > scaled(max) || (positive && number == BigInt.zero)) {
    throw FormatException('$label须${positive ? '大于零且' : ''}不超过 $max。');
  }
  return value;
}

String requiredText(String value, String label, int max) {
  final result = value.trim();
  if (result.isEmpty || result.length > max) {
    throw FormatException('$label须填写 1–$max 个字符。');
  }
  return result;
}

/// Positive decimal multiplication, half up at four fractional places.
String convertedMoney(String amount, String rate) {
  BigInt units(String value, int places) {
    final parts = value.split('.');
    return BigInt.parse(parts[0]) * BigInt.from(10).pow(places) +
        BigInt.parse((parts.length > 1 ? parts[1] : '').padRight(places, '0'));
  }

  final value = units(decimalInput(amount, '原币金额', max: '100000000'), 4) *
      units(
          decimalInput(rate, '汇率', places: 8, max: '100000000', positive: true),
          8);
  final divisor = BigInt.from(10).pow(8);
  final rounded = (value + divisor ~/ BigInt.two) ~/ divisor;
  final text = rounded.toString().padLeft(5, '0');
  return decimalInput(
      '${text.substring(0, text.length - 4)}.${text.substring(text.length - 4)}',
      '换算金额',
      max: '100000000');
}

class DecimalField extends StatelessWidget {
  const DecimalField(this.label, this.controller,
      {super.key,
      this.optional = false,
      this.max = '99999999999999',
      this.positive = false,
      this.places = 4,
      this.enabled = true});
  final String label, max;
  final TextEditingController controller;
  final bool optional, positive, enabled;
  final int places;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextFormField(
          controller: controller,
          enabled: enabled,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: InputDecoration(
              labelText: label, helperText: optional ? '留空表示未知' : null),
          validator: (v) {
            if (optional && (v ?? '').trim().isEmpty) return null;
            try {
              decimalInput(v ?? '', label,
                  max: max, positive: positive, places: places);
              return null;
            } on FormatException catch (e) {
              return e.message;
            }
          }));
}

int integerInput(String raw, String label, int min, int max) {
  final value = int.tryParse(raw.trim());
  if (value == null || value < min || value > max) {
    throw FormatException('$label须为 $min–$max 的整数。');
  }
  return value;
}

String marginInput(String raw) {
  final value = raw.trim();
  if (!RegExp(r'^-?\d+(\.\d{1,2})?$').hasMatch(value) || value.length > 12) {
    throw const FormatException('毛利率须为 -1000 至 100，最多两位小数。');
  }
  final negative = value.startsWith('-');
  final parts = (negative ? value.substring(1) : value).split('.');
  final cents = BigInt.parse(parts[0]) * BigInt.from(100) +
      BigInt.parse((parts.length > 1 ? parts[1] : '').padRight(2, '0'));
  if (cents > BigInt.from(negative ? 100000 : 10000)) {
    throw const FormatException('毛利率须为 -1000 至 100。');
  }
  return value;
}
