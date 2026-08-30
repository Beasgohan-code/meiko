package ai.meiko.app.ui.chat

import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.ui.draw.drawBehind
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.InsertDriveFile
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ai.meiko.app.ui.theme.MeikoColors

private data class PendingUri(val uri: Uri, val name: String)

private fun displayName(context: Context, uri: Uri): String {
    var name = uri.lastPathSegment ?: "file"
    context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
        val idx = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
        if (idx >= 0 && cursor.moveToFirst()) name = cursor.getString(idx)
    }
    return name
}

@Composable
fun Composer(
    isStreaming: Boolean,
    onSend: (String) -> Unit,
    onStop: () -> Unit,
    onAttach: (fileName: String, bytes: ByteArray, mimeType: String) -> Unit = { _, _, _ -> },
) {
    var text by remember { mutableStateOf("") }
    val pending = remember { mutableStateListOf<PendingUri>() }
    val context = LocalContext.current

    val pickFile = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        if (uri != null) pending.add(PendingUri(uri, displayName(context, uri)))
    }

    fun flushAndSend() {
        val trimmed = text.trim()
        if (trimmed.isEmpty() && pending.isEmpty()) return
        pending.toList().forEach { p ->
            val bytes = context.contentResolver.openInputStream(p.uri)?.use { it.readBytes() }
            val mime = context.contentResolver.getType(p.uri) ?: "application/octet-stream"
            if (bytes != null) onAttach(p.name, bytes, mime)
        }
        pending.clear()
        if (trimmed.isNotEmpty()) onSend(trimmed)
        text = ""
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            // Liquid-glass composer bar: translucent tint + hairline top border,
            // matching the web app's frosted composer.
            .background(MeikoColors.Bg1.copy(alpha = 0.86f))
            .drawBehind {
                drawLine(
                    color = MeikoColors.Border,
                    start = androidx.compose.ui.geometry.Offset(0f, 0f),
                    end = androidx.compose.ui.geometry.Offset(size.width, 0f),
                    strokeWidth = 1.dp.toPx(),
                )
            }
            .padding(horizontal = 10.dp, vertical = 8.dp)
            .animateContentSize(),
    ) {
        AnimatedVisibility(
            visible = pending.isNotEmpty(),
            enter = fadeIn(tween(160)) + scaleIn(tween(160), initialScale = 0.92f),
            exit = fadeOut(tween(120)) + scaleOut(tween(120), targetScale = 0.92f),
        ) {
            LazyRow(modifier = Modifier.padding(bottom = 6.dp)) {
                items(pending) { p ->
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .padding(end = 6.dp)
                            .clip(RoundedCornerShape(999.dp))
                            .background(MeikoColors.Bg2)
                            .border(1.dp, MeikoColors.Border, RoundedCornerShape(999.dp))
                            .padding(start = 10.dp, end = 4.dp, top = 4.dp, bottom = 4.dp),
                    ) {
                        Icon(Icons.Filled.InsertDriveFile, contentDescription = null, tint = MeikoColors.VioletSoft, modifier = Modifier.size(13.dp))
                        Text(p.name, fontSize = 11.sp, color = MeikoColors.Text1, modifier = Modifier.padding(start = 6.dp, end = 4.dp))
                        IconButton(onClick = { pending.remove(p) }, modifier = Modifier.size(20.dp)) {
                            Icon(Icons.Filled.Close, contentDescription = "Remove", tint = MeikoColors.Text2, modifier = Modifier.size(12.dp))
                        }
                    }
                }
            }
        }

        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { pickFile.launch("*/*") }) {
                Icon(Icons.Filled.AttachFile, contentDescription = "Attach file", tint = MeikoColors.Text2)
            }
            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("Ask Meiko anything…", color = MeikoColors.Text2) },
                shape = RoundedCornerShape(20.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedTextColor = MeikoColors.Text0,
                    unfocusedTextColor = MeikoColors.Text0,
                    focusedBorderColor = MeikoColors.Violet,
                    unfocusedBorderColor = MeikoColors.Border,
                    cursorColor = MeikoColors.Violet,
                ),
                maxLines = 5,
            )
            IconButton(
                onClick = {
                    if (isStreaming) onStop() else flushAndSend()
                },
                modifier = Modifier
                    .padding(start = 6.dp)
                    .size(44.dp)
                    .background(if (isStreaming) MeikoColors.Danger else MeikoColors.Violet, CircleShape),
            ) {
                Icon(
                    imageVector = if (isStreaming) Icons.Filled.Stop else Icons.Filled.ArrowUpward,
                    contentDescription = if (isStreaming) "Stop" else "Send",
                    tint = Color.White,
                )
            }
        }
    }
}
