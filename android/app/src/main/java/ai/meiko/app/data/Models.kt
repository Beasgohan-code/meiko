package ai.meiko.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class AgentModeMeta(
    val id: String,
    val name: String,
    val description: String,
    val icon: String = "",
    @SerialName("max_steps") val maxSteps: Int = 20,
)

@Serializable
data class PersonaMeta(val id: String, val name: String, val tagline: String = "")

@Serializable
data class ProviderMeta(
    val id: String,
    @SerialName("display_name") val displayName: String,
    @SerialName("default_base_url") val defaultBaseUrl: String = "",
    @SerialName("default_model") val defaultModel: String = "",
    @SerialName("requires_key") val requiresKey: Boolean = true,
    @SerialName("free_tier") val freeTier: Boolean = false,
    @SerialName("key_help_url") val keyHelpUrl: String = "",
    val description: String = "",
)

@Serializable
data class ModelMeta(
    val id: String,
    @SerialName("display_name") val displayName: String,
    val family: String = "",
    val reasoning: Boolean = false,
    val vision: Boolean = false,
    @SerialName("context_window") val contextWindow: String = "",
    @SerialName("good_for") val goodFor: List<String> = emptyList(),
    val tag: String = "",
)

@Serializable
data class ConnectorMeta(
    val id: String,
    val name: String,
    val description: String = "",
    val enabled: Boolean = false,
    @SerialName("requires_key") val requiresKey: Boolean = false,
    val actions: List<String> = emptyList(),
)

@Serializable
data class SkillMeta(
    val id: String,
    val name: String,
    val description: String = "",
    val triggers: List<String> = emptyList(),
)

@Serializable
data class MemoryFact(val id: String, val fact: String, @SerialName("created_at") val createdAt: Double = 0.0)

@Serializable
data class ConversationSummary(
    val id: String,
    val title: String = "",
    val pinned: Int = 0,
    @SerialName("updated_at") val updatedAt: Double = 0.0,
)

@Serializable
data class ConversationMessageRow(val role: String, val content: String)

enum class PlanTaskStatus { PENDING, IN_PROGRESS, DONE }

data class PlanTask(val text: String, val status: PlanTaskStatus)

data class Citation(val url: String, val via: String)

data class ToolTrace(
    val id: String,
    val name: String,
    var arguments: String? = null,
    var result: String? = null,
    var done: Boolean = false,
)

enum class ChatRole { USER, ASSISTANT }

data class ChatMessage(
    val id: String,
    val role: ChatRole,
    var content: String = "",
    val tools: MutableList<ToolTrace> = mutableListOf(),
    var streaming: Boolean = false,
    var error: String? = null,
    var plan: MutableList<PlanTask> = mutableListOf(),
    var citations: MutableList<Citation> = mutableListOf(),
    var providerNotices: MutableList<String> = mutableListOf(),
    var generatedImages: MutableList<String> = mutableListOf(),
)
