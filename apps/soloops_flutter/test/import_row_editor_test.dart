import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soloops_flutter/features/imports/import_batch_page.dart';

const fields = [
  {'key': 'sku', 'label': 'SKU', 'help': '稳定标识'},
  {'key': 'name', 'label': '商品名', 'help': '原始商品名'},
  {'key': 'facts', 'label': '商品参数', 'help': '已核对参数'},
];

void main() {
  testWidgets('edited correction survives save after cancelled back',
      (tester) async {
    Map<String, dynamic>? saved;
    await tester.pumpWidget(MaterialApp(
        home: Builder(
            builder: (context) => Scaffold(
                body: TextButton(
                    onPressed: () async {
                      saved = await Navigator.push<Map<String, dynamic>>(
                          context,
                          MaterialPageRoute(
                              builder: (_) => const ImportRowEditor(
                                  {
                                    'row_number': 2,
                                    'raw': {
                                      'sku': 'SYN-FIX',
                                      'name': '',
                                      'facts': '500 mL'
                                    }
                                  },
                                  fields,
                                  {},
                                  mapping: {
                                    'sku': 'sku',
                                    'name': 'name',
                                    'facts': 'facts'
                                  })));
                    },
                    child: const Text('打开'))))));
    await tester.tap(find.text('打开'));
    await tester.pumpAndSettle();
    await tester.enterText(
        find.byType(TextFormField).at(1), 'SyntheticFixedCup');
    await tester.pumpAndSettle();
    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    expect(find.text('离开当前表单'), findsOneWidget);
    await tester.tap(find.text('返回'));
    await tester.pumpAndSettle();
    expect(find.text('SyntheticFixedCup'), findsOneWidget);
    await tester.ensureVisible(find.text('保存修正，返回预览'));
    await tester.tap(find.text('保存修正，返回预览'));
    await tester.pumpAndSettle();
    expect(saved, {'name': 'SyntheticFixedCup'});
    expect(find.text('打开'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'mapped source columns and explicit blank corrections remain distinct',
      (tester) async {
    Map<String, dynamic>? saved;
    await tester.pumpWidget(MaterialApp(
        home: Builder(
            builder: (context) => Scaffold(
                body: TextButton(
                    onPressed: () async {
                      saved = await Navigator.push<Map<String, dynamic>>(
                          context,
                          MaterialPageRoute(
                              builder: (_) => const ImportRowEditor(
                                  {
                                    'row_number': 2,
                                    'raw': {
                                      'Seller SKU': '001',
                                      'Title': 'Mapped cup',
                                      'Spec': 'Old fact'
                                    }
                                  },
                                  fields,
                                  {'facts': ''},
                                  mapping: {
                                    'sku': 'Seller SKU',
                                    'name': 'Title',
                                    'facts': 'Spec'
                                  })));
                    },
                    child: const Text('打开'))))));
    await tester.tap(find.text('打开'));
    await tester.pumpAndSettle();
    final controllers = tester
        .widgetList<TextFormField>(find.byType(TextFormField))
        .map((w) => w.controller!.text)
        .toList();
    expect(controllers, ['001', 'Mapped cup', '']);
    await tester.enterText(
        find.byType(TextFormField).at(1), 'Corrected mapped cup');
    await tester.ensureVisible(find.text('保存修正，返回预览'));
    await tester.tap(find.text('保存修正，返回预览'));
    await tester.pumpAndSettle();
    expect(saved, {'facts': '', 'name': 'Corrected mapped cup'});
    expect(tester.takeException(), isNull);
  });
}
