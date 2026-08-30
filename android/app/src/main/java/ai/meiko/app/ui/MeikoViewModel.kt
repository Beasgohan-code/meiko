package ai.meiko.app.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import ai.meiko.app.BuildConfig
import ai.meiko.app.data.AgentModeMeta
import ai.meiko.app.data.ChatMessage
import ai.meiko.app.data.ChatRole
import ai.meiko.app.data.Citation
import ai.meiko.app.data.ConnectorMeta
import ai.meiko.app.data.ConversationSummary
import ai.meiko.app.data.MeikoApi
import ai.meiko.app.data.MeikoPrefs
import ai.meiko.app.data.MemoryFact
import ai.meiko.app.data.ModelMeta
import ai.meiko.app.data.PersonaMeta
import ai.meiko.app.data.PlanTask
import ai.meiko.app.data.PlanTaskStatus
import ai.meiko.app.data.ProviderMeta
import ai.meiko.app.data.SkillMeta
import ai.meiko.app.data.ToolTrace
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive
import java.util.UUID

enum class OrbState { IDLE, THINKING, SPEAKING, TOOL }

data class MeikoUiState(
    val messages: List<ChatMessage> = emptyList(),
    val isStreaming: Boolean = false,
    val mode: String = "autonomous",
    val personaId: String = "default",
    val provider: String? = null,
    val model: String? = null,
    val uiLanguage: String = "en",
    val backendUrl: String = "",
    val orbState: OrbState = OrbState.IDLE,
    val modes: List<AgentModeMeta> = emptyList(),
    val personas: List<PersonaMeta> = emptyList(),
    val providers: List<ProviderMeta> = emptyList(),
    val connectors: List<ConnectorMeta> = emptyList(),
    val skills: List<SkillMeta> = emptyList(),
    val models: List<ModelMeta> = emptyList(),
    val memories: List<MemoryFact> = emptyList(),
    val conversations: List<ConversationSummary> = emptyList(),
    val conversationId: String? = null,
    val darkTheme: Boolean = true,
    val githubAuthEnabled: Boolean = false,
    val authUsername: String? = null,
    val authAvatarUrl: String? = null,
    val showAuthScreen: Boolean = false,
)

class MeikoViewModel(application: Application) : AndroidViewModel(application) {

    private val prefs = MeikoPrefs(application)
    private lateinit var api: MeikoApi
    private var userId: String = ""
    private var sessionId: String = UUID.randomUUID().toString()
    private var streamJob: Job? = null

