import 'package:flutter/material.dart';
import '../core/app_state.dart';
import 'common.dart';
import '../core/business_time.dart';
import 'business_time_fields.dart';

class ChoiceField extends StatelessWidget {
  const ChoiceField(this.label, this.value, this.choices, this.onChanged,
      {super.key, this.help});
  final String label;
  final String? value;
  final Map<String, String> choices;
  final void Function(String)? onChanged;
  final String? help;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: DropdownButtonFormField<String>(
        key: ValueKey('$label:$value:${choices.keys.join('|')}'),
        value: choices.containsKey(value) ? value : null,
        isExpanded: true,
        itemHeight: null,
        decoration: InputDecoration(
            labelText: label, helperText: help, helperMaxLines: 6),
        items: choices.entries
            .map((e) => DropdownMenuItem(
                value: e.key,
                child: Text(e.value, overflow: TextOverflow.ellipsis)))
            .toList(),
        onChanged: onChanged == null
            ? null
            : (v) {
                if (v != null) onChanged!(v);
              },
      ));
}

class FactLine extends StatelessWidget {
  const FactLine(this.label, this.value, {super.key});
  final String label;
  final Object? value;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Tooltip(
          message: value == null ? '' : '$value',
          child: SelectableText('$label：${businessTimeText(context, value)}')));
}

/// Shared request lifecycle; domain pages supply their own forms and details.
abstract class BusinessPageState<T extends StatefulWidget> extends State<T>
    with WidgetsBindingObserver {
  DateTime? _pausedAt;
  bool resumedData = false;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused) _pausedAt = DateTime.now();
    if (state == AppLifecycleState.resumed &&
        _pausedAt != null &&
        DateTime.now().difference(_pausedAt!) > const Duration(minutes: 1) &&
        mounted) {
      setState(() => resumedData = true);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  bool busy = false;
  String? error, success;
  Future<void> perform(Future<void> Function() action,
      {String? message}) async {
    if (busy || !mounted) return;
    setState(() {
      busy = true;
      error = null;
      success = null;
    });
    try {
      await action();
      if (mounted) {
        setState(() {
          success = message ?? success;
          resumedData = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => error = e is FormatException ? e.message : '$e');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  List<Widget> get feedback => [
        if (resumedData) const Text('页面保留离开前的数据和输入，可刷新当前记录核对最新状态。'),
        if (busy) const LinearProgressIndicator(),
        if (error != null) Notice(error!),
        if (success != null)
          Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(success!,
                  style:
                      TextStyle(color: Theme.of(context).colorScheme.primary))),
      ];
}

List<Json> rows(dynamic value) => value is List ? objects(value) : [];

String? awareDate(String value, String label, {bool required = false}) {
  if (value.trim().isEmpty) {
    if (required) throw FormatException('请填写$label。');
    return null;
  }
  try {
    BusinessTime.instant(value);
  } on FormatException catch (e) {
    throw FormatException('$label：${e.message}');
  }
  return value.trim();
}
