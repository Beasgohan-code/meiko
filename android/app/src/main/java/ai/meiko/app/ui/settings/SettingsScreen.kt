package ai.meiko.app.ui.settings

import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.RemoveRedEye
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch
import ai.meiko.app.data.ProviderMeta
import ai.meiko.app.ui.MeikoViewModel
import ai.meiko.app.ui.theme.MeikoColors

private val LANGUAGES = listOf(
    "en" to "English", "es" to "Español", "hi" to "हिन्दी", "fr" to "Français",
    "de" to "Deutsch", "ja" to "日本語", "zh" to "中文", "ar" to "العربية",
    "pt" to "Português", "ru" to "Русский", "ml" to "മലയാളം", "ko" to "한국어",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(viewModel: MeikoViewModel, onBack: () -> Unit) {
    val state by viewModel.state.collectAsState()
    val scope = rememberCoroutineScope()
    var tab by rememberSaveable { mutableStateOf(0) }
    var selectedProvider by remember(state.provider) { mutableStateOf(state.provider ?: "nvidia") }
    var selectedModel by remember(state.model) { mutableStateOf(state.model) }
    var selectedPersona by remember(state.personaId) { mutableStateOf(state.personaId) }
    var selectedLanguage by remember(state.uiLanguage) { mutableStateOf(state.uiLanguage) }
    var apiKeyInput by remember { mutableStateOf("") }
    var saveMessage by remember { mutableStateOf<String?>(null) }

    val tabs = if (state.githubAuthEnabled) {
        listOf("Providers", "Models", "Persona", "Memory", "Skills", "Account")
    } else {
        listOf("Providers", "Models", "Persona", "Memory", "Skills")
    }

    Scaffold(
        containerColor = MeikoColors.Bg0,
        topBar = {
            TopAppBar(
                title = { Text("Settings", color = MeikoColors.Text0, fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, contentDescription = "Back", tint = MeikoColors.Text1) }
                },
                colors = androidx.compose.material3.TopAppBarDefaults.topAppBarColors(containerColor = MeikoColors.Bg1),
            )
        },
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxWidth()) {
            TabRow(selectedTabIndex = tab, containerColor = MeikoColors.Bg1, contentColor = MeikoColors.Violet) {
                tabs.forEachIndexed { i, label ->
                    Tab(selected = tab == i, onClick = { tab = i }, text = { Text(label, fontSize = 12.sp) })
                }
            }

            Column(modifier = Modifier.padding(16.dp).verticalScroll(rememberScrollState())) {
                when (tab) {
                    0 -> ProvidersTab(
                        providers = state.providers,
                        selectedProvider = selectedProvider,
                        onSelectProvider = {
                            selectedProvider = it
                            selectedModel = null
                            viewModel.setProvider(it, null)
                        },
                        apiKeyInput = apiKeyInput,
                        onApiKeyChange = { apiKeyInput = it },
                    )
                    1 -> ModelsTab(
                        models = state.models,
                        selectedModel = selectedModel,
                        onSelect = { selectedModel = it },
                    )
                    2 -> PersonaTab(
                        personas = state.personas,
                        selected = selectedPersona,
                        onSelect = { selectedPersona = it },
                        languages = LANGUAGES,
                        selectedLanguage = selectedLanguage,
                        onSelectLanguage = { selectedLanguage = it; viewModel.setUiLanguage(it) },
                    )
                    3 -> MemoryTab(
                        memories = state.memories,
                        onDelete = { viewModel.deleteMemory(it) },
                        onClearAll = { viewModel.clearAllMemories() },
                    )
                    4 -> SkillsTab(skills = state.skills)
                    5 -> AccountTab(
                        username = state.authUsername,
                        avatarUrl = state.authAvatarUrl,
                        onSignIn = { viewModel.setAuthScreenVisible(true) },
                        onSignOut = { viewModel.signOut() },
                    )
                }

                Spacer(Modifier.height(16.dp))
                Button(
                    onClick = {
                        scope.launch {
                            viewModel.setProvider(selectedProvider, selectedModel)
                            viewModel.setPersona(selectedPersona)
                            val keys = if (apiKeyInput.isNotBlank()) mapOf(selectedProvider to apiKeyInput) else null
                            viewModel.saveSettings(selectedProvider, selectedModel, selectedPersona, keys, selectedLanguage)
                            saveMessage = "Settings saved."
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MeikoColors.Violet),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Save settings")
                }
                saveMessage?.let {
                    Text(it, color = MeikoColors.Success, fontSize = 12.sp, modifier = Modifier.padding(top = 8.dp))
                }
                Spacer(Modifier.height(24.dp))
            }
        }
    }
}

