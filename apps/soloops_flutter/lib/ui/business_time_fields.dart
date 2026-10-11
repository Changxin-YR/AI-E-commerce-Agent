import 'package:flutter/material.dart';
import '../core/business_time.dart';

class BusinessTimeZone extends InheritedWidget {
  const BusinessTimeZone({super.key, required this.zone, required super.child});
  final String zone;
  static String of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<BusinessTimeZone>()?.zone ??
      'UTC';
  @override
  bool updateShouldNotify(BusinessTimeZone oldWidget) => zone != oldWidget.zone;
}

String businessTimeText(BuildContext context, Object? value, {String? zone}) {
  if (value == null || value == '') return '未知';
  return '$value'.replaceAllMapped(
      RegExp(
          r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})'),
      (match) {
    try {
      return BusinessTime.display(
          match[0]!, zone ?? BusinessTimeZone.of(context));
    } on FormatException {
      return '${match[0]}（原始时间）';
    }
  });
}

class BusinessDateTimeField extends StatelessWidget {
  const BusinessDateTimeField(this.label, this.controller,
      {super.key, this.zone, this.enabled = true, this.required = true});
  final String label;
  final TextEditingController controller;
  final TextEditingController? zone;
  final bool enabled, required;
  Future<void> pick(BuildContext context) async {
    try {
      final name = zone?.text.trim() ?? BusinessTimeZone.of(context);
      final current = BusinessTime.inZone(
          DateTime.tryParse(controller.text) ?? DateTime.now().toUtc(), name);
      final first = DateTime(1900), last = DateTime(2100, 12, 31);
      final initial = DateTime(current.year, current.month, current.day);
      final chosen = await showDatePicker(
          context: context,
          initialDate: initial.isBefore(first)
              ? first
              : initial.isAfter(last)
                  ? last
                  : initial,
          firstDate: first,
          lastDate: last,
          helpText: '$label · $name');
      if (chosen == null || !context.mounted) return;
      final time = await showTimePicker(
          context: context,
          initialTime: TimeOfDay(hour: current.hour, minute: current.minute),
          helpText: name,
          builder: (context, child) => MediaQuery(
              data:
                  MediaQuery.of(context).copyWith(alwaysUse24HourFormat: true),
              child: child!));
      if (time == null || !context.mounted) return;
      final candidates =
          BusinessTime.candidates(chosen, time.hour, time.minute, name);
      if (candidates.isEmpty) {
        throw const FormatException('该时间因夏令时切换而不存在，请另选时间。');
      }
      DateTime? selected = candidates.first;
      if (candidates.length > 1) {
        selected = await showDialog<DateTime>(
            context: context,
            builder: (dialog) =>
                SimpleDialog(title: const Text('此时间出现两次，请选择偏移'), children: [
                  for (final value in candidates)
                    SimpleDialogOption(
                        onPressed: () => Navigator.pop(dialog, value),
                        child: Text(BusinessTime.display(
                            BusinessTime.iso(value, name), name)))
                ]));
      }
      if (selected != null && context.mounted) {
        controller.text = BusinessTime.iso(selected, name);
      }
    } on FormatException catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
      listenable: Listenable.merge([controller, if (zone != null) zone!]),
      builder: (context, _) {
        String? helper;
        try {
          if (controller.text.isNotEmpty) {
            helper = BusinessTime.display(controller.text,
                zone?.text.trim() ?? BusinessTimeZone.of(context));
          }
        } on FormatException {
          helper = '可用日历选择，或输入含偏移的 ISO 时间。';
        }
        return Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: TextFormField(
                controller: controller,
                enabled: enabled,
                autovalidateMode: AutovalidateMode.onUserInteraction,
                decoration: InputDecoration(
                    labelText: label,
                    helperText: helper,
                    helperMaxLines: 4,
                    suffixIcon: IconButton(
                        tooltip: '选择日期与时间',
                        onPressed: enabled ? () => pick(context) : null,
                        icon: const Icon(Icons.calendar_month_outlined))),
                validator: (value) {
                  if ((value ?? '').trim().isEmpty) {
                    return required ? '请填写$label' : null;
                  }
                  try {
                    BusinessTime.instant(value!);
                    BusinessTime.location(
                        zone?.text.trim() ?? BusinessTimeZone.of(context));
                    return null;
                  } on FormatException catch (e) {
                    return e.message;
                  }
                }));
      });
}