    private val _state = MutableStateFlow(MeikoUiState())
    val state: StateFlow<MeikoUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            val backendUrl = prefs.backendUrl(BuildConfig.DEFAULT_BACKEND_URL)
            val apiKey = prefs.apiKey()
            api = MeikoApi(backendUrl, apiKey)
            userId = prefs.userId()
            val mode = prefs.mode()
            val personaId = prefs.personaId()
            val provider = prefs.provider()
            val model = prefs.model()
            val uiLanguage = prefs.uiLanguage()
            val theme = prefs.theme()
            val authUsername = prefs.authUsername()
            val authAvatarUrl = prefs.authAvatarUrl()
            _state.value = _state.value.copy(
                backendUrl = backendUrl,
                mode = mode,
                personaId = personaId,
                provider = provider,
                model = model,
                uiLanguage = uiLanguage,
                darkTheme = theme != "light",
                authUsername = authUsername,
                authAvatarUrl = authAvatarUrl,
            )
            refreshCatalogs()
            runCatching { api.fetchAuthConfig() }.onSuccess { cfg ->
                _state.value = _state.value.copy(githubAuthEnabled = cfg.github_enabled)
            }
        }
    }

    // ---------- Optional GitHub sign-in ----------
    fun githubLoginUrl(): String = api.githubLoginUrl()

    fun setAuthScreenVisible(visible: Boolean) {
        _state.value = _state.value.copy(showAuthScreen = visible)
    }

    /** Called by AuthScreen once it intercepts the meiko://auth#token=...
     * redirect. Resolves the profile, persists the session, and switches
     * the app's active user_id to the account so data follows it. */
    fun onGithubToken(token: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(showAuthScreen = false)
            runCatching { api.fetchMe(token) }.onSuccess { user ->
                prefs.setAuthSession(token, user.user_id, user.username, user.avatar_url)
                userId = user.user_id
                _state.value = _state.value.copy(
                    authUsername = user.username,
                    authAvatarUrl = user.avatar_url,
                    conversationId = null,
                    messages = emptyList(),
                )
                refreshCatalogs()
            }
        }
    }

    fun signOut() {
        viewModelScope.launch {
            prefs.clearAuthSession()
            _state.value = _state.value.copy(authUsername = null, authAvatarUrl = null)
        }
    }

    /** Light-mode toggle (Claude/Open-Design-inspired, matching the web app's theme switch). */
    fun toggleTheme() {
        val next = !_state.value.darkTheme
        _state.value = _state.value.copy(darkTheme = next)
        viewModelScope.launch { prefs.setTheme(if (next) "dark" else "light") }
    }

    private fun refreshCatalogs() {
        viewModelScope.launch {
            runCatching { api.fetchModes() }.onSuccess { _state.value = _state.value.copy(modes = it) }
            runCatching { api.fetchPersonas() }.onSuccess { _state.value = _state.value.copy(personas = it) }
            runCatching { api.fetchProviders() }.onSuccess { _state.value = _state.value.copy(providers = it) }
            runCatching { api.fetchConnectors() }.onSuccess { _state.value = _state.value.copy(connectors = it) }
            runCatching { api.fetchSkills() }.onSuccess { _state.value = _state.value.copy(skills = it) }
            refreshModels()
            refreshMemories()
        }
    }

    fun refreshModels() {
        viewModelScope.launch {
            val providerId = _state.value.provider ?: "nvidia"
            runCatching { api.fetchModels(providerId) }.onSuccess { _state.value = _state.value.copy(models = it) }
        }
    }

    fun refreshMemories() {
        viewModelScope.launch {
            runCatching { api.fetchMemories(userId) }.onSuccess { _state.value = _state.value.copy(memories = it) }
        }
    }

    fun refreshConversations(query: String? = null) {
        viewModelScope.launch {
            val result = runCatching {
                if (!query.isNullOrBlank()) api.searchConversations(userId, query) else api.listConversations(userId)
            }.getOrDefault(emptyList())
            _state.value = _state.value.copy(conversations = result)
        }
    }

    fun setMode(mode: String) {
        _state.value = _state.value.copy(mode = mode)
        viewModelScope.launch { prefs.setMode(mode) }
    }

    fun setPersona(personaId: String) {
        _state.value = _state.value.copy(personaId = personaId)
        viewModelScope.launch { prefs.setPersonaId(personaId) }
    }

    fun setProvider(provider: String?, model: String?) {
        _state.value = _state.value.copy(provider = provider, model = model)
        viewModelScope.launch {
            provider?.let { prefs.setProvider(it) }
            prefs.setModel(model)
        }
        refreshModels()
    }

    fun setUiLanguage(lang: String) {
        _state.value = _state.value.copy(uiLanguage = lang)
        viewModelScope.launch { prefs.setUiLanguage(lang) }
    }

    fun updateBackendUrl(url: String) {
        api.updateBaseUrl(url)
        _state.value = _state.value.copy(backendUrl = url)
        viewModelScope.launch { prefs.setBackendUrl(url) }
        refreshCatalogs()
    }

    fun updateApiKey(key: String) {
        api.updateApiKey(key)
        viewModelScope.launch { prefs.setApiKey(key) }
    }

    suspend fun saveSettings(provider: String?, model: String?, persona: String?, apiKeys: Map<String, String>?, uiLanguage: String?) {
        api.updateUserSettings(userId, provider, model, persona, apiKeys, uiLanguage)
    }

    suspend fun getUserSettingsRaw(): JsonObject = api.getUserSettings(userId)

    fun toggleConnector(connector: ConnectorMeta) {
        viewModelScope.launch {
            runCatching { api.toggleConnector(connector.id, !connector.enabled) }
            runCatching { api.fetchConnectors() }.onSuccess { _state.value = _state.value.copy(connectors = it) }
        }
    }

    fun deleteMemory(id: String) {
        viewModelScope.launch {
            runCatching { api.deleteMemory(id) }
            refreshMemories()
        }
    }

    fun clearAllMemories() {
        viewModelScope.launch {
            runCatching { api.clearMemories(userId) }
            refreshMemories()
        }
    }

    private fun refreshSkills() {
        viewModelScope.launch {
            runCatching { api.fetchSkills() }.onSuccess { _state.value = _state.value.copy(skills = it) }
        }
    }

    suspend fun fetchSkillDetail(skillId: String) = api.fetchSkillDetail(skillId)

    /** Returns an error message on failure, or null on success — lets the
     * "Add a skill" dialog show why saving failed (e.g. empty body). */
    suspend fun saveSkill(
        name: String,
        description: String,
        triggers: List<String>,
        body: String,
        existingSkillId: String?,
    ): String? {
        val draft = ai.meiko.app.data.SkillDraft(name, description, triggers, body, existingSkillId)
        return try {
            if (existingSkillId != null) api.updateSkill(existingSkillId, draft) else api.createSkill(draft)
            refreshSkills()
            null
        } catch (e: Exception) {
            e.message ?: "Failed to save skill"
        }
    }

    fun deleteSkill(skillId: String) {
        viewModelScope.launch {
            runCatching { api.deleteSkill(skillId) }
            refreshSkills()
        }
    }

    fun newConversation() {
        sessionId = UUID.randomUUID().toString()
        _state.value = _state.value.copy(messages = emptyList(), conversationId = null)
    }

    fun openConversation(id: String) {
        viewModelScope.launch {
            val rows = runCatching { api.getConversationMessages(id) }.getOrDefault(emptyList())
            val msgs = rows.filter { it.role == "user" || it.role == "assistant" }.map {
                ChatMessage(
                    id = UUID.randomUUID().toString(),
                    role = if (it.role == "user") ChatRole.USER else ChatRole.ASSISTANT,
                    content = it.content,
                )
            }
            sessionId = id
            _state.value = _state.value.copy(messages = msgs, conversationId = id)
        }
    }

    fun renameConversation(id: String, title: String) {
        viewModelScope.launch {
            runCatching { api.renameConversation(id, title) }
            refreshConversations()
        }
    }

    fun deleteConversation(id: String) {
        viewModelScope.launch {
            runCatching { api.deleteConversation(id) }
            if (id == _state.value.conversationId) newConversation()
            refreshConversations()
        }
    }

    fun pinConversation(id: String, pinned: Boolean) {
        viewModelScope.launch {
            runCatching { api.pinConversation(id, pinned) }
            refreshConversations()
        }
    }

    fun downloadUrl(filename: String): String = api.downloadUrl(sessionId, filename)

    /** Upload an attachment (paperclip / share-sheet) into this session's workspace,
     * then post a small confirmation message — mirrors the web app's onAttach flow. */
    fun uploadFile(fileName: String, bytes: ByteArray, mimeType: String) {
        val userMsgId = UUID.randomUUID().toString()
        _state.value = _state.value.copy(
            messages = _state.value.messages + ChatMessage(id = userMsgId, role = ChatRole.USER, content = "📎 Uploaded: $fileName"),
        )
        viewModelScope.launch {
            val ok = api.uploadFile(sessionId, fileName, bytes, mimeType)
            val replyId = UUID.randomUUID().toString()
            val reply = if (ok) "Got your file **$fileName** — ask me anything about it!" else "Sorry, that upload failed — please try again."
            _state.value = _state.value.copy(
                messages = _state.value.messages + ChatMessage(id = replyId, role = ChatRole.ASSISTANT, content = reply),
            )
        }
    }

    fun stopStreaming() {
        streamJob?.cancel()
        streamJob = null
        _state.value = _state.value.copy(isStreaming = false, orbState = OrbState.IDLE)
    }

    fun sendMessage(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return

        val userMsg = ChatMessage(id = UUID.randomUUID().toString(), role = ChatRole.USER, content = trimmed)
        val assistantMsg = ChatMessage(id = UUID.randomUUID().toString(), role = ChatRole.ASSISTANT, streaming = true)
        _state.value = _state.value.copy(
            messages = _state.value.messages + userMsg + assistantMsg,
            isStreaming = true,
            orbState = OrbState.THINKING,
        )

        val s = _state.value
        var finalText = ""
        var newConversationId: String? = null

        streamJob = viewModelScope.launch {
            api.streamChat(
                userId = userId,
                message = trimmed,
                mode = s.mode,
                conversationId = s.conversationId,
                sessionId = sessionId,
                personaId = s.personaId,
                provider = s.provider,
                model = s.model,
                uiLanguage = if (s.uiLanguage != "en") s.uiLanguage else null,
            ).catch { e ->
                updateAssistant(assistantMsg.id) { it.copy(error = e.message ?: "Connection error", streaming = false) }
            }.collect { event ->
                when (event.type) {
                    "thinking" -> {
                        val delta = event.data["text"]?.jsonPrimitive?.content ?: ""
                        _state.value = _state.value.copy(orbState = OrbState.THINKING)
                        updateAssistant(assistantMsg.id) {
                            it.thinking += delta
                            it.isThinking = true
                            it
                        }
                    }
                    "token" -> {
                        val delta = event.data["text"]?.jsonPrimitive?.content ?: ""
                        _state.value = _state.value.copy(orbState = OrbState.SPEAKING)
                        updateAssistant(assistantMsg.id) {
                            it.isThinking = false
                            it.copy(content = it.content + delta)
                        }
                    }
                    "tool_call" -> {
                        _state.value = _state.value.copy(orbState = OrbState.TOOL)
                        val name = event.data["name"]?.jsonPrimitive?.content ?: "tool"
                        val id = event.data["id"]?.jsonPrimitive?.content ?: UUID.randomUUID().toString()
                        updateAssistant(assistantMsg.id) {
                            it.tools.add(ToolTrace(id = id, name = name))
                            it.isThinking = false
                            it
                        }
                    }
                    "tool_result" -> {
                        val id = event.data["id"]?.jsonPrimitive?.content
                        val result = event.data["result"]?.jsonPrimitive?.content ?: ""
                        val name = event.data["name"]?.jsonPrimitive?.content
                        updateAssistant(assistantMsg.id) {
                            it.tools.find { t -> t.id == id }?.let { t ->
                                t.result = result
                                t.done = true
                            }
                            if (name == "generate_image" && result.startsWith("images/")) {
                                it.generatedImages.add(result.removePrefix("images/"))
                            }
                            it
                        }
                        _state.value = _state.value.copy(orbState = OrbState.THINKING)
                    }
                    "plan_update" -> {
                        val tasks = (event.data["tasks"] as? JsonArray)?.mapNotNull { el ->
                            val obj = el as? JsonObject ?: return@mapNotNull null
                            val statusRaw = obj["status"]?.jsonPrimitive?.content ?: "pending"
                            val status = when (statusRaw) {
                                "done" -> PlanTaskStatus.DONE
                                "in_progress" -> PlanTaskStatus.IN_PROGRESS
                                else -> PlanTaskStatus.PENDING
                            }
                            PlanTask(obj["text"]?.jsonPrimitive?.content ?: "", status)
                        } ?: emptyList()
                        updateAssistant(assistantMsg.id) {
                            it.plan.clear()
                            it.plan.addAll(tasks)
                            it
                        }
                    }
                    "citations" -> {
                        val sources = (event.data["sources"] as? JsonArray)?.mapNotNull { el ->
                            val obj = el as? JsonObject ?: return@mapNotNull null
                            Citation(obj["url"]?.jsonPrimitive?.content ?: "", obj["via"]?.jsonPrimitive?.content ?: "")
                        } ?: emptyList()
                        updateAssistant(assistantMsg.id) {
                            it.citations.clear()
                            it.citations.addAll(sources)
                            it
                        }
                    }
                    "provider_switch" -> {
                        val from = event.data["from"]?.jsonPrimitive?.content ?: "?"
                        val to = event.data["to"]?.jsonPrimitive?.content ?: "?"
                        updateAssistant(assistantMsg.id) {
                            it.providerNotices.add("Switched from $from to $to after an error — continuing automatically.")
                            it
                        }
                    }
                    "final" -> {
                        finalText = event.data["text"]?.jsonPrimitive?.content ?: ""
                        val stats = event.data["stats"] as? JsonObject
                        if (stats != null) {
                            val info = RunInfo(
                                provider = stats["provider"]?.jsonPrimitive?.contentOrNull,
                                model = stats["model"]?.jsonPrimitive?.contentOrNull,
                                steps = stats["steps"]?.jsonPrimitive?.intOrNull,
                                toolCalls = stats["tool_calls"]?.jsonPrimitive?.intOrNull,
                                elapsedSeconds = stats["elapsed_seconds"]?.jsonPrimitive?.doubleOrNull,
                                providerSwitches = stats["provider_switches"]?.jsonPrimitive?.intOrNull,
                                tokensPerSecond = stats["tokens_per_second"]?.jsonPrimitive?.doubleOrNull,
                            )
                            updateAssistant(assistantMsg.id) { it.copy(runInfo = info, isThinking = false) }
                        }
                    }
                    "error" -> {
                        val msg = event.data["message"]?.jsonPrimitive?.content ?: "Something went wrong"
                        updateAssistant(assistantMsg.id) { it.copy(error = msg) }
                    }
                    "conversation_created", "done" -> {
                        val cid = event.data["conversation_id"]?.jsonPrimitive?.content
                        if (cid != null && newConversationId == null) newConversationId = cid
                    }
                }
            }

            updateAssistant(assistantMsg.id) {
                it.copy(content = if (finalText.isNotEmpty()) finalText else it.content, streaming = false)
            }
            if (newConversationId != null && _state.value.conversationId == null) {
                _state.value = _state.value.copy(conversationId = newConversationId)
            }
            _state.value = _state.value.copy(isStreaming = false, orbState = OrbState.IDLE)
        }
    }

    private fun updateAssistant(id: String, transform: (ChatMessage) -> ChatMessage) {
        _state.value = _state.value.copy(
            messages = _state.value.messages.map { if (it.id == id) transform(it) else it }
        )
    }
}
