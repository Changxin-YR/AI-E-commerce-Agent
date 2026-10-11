import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'runtime_probe.dart';
import 'closure_probe.dart';
import 'package:flutter/foundation.dart';

void main() => runApp(const SoloOpsApp());

class SoloOpsApp extends StatelessWidget {
  const SoloOpsApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'SoloOps · 工程验证',
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
        locale: const Locale('zh', 'CN'),
        theme: ThemeData(
            colorScheme:
                ColorScheme.fromSeed(seedColor: const Color(0xFF315C52)),
            useMaterial3: true),
        darkTheme: ThemeData(
            colorScheme: ColorScheme.fromSeed(
                seedColor: const Color(0xFF315C52),
                brightness: Brightness.dark),
            useMaterial3: true),
        home: const StartupPage(),
      );
}

class StartupPage extends StatefulWidget {
  const StartupPage({super.key});
  @override
  State<StartupPage> createState() => _StartupPageState();
}

class _StartupPageState extends State<StartupPage> with WidgetsBindingObserver {
  String lifecycle = '尚未收到生命周期事件';
  Map<String, String> results = {};
  bool running = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    recordProbe('startup', Platform.operatingSystem);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    setState(() => lifecycle = state.name);
    recordProbe('lifecycle', state.name);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('SoloOps')),
        body: SafeArea(
            child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Text('三端工程验证', style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 16),
            const Text('M0-B · Android 与鸿蒙共享 Dart 验证页面'),
            const SizedBox(height: 24),
            Text('运行平台：${Platform.operatingSystem}'),
            Text('生命周期：$lifecycle'),
            Text('主题：${Theme.of(context).brightness.name}'),
            const SizedBox(height: 24),
            FilledButton(
                onPressed: () {
                  recordProbe('navigation', 'environment');
                  Navigator.of(context)
                      .push<void>(MaterialPageRoute(
                          builder: (_) => const EnvironmentPage()))
                      .then((_) {
                    recordProbe('navigation', 'startup');
                  });
                },
                child: const Text('查看环境信息')),
            const SizedBox(height: 12),
            FilledButton(
                onPressed: running
                    ? null
                    : () async {
                        setState(() => running = true);
                        final value = await runRuntimeProbe();
                        if (mounted) {
                          setState(() {
                            results = value;
                            running = false;
                          });
                        }
                      },
                child: Text(running ? '验证中…' : '运行合成诊断')),
            if (kDebugMode)
              FilledButton(
                  onPressed: () => Navigator.of(context).push<void>(
                      MaterialPageRoute(builder: (_) => const ClosurePage())),
                  child: const Text('M0 技术验收')),
            const Text('仅写入合成剪贴板文本和临时文件；不登录账号。'),
            for (final item in results.entries)
              Text('${item.key}: ${item.value}'),
          ],
        )),
      );
}

class EnvironmentPage extends StatelessWidget {
  const EnvironmentPage({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('环境信息')),
        body: SafeArea(
            child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            SelectableText('Dart：${Platform.version}\n'
                '系统：${Platform.operatingSystemVersion}\n'
                '窗口：${MediaQuery.sizeOf(context)}\n'
                '方向：${MediaQuery.orientationOf(context).name}\n'
                '字体比例：${MediaQuery.textScalerOf(context).scale(1)}\n'
                '主题：${Theme.of(context).brightness.name}\n'
                '本页面用于模拟器兼容性验证。')
          ],
        )),
      );
}
