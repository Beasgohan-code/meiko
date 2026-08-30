package ai.meiko.app.ui.chat

import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.animateFloat
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.RadioButtonUnchecked
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import dev.jeziellago.compose.markdowntext.MarkdownText
import ai.meiko.app.data.ChatMessage
import ai.meiko.app.data.ChatRole
import ai.meiko.app.data.PlanTaskStatus
import ai.meiko.app.data.RunInfo
import ai.meiko.app.ui.theme.MeikoColors

@Composable
fun MessageBubble(message: ChatMessage, downloadUrl: (String) -> String) {
    val isUser = message.role == ChatRole.USER
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        Column(
            modifier = Modifier
                .widthIn(max = 320.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(if (isUser) MeikoColors.Violet.copy(alpha = 0.18f) else MeikoColors.Panel)
                .border(1.dp, MeikoColors.Border, RoundedCornerShape(16.dp))
                .padding(12.dp),
        ) {
            if (message.thinking.isNotEmpty()) {
                ThinkingPanel(text = message.thinking, isThinking = message.isThinking)
                Spacer(Modifier.height(8.dp))
            }

            if (message.plan.isNotEmpty()) {
                PlanTracker(message)
                Spacer(Modifier.height(8.dp))
            }

            if (message.tools.isNotEmpty()) {
                message.tools.forEach { tool ->
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 4.dp)) {
                        if (tool.done) {
                            Icon(Icons.Filled.CheckCircle, contentDescription = null, tint = MeikoColors.Success, modifier = Modifier.padding(end = 4.dp))
                        } else {
                            CircularProgressIndicator(modifier = Modifier.padding(end = 6.dp), color = MeikoColors.VioletSoft, strokeWidth = 2.dp)
                        }
                        Text("Tool: ${tool.name}", fontSize = 11.sp, color = MeikoColors.Text2)
                    }
                }
            }

            message.providerNotices.forEach { notice ->
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 6.dp)) {
                    Icon(Icons.Filled.Sync, contentDescription = null, tint = MeikoColors.Cyan, modifier = Modifier.padding(end = 4.dp))
                    Text(notice, fontSize = 10.5.sp, color = MeikoColors.Cyan)
                }
            }

            if (message.content.isNotEmpty()) {
                Row(verticalAlignment = Alignment.Bottom) {
                    MarkdownText(
                        markdown = message.content,
                        style = androidx.compose.ui.text.TextStyle(color = MeikoColors.Text0, fontSize = 14.sp),
                        modifier = Modifier.weight(1f, fill = false),
                    )
                    if (message.streaming && !message.isThinking) {
                        StreamCaret()
                    }
                }
            } else if (message.streaming) {
                Text("Thinking…", fontSize = 13.sp, color = MeikoColors.Text2)
            }

            message.error?.let {
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 6.dp)) {
                    Icon(Icons.Filled.Warning, contentDescription = null, tint = MeikoColors.Danger, modifier = Modifier.padding(end = 4.dp))
                    Text(it, fontSize = 12.sp, color = MeikoColors.Danger)
                }
            }

            if (message.generatedImages.isNotEmpty()) {
                LazyRow {
                    items(message.generatedImages) { filename ->
                        AsyncImage(
                            model = downloadUrl(filename),
                            contentDescription = "Generated image",
                            contentScale = ContentScale.Crop,
                            modifier = Modifier
                                .padding(top = 8.dp, end = 6.dp)
                                .clip(RoundedCornerShape(10.dp)),
                        )
                    }
                }
            }

            if (message.citations.isNotEmpty()) {
                Spacer(Modifier.height(6.dp))
                message.citations.forEachIndexed { idx, c ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Filled.Link, contentDescription = null, tint = MeikoColors.VioletSoft, modifier = Modifier.padding(end = 4.dp))
                        Text("[${idx + 1}] ${c.url}", fontSize = 10.sp, color = MeikoColors.VioletSoft)
                    }
                }
            }

            if (!message.streaming) {
                message.runInfo?.let { RunTelemetry(it) }
            }
        }
    }
}

/** Blinking streaming cursor (Groq/Claude/Arena-style live token cursor),
 * mirroring the web app's `.stream-caret` CSS animation. */
@Composable
private fun StreamCaret() {
    val transition = androidx.compose.animation.core.rememberInfiniteTransition(label = "caret")
    val alpha by transition.animateFloat(
        initialValue = 1f,
        targetValue = 0f,
        animationSpec = androidx.compose.animation.core.infiniteRepeatable(
            androidx.compose.animation.core.tween(850, easing = androidx.compose.animation.core.LinearEasing),
            androidx.compose.animation.core.RepeatMode.Reverse,
        ),
        label = "caret-alpha",
    )
    Box(
        modifier = Modifier
            .padding(start = 2.dp, bottom = 2.dp)
            .width(2.dp)
            .height(14.dp)
            .background(MeikoColors.VioletSoft.copy(alpha = alpha), RoundedCornerShape(1.dp)),
    )
}

