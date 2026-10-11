import 'package:flutter/material.dart';
import '../core/app_state.dart';
import 'common.dart';

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
      child: SelectableText(
          '$label：${value == null || value == '' ? '未知' : value}'));
}

/// Shared request lifecycle; domain pages supply their own forms and details.
abstract class BusinessPageState<T extends StatefulWidget> extends State<T> {
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
      if (mounted) setState(() => success = message ?? success);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  List<Widget> get feedback => [
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
