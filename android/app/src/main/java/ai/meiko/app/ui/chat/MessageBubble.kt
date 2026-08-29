package ai.meiko.app.ui.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.RadioButtonUnchecked
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.jeziellago.compose.markdowntext.MarkdownText
import ai.meiko.app.data.ChatMessage
import ai.meiko.app.data.ChatRole
import ai.meiko.app.data.PlanTaskStatus
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
                MarkdownText(markdown = message.content, style = androidx.compose.ui.text.TextStyle(color = MeikoColors.Text0, fontSize = 14.sp))
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
