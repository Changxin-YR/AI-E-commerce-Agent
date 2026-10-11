import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soloops_flutter/ui/common.dart';

void main() {
  for (final nested in [true, false]) {
    testWidgets('offscreen form still validates with nested=$nested',
        (tester) async {
      tester.view.physicalSize = const Size(390, 650);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final form = GlobalKey<FormState>();
      final value = TextEditingController();
      addTearDown(value.dispose);
      bool? submitted;
      final input = FormInput('Required value', value);
      final contents = [
        if (nested) Form(key: form, child: input) else input,
        const SizedBox(height: 2200),
        FilledButton(
            onPressed: () => submitted = form.currentState?.validate(),
            child: const Text('Submit')),
      ];
      await tester.pumpWidget(MaterialApp(
          home: Scaffold(
              body: nested
                  ? PageBody(children: contents)
                  : Form(key: form, child: PageBody(children: contents)))));
      await tester.scrollUntilVisible(find.text('Submit'), 500,
          scrollable: find.byType(Scrollable).first);
      await tester.tap(find.text('Submit'));
      await tester.pumpAndSettle();
      expect(submitted, isFalse,
          reason: 'Required offscreen input must still be registered');
      final scroll =
          tester.state<ScrollableState>(find.byType(Scrollable).first);
      scroll.position.jumpTo(0);
      await tester.pumpAndSettle();
      expect(find.text('请填写Required value'), findsOneWidget);
      await tester.enterText(find.byType(TextFormField), 'Validated value');
      FocusManager.instance.primaryFocus?.unfocus();
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('Submit'), 500,
          scrollable: find.byType(Scrollable).first);
      await tester.tap(find.text('Submit'));
      await tester.pumpAndSettle();
      expect(submitted, isTrue);
      expect(tester.takeException(), isNull);
    });
  }
}
