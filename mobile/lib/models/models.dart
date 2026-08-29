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

enum PlanTaskStatus { pending, inProgress, done }

class PlanTask {
  final String text;
  final PlanTaskStatus status;

  PlanTask({required this.text, required this.status});

  factory PlanTask.fromJson(Map<String, dynamic> json) {
    final raw = json['status'] as String? ?? 'pending';
    final status = raw == 'done'
        ? PlanTaskStatus.done
        : raw == 'in_progress'
            ? PlanTaskStatus.inProgress
            : PlanTaskStatus.pending;
    return PlanTask(text: json['text'] as String? ?? '', status: status);
  }
}

class Citation {
  final String url;
  final String via;
  Citation({required this.url, required this.via});

  factory Citation.fromJson(Map<String, dynamic> json) =>
      Citation(url: json['url'] as String? ?? '', via: json['via'] as String? ?? '');
}

class SkillMeta {
  final String id;
  final String name;
  final String description;
  final List<String> triggers;

  SkillMeta({required this.id, required this.name, required this.description, required this.triggers});

  factory SkillMeta.fromJson(Map<String, dynamic> json) => SkillMeta(
        id: json['id'] as String,
        name: json['name'] as String,
        description: json['description'] as String? ?? '',
        triggers: (json['triggers'] as List? ?? []).map((e) => e.toString()).toList(),
      );
}

class ModelMeta {
  final String id;
  final String displayName;
  final String family;
  final bool reasoning;
  final bool vision;
  final String contextWindow;
  final List<String> goodFor;
  final String tag;

  ModelMeta({
    required this.id,
    required this.displayName,
    required this.family,
    required this.reasoning,
    required this.vision,
    required this.contextWindow,
    required this.goodFor,
    required this.tag,
  });

  factory ModelMeta.fromJson(Map<String, dynamic> json) => ModelMeta(
        id: json['id'] as String,
        displayName: json['display_name'] as String? ?? json['id'] as String,
        family: json['family'] as String? ?? '',
        reasoning: json['reasoning'] as bool? ?? false,
        vision: json['vision'] as bool? ?? false,
        contextWindow: json['context_window'] as String? ?? '',
        goodFor: (json['good_for'] as List? ?? []).map((e) => e.toString()).toList(),
        tag: json['tag'] as String? ?? '',
      );
}

class MemoryFact {
  final String id;
  final String fact;

  MemoryFact({required this.id, required this.fact});

  factory MemoryFact.fromJson(Map<String, dynamic> json) =>
      MemoryFact(id: json['id'] as String, fact: json['fact'] as String? ?? '');
}

class ConversationSummary {
  final String id;
  final String title;
  final bool pinned;
  final double updatedAt;

  ConversationSummary({required this.id, required this.title, required this.pinned, required this.updatedAt});

  factory ConversationSummary.fromJson(Map<String, dynamic> json) => ConversationSummary(
        id: json['id'] as String,
        title: (json['title'] as String?)?.isNotEmpty == true ? json['title'] as String : 'Untitled',
        pinned: (json['pinned'] as int? ?? 0) == 1,
        updatedAt: (json['updated_at'] as num?)?.toDouble() ?? 0,
      );
}

enum ChatRole { user, assistant }

class ChatMessage {
  final String id;
  final ChatRole role;
  String content;
  final List<ToolTrace> tools;
  bool streaming;
  String? error;
  List<PlanTask> plan;
  List<Citation> citations;
  List<String> providerNotices;

  ChatMessage({
    required this.id,
    required this.role,
    this.content = '',
    List<ToolTrace>? tools,
    this.streaming = false,
    this.error,
    List<PlanTask>? plan,
    List<Citation>? citations,
    List<String>? providerNotices,
  })  : tools = tools ?? [],
        plan = plan ?? [],
        citations = citations ?? [],
        providerNotices = providerNotices ?? [];
}
