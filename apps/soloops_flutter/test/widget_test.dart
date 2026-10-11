import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soloops_flutter/main.dart';

void main() {
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
