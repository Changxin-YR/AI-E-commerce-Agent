import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soloops_flutter/core/api_client.dart';
import 'package:soloops_flutter/core/app_state.dart';
import 'package:soloops_flutter/core/business_navigation.dart';
import 'package:soloops_flutter/features/finance/expenses_page.dart';
import 'package:soloops_flutter/features/profit/profit_page.dart';
import 'package:soloops_flutter/product_app.dart';
import 'package:soloops_flutter/ui/business_time_fields.dart';
import 'package:soloops_flutter/ui/common.dart';
import 'package:soloops_flutter/ui/edit_guard.dart';

class SyntheticApi extends ApiClient {
  final calls = <String>[];
  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? query}) async {
    calls.add(path);
    if (path.endsWith('/profit/saved')) return [];
    throw const ApiFailure('合成离线反馈');
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel('soloops/device'),
            (call) async {
      if (call.method == 'settingsRead') return <String, dynamic>{};
      return null;
    });
  });
  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel('soloops/device'), null);
    businessRoutes.clear();
  });

  for (final size in [const Size(390, 844), const Size(640, 360)]) {
    testWidgets('product login remains usable at $size and 2x text',
        (tester) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      tester.platformDispatcher.textScaleFactorTestValue = 2;
      tester.platformDispatcher.platformBrightnessTestValue = Brightness.dark;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      addTearDown(tester.platformDispatcher.clearPlatformBrightnessTestValue);
      await tester.pumpWidget(const ProductApp());
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('登录'), 180,
          scrollable: find.byType(Scrollable).first);
      await tester.tap(find.text('登录'));
      await tester.pumpAndSettle();
      expect(find.text('请填写账号'), findsOneWidget);
      expect(find.text('请填写密码'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('dirty editor protects system back and business navigation',
      (tester) async {
    final controller = TextEditingController();
    final app = AppState(api: SyntheticApi());
    addTearDown(controller.dispose);
    addTearDown(app.dispose);
    await tester.pumpWidget(MaterialApp(
        home: Builder(
            builder: (context) => Scaffold(
                body: TextButton(
                    onPressed: () => Navigator.push<void>(
                        context,
                        MaterialPageRoute(
                            builder: (_) => EditGuard(
                                app: app,
                                controllers: [controller],
                                child: Scaffold(
                                    appBar: AppBar(title: const Text('编辑测试')),
                                    body: FormInput('正文', controller))))),
                    child: const Text('打开'))))));
    await tester.tap(find.text('打开'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField), '未保存正文');
    await tester.pumpAndSettle();
    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    expect(find.text('离开当前表单'), findsOneWidget);
    await tester.tap(find.text('返回'));
    await tester.pumpAndSettle();
    expect(controller.text, '未保存正文');
    final navigation = app.canNavigate();
    await tester.pumpAndSettle();
    await tester.tap(find.text('返回'));
    await tester.pumpAndSettle();
    expect(await navigation, isFalse);
    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    await tester.tap(find.text('确认'));
    await tester.pumpAndSettle();
    expect(find.text('打开'), findsOneWidget);
    expect(app.navigationChecks, isEmpty);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'deep link parses encoded query and rejects cross-shop and external paths',
      (tester) async {
    final app = AppState(api: SyntheticApi())..shopId = 4;
    addTearDown(app.dispose);
    Map<String, String>? received;
    businessRoutes['/probe'] = (app, query) {
      received = query;
      return const Scaffold(body: Text('目标页'));
    };
    late BuildContext source;
    await tester.pumpWidget(MaterialApp(home: Builder(builder: (context) {
      source = context;
      return const Scaffold(body: Text('源页'));
    })));
    openBusinessPath(source, app, '/probe?shop=4&sku=A%2BB&run=8');
    await tester.pumpAndSettle();
    expect(received, {'shop': '4', 'sku': 'A+B', 'run': '8'});
    Navigator.of(source).pop();
    await tester.pumpAndSettle();
    received = null;
    await openBusinessPath(source, app, '/probe?shop=7');
    await tester.pumpAndSettle();
    expect(received, isNull);
    await openBusinessPath(source, app, 'https://example.com/probe');
    await tester.pumpAndSettle();
    expect(received, isNull);
  });

  testWidgets('expense form and timezone feedback fit narrow large-text screen',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    final app = AppState(api: SyntheticApi())
      ..shopId = 4
      ..shops = [
        {'id': 4, 'timezone': 'America/New_York', 'currency': 'USD'}
      ];
    addTearDown(app.dispose);
    await tester.pumpWidget(MaterialApp(
        home: BusinessTimeZone(
            zone: 'America/New_York',
            child: ExpenseEditor(app, partition: const {
              'data_identity': 'synthetic',
              'channel': 'generic'
            }))));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.byType(BusinessDateTimeField), 220,
        scrollable: find.byType(Scrollable).first);
    await tester.enterText(
        find.descendant(
            of: find.byType(BusinessDateTimeField),
            matching: find.byType(TextFormField)),
        '2026-02-30T00:00:00Z');
    await tester.pumpAndSettle();
    expect(find.textContaining('请填写有效日期'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'profit unknown fee remains distinct from explicit zero in editable form',
      (tester) async {
    final api = SyntheticApi();
    final app = AppState(api: api)..shopId = 4;
    addTearDown(app.dispose);
    await tester.pumpWidget(MaterialApp(home: ProfitPage(app)));
    await tester.pumpAndSettle();
    expect(api.calls, contains('/shops/4/profit/saved'));
    await tester.scrollUntilVisible(
        find.text('空白费用表示未知；填写 0 表示明确为零，也须填写依据。'), 250,
        scrollable: find.byType(Scrollable).first);
    expect(find.text('未填 · 未计入'), findsWidgets);
    expect(tester.takeException(), isNull);
  });
}
