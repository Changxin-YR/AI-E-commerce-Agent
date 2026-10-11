import 'dart:io';

import 'package:flutter/material.dart';

void main() => runApp(const SoloOpsApp());

class SoloOpsApp extends StatelessWidget {
  const SoloOpsApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'SoloOps · 工程验证',
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF315C52)),
          useMaterial3: true,
        ),
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

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    setState(() => lifecycle = state.name);
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
              const Text('M0-A · Android 与鸿蒙共享 Dart 启动页面'),
              const SizedBox(height: 24),
              Text('运行平台：${Platform.operatingSystem}'),
              Text('生命周期：$lifecycle'),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: () => Navigator.of(context).push<void>(
                  MaterialPageRoute(builder: (_) => const EnvironmentPage()),
                ),
                child: const Text('查看环境信息'),
              ),
            ],
          ),
        ),
      );
}

class EnvironmentPage extends StatelessWidget {
  const EnvironmentPage({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('环境信息')),
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: SelectableText('Dart：${Platform.version}\n'
                '系统：${Platform.operatingSystemVersion}\n'
                '本页面用于最小工程构建验证。'),
          ),
        ),
      );
}
