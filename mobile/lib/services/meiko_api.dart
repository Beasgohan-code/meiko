import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/models.dart';

/// Meiko App — API client for the FastAPI backend.
/// Handles REST calls plus a manually-parsed SSE stream for chat.
class MeikoApi {
  final String baseUrl;
  final String? apiKey;

  MeikoApi({required this.baseUrl, this.apiKey});

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (apiKey != null && apiKey!.isNotEmpty) 'X-API-Key': apiKey!,
      };

  Uri _u(String path) => Uri.parse('$baseUrl$path');

  Future<List<ProviderMeta>> fetchProviders() async {
    final res = await http.get(_u('/api/providers'));
    final list = jsonDecode(res.body) as List;
    return list.map((e) => ProviderMeta.fromJson(e)).toList();
  }

  Future<List<AgentModeMeta>> fetchModes() async {
    final res = await http.get(_u('/api/modes'));
    final list = jsonDecode(res.body) as List;
    return list.map((e) => AgentModeMeta.fromJson(e)).toList();
  }

  Future<List<PersonaMeta>> fetchPersonas() async {
    final res = await http.get(_u('/api/personas'));
    final list = jsonDecode(res.body) as List;
    return list.map((e) => PersonaMeta.fromJson(e)).toList();
  }

  Future<List<ConnectorMeta>> fetchConnectors() async {
    final res = await http.get(_u('/api/connectors'));
    final list = jsonDecode(res.body) as List;
    return list.map((e) => ConnectorMeta.fromJson(e)).toList();
  }

  Future<void> toggleConnector(String id, bool enabled) async {
    await http.post(_u('/api/connectors/$id/toggle'),
        headers: _headers, body: jsonEncode({'enabled': enabled}));
  }

  Future<List<SkillMeta>> fetchSkills() async {
    final res = await http.get(_u('/api/skills'));
    final list = jsonDecode(res.body) as List;
    return list.map((e) => SkillMeta.fromJson(e)).toList();
  }

  Future<List<ConversationSummary>> listConversations(String userId) async {
    final res = await http.get(_u('/api/conversations?user_id=$userId'), headers: _headers);
    final list = jsonDecode(res.body) as List;
    return list.map((e) => ConversationSummary.fromJson(e)).toList();
  }

  Future<List<ConversationSummary>> searchConversations(String userId, String query) async {
    final res = await http.get(
      _u('/api/conversations/search?user_id=${Uri.encodeQueryComponent(userId)}&q=${Uri.encodeQueryComponent(query)}'),
      headers: _headers,
    );
    final list = jsonDecode(res.body) as List;
    return list.map((e) => ConversationSummary.fromJson(e)).toList();
  }

  Future<List<Map<String, dynamic>>> getConversationMessages(String conversationId) async {
    final res = await http.get(_u('/api/conversations/$conversationId/messages'), headers: _headers);
    final list = jsonDecode(res.body) as List;
    return list.cast<Map<String, dynamic>>();
  }

  Future<void> renameConversation(String conversationId, String title) async {
    await http.patch(_u('/api/conversations/$conversationId'), headers: _headers, body: jsonEncode({'title': title}));
  }

  Future<void> deleteConversation(String conversationId) async {
    await http.delete(_u('/api/conversations/$conversationId'), headers: _headers);
  }

  Future<void> pinConversation(String conversationId, bool pinned) async {
    await http.post(_u('/api/conversations/$conversationId/pin?pinned=$pinned'), headers: _headers);
  }

  Future<Map<String, dynamic>> getUserSettings(String userId) async {
    final res = await http.get(_u('/api/settings?user_id=$userId'));
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<void> updateUserSettings({
    required String userId,
    String? provider,
    String? model,
    String? persona,
    Map<String, String>? apiKeys,
    String? uiLanguage,
  }) async {
    await http.post(
      _u('/api/settings'),
      headers: _headers,
      body: jsonEncode({
        'user_id': userId,
        if (provider != null) 'provider': provider,
        if (model != null) 'model': model,
        if (persona != null) 'persona': persona,
        if (apiKeys != null) 'api_keys': apiKeys,
        if (uiLanguage != null) 'ui_language': uiLanguage,
      }),
    );
  }

  Future<List<ModelMeta>> fetchModels(String provider) async {
    final res = await http.get(_u('/api/models?provider=$provider'));
    final list = jsonDecode(res.body) as List;
    return list.map((e) => ModelMeta.fromJson(e)).toList();
  }

  Future<List<MemoryFact>> fetchMemories(String userId) async {
    final res = await http.get(_u('/api/memories?user_id=$userId'), headers: _headers);
    final list = jsonDecode(res.body) as List;
    return list.map((e) => MemoryFact.fromJson(e)).toList();
  }

  Future<void> deleteMemory(String memoryId) async {
    await http.delete(_u('/api/memories/$memoryId'), headers: _headers);
  }

  Future<void> clearMemories(String userId) async {
    await http.delete(_u('/api/memories?user_id=$userId'), headers: _headers);
  }

  Future<Map<String, dynamic>> uploadFile(String sessionId, String filename, List<int> bytes, String mime) async {
    final uri = _u('/api/upload?session_id=$sessionId');
    final request = http.MultipartRequest('POST', uri);
    request.files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
    final streamedResponse = await request.send();
    final res = await http.Response.fromStream(streamedResponse);
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  String downloadUrl(String sessionId, String filename) => '$baseUrl/api/download/$sessionId/$filename';

  /// Streams a chat turn via SSE. Each parsed JSON event is delivered
  /// through [onEvent]. Cancel by cancelling the returned StreamSubscription
  /// or by closing [client] the caller passes in (for abort support).
  Future<void> streamChat({
    required String userId,
    required String message,
    required String mode,
    String? conversationId,
    String? sessionId,
    String? provider,
    String? model,
    String? personaId,
    required void Function(Map<String, dynamic> event) onEvent,
    http.Client? client,
  }) async {
    final c = client ?? http.Client();
    final request = http.Request('POST', _u('/api/chat/stream'));
    request.headers.addAll(_headers);
    request.body = jsonEncode({
      'user_id': userId,
      'message': message,
      'mode': mode,
      'conversation_id': conversationId,
      'session_id': sessionId,
      'provider': provider,
      'model': model,
      'persona_id': personaId,
    });

    final streamedResponse = await c.send(request);
    final stream = streamedResponse.stream.transform(utf8.decoder);

    String buffer = '';
    await for (final chunk in stream) {
      buffer += chunk;
      final parts = buffer.split('\n\n');
      buffer = parts.removeLast();
      for (final part in parts) {
        final line = part.trim();
        if (!line.startsWith('data:')) continue;
        final data = line.substring(5).trim();
        if (data.isEmpty) continue;
        try {
          onEvent(jsonDecode(data) as Map<String, dynamic>);
        } catch (_) {
          // ignore malformed chunk
        }
      }
    }
    if (client == null) c.close();
  }
}