class BusinessDateField extends StatelessWidget {
  const BusinessDateField(this.label, this.controller,
      {super.key, this.enabled = true});
  final String label;
  final TextEditingController controller;
  final bool enabled;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextFormField(
          controller: controller,
          enabled: enabled,
          autovalidateMode: AutovalidateMode.onUserInteraction,
          decoration: InputDecoration(
              labelText: label,
              suffixIcon: IconButton(
                  tooltip: '选择日期',
                  onPressed: !enabled
                      ? null
                      : () async {
                          final now = BusinessTime.inZone(
                              DateTime.now().toUtc(),
                              BusinessTimeZone.of(context));
                          final first = DateTime(1900),
                              last = DateTime(2100, 12, 31);
                          final current = DateTime.tryParse(controller.text) ??
                              DateTime(now.year, now.month, now.day);
                          final value = await showDatePicker(
                              context: context,
                              initialDate: current.isBefore(first)
                                  ? first
                                  : current.isAfter(last)
                                      ? last
                                      : current,
                              firstDate: first,
                              lastDate: last);
                          if (value != null && context.mounted) {
                            controller.text = BusinessTime.day(value);
                          }
                        },
                  icon: const Icon(Icons.calendar_month_outlined))),
          validator: (value) {
            try {
              BusinessTime.date(value ?? '');
              return null;
            } on FormatException catch (e) {
              return e.message;
            }
          }));
}

class BusinessZoneField extends StatelessWidget {
  const BusinessZoneField(this.label, this.controller,
      {super.key, this.enabled = true});
  final String label;
  final TextEditingController controller;
  final bool enabled;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextFormField(
          controller: controller,
          enabled: enabled,
          autovalidateMode: AutovalidateMode.onUserInteraction,
          decoration: InputDecoration(
              labelText: label,
              suffixIcon: IconButton(
                  tooltip: '查找业务时区',
                  onPressed: !enabled
                      ? null
                      : () async {
                          final value = await showDialog<String>(
                              context: context,
                              builder: (_) => const _ZoneDialog());
                          if (value != null && context.mounted) {
                            controller.text = value;
                          }
                        },
                  icon: const Icon(Icons.search))),
          validator: (value) {
            try {
              BusinessTime.location(value ?? '');
              return null;
            } on FormatException catch (e) {
              return e.message;
            }
          }));
}

class _ZoneDialog extends StatefulWidget {
  const _ZoneDialog();
  @override
  State<_ZoneDialog> createState() => _ZoneDialogState();
}

class _ZoneDialogState extends State<_ZoneDialog> {
  String search = '';
  @override
  Widget build(BuildContext context) {
    final values = BusinessTime.zones
        .where((z) => z.toLowerCase().contains(search.toLowerCase()))
        .toList();
    return AlertDialog(
        title: const Text('选择业务时区'),
        content: SizedBox(
            width: 420,
            height: MediaQuery.sizeOf(context).height * .5,
            child: Column(children: [
              TextField(
                  autofocus: true,
                  decoration:
                      const InputDecoration(labelText: '搜索城市或区域，如 Shanghai'),
                  onChanged: (v) => setState(() => search = v)),
              Expanded(
                  child: ListView.builder(
                      itemCount: values.length,
                      itemBuilder: (context, index) => ListTile(
                          title: Text(values[index]),
                          onTap: () => Navigator.pop(context, values[index]))))
            ])),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context), child: const Text('取消'))
        ]);
  }
}