@Composable
private fun ProvidersTab(
    providers: List<ProviderMeta>,
    selectedProvider: String,
    onSelectProvider: (String) -> Unit,
    apiKeyInput: String,
    onApiKeyChange: (String) -> Unit,
) {
    Column {
        Text("Choose a provider", fontWeight = FontWeight.Bold, color = MeikoColors.Text0, fontSize = 14.sp)
        Spacer(Modifier.height(4.dp))
        Text(
            "NVIDIA NIM is Meiko's default free provider with 20+ models. Bring your own key for Gemini, Groq, OpenRouter, OpenAI, or a local Ollama endpoint.",
            fontSize = 12.sp,
            color = MeikoColors.Text2,
        )
        Spacer(Modifier.height(12.dp))
        providers.forEach { p ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(MeikoColors.Panel)
                    .border(1.dp, if (p.id == selectedProvider) MeikoColors.Violet else MeikoColors.Border, RoundedCornerShape(12.dp))
                    .clickable { onSelectProvider(p.id) }
                    .padding(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = p.id == selectedProvider, onClick = { onSelectProvider(p.id) })
                Column(modifier = Modifier.padding(start = 6.dp)) {
                    Text(p.displayName, color = MeikoColors.Text0, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                    if (p.freeTier) Text("Free tier available", color = MeikoColors.Success, fontSize = 10.sp)
                    if (p.description.isNotBlank()) Text(p.description, color = MeikoColors.Text2, fontSize = 10.5.sp)
                }
            }
            Spacer(Modifier.height(6.dp))
        }

        Spacer(Modifier.height(12.dp))
        Text("API key for $selectedProvider", fontWeight = FontWeight.Bold, color = MeikoColors.Text0, fontSize = 13.sp)
        var visible by remember { mutableStateOf(false) }
        OutlinedTextField(
            value = apiKeyInput,
            onValueChange = onApiKeyChange,
            placeholder = { Text("Paste your API key (optional)", color = MeikoColors.Text2) },
            visualTransformation = if (visible) VisualTransformation.None else PasswordVisualTransformation(),
            trailingIcon = {
                IconButton(onClick = { visible = !visible }) {
                    Icon(Icons.Filled.RemoveRedEye, contentDescription = "Toggle visibility", tint = MeikoColors.Text2)
                }
            },
            modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedTextColor = MeikoColors.Text0,
                unfocusedTextColor = MeikoColors.Text0,
                focusedBorderColor = MeikoColors.Violet,
                unfocusedBorderColor = MeikoColors.Border,
            ),
        )
    }
}

@Composable
private fun ModelsTab(models: List<ai.meiko.app.data.ModelMeta>, selectedModel: String?, onSelect: (String) -> Unit) {
    Column {
        Text("Pick a model", fontWeight = FontWeight.Bold, color = MeikoColors.Text0, fontSize = 14.sp)
        Spacer(Modifier.height(4.dp))
        Text(
            "Your free NVIDIA key unlocks a full catalog of large language models — reasoning specialists, vision models, and long-context generalists.",
            fontSize = 12.sp,
            color = MeikoColors.Text2,
        )
        Spacer(Modifier.height(10.dp))
        models.forEach { m ->
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(MeikoColors.Panel)
                    .border(1.dp, if (m.id == selectedModel) MeikoColors.Violet else MeikoColors.Border, RoundedCornerShape(12.dp))
                    .clickable { onSelect(m.id) }
                    .padding(12.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(m.displayName, color = MeikoColors.Text0, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                    Spacer(Modifier.weight(1f))
                    if (m.tag.isNotBlank()) Badge(m.tag)
                }
                Row(modifier = Modifier.padding(top = 4.dp)) {
                    if (m.reasoning) Badge("🧠 reasoning")
                    if (m.vision) Badge("👁 vision")
                    if (m.contextWindow.isNotBlank()) Badge(m.contextWindow)
                }
                if (m.goodFor.isNotEmpty()) {
                    Text(m.goodFor.joinToString(" · "), fontSize = 10.5.sp, color = MeikoColors.Text2, modifier = Modifier.padding(top = 4.dp))
                }
            }
        }
    }
}

@Composable
private fun Badge(text: String) {
    Text(
        text,
        fontSize = 9.5.sp,
        color = MeikoColors.VioletSoft,
        modifier = Modifier
            .padding(end = 4.dp, top = 2.dp)
            .clip(RoundedCornerShape(999.dp))
            .background(MeikoColors.Violet.copy(alpha = 0.15f))
            .padding(horizontal = 6.dp, vertical = 2.dp),
    )
}

