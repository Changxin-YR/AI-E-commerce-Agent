import 'package:timezone/data/latest.dart' as data;
import 'package:timezone/timezone.dart' as tz;

/// Business time never depends on the phone's timezone.
class BusinessTime {
  static bool _ready = false;
  static void initialize() {
    if (!_ready) {
      data.initializeTimeZones();
      _ready = true;
    }
  }

  static tz.Location location(String name) {
    initialize();
    try {
      return tz.getLocation(name.trim());
    } catch (_) {
      throw const FormatException('请选择有效的 IANA 业务时区。');
    }
  }

  static List<String> get zones {
    initialize();
    return tz.timeZoneDatabase.locations.keys.toList()..sort();
  }

  static DateTime date(String text) {
    final value = text.trim();
    final parsed = DateTime.tryParse('${value}T00:00:00Z');
    if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value) ||
        parsed == null ||
        day(parsed) != value) {
      throw const FormatException('请填写有效日期，例如 2026-10-11。');
    }
    return parsed;
  }

  static DateTime instant(String text) {
    final value = text.trim();
    final match = RegExp(
            r'^(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?(Z|[+-]\d{2}:\d{2})$')
        .firstMatch(value);
    if (match == null) {
      throw const FormatException(
          '时间须包含有效日期和时区偏移，例如 2026-10-11T09:00:00+08:00。');
    }
    date(match[1]!);
    final hour = int.parse(match[2]!),
        minute = int.parse(match[3]!),
        second = int.parse(match[4] ?? '0');
    final offset = match[6]!;
    if (hour > 23 ||
        minute > 59 ||
        second > 59 ||
        (offset != 'Z' &&
            (int.parse(offset.substring(1, 3)) > 23 ||
                int.parse(offset.substring(4)) > 59))) {
      throw const FormatException('小时、分钟、秒或时区偏移无效。');
    }
    return DateTime.parse(value).toUtc();
  }

  static tz.TZDateTime inZone(DateTime value, String zone) =>
      tz.TZDateTime.from(value, location(zone));
  static String day(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-${two(value.month)}-${two(value.day)}';
  static String two(int value) => value.toString().padLeft(2, '0');
  static String offset(Duration value) {
    final minutes = value.inMinutes.abs();
    return '${value.isNegative ? '-' : '+'}${two(minutes ~/ 60)}:${two(minutes % 60)}';
  }

  static String iso(DateTime value, String zone) {
    final local = inZone(value, zone);
    return '${day(local)}T${two(local.hour)}:${two(local.minute)}:${two(local.second)}${offset(local.timeZoneOffset)}';
  }

  static String display(String value, String zone) {
    final local = inZone(instant(value), zone);
    return '${day(local)} ${two(local.hour)}:${two(local.minute)}:${two(local.second)} (UTC${offset(local.timeZoneOffset)} · $zone)';
  }

  /// Enumerate valid instants instead of silently normalizing a DST gap/fold.
  static List<DateTime> candidates(
      DateTime day, int hour, int minute, String zone) {
    final loc = location(zone);
    final wall = DateTime.utc(day.year, day.month, day.day, hour, minute);
    final result = <DateTime>[];
    for (final milliseconds in loc.zones.map((z) => z.offset).toSet()) {
      final utc = wall.subtract(Duration(milliseconds: milliseconds));
      final local = tz.TZDateTime.from(utc, loc);
      if (local.year == day.year &&
          local.month == day.month &&
          local.day == day.day &&
          local.hour == hour &&
          local.minute == minute) {
        result.add(utc);
      }
    }
    return result..sort();
  }
}
