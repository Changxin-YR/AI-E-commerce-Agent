import 'package:flutter/material.dart';
import '../core/app_state.dart';
import 'common.dart';

/// Protects local edits on back, deep-link navigation and shop/tab switches.
class EditGuard extends StatefulWidget {
  const EditGuard(
      {super.key,
      this.app,
      required this.child,
      this.controllers = const [],
      this.cleanKey,
      this.stateValue,
      this.dirty,
      this.pending = false,
      this.busy = false});
  final AppState? app;
  final Widget child;
  final List<TextEditingController> controllers;
  final Object? cleanKey, stateValue;
  final bool Function()? dirty;
  final bool pending, busy;
  @override
  State<EditGuard> createState() => _EditGuardState();
}

class _EditGuardState extends State<EditGuard> {
  final originals = <TextEditingController, String>{};
  Object? originalState;
  bool leaving = false, prompting = false;
  bool get dirty =>
      widget.pending ||
      (widget.dirty?.call() ??
          (widget.stateValue != originalState ||
              originals.entries.any((e) => e.key.text != e.value)));
  @override
  void initState() {
    super.initState();
    sync(reset: true);
    widget.app?.navigationChecks.add(check);
  }

  void changed() {
    if (mounted) setState(() {});
  }

  void sync({bool reset = false}) {
    for (final c in originals.keys.toList()) {
      if (!widget.controllers.contains(c)) {
        c.removeListener(changed);
        originals.remove(c);
      }
    }
    for (final c in widget.controllers) {
      if (!originals.containsKey(c)) {
        originals[c] = c.text;
        c.addListener(changed);
      }
      if (reset) originals[c] = c.text;
    }
    if (reset) originalState = widget.stateValue;
  }

  @override
  void didUpdateWidget(EditGuard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.app != widget.app) {
      oldWidget.app?.navigationChecks.remove(check);
      widget.app?.navigationChecks.add(check);
    }
    sync(reset: oldWidget.cleanKey != widget.cleanKey);
  }

  Future<bool> check() async {
    if (!mounted || ModalRoute.of(context)?.isCurrent != true || leaving) {
      return true;
    }
    if (prompting) return false;
    if (widget.busy) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('当前请求处理中，请等待结果后再离开。')));
      return false;
    }
    if (!dirty) return true;
    prompting = true;
    try {
      return await confirmAction(
          context,
          '离开当前表单',
          widget.pending
              ? '上次请求结果尚未确认。离开会丢失本页的恢复信息；建议先核对同次请求或回读记录。仍要离开吗？'
              : '本页有未保存修改，离开将放弃这些输入。');
    } finally {
      prompting = false;
    }
  }

  @override
  void dispose() {
    widget.app?.navigationChecks.remove(check);
    for (final c in originals.keys) {
      c.removeListener(changed);
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
      canPop: leaving || (!dirty && !widget.busy),
      onPopInvokedWithResult: (didPop, result) async {
        if (didPop || !await check() || !mounted) return;
        setState(() => leaving = true);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) Navigator.of(context).pop(result);
        });
      },
      child: widget.child);
}
