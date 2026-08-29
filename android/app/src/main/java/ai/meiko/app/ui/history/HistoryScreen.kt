package ai.meiko.app.ui.history

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.PushPin
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ai.meiko.app.ui.MeikoViewModel
import ai.meiko.app.ui.theme.MeikoColors

@Composable
fun HistoryScreen(viewModel: MeikoViewModel, onBack: () -> Unit, onOpenConversation: (String) -> Unit) {
    val state by viewModel.state.collectAsState()
    var query by remember { mutableStateOf("") }

    LaunchedEffect(query) { viewModel.refreshConversations(query.ifBlank { null }) }

    Scaffold(
        containerColor = MeikoColors.Bg0,
        topBar = {
            TopAppBar(
                title = { Text("Conversation history", color = MeikoColors.Text0, fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, contentDescription = "Back", tint = MeikoColors.Text1) }
                },
                colors = androidx.compose.material3.TopAppBarDefaults.topAppBarColors(containerColor = MeikoColors.Bg1),
            )
        },
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize().padding(12.dp)) {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                placeholder = { Text("Search conversations…", color = MeikoColors.Text2) },
                modifier = Modifier.fillMaxWidth(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedTextColor = MeikoColors.Text0,
                    unfocusedTextColor = MeikoColors.Text0,
                    focusedBorderColor = MeikoColors.Violet,
                    unfocusedBorderColor = MeikoColors.Border,
                ),
            )
            LazyColumn(modifier = Modifier.padding(top = 10.dp)) {
                items(state.conversations, key = { it.id }) { conv ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                            .clip(RoundedCornerShape(10.dp))
                            .background(MeikoColors.Panel)
                            .clickable { onOpenConversation(conv.id) }
                            .padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(
                            conv.title.ifBlank { "Untitled conversation" },
                            color = MeikoColors.Text0,
                            fontSize = 13.sp,
                            modifier = Modifier.weight(1f),
                        )
                        IconButton(onClick = { viewModel.pinConversation(conv.id, conv.pinned == 0) }) {
                            Icon(
                                Icons.Filled.PushPin,
                                contentDescription = "Pin",
                                tint = if (conv.pinned != 0) MeikoColors.Violet else MeikoColors.Text2,
                            )
                        }
                        IconButton(onClick = { viewModel.deleteConversation(conv.id) }) {
                            Icon(Icons.Filled.Delete, contentDescription = "Delete", tint = MeikoColors.Danger)
                        }
                    }
                }
            }
        }
    }
}
