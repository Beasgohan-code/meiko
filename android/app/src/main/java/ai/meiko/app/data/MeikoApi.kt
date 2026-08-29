package ai.meiko.app.data

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.cio.CIO
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.HttpRequestBuilder
import io.ktor.client.request.delete
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.parameter
import io.ktor.client.request.patch
import io.ktor.client.request.post
import io.ktor.client.request.preparePost
import io.ktor.client.request.setBody
import io.ktor.client.statement.HttpStatement
import io.ktor.client.statement.bodyAsChannel
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import io.ktor.utils.io.readUTF8Line
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** Structured SSE event from /api/chat/stream, mirroring the harness's AgentEvent. */
data class AgentEvent(val type: String, val data: JsonObject)

class MeikoApi(private var baseUrl: String, private var apiKey: String? = null) {

    private val json = Json { ignoreUnknownKeys = true; isLenient = true }

    private val client = HttpClient(CIO) {
        install(ContentNegotiation) { json(json) }
        install(HttpTimeout) {
            requestTimeoutMillis = 180_000
            connectTimeoutMillis = 20_000
        }
    }

    fun updateBaseUrl(url: String) {
        baseUrl = url.trimEnd('/')
    }

    fun updateApiKey(key: String?) {
        apiKey = key
    }

    private fun HttpRequestBuilder.withAuth() {
        apiKey?.let { if (it.isNotBlank()) header("X-API-Key", it) }
    }

    suspend fun fetchModes(): List<AgentModeMeta> = client.get("$baseUrl/api/modes").body()
    suspend fun fetchPersonas(): List<PersonaMeta> = client.get("$baseUrl/api/personas").body()
    suspend fun fetchProviders(): List<ProviderMeta> = client.get("$baseUrl/api/providers").body()
    suspend fun fetchModels(provider: String): List<ModelMeta> =
        client.get("$baseUrl/api/models") { parameter("provider", provider) }.body()
    suspend fun fetchSkills(): List<SkillMeta> = client.get("$baseUrl/api/skills").body()

    suspend fun fetchConnectors(): List<ConnectorMeta> =
        client.get("$baseUrl/api/connectors") { withAuth() }.body()

    suspend fun toggleConnector(id: String, enabled: Boolean) {
        client.post("$baseUrl/api/connectors/$id/toggle") {
            withAuth()
            contentType(ContentType.Application.Json)
            setBody(buildJsonObject { put("enabled", enabled) })
        }
    }

    suspend fun getUserSettings(userId: String): JsonObject =
        client.get("$baseUrl/api/settings") { parameter("user_id", userId) }.body()

    suspend fun updateUserSettings(
        userId: String,
        provider: String? = null,
        model: String? = null,
        persona: String? = null,
        apiKeys: Map<String, String>? = null,
        uiLanguage: String? = null,
    ) {
        client.post("$baseUrl/api/settings") {
            withAuth()
            contentType(ContentType.Application.Json)
            setBody(buildJsonObject {
                put("user_id", userId)
                provider?.let { put("provider", it) }
                model?.let { put("model", it) }
                persona?.let { put("persona", it) }
                uiLanguage?.let { put("ui_language", it) }
                apiKeys?.let { keys ->
                    put("api_keys", buildJsonObject { keys.forEach { (k, v) -> put(k, v) } })
                }
            })
        }
    }

    suspend fun fetchMemories(userId: String): List<MemoryFact> =
        client.get("$baseUrl/api/memories") {
            withAuth()
            parameter("user_id", userId)
        }.body()

    suspend fun deleteMemory(memoryId: String) {
        client.delete("$baseUrl/api/memories/$memoryId") { withAuth() }
    }

    suspend fun clearMemories(userId: String) {
        client.delete("$baseUrl/api/memories") {
            withAuth()
            parameter("user_id", userId)
        }
    }

    suspend fun listConversations(userId: String): List<ConversationSummary> =
        client.get("$baseUrl/api/conversations") {
            withAuth()
            parameter("user_id", userId)
        }.body()

    suspend fun searchConversations(userId: String, query: String): List<ConversationSummary> =
        client.get("$baseUrl/api/conversations/search") {
            withAuth()
            parameter("user_id", userId)
            parameter("q", query)
        }.body()

    suspend fun getConversationMessages(conversationId: String): List<ConversationMessageRow> =
        client.get("$baseUrl/api/conversations/$conversationId/messages") { withAuth() }.body()

    suspend fun renameConversation(conversationId: String, title: String) {
        client.patch("$baseUrl/api/conversations/$conversationId") {
            withAuth()
            contentType(ContentType.Application.Json)
            setBody(buildJsonObject { put("title", title) })
        }
    }

    suspend fun deleteConversation(conversationId: String) {
        client.delete("$baseUrl/api/conversations/$conversationId") { withAuth() }
    }

    suspend fun pinConversation(conversationId: String, pinned: Boolean) {
        client.post("$baseUrl/api/conversations/$conversationId/pin") {
            withAuth()
            parameter("pinned", pinned)
        }
    }

    fun downloadUrl(sessionId: String, filename: String): String = "$baseUrl/api/download/$sessionId/$filename"

    /**
     * Streams a chat turn via SSE (POST + chunked response), emitting one [AgentEvent] per
     * "data: {...}" line — mirrors the web/Flutter/Telegram clients' handling of plan_update,
     * tool_call, tool_result, citations, provider_switch, token, final, error, done.
     */
    fun streamChat(
        userId: String,
        message: String,
        mode: String,
        conversationId: String?,
        sessionId: String?,
        personaId: String?,
        provider: String?,
        model: String?,
        uiLanguage: String?,
    ): Flow<AgentEvent> = flow {
        val requestBody = buildJsonObject {
            put("user_id", userId)
            put("message", message)
            put("mode", mode)
            conversationId?.let { put("conversation_id", it) }
            sessionId?.let { put("session_id", it) }
            personaId?.let { put("persona_id", it) }
            provider?.let { put("provider", it) }
            model?.let { put("model", it) }
            uiLanguage?.let { put("ui_language", it) }
        }

        val statement: HttpStatement = client.preparePost("$baseUrl/api/chat/stream") {
            withAuth()
            contentType(ContentType.Application.Json)
            setBody(requestBody)
        }

        statement.execute { response ->
            val channel = response.bodyAsChannel()
            while (!channel.isClosedForRead) {
                val line = channel.readUTF8Line() ?: break
                if (!line.startsWith("data:")) continue
                val payload = line.removePrefix("data:").trim()
                if (payload.isEmpty()) continue
                try {
                    val obj = json.parseToJsonElement(payload) as? JsonObject ?: continue
                    val type = (obj["type"] as? JsonElement)?.jsonPrimitive?.content ?: continue
                    emit(AgentEvent(type, obj))
                } catch (_: Exception) {
                    // skip malformed lines
                }
            }
        }
    }

    suspend fun getUsage(userId: String, days: Int = 30): JsonObject =
        client.get("$baseUrl/api/usage") {
            withAuth()
            parameter("user_id", userId)
            parameter("days", days)
        }.body()
}
