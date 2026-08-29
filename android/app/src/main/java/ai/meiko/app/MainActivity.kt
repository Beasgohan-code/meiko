package ai.meiko.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import ai.meiko.app.ui.MeikoViewModel
import ai.meiko.app.ui.chat.MeikoApp
import ai.meiko.app.ui.theme.MeikoColors
import ai.meiko.app.ui.theme.MeikoTheme

class MainActivity : ComponentActivity() {
    private val viewModel: MeikoViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MeikoTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MeikoColors.Bg0) {
                    MeikoApp(viewModel = viewModel)
                }
            }
        }
    }
}
