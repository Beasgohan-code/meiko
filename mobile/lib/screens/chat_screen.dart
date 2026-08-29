import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../models/models.dart';
import '../providers/meiko_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/composer.dart';
import '../widgets/message_bubble.dart';
import '../widgets/meiko_orb.dart';
import 'settings_screen.dart';

const _modeIcons = {
  'chat': Icons.chat_bubble_outline,
  'research': Icons.search,
  'code': Icons.code,
  'autonomous': Icons.memory,
  'creative': Icons.image_outlined,
};

const _suggestions = [
  'Research the latest breakthroughs in fusion energy',
  'Write a Python script that batch-renames files and zip the result',
  'Generate an image of a cyberpunk city at sunset',
  'Explain transformers like I\'m five',
];

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _scrollController = ScrollController();

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _attachImage(MeikoProvider meiko) async {
    final picker = ImagePicker();
    final file = await picker.pickImage(source: ImageSource.gallery);
    if (file == null) return;
    final bytes = await File(file.path).readAsBytes();
    await meiko.api.uploadFile(meiko.sessionId, file.name, bytes, 'image/jpeg');
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Uploaded ${file.name}')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final meiko = context.watch<MeikoProvider>();
    _scrollToBottom();

    return Scaffold(
      drawer: _buildDrawer(meiko),
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Meiko Agent', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            Text(
              'Mode: ${meiko.modes.firstWhere((m) => m.id == meiko.mode, orElse: () => AgentModeMeta(id: meiko.mode, name: meiko.mode, description: '', icon: '', maxSteps: 0)).name}',
              style: const TextStyle(fontSize: 11, color: MeikoColors.text2),
            ),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Center(child: MeikoOrb(state: meiko.orbState, size: 34)),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: meiko.messages.isEmpty ? _buildHero(meiko) : _buildMessageList(meiko),
          ),
          Composer(
            onSend: (text) => meiko.sendMessage(text),
            onAttach: () => _attachImage(meiko),
            isStreaming: meiko.isStreaming,
            onStop: meiko.stopStreaming,
          ),
        ],
      ),
    );
  }

  Widget _buildHero(MeikoProvider meiko) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const MeikoOrb(state: OrbState.idle, size: 140),
            const SizedBox(height: 18),
            ShaderMask(
              shaderCallback: (bounds) => meikoGradient().createShader(bounds),
              child: const Text(
                "Hey, I'm Meiko.",
                style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Colors.white),
              ),
            ),
            const SizedBox(height: 8),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                "Your open, pluggable AI agent — research, code, create, and automate. "
                "Bring your own free API key and I'll get to work.",
                textAlign: TextAlign.center,
                style: TextStyle(color: MeikoColors.text1, fontSize: 13.5),
              ),
            ),
            const SizedBox(height: 20),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: _suggestions
                  .map((s) => ActionChip(
                        label: Text(s, style: const TextStyle(fontSize: 12)),
                        backgroundColor: MeikoColors.panel,
                        side: const BorderSide(color: MeikoColors.border),
                        onPressed: () => meiko.sendMessage(s),
                      ))
                  .toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMessageList(MeikoProvider meiko) {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      itemCount: meiko.messages.length,
      itemBuilder: (context, index) => MessageBubble(message: meiko.messages[index]),
    );
  }

  Widget _buildDrawer(MeikoProvider meiko) {
    return Drawer(
      backgroundColor: MeikoColors.bg1,
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: ShaderMask(
                shaderCallback: (bounds) => meikoGradient().createShader(bounds),
                child: const Text('Meiko', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white)),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: ElevatedButton.icon(
                onPressed: () {
                  meiko.newConversation();
                  Navigator.pop(context);
                },
                icon: const Icon(Icons.add, size: 18),
                label: const Text('New chat'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: MeikoColors.violet.withOpacity(0.15),
                  foregroundColor: Colors.white,
                  minimumSize: const Size.fromHeight(42),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text('AGENT MODE', style: TextStyle(fontSize: 11, color: MeikoColors.text2, letterSpacing: 1)),
            ),
            ...meiko.modes.map((m) => ListTile(
                  leading: Icon(_modeIcons[m.id] ?? Icons.auto_awesome, size: 18,
                      color: meiko.mode == m.id ? MeikoColors.violetSoft : MeikoColors.text2),
                  title: Text(m.name, style: TextStyle(fontSize: 13.5, color: meiko.mode == m.id ? Colors.white : MeikoColors.text1)),
                  subtitle: Text(m.description, style: const TextStyle(fontSize: 10.5, color: MeikoColors.text2)),
                  selected: meiko.mode == m.id,
                  selectedTileColor: MeikoColors.violet.withOpacity(0.1),
                  onTap: () {
                    meiko.setMode(m.id);
                    Navigator.pop(context);
                  },
                )),
            const SizedBox(height: 10),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text('PERSONA', style: TextStyle(fontSize: 11, color: MeikoColors.text2, letterSpacing: 1)),
            ),
            ...meiko.personas.map((p) => ListTile(
                  dense: true,
                  title: Text(p.name, style: TextStyle(fontSize: 13, color: meiko.personaId == p.id ? Colors.white : MeikoColors.text1)),
                  subtitle: Text(p.tagline, style: const TextStyle(fontSize: 10.5, color: MeikoColors.text2)),
                  selected: meiko.personaId == p.id,
                  selectedTileColor: MeikoColors.violet.withOpacity(0.1),
                  onTap: () {
                    meiko.setPersona(p.id);
                    Navigator.pop(context);
                  },
                )),
            const Spacer(),
            const Divider(color: MeikoColors.border),
            ListTile(
              leading: const Icon(Icons.settings, size: 18, color: MeikoColors.text1),
              title: const Text('Settings & Connectors', style: TextStyle(fontSize: 13.5)),
              onTap: () {
                Navigator.pop(context);
                Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen()));
              },
            ),
          ],
        ),
      ),
    );
  }
}
