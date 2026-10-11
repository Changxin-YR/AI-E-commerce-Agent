import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soloops_flutter/main.dart';

void main() {
  testWidgets('small landscape and large text keep environment scrollable',
      (tester) async {
    tester.view.physicalSize = const Size(640, 360);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    tester.platformDispatcher.platformBrightnessTestValue = Brightness.dark;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    addTearDown(tester.platformDispatcher.clearPlatformBrightnessTestValue);
    await tester.pumpWidget(const SoloOpsApp());
    await tester.scrollUntilVisible(find.text('查看环境信息'), 150);
    await tester.tap(find.text('查看环境信息'));
    await tester.pumpAndSettle();
    expect(find.byType(BackButton), findsOneWidget);
    expect(find.textContaining('主题：dark'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.drag(find.byType(ListView).last, const Offset(0, -300));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('shared shell opens environment page and returns',
      (tester) async {
    await tester.pumpWidget(const SoloOpsApp());
    expect(find.text('三端工程验证'), findsOneWidget);
    await tester.tap(find.text('查看环境信息'));
    await tester.pumpAndSettle();
    expect(find.text('环境信息'), findsOneWidget);
    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    expect(find.text('三端工程验证'), findsOneWidget);
  });
}
