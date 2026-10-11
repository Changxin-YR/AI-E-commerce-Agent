import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'core/app_state.dart';
import 'features/account_pages.dart';
import 'features/workbench_page.dart';
import 'ui/common.dart';

class ProductApp extends StatefulWidget {
  const ProductApp({super.key});
  @override
  State<ProductApp> createState() => _ProductAppState();
}

class _ProductAppState extends State<ProductApp> {
  final app = AppState();
  @override
  void initState() {
    super.initState();
    app.initialize();
  }

  @override
  void dispose() {
    app.dispose();
    super.dispose();
  }

  ThemeData theme(Brightness brightness) {
    final scheme = ColorScheme.fromSeed(
        seedColor: const Color(0xFF4D6544), brightness: brightness);
    return ThemeData(
        useMaterial3: true,
        colorScheme: scheme,
        scaffoldBackgroundColor: brightness == Brightness.light
            ? const Color(0xFFF7F8F4)
            : const Color(0xFF141913),
        appBarTheme: AppBarTheme(
            backgroundColor: brightness == Brightness.light
                ? const Color(0xFFF7F8F4)
                : const Color(0xFF141913),
            elevation: 0,
            scrolledUnderElevation: 0),
        inputDecorationTheme: InputDecorationTheme(
            filled: true,
            fillColor: scheme.surface,
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
            border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none)),
        filledButtonTheme: FilledButtonThemeData(
            style: FilledButton.styleFrom(
                minimumSize: const Size(48, 52),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)))));
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
      animation: app,
      builder: (context, _) => MaterialApp(
          key: ValueKey('${app.session?['user_id']}:${app.shopId}'),
          title: 'SoloOps',
          debugShowCheckedModeBanner: false,
          locale: const Locale('zh', 'CN'),
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
          theme: theme(Brightness.light),
          darkTheme: theme(Brightness.dark),
          home: app.loading
              ? const Scaffold(body: Center(child: CircularProgressIndicator()))
              : app.session == null
                  ? LoginPage(app)
                  : BusinessShell(app)));
}

class BusinessShell extends StatefulWidget {
  const BusinessShell(this.app, {super.key});
  final AppState app;
  @override
  State<BusinessShell> createState() => _BusinessShellState();
}

class _BusinessShellState extends State<BusinessShell> {
  int selected = 0;
  static const labels = ['首页', '待办', 'AI', '客服', '我的'];
  @override
  Widget build(BuildContext context) {
    final app = widget.app;
    final pages = <Widget>[
      WorkbenchPage(app),
      WorkbenchPage(app, tasksOnly: true),
      RecordListPage(app,
          path: '/agent/runs',
          title: 'AI 运营记录',
          empty: '还没有运营任务。',
          titleKeys: const ['reason'],
          detailKeys: const ['created_at', 'status']),
      RecordListPage(app,
          path: '/support/messages',
          title: '客服消息',
          empty: '导入消息报表后，可在这里查看客户的问题。',
          titleKeys: const ['body'],
          detailKeys: const ['order_id', 'sent_at']),
      SettingsPage(app)
    ];
    return Scaffold(
        appBar: AppBar(title: Text(labels[selected]), actions: [
          if (app.shops.isNotEmpty)
            SizedBox(
                width: 180,
                child: Padding(
                    padding: const EdgeInsets.only(right: 16),
                    child: ShopPicker(app)))
        ]),
        body: app.shopId == null && selected != 4
            ? PageBody(children: [
                const SectionTitle('准备你的经营空间'),
                const Text('先填写经营资料并创建店铺，再导入商品、订单等报表。'),
                const SizedBox(height: 24),
                FilledButton(
                    onPressed: () => setState(() => selected = 4),
                    child: const Text('设置店铺'))
              ])
            : pages[selected],
        bottomNavigationBar: NavigationBar(
            selectedIndex: selected,
            onDestinationSelected: (index) => setState(() => selected = index),
            destinations: const [
              NavigationDestination(
                  icon: Icon(Icons.home_outlined),
                  selectedIcon: Icon(Icons.home),
                  label: '首页'),
              NavigationDestination(icon: Icon(Icons.task_alt), label: '待办'),
              NavigationDestination(
                  icon: Icon(Icons.auto_awesome_outlined), label: 'AI'),
              NavigationDestination(
                  icon: Icon(Icons.chat_bubble_outline), label: '客服'),
              NavigationDestination(
                  icon: Icon(Icons.person_outline), label: '我的')
            ]));
  }
}
