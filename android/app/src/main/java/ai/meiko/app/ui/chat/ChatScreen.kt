package ai.meiko.app.ui.chat

import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.animation.togetherWith
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ai.meiko.app.ui.MeikoViewModel
import ai.meiko.app.ui.OrbState
import ai.meiko.app.ui.theme.MeikoColors

private val SUGGESTIONS = listOf(
    "Research the latest breakthroughs in fusion energy",
    "Write a Python script that batch-renames files and zip the result",
    "Generate an image of a cyberpunk city at sunset",
    "Explain transformers like I'm five",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(viewModel: MeikoViewModel, onOpenSettings: () -> Unit, onOpenHistory: () -> Unit) {
    val state by viewModel.state.collectAsState()
    val listState = rememberLazyListState()

    LaunchedEffect(state.messages.size) {
        if (state.messages.isNotEmpty()) listState.animateScrollToItem(state.messages.size - 1)
    }

    Scaffold(
        containerColor = MeikoColors.Bg0,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Meiko Agent", fontWeight = FontWeight.Bold, fontSize = 16.sp, color = MeikoColors.Text0)
                        Text(
                            "Mode: ${state.modes.find { it.id == state.mode }?.name ?: state.mode} · ${state.provider ?: "auto"}",
                            fontSize = 11.sp,
                            color = MeikoColors.Text2,
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.toggleTheme() }) {
                        Icon(
                            if (state.darkTheme) Icons.Filled.LightMode else Icons.Filled.DarkMode,
                            contentDescription = if (state.darkTheme) "Switch to light mode" else "Switch to dark mode",
                            tint = MeikoColors.Text1,
                        )
                    }
                    IconButton(onClick = onOpenHistory) { Icon(Icons.Filled.History, contentDescription = "History", tint = MeikoColors.Text1) }
                    IconButton(onClick = onOpenSettings) { Icon(Icons.Filled.Settings, contentDescription = "Settings", tint = MeikoColors.Text1) }
                    MeikoOrb(state = state.orbState, size = 34.dp, modifier = Modifier.padding(end = 8.dp))
                },
                // Liquid-glass topbar: translucent tint + hairline border instead of a
                // flat opaque surface, matching the web app's frosted-glass chrome.
                colors = androidx.compose.material3.TopAppBarDefaults.topAppBarColors(
                    containerColor = MeikoColors.Bg1.copy(alpha = 0.72f),
                ),
                modifier = Modifier
                    .border(1.dp, MeikoColors.Border),
            )
        },
        bottomBar = {
            Composer(
                isStreaming = state.isStreaming,
                onSend = { viewModel.sendMessage(it) },
                onStop = { viewModel.stopStreaming() },
                onAttach = { name, bytes, mime -> viewModel.uploadFile(name, bytes, mime) },
            )
        },
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            androidx.compose.animation.AnimatedContent(
                targetState = state.messages.isEmpty(),
                label = "chat-body",
                transitionSpec = {
                    (androidx.compose.animation.fadeIn(tween(260)) + androidx.compose.animation.scaleIn(initialScale = 0.98f, animationSpec = tween(260)))
                        .togetherWith(androidx.compose.animation.fadeOut(tween(160)))
                },
            ) { empty ->
                if (empty) {
                    HeroSection(onSuggestionTap = { viewModel.sendMessage(it) })
                } else {
                    LazyColumn(
                        state = listState,
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        items(state.messages, key = { it.id }) { msg ->
                            AnimatedMessageEntrance {
                                MessageBubble(message = msg, downloadUrl = { viewModel.downloadUrl(it) })
                            }
                        }
                    }
                }
            }
        }
    }
}

/** Fade + slide-up entrance for each chat bubble (Groq/Claude/Arena-style
 * animated message appearance), mirroring the web app's framer-motion
 * message entrance transition. */
@Composable
private fun AnimatedMessageEntrance(content: @Composable () -> Unit) {
    var visible by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(false) }
    LaunchedEffect(Unit) { visible = true }
    androidx.compose.animation.AnimatedVisibility(
        visible = visible,
        enter = androidx.compose.animation.fadeIn(tween(320)) +
            androidx.compose.animation.slideInVertically(tween(320)) { it / 6 },
    ) {
        content()
    }
}

@Composable
private fun HeroSection(onSuggestionTap: (String) -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        MeikoOrb(state = OrbState.IDLE, size = 140.dp)
        Spacer(Modifier.height(18.dp))
        Text(
            "Hey, I'm Meiko.",
            fontSize = 26.sp,
            fontWeight = FontWeight.Bold,
            color = MeikoColors.Text0,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            "Your open, pluggable AI agent — research, code, create, and automate. Bring your own free API key " +
                "(NVIDIA, Gemini, Groq & more) and I'll get to work.",
            fontSize = 13.5.sp,
            color = MeikoColors.Text1,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
        )
        Spacer(Modifier.height(20.dp))
        SUGGESTIONS.forEach { s ->
            Row(
                modifier = Modifier
                    .padding(vertical = 4.dp)
                    .clip(RoundedCornerShape(999.dp))
                    .background(MeikoColors.Panel)
                    .border(1.dp, MeikoColors.Border, RoundedCornerShape(999.dp))
                    .clickable { onSuggestionTap(s) }
                    .padding(horizontal = 14.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Filled.AutoAwesome, contentDescription = null, tint = MeikoColors.VioletSoft, modifier = Modifier.size(12.dp))
                Spacer(Modifier.width(6.dp))
                Text(s, fontSize = 12.sp, color = MeikoColors.Text1)
            }
        }
    }
}

@Composable
fun MeikoOrb(state: OrbState, size: androidx.compose.ui.unit.Dp, modifier: Modifier = Modifier) {
    val transition = rememberInfiniteTransition(label = "orb")
    val pulse by transition.animateFloat(
        initialValue = 0.85f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1200, easing = LinearEasing), RepeatMode.Reverse),
        label = "pulse",
    )
    val colors = when (state) {
        OrbState.IDLE -> listOf(MeikoColors.Violet, MeikoColors.Cyan)
        OrbState.THINKING -> listOf(MeikoColors.VioletSoft, MeikoColors.Violet)
        OrbState.SPEAKING -> listOf(MeikoColors.Cyan, MeikoColors.VioletSoft)
        OrbState.TOOL -> listOf(MeikoColors.Success, MeikoColors.Cyan)
    }
    Box(
        modifier = modifier
            .size(size * if (state == OrbState.IDLE) 1f else pulse)
            .clip(CircleShape)
            .background(Brush.linearGradient(colors)),
    )
}
