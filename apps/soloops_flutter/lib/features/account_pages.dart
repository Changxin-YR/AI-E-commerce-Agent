import 'package:flutter/material.dart';
import '../core/app_state.dart';
import '../core/business_navigation.dart';
import '../ui/common.dart';

class LoginPage extends StatefulWidget {
  const LoginPage(this.app, {super.key});
  final AppState app;
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final form = GlobalKey<FormState>();
  late final address = TextEditingController(text: widget.app.api.baseUrl);
  final username = TextEditingController();
  final password = TextEditingController();
  bool busy = false;
  String? error;
  Future<void> login() async {
    if (!form.currentState!.validate()) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.app.login(address.text, username.text, password.text);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      password.clear();
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    address.dispose();
    username.dispose();
    password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      body: Center(
          child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 540),
              child: Form(
                  key: form,
                  child: PageBody(children: [
                    const SizedBox(height: 52),
                    Icon(Icons.eco_outlined,
                        size: 48, color: Theme.of(context).colorScheme.primary),
                    const SizedBox(height: 20),
                    Text('SoloOps',
                        style: Theme.of(context).textTheme.headlineLarge),
                    const SizedBox(height: 12),
                    const Text('把每天的经营事务，整理成下一步行动。'),
                    const SizedBox(height: 36),
                    FormInput('服务地址', address, type: TextInputType.url),
                    FormInput('账号', username),
                    FormInput('密码', password, secret: true),
                    if (error ?? widget.app.notice case final message?)
                      Notice(message),
                    FilledButton(
                        onPressed: busy ? null : login,
                        child: Text(busy ? '正在登录…' : '登录')),
                    const SizedBox(height: 20),
                    const Text('使用管理员创建的经营账号。登录后可创建店铺、导入报表并开始处理事务。')
                  ])))));
}

class SettingsPage extends StatefulWidget {
  const SettingsPage(this.app, {super.key});
  final AppState app;
  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  String? error;
  bool busy = false;
  Future<void> editProfile() async {
    try {
      final value = await widget.app.api.get('/profile');
      if (!mounted) return;
      await Navigator.of(context).push<void>(MaterialPageRoute(
          builder: (_) =>
              ProfileEditor(widget.app, value == null ? null : object(value))));
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> logout(bool all) async {
    if (!await confirmAction(context, all ? '退出所有设备' : '退出当前设备',
        all ? '当前账号在网页和各设备的登录都会失效。' : '安全凭据会从当前设备移除，下次使用需重新登录。')) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.app.logout(all: all);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => PageBody(children: [
        Text('${widget.app.session?['username'] ?? ''}',
            style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 8),
        Text(widget.app.api.baseUrl),
        if (error != null) Notice(error!),
        const SectionTitle('经营资料'),
        ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.person_outline),
            title: const Text('经营档案'),
            subtitle: const Text('市场、币种、语言和业务时区'),
            trailing: const Icon(Icons.chevron_right),
            onTap: editProfile),
        const SectionTitle('我的店铺'),
        for (final shop in widget.app.shops)
          RadioListTile<int>(
              value: shop['id'] as int,
              groupValue: widget.app.shopId,
              onChanged: (value) {
                if (value != null) widget.app.selectShop(value);
              },
              title: Text('${shop['name']}'),
              subtitle: Text(
                  '${shop['market']} · ${shop['currency']} · ${shop['timezone']}')),
        OutlinedButton.icon(
            onPressed: () => Navigator.of(context).push<void>(
                MaterialPageRoute(builder: (_) => ShopEditor(widget.app))),
            icon: const Icon(Icons.add),
            label: const Text('创建店铺')),
        const SectionTitle('业务工具'),
        for (final entry in const {
          '/imports': '数据导入',
          '/listings': 'Listing 文案',
          '/agent': 'AI 运营',
          '/support': '客服处理',
          '/inventory': '库存快照',
          '/analytics': '经营分析',
          '/overview': '跨店经营总览'
        }.entries)
          ListTile(
              title: Text(entry.value),
              trailing: const Icon(Icons.chevron_right),
              onTap: widget.app.shopId == null
                  ? null
                  : () => openBusinessPath(context, widget.app, entry.key)),
        const SectionTitle('登录与设备'),
        ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.logout),
            title: const Text('退出当前设备'),
            onTap: busy ? null : () => logout(false)),
        ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.devices),
            title: const Text('退出所有设备'),
            onTap: busy ? null : () => logout(true))
      ]);
}

const currencies = [
  'USD',
  'CNY',
  'EUR',
  'GBP',
  'JPY',
  'CAD',
  'AUD',
  'HKD',
  'SGD'
];
const zones = [
  'Asia/Shanghai',
  'America/New_York',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Berlin',
  'Asia/Tokyo',
  'UTC'
];

