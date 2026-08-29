import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/models.dart';
import '../providers/meiko_provider.dart';
import '../theme/app_theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final Map<String, TextEditingController> _keyControllers = {};
  late TextEditingController _urlController;
  late TextEditingController _personaController;
  String? _activeProvider;
  String _saveStatus = '';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    final meiko = context.read<MeikoProvider>();
    _urlController = TextEditingController(text: meiko.backendUrl);
    _personaController = TextEditingController();
    _githubTokenController = TextEditingController();
    _activeProvider = meiko.provider ?? 'nvidia';
    meiko.api.getUserSettings(meiko.userId).then((s) {
      if (s['persona'] != null) _personaController.text = s['persona'];
      if (s['provider'] != null) setState(() => _activeProvider = s['provider']);
    });
    meiko.loadSkills().then((s) => setState(() => _skills = s));
  }

  List<SkillMeta> _skills = [];
  late TextEditingController _githubTokenController;

  @override
  Widget build(BuildContext context) {
    final meiko = context.watch<MeikoProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: const [Tab(text: 'Providers'), Tab(text: 'Connectors'), Tab(text: 'Skills'), Tab(text: 'Server & Persona')],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildProvidersTab(meiko),
          _buildConnectorsTab(meiko),
          _buildSkillsTab(meiko),
          _buildServerTab(meiko),
        ],
      ),
    );
  }

  Widget _buildProvidersTab(MeikoProvider meiko) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text(
          'Pick your model provider and paste a free API key. NVIDIA NIM, Gemini, OpenRouter, Groq, '
          'Cerebras, Hugging Face and Mistral all offer generous free tiers.',
          style: TextStyle(color: MeikoColors.text2, fontSize: 12.5),
        ),
        const SizedBox(height: 14),
        ...meiko.providers.map((p) => _providerCard(p)),
        const SizedBox(height: 10),
        ElevatedButton(
          onPressed: () async {
            setState(() => _saveStatus = 'Saving…');
            final keys = <String, String>{};
            _keyControllers.forEach((k, v) {
              if (v.text.isNotEmpty) keys[k] = v.text;
            });
            await meiko.api.updateUserSettings(
              userId: meiko.userId,
              provider: _activeProvider,
              apiKeys: keys,
            );
            meiko.setProvider(_activeProvider, null);
            setState(() => _saveStatus = 'Saved ✓');
          },
          style: ElevatedButton.styleFrom(backgroundColor: MeikoColors.violet, minimumSize: const Size.fromHeight(46)),
          child: Text(_saveStatus.isEmpty ? 'Save provider settings' : _saveStatus),
        ),
      ],
    );
  }

  Widget _providerCard(ProviderMeta p) {
    _keyControllers.putIfAbsent(p.id, () => TextEditingController());
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Radio<String>(
                  value: p.id,
                  groupValue: _activeProvider,
                  activeColor: MeikoColors.violet,
                  onChanged: (v) => setState(() => _activeProvider = v),
                ),
                Expanded(child: Text(p.displayName, style: const TextStyle(fontWeight: FontWeight.w600))),
                if (p.freeTier)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(color: MeikoColors.success.withOpacity(0.15), borderRadius: BorderRadius.circular(999)),
                    child: const Text('FREE', style: TextStyle(fontSize: 10, color: MeikoColors.success, fontWeight: FontWeight.bold)),
                  ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.only(left: 40, bottom: 6),
              child: Text(p.description, style: const TextStyle(fontSize: 11.5, color: MeikoColors.text2)),
            ),
            if (p.requiresKey)
              Padding(
                padding: const EdgeInsets.only(left: 40),
                child: TextField(
                  controller: _keyControllers[p.id],
                  obscureText: true,
                  decoration: InputDecoration(hintText: '${p.displayName} API key', isDense: true),
                ),
              ),
            Padding(
              padding: const EdgeInsets.only(left: 40, top: 6),
              child: GestureDetector(
                onTap: () => launchUrl(Uri.parse(p.keyHelpUrl), mode: LaunchMode.externalApplication),
                child: const Text('Get a free API key →', style: TextStyle(color: MeikoColors.cyan, fontSize: 11.5)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConnectorsTab(MeikoProvider meiko) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text(
          'Connectors give Meiko extra tools (like Claude Connectors / MCP). Toggle them on/off.',
          style: TextStyle(color: MeikoColors.text2, fontSize: 12.5),
        ),
        const SizedBox(height: 10),
        Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('GitHub (read + write)', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                const SizedBox(height: 4),
                const Text(
                  'Add a Personal Access Token (repo scope) to let Meiko read files, commit changes, open PRs, and create issues in your repos.',
                  style: TextStyle(fontSize: 11.5, color: MeikoColors.text2),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _githubTokenController,
                  obscureText: true,
                  decoration: const InputDecoration(hintText: 'ghp_… personal access token'),
                ),
                const SizedBox(height: 10),
                ElevatedButton(
                  onPressed: () async {
                    await meiko.api.updateUserSettings(userId: meiko.userId, apiKeys: {'github': _githubTokenController.text.trim()});
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('GitHub token saved')));
                    }
                  },
                  style: ElevatedButton.styleFrom(backgroundColor: MeikoColors.violet),
                  child: const Text('Save GitHub token'),
                ),
              ],
            ),
          ),
        ),
        ...meiko.connectors.map((c) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: SwitchListTile(
                activeColor: MeikoColors.violet,
                title: Text(c.name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                subtitle: Text(c.description, style: const TextStyle(fontSize: 11.5, color: MeikoColors.text2)),
                value: c.enabled,
                onChanged: (_) => setState(() => meiko.toggleConnector(c)),
              ),
            )),
      ],
    );
  }

  Widget _buildSkillsTab(MeikoProvider meiko) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text(
          'Skills are reusable playbooks Meiko loads on demand for specialized tasks. Meiko decides when to use one automatically.',
          style: TextStyle(color: MeikoColors.text2, fontSize: 12.5),
        ),
        const SizedBox(height: 10),
        if (_skills.isEmpty) const Text('No skills installed yet.', style: TextStyle(color: MeikoColors.text2)),
        ..._skills.map((s) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(s.name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                    const SizedBox(height: 4),
                    Text(s.description, style: const TextStyle(fontSize: 12, color: MeikoColors.text1)),
                    if (s.triggers.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text('Triggers on: ${s.triggers.join(', ')}', style: const TextStyle(fontSize: 11, color: MeikoColors.text2)),
                    ],
                  ],
                ),
              ),
            )),
      ],
    );
  }

  Widget _buildServerTab(MeikoProvider meiko) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Meiko backend URL', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
        const SizedBox(height: 6),
        TextField(
          controller: _urlController,
          decoration: const InputDecoration(hintText: 'https://your-meiko-backend.example.com'),
        ),
        const SizedBox(height: 6),
        const Text(
          'Use http://10.0.2.2:8000 for Android emulator pointing at localhost, or your deployed backend URL.',
          style: TextStyle(fontSize: 11, color: MeikoColors.text2),
        ),
        const SizedBox(height: 16),
        ElevatedButton(
          onPressed: () => meiko.updateBackendUrl(_urlController.text.trim()),
          style: ElevatedButton.styleFrom(backgroundColor: MeikoColors.violet),
          child: const Text('Save & Reconnect'),
        ),
        const Divider(height: 40, color: MeikoColors.border),
        const Text('Custom persona instructions', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
        const SizedBox(height: 6),
        TextField(
          controller: _personaController,
          maxLines: 5,
          decoration: const InputDecoration(hintText: 'e.g. Always be extra concise and use bullet points.'),
        ),
        const SizedBox(height: 10),
        ElevatedButton(
          onPressed: () async {
            await meiko.api.updateUserSettings(userId: meiko.userId, persona: _personaController.text);
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Persona saved')));
          },
          style: ElevatedButton.styleFrom(backgroundColor: MeikoColors.violet),
          child: const Text('Save persona'),
        ),
      ],
    );
  }
}
