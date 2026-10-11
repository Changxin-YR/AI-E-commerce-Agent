import 'package:flutter/material.dart';
import '../core/app_state.dart';

class Notice extends StatelessWidget {
  const Notice(this.message, {super.key, this.onRetry});
  final String message;
  final VoidCallback? onRetry;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(message,
            style: TextStyle(color: Theme.of(context).colorScheme.error)),
        if (onRetry != null)
          TextButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('重试'))
      ]));
}

class PageBody extends StatelessWidget {
  const PageBody({super.key, required this.children});
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => SafeArea(
      child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(20),
          children: children));
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key});
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(top: 24, bottom: 12),
      child: Text(text, style: Theme.of(context).textTheme.titleLarge));
}

class FormInput extends StatelessWidget {
  const FormInput(this.label, this.controller,
      {super.key,
      this.lines = 1,
      this.required = true,
      this.secret = false,
      this.enabled = true,
      this.type});
  final String label;
  final TextEditingController controller;
  final int lines;
  final bool required;
  final bool secret;
  final bool enabled;
  final TextInputType? type;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextFormField(
          controller: controller,
          enabled: enabled,
          obscureText: secret,
          autocorrect: !secret,
          enableSuggestions: !secret,
          maxLines: lines,
          keyboardType: type,
          decoration:
              InputDecoration(labelText: label, alignLabelWithHint: lines > 1),
          validator: (value) => required && (value?.trim().isEmpty ?? true)
              ? '请填写$label'
              : null));
}

Future<bool> confirmAction(
        BuildContext context, String title, String message) async =>
    await showDialog<bool>(
        context: context,
        builder: (context) =>
            AlertDialog(title: Text(title), content: Text(message), actions: [
              TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('返回')),
              FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('确认'))
            ])) ??
    false;

class ShopPicker extends StatelessWidget {
  const ShopPicker(this.app, {super.key});
  final AppState app;
  @override
  Widget build(BuildContext context) => DropdownButtonHideUnderline(
      child: DropdownButton<int>(
          value: app.shopId,
          hint: const Text('选择店铺'),
          isExpanded: true,
          items: app.shops
              .map((shop) => DropdownMenuItem<int>(
                  value: shop['id'] as int,
                  child:
                      Text('${shop['name']}', overflow: TextOverflow.ellipsis)))
              .toList(),
          onChanged: (value) {
            if (value != null) app.selectShop(value);
          }));
}