class ChoiceField extends StatelessWidget {
  const ChoiceField(this.label, this.value, this.choices, this.onChanged,
      {super.key});
  final String label;
  final String value;
  final Map<String, String> choices;
  final ValueChanged<String> onChanged;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: DropdownButtonFormField<String>(
          isExpanded: true,
          value: value,
          decoration: InputDecoration(labelText: label),
          items: choices.entries
              .map((e) => DropdownMenuItem(value: e.key, child: Text(e.value)))
              .toList(),
          onChanged: (value) {
            if (value != null) onChanged(value);
          }));
}

class ProfileEditor extends StatefulWidget {
  const ProfileEditor(this.app, this.profile, {super.key});
  final AppState app;
  final Json? profile;
  @override
  State<ProfileEditor> createState() => _ProfileEditorState();
}

class _ProfileEditorState extends State<ProfileEditor> {
  final form = GlobalKey<FormState>();
  late final fields = {
    for (final key in [
      'display_name',
      'target_market',
      'business_model',
      'category'
    ])
      key: TextEditingController(
          text:
              '${widget.profile?[key] ?? (key == 'target_market' ? 'US' : '')}')
  };
  late String currency = '${widget.profile?['currency'] ?? 'USD'}';
  late String timezone = '${widget.profile?['timezone'] ?? 'Asia/Shanghai'}';
  late String language = '${widget.profile?['language'] ?? 'zh-CN'}';
  bool busy = false;
  String? error;
  Future<void> save() async {
    if (!form.currentState!.validate()) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.app.api.put('/profile', {
        for (final e in fields.entries)
          e.key: e.key == 'target_market'
              ? e.value.text.trim().toUpperCase()
              : e.value.text.trim(),
        'currency': currency,
        'timezone': timezone,
        'language': language,
        'version': widget.profile?['version'] ?? 0
      });
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    for (final controller in fields.values) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('经营档案')),
      body: Form(
          key: form,
          child: PageBody(children: [
            FormInput('经营名称', fields['display_name']!),
            FormInput('目标市场（如 US）', fields['target_market']!),
            FormInput('经营模式', fields['business_model']!),
            FormInput('主营类目', fields['category']!),
            ChoiceField('常用币种', currency, {for (final c in currencies) c: c},
                (v) => setState(() => currency = v)),
            ChoiceField('业务时区', timezone, {for (final z in zones) z: z},
                (v) => setState(() => timezone = v)),
            ChoiceField(
                '默认语言',
                language,
                const {
                  'zh-CN': '简体中文',
                  'en': '英语',
                  'ja': '日语',
                  'de': '德语',
                  'fr': '法语',
                  'es': '西班牙语'
                },
                (v) => setState(() => language = v)),
            if (error != null) Notice(error!),
            FilledButton(
                onPressed: busy ? null : save,
                child: Text(busy ? '保存中…' : '保存经营资料'))
          ])));
}

class ShopEditor extends StatefulWidget {
  const ShopEditor(this.app, {super.key});
  final AppState app;
  @override
  State<ShopEditor> createState() => _ShopEditorState();
}

class _ShopEditorState extends State<ShopEditor> {
  final form = GlobalKey<FormState>();
  final name = TextEditingController();
  final code = TextEditingController();
  final market = TextEditingController(text: 'US');
  String currency = 'USD', timezone = 'Asia/Shanghai', platform = 'manual';
  bool busy = false;
  String? error;
  Future<void> save() async {
    if (!form.currentState!.validate()) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final shop = object(await widget.app.api.post('/shops', {
        'code': code.text.trim().toLowerCase(),
        'name': name.text.trim(),
        'market': market.text.trim().toUpperCase(),
        'platform': platform,
        'currency': currency,
        'timezone': timezone
      }));
      await widget.app.loadShops();
      await widget.app.selectShop(shop['id'] as int);
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    name.dispose();
    code.dispose();
    market.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('创建店铺')),
      body: Form(
          key: form,
          child: PageBody(children: [
            FormInput('店铺名称', name),
            FormInput('店铺标识（小写字母、数字或下划线）', code),
            FormInput('市场（如 US）', market),
            ChoiceField(
                '平台',
                platform,
                const {
                  'manual': '手工经营',
                  'shopify': 'Shopify',
                  'amazon': 'Amazon',
                  'other': '其他'
                },
                (v) => setState(() => platform = v)),
            ChoiceField('币种', currency, {for (final c in currencies) c: c},
                (v) => setState(() => currency = v)),
            ChoiceField('时区', timezone, {for (final z in zones) z: z},
                (v) => setState(() => timezone = v)),
            if (error != null) Notice(error!),
            FilledButton(
                onPressed: busy ? null : save,
                child: Text(busy ? '创建中…' : '创建店铺'))
          ])));
}