@Composable
private fun PersonaTab(
    personas: List<ai.meiko.app.data.PersonaMeta>,
    selected: String,
    onSelect: (String) -> Unit,
    languages: List<Pair<String, String>>,
    selectedLanguage: String,
    onSelectLanguage: (String) -> Unit,
) {
    Column {
        Text("Persona", fontWeight = FontWeight.Bold, color = MeikoColors.Text0, fontSize = 14.sp)
        Spacer(Modifier.height(8.dp))
        personas.forEach { p ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(MeikoColors.Panel)
                    .border(1.dp, if (p.id == selected) MeikoColors.Violet else MeikoColors.Border, RoundedCornerShape(12.dp))
                    .clickable { onSelect(p.id) }
                    .padding(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = p.id == selected, onClick = { onSelect(p.id) })
                Column(modifier = Modifier.padding(start = 6.dp)) {
                    Text(p.name, color = MeikoColors.Text0, fontSize = 13.sp)
                    if (p.tagline.isNotBlank()) Text(p.tagline, color = MeikoColors.Text2, fontSize = 10.5.sp)
                }
            }
            Spacer(Modifier.height(6.dp))
        }

        Spacer(Modifier.height(16.dp))
        Text("Reply language", fontWeight = FontWeight.Bold, color = MeikoColors.Text0, fontSize = 14.sp)
        Spacer(Modifier.height(8.dp))
        var expanded by remember { mutableStateOf(false) }
        Box {
            OutlinedButton(onClick = { expanded = true }, modifier = Modifier.fillMaxWidth()) {
                Text(languages.find { it.first == selectedLanguage }?.second ?: "English")
            }
            DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                languages.forEach { (code, label) ->
                    DropdownMenuItem(text = { Text(label) }, onClick = { onSelectLanguage(code); expanded = false })
                }
            }
        }
    }
}

@Composable
private fun MemoryTab(memories: List<ai.meiko.app.data.MemoryFact>, onDelete: (String) -> Unit, onClearAll: () -> Unit) {
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Filled.Psychology, contentDescription = null, tint = MeikoColors.VioletSoft)
            Text("Persistent memory", fontWeight = FontWeight.Bold, color = MeikoColors.Text0, fontSize = 14.sp, modifier = Modifier.padding(start = 6.dp))
        }
        Spacer(Modifier.height(4.dp))
        Text(
            "Meiko remembers facts you share across conversations so it doesn't ask twice.",
            fontSize = 12.sp,
            color = MeikoColors.Text2,
        )
        Spacer(Modifier.height(10.dp))
        if (memories.isEmpty()) {
            Text("No memories yet — Meiko will learn as you chat.", color = MeikoColors.Text2, fontSize = 12.sp)
        } else {
            memories.forEach { m ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 3.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(MeikoColors.Panel)
                        .padding(10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(m.fact, color = MeikoColors.Text1, fontSize = 12.5.sp, modifier = Modifier.weight(1f))
                    IconButton(onClick = { onDelete(m.id) }) {
                        Icon(Icons.Filled.Delete, contentDescription = "Delete", tint = MeikoColors.Danger)
                    }
                }
            }
            Spacer(Modifier.height(10.dp))
            TextButton(onClick = onClearAll) {
                Text("Clear all memories", color = MeikoColors.Danger)
            }
        }
    }
}

@Composable
private fun AccountTab(
    username: String?,
    avatarUrl: String?,
    onSignIn: () -> Unit,
    onSignOut: () -> Unit,
) {
    Column {
        Text("Account", fontWeight = FontWeight.Bold, color = MeikoColors.Text0, fontSize = 14.sp)
        Spacer(Modifier.height(4.dp))
        Text(
            "Optional: sign in with GitHub to make your conversations, memories, and settings follow your account across every device — instead of a locally-generated id.",
            fontSize = 12.sp,
            color = MeikoColors.Text2,
        )
        Spacer(Modifier.height(14.dp))
        if (username != null) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(MeikoColors.Panel)
                    .padding(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (avatarUrl != null) {
                    coil.compose.AsyncImage(
                        model = avatarUrl,
                        contentDescription = username,
                        modifier = Modifier
                            .height(40.dp)
                            .clip(RoundedCornerShape(20.dp)),
                    )
                    Spacer(Modifier.width(10.dp))
                }
                Column(modifier = Modifier.weight(1f)) {
                    Text("Signed in as", color = MeikoColors.Text2, fontSize = 11.sp)
                    Text(username, color = MeikoColors.Text0, fontSize = 14.sp, fontWeight = FontWeight.Medium)
                }
                TextButton(onClick = onSignOut) { Text("Sign out", color = MeikoColors.Violet) }
            }
        } else {
            OutlinedButton(
                onClick = onSignIn,
                colors = ButtonDefaults.outlinedButtonColors(contentColor = MeikoColors.Text0),
            ) {
                Text("Sign in with GitHub")
            }
        }
    }
}

@Composable
private fun SkillsTab(skills: List<ai.meiko.app.data.SkillMeta>) {
    Column {
        Text("Skills", fontWeight = FontWeight.Bold, color = MeikoColors.Text0, fontSize = 14.sp)
        Spacer(Modifier.height(4.dp))
        Text("Reusable playbooks Meiko can invoke automatically when your message matches a trigger.", fontSize = 12.sp, color = MeikoColors.Text2)
        Spacer(Modifier.height(10.dp))
        if (skills.isEmpty()) {
            Text("No skills installed.", color = MeikoColors.Text2, fontSize = 12.sp)
        }
        skills.forEach { s ->
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(MeikoColors.Panel)
                    .padding(10.dp),
            ) {
                Text(s.name, color = MeikoColors.Text0, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                if (s.description.isNotBlank()) Text(s.description, color = MeikoColors.Text2, fontSize = 11.sp)
            }
        }
    }
}
