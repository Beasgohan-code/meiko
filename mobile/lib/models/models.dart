/// Meiko App — core data models shared across the app.
library models;

class AgentModeMeta {
  final String id;
  final String name;
  final String description;
  final String icon;
  final int maxSteps;

  AgentModeMeta({
    required this.id,
    required this.name,
    required this.description,
    required this.icon,
    required this.maxSteps,
  });

  factory AgentModeMeta.fromJson(Map<String, dynamic> json) => AgentModeMeta(
        id: json['id'] as String,
        name: json['name'] as String,
        description: json['description'] as String,
        icon: json['icon'] as String,
        maxSteps: json['max_steps'] as int,
      );
}

class PersonaMeta {
  final String id;
  final String name;
  final String tagline;

  PersonaMeta({required this.id, required this.name, required this.tagline});

  factory PersonaMeta.fromJson(Map<String, dynamic> json) => PersonaMeta(
        id: json['id'] as String,
        name: json['name'] as String,
        tagline: json['tagline'] as String,
      );
}

class ProviderMeta {
  final String id;
  final String displayName;
  final String defaultBaseUrl;
  final String defaultModel;
  final bool requiresKey;
  final bool freeTier;
  final String keyHelpUrl;
  final String description;

  ProviderMeta({
    required this.id,
    required this.displayName,
    required this.defaultBaseUrl,
    required this.defaultModel,
    required this.requiresKey,
    required this.freeTier,
    required this.keyHelpUrl,
    required this.description,
  });

  factory ProviderMeta.fromJson(Map<String, dynamic> json) => ProviderMeta(
        id: json['id'] as String,
        displayName: json['display_name'] as String,
        defaultBaseUrl: json['default_base_url'] as String,
        defaultModel: json['default_model'] as String,
        requiresKey: json['requires_key'] as bool,
        freeTier: json['free_tier'] as bool,
        keyHelpUrl: json['key_help_url'] as String,
        description: json['description'] as String,
      );
}

class ConnectorMeta {
  final String id;
  final String name;
  final String description;
  bool enabled;
  final bool requiresKey;
  final List<String> actions;

  ConnectorMeta({
    required this.id,
    required this.name,
    required this.description,
    required this.enabled,
    required this.requiresKey,
    required this.actions,
  });

  factory ConnectorMeta.fromJson(Map<String, dynamic> json) => ConnectorMeta(
        id: json['id'] as String,
        name: json['name'] as String,
        description: json['description'] as String,
        enabled: json['enabled'] as bool,
        requiresKey: json['requires_key'] as bool,
        actions: (json['actions'] as List).map((e) => e.toString()).toList(),
      );
}

enum ToolStatus { calling, done }

class ToolTrace {
  final String id;
  final String name;
  String? result;
  ToolStatus status;

  ToolTrace({required this.id, required this.name, this.result, this.status = ToolStatus.calling});
}

enum ChatRole { user, assistant }

class ChatMessage {
  final String id;
  final ChatRole role;
  String content;
  final List<ToolTrace> tools;
  bool streaming;
  String? error;

  ChatMessage({
    required this.id,
    required this.role,
    this.content = '',
    List<ToolTrace>? tools,
    this.streaming = false,
    this.error,
  }) : tools = tools ?? [];
}
