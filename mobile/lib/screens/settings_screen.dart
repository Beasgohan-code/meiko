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
    _tabController = TabController(length: 5, vsync: this);
    final meiko = context.read<MeikoProvider>();
    _urlController = TextEditingController(text: meiko.backendUrl);
    _personaController = TextEditingController();
    _githubTokenController = TextEditingController();
    _activeProvider = meiko.provider ?? 'nvidia';
    _activeModel = meiko.model;
    meiko.api.getUserSettings(meiko.userId).then((s) {
      if (s['persona'] != null) _personaController.text = s['persona'];
      if (s['provider'] != null) setState(() => _activeProvider = s['provider']);
      if (s['model'] != null && (s['model'] as String).isNotEmpty) setState(() => _activeModel = s['model']);
      if (s['ui_language'] != null) setState(() => _replyLanguage = s['ui_language']);
    });
    meiko.loadSkills().then((s) => setState(() => _skills = s));
    _loadModels();
    _loadMemories();
  }

  List<SkillMeta> _skills = [];
  List<ModelMeta> _models = [];
  List<MemoryFact> _memories = [];
  String? _activeModel;
  String _replyLanguage = 'en';
  late TextEditingController _githubTokenController;

  static const List<Map<String, String>> _languages = [
    {'code': 'en', 'flag': '🇬🇧', 'label': 'English'},
    {'code': 'es', 'flag': '🇪🇸', 'label': 'Español'},
    {'code': 'fr', 'flag': '🇫🇷', 'label': 'Français'},
    {'code': 'de', 'flag': '🇩🇪', 'label': 'Deutsch'},
    {'code': 'hi', 'flag': '🇮🇳', 'label': 'हिन्दी'},
    {'code': 'pt', 'flag': '🇵🇹', 'label': 'Português'},
    {'code': 'ar', 'flag': '🇸🇦', 'label': 'العربية'},
    {'code': 'ja', 'flag': '🇯🇵', 'label': '日本語'},
    {'code': 'zh', 'flag': '🇨🇳', 'label': '中文'},
    {'code': 'ru', 'flag': '🇷🇺', 'label': 'Русский'},
    {'code': 'ko', 'flag': '🇰🇷', 'label': '한국어'},
    {'code': 'id', 'flag': '🇮🇩', 'label': 'Bahasa Indonesia'},
  ];

  Future<void> _loadModels() async {
    final meiko = context.read<MeikoProvider>();
    final models = await meiko.api.fetchModels(_activeProvider ?? 'nvidia');
    if (mounted) setState(() => _models = models);
  }

  Future<void> _loadMemories() async {
    final meiko = context.read<MeikoProvider>();
    try {
      final memories = await meiko.api.fetchMemories(meiko.userId);
      if (mounted) setState(() => _memories = memories);
    } catch (_) {
      // ignore — leave memories empty
    }
  }

  @override
  Widget build(BuildContext context) {
    final meiko = context.watch<MeikoProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: const [
            Tab(text: 'Providers'),
            Tab(text: 'Connectors'),
            Tab(text: 'Skills'),
            Tab(text: 'Memory'),
            Tab(text: 'Server & Persona'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildProvidersTab(meiko),
          _buildConnectorsTab(meiko),
          _buildSkillsTab(meiko),
          _buildMemoryTab(meiko),
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
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Pick a model — $_activeProvider', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                const SizedBox(height: 4),
                const Text(
                  'NVIDIA alone offers 20+ free curated models (DeepSeek, Kimi, GLM, Qwen, Llama, Mistral, Nemotron…).',
                  style: TextStyle(fontSize: 11.5, color: MeikoColors.text2),
                ),
                const SizedBox(height: 8),
                if (_models.isEmpty) const Text('Loading models…', style: TextStyle(color: MeikoColors.text2)),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _models.map((m) {
                    final selected = _activeModel == m.id;
                    return GestureDetector(
                      onTap: () => setState(() => _activeModel = m.id),
                      child: Container(
                        width: 160,
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: selected ? MeikoColors.violet.withOpacity(0.15) : Colors.white.withOpacity(0.02),
                          border: Border.all(color: selected ? MeikoColors.violet : MeikoColors.border),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(m.displayName, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
                            const SizedBox(height: 4),
                            Wrap(
                              spacing: 4,
                              children: [
                                if (m.tag.isNotEmpty) _miniBadge(m.tag),
                                if (m.reasoning) _miniBadge('reasoning'),
                                if (m.vision) _miniBadge('vision'),
                                if (m.contextWindow.isNotEmpty) _miniBadge(m.contextWindow),
                              ],
                            ),
                          ],
                        ),
                      ),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Reply language', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                const SizedBox(height: 4),
                const Text(
                  'Meiko will reply in this language regardless of your device language.',
                  style: TextStyle(fontSize: 11.5, color: MeikoColors.text2),
                ),
                const SizedBox(height: 8),
                DropdownButton<String>(
                  value: _replyLanguage,
                  isExpanded: true,
                  dropdownColor: MeikoColors.panel,
                  items: _languages
                      .map((l) => DropdownMenuItem(value: l['code'], child: Text('${l['flag']} ${l['label']}')))
                      .toList(),
                  onChanged: (v) => setState(() => _replyLanguage = v ?? 'en'),
                ),
              ],
            ),
          ),
        ),
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
              model: _activeModel,
              apiKeys: keys,
              uiLanguage: _replyLanguage,
            );
            meiko.setProvider(_activeProvider, _activeModel);
            setState(() => _saveStatus = 'Saved ✓');
          },
          style: ElevatedButton.styleFrom(backgroundColor: MeikoColors.violet, minimumSize: const Size.fromHeight(46)),
          child: Text(_saveStatus.isEmpty ? 'Save provider settings' : _saveStatus),
        ),
      ],
    );
  }

  Widget _miniBadge(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(color: Colors.white.withOpacity(0.06), borderRadius: BorderRadius.circular(999)),
      child: Text(text, style: const TextStyle(fontSize: 9, color: MeikoColors.text2)),
    );
  }

  Widget _buildMemoryTab(MeikoProvider meiko) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text(
          "Meiko saves durable facts about you across sessions (preferences, ongoing projects, etc.). "
          "Review or clear what it knows here.",
          style: TextStyle(color: MeikoColors.text2, fontSize: 12.5),
        ),
        const SizedBox(height: 10),
        if (_memories.isEmpty) const Text("I don't have any long-term memories about you yet.", style: TextStyle(color: MeikoColors.text2)),
        ..._memories.map((m) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                dense: true,
                title: Text(m.fact, style: const TextStyle(fontSize: 12.5)),
                trailing: IconButton(
                  icon: const Icon(Icons.delete_outline, size: 18, color: MeikoColors.text2),
                  onPressed: () async {
                    await meiko.api.deleteMemory(m.id);
                    _loadMemories();
                  },
                ),
              ),
            )),
        if (_memories.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: OutlinedButton(
              onPressed: () async {
                await meiko.api.clearMemories(meiko.userId);
                _loadMemories();
              },
              style: OutlinedButton.styleFrom(foregroundColor: MeikoColors.danger, minimumSize: const Size.fromHeight(44)),
              child: const Text('Clear all'),
            ),
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
                  onChanged: (v) {
                    setState(() {
                      _activeProvider = v;
                      _activeModel = null;
                    });
                    _loadModels();
                  },
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
