import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

import '../models/models.dart';
import '../services/meiko_api.dart';

enum OrbState { idle, thinking, tool, speaking }

/// Central app state: connection config, chat history, streaming logic.
class MeikoProvider extends ChangeNotifier {
  static const _uuid = Uuid();

  late MeikoApi api;
  String backendUrl;
  String userId;
  String sessionId = _uuid.v4();
  String? conversationId;

  String mode = 'autonomous';
  String personaId = 'default';
  String? provider;
  String? model;

  List<AgentModeMeta> modes = [];
  List<PersonaMeta> personas = [];
  List<ProviderMeta> providers = [];
  List<ConnectorMeta> connectors = [];

  final List<ChatMessage> messages = [];
  bool isStreaming = false;
  OrbState orbState = OrbState.idle;

  http.Client? _activeClient;

  MeikoProvider({required this.backendUrl, required this.userId}) {
    api = MeikoApi(baseUrl: backendUrl);
  }

  static Future<MeikoProvider> create() async {
    final prefs = await SharedPreferences.getInstance();
    var userId = prefs.getString('meiko_user_id');
    if (userId == null) {
      userId = 'user-${_uuid.v4().substring(0, 8)}';
      await prefs.setString('meiko_user_id', userId);
    }
    final backendUrl = prefs.getString('meiko_backend_url') ?? 'http://10.0.2.2:8000';
    final p = MeikoProvider(backendUrl: backendUrl, userId: userId);
    await p.loadMeta();
    return p;
  }

  Future<void> updateBackendUrl(String url) async {
    backendUrl = url;
    api = MeikoApi(baseUrl: url);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('meiko_backend_url', url);
    notifyListeners();
    await loadMeta();
  }

  Future<void> loadMeta() async {
    try {
      modes = await api.fetchModes();
      personas = await api.fetchPersonas();
      providers = await api.fetchProviders();
      connectors = await api.fetchConnectors();
      notifyListeners();
    } catch (_) {
      // backend may be unreachable yet; UI shows a connection hint
    }
  }

  void setMode(String m) {
    mode = m;
    notifyListeners();
  }

  void setPersona(String p) {
    personaId = p;
    notifyListeners();
  }

  void setProvider(String? p, String? m) {
    provider = p;
    model = m;
    notifyListeners();
  }

  Future<void> toggleConnector(ConnectorMeta c) async {
    await api.toggleConnector(c.id, !c.enabled);
    c.enabled = !c.enabled;
    notifyListeners();
  }

  void newConversation() {
    conversationId = null;
    sessionId = _uuid.v4();
    messages.clear();
    notifyListeners();
  }

  Future<List<ConversationSummary>> loadHistory({String? query}) async {
    try {
      if (query != null && query.trim().isNotEmpty) {
        return await api.searchConversations(userId, query.trim());
      }
      return await api.listConversations(userId);
    } catch (_) {
      return [];
    }
  }

  Future<void> openConversation(String id) async {
    try {
      final rows = await api.getConversationMessages(id);
      messages.clear();
      for (final r in rows) {
        final role = r['role'] as String?;
        if (role != 'user' && role != 'assistant') continue;
        messages.add(ChatMessage(
          id: _uuid.v4(),
          role: role == 'user' ? ChatRole.user : ChatRole.assistant,
          content: r['content'] as String? ?? '',
        ));
      }
      conversationId = id;
      sessionId = id;
      notifyListeners();
    } catch (_) {
      // ignore — leave current state as-is
    }
  }

  Future<void> renameConversation(String id, String title) async {
    await api.renameConversation(id, title);
  }

  Future<void> deleteConversation(String id) async {
    await api.deleteConversation(id);
    if (id == conversationId) newConversation();
  }

  Future<void> pinConversation(String id, bool pinned) async {
    await api.pinConversation(id, pinned);
  }

  Future<List<SkillMeta>> loadSkills() async {
    try {
      return await api.fetchSkills();
    } catch (_) {
      return [];
    }
  }

  Future<void> sendMessage(String text) async {
    final userMsg = ChatMessage(id: _uuid.v4(), role: ChatRole.user, content: text);
    messages.add(userMsg);

    final assistantMsg = ChatMessage(id: _uuid.v4(), role: ChatRole.assistant, streaming: true);
    messages.add(assistantMsg);

    isStreaming = true;
    orbState = OrbState.thinking;
    notifyListeners();

    _activeClient = http.Client();
    String finalText = '';
    int toolCounter = 0;

    try {
      await api.streamChat(
        userId: userId,
        message: text,
        mode: mode,
        conversationId: conversationId,
        sessionId: sessionId,
        provider: provider,
        model: model,
        personaId: personaId,
        client: _activeClient,
        onEvent: (event) {
          final type = event['type'];
          switch (type) {
            case 'token':
              orbState = OrbState.speaking;
              assistantMsg.content += (event['text'] ?? '') as String;
              notifyListeners();
              break;
            case 'tool_call':
              orbState = OrbState.tool;
              final id = event['id']?.toString() ?? 'tool-${toolCounter++}';
              assistantMsg.tools.add(ToolTrace(id: id, name: event['name'] as String? ?? 'tool'));
              notifyListeners();
              break;
            case 'tool_result':
              orbState = OrbState.thinking;
              final id = event['id']?.toString();
              final result = event['result'] as String?;
              final trace = assistantMsg.tools.where((t) => t.id == id).toList();
              if (trace.isNotEmpty) {
                trace.first.result = result;
                trace.first.status = ToolStatus.done;
              }
              notifyListeners();
              break;
            case 'plan_update':
              final tasks = (event['tasks'] as List? ?? []).map((e) => PlanTask.fromJson(e as Map<String, dynamic>)).toList();
              assistantMsg.plan = tasks;
              notifyListeners();
              break;
            case 'citations':
              final sources = (event['sources'] as List? ?? []).map((e) => Citation.fromJson(e as Map<String, dynamic>)).toList();
              assistantMsg.citations = sources;
              notifyListeners();
              break;
            case 'provider_switch':
              final from = event['from'] as String? ?? '?';
              final to = event['to'] as String? ?? '?';
              assistantMsg.providerNotices.add('Switched from $from to $to after an error — continuing automatically.');
              notifyListeners();
              break;
            case 'final':
              finalText = event['text'] as String? ?? '';
              break;
            case 'error':
              assistantMsg.error = event['message'] as String?;
              break;
            case 'conversation_created':
              final cid = event['conversation_id'] as String?;
              if (cid != null && conversationId == null) conversationId = cid;
              break;
            case 'done':
              final cid = event['conversation_id'] as String?;
              if (cid != null && conversationId == null) conversationId = cid;
              break;
          }
        },
      );
    } catch (e) {
      assistantMsg.error = 'Connection error: $e';
    } finally {
      assistantMsg.streaming = false;
      if (finalText.isNotEmpty) assistantMsg.content = finalText;
      isStreaming = false;
      orbState = OrbState.idle;
      _activeClient = null;
      notifyListeners();
    }
  }

  void stopStreaming() {
    _activeClient?.close();
    _activeClient = null;
    isStreaming = false;
    orbState = OrbState.idle;
    if (messages.isNotEmpty && messages.last.role == ChatRole.assistant) {
      messages.last.streaming = false;
    }
    notifyListeners();
  }
}