/**
 * Collapsible "thinking" trace -- DeepSeek-R1/QwQ/Gemini-Thinking-style
 * chain of thought, Claude Extended-Thinking-style presentation. Mirrors
 * the web app's ThinkingPanel.
 */
@Composable
private fun ThinkingPanel(text: String, isThinking: Boolean) {
    var expanded by remember(isThinking) { mutableStateOf(isThinking) }
    Column(
        modifier = Modifier
            .clip(RoundedCornerShape(10.dp))
            .background(MeikoColors.Bg2.copy(alpha = 0.5f))
            .border(1.dp, MeikoColors.Border, RoundedCornerShape(10.dp))
            .clickable { expanded = !expanded }
            .animateContentSize(),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 7.dp),
        ) {
            Icon(Icons.Filled.Psychology, contentDescription = null, tint = MeikoColors.VioletSoft, modifier = Modifier.padding(end = 6.dp))
            Text(
                if (isThinking) "Thinking…" else "Thought process",
                fontSize = 11.5.sp,
                fontWeight = FontWeight.SemiBold,
                color = MeikoColors.Text2,
                modifier = Modifier.weight(1f),
            )
            Icon(
                Icons.Filled.ExpandMore,
                contentDescription = null,
                tint = MeikoColors.Text2,
                modifier = Modifier.graphicsLayer(rotationZ = if (expanded) 180f else 0f),
            )
        }
        if (expanded) {
            Text(
                text,
                fontSize = 11.5.sp,
                color = MeikoColors.Text1,
                modifier = Modifier
                    .padding(horizontal = 12.dp)
                    .padding(bottom = 10.dp)
                    .heightIn(max = 220.dp)
                    .verticalScroll(rememberScrollState()),
            )
        }
    }
}

/** Groq-style tok/s + provider/model run-telemetry badge, mirrors the web app. */
@Composable
private fun RunTelemetry(info: RunInfo) {
    if (info.provider == null) return
    val parts = mutableListOf<String>()
    parts.add(if (info.model != null) "${info.provider} · ${info.model}" else info.provider)
    info.elapsedSeconds?.let { parts.add("%.1fs".format(it)) }
    info.steps?.let { if (it > 0) parts.add("$it step${if (it == 1) "" else "s"}") }
    info.toolCalls?.let { if (it > 0) parts.add("$it tool call${if (it == 1) "" else "s"}") }
    info.providerSwitches?.let { if (it > 0) parts.add("$it fallback${if (it == 1) "" else "s"}") }

    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .padding(top = 8.dp)
            .clip(RoundedCornerShape(999.dp))
            .background(MeikoColors.Bg2.copy(alpha = 0.5f))
            .padding(horizontal = 9.dp, vertical = 3.dp),
    ) {
        Icon(Icons.Filled.Speed, contentDescription = null, tint = MeikoColors.Text2, modifier = Modifier.padding(end = 4.dp))
        Text(parts.joinToString(" · "), fontSize = 9.5.sp, color = MeikoColors.Text2)
        if (info.tokensPerSecond != null && info.tokensPerSecond > 0) {
            Text(" · ", fontSize = 9.5.sp, color = MeikoColors.Text2)
            Icon(Icons.Filled.Bolt, contentDescription = null, tint = MeikoColors.Cyan, modifier = Modifier.padding(end = 2.dp))
            Text("%.1f tok/s".format(info.tokensPerSecond), fontSize = 9.5.sp, color = MeikoColors.Cyan)
        }
    }
}

@Composable
private fun PlanTracker(message: ChatMessage) {
    Column {
        Text("Plan", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = MeikoColors.Text2)
        message.plan.forEach { task ->
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 2.dp)) {
                val (icon, tint) = when (task.status) {
                    PlanTaskStatus.DONE -> Icons.Filled.CheckCircle to MeikoColors.Success
                    PlanTaskStatus.IN_PROGRESS -> Icons.Filled.Sync to MeikoColors.VioletSoft
                    PlanTaskStatus.PENDING -> Icons.Filled.RadioButtonUnchecked to MeikoColors.Text2
                }
                Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.padding(end = 6.dp))
                Text(task.text, fontSize = 11.5.sp, color = MeikoColors.Text1)
            }
        }
    }
}
