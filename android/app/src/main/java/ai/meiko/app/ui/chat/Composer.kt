package ai.meiko.app.ui.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ai.meiko.app.ui.theme.MeikoColors

@Composable
fun Composer(isStreaming: Boolean, onSend: (String) -> Unit, onStop: () -> Unit) {
    var text by remember { mutableStateOf("") }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(MeikoColors.Bg1)
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
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
                if (isStreaming) {
                    onStop()
                } else if (text.isNotBlank()) {
                    onSend(text)
                    text = ""
                }
            },
            modifier = Modifier
                .padding(start = 6.dp)
                .size(44.dp)
                .background(if (isStreaming) MeikoColors.Danger else MeikoColors.Violet, CircleShape),
        ) {
            Icon(
                imageVector = if (isStreaming) Icons.Filled.Stop else Icons.Filled.ArrowUpward,
                contentDescription = if (isStreaming) "Stop" else "Send",
                tint = androidx.compose.ui.graphics.Color.White,
            )
        }
    }
}
