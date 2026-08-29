package ai.meiko.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

object MeikoColors {
    val Bg0 = Color(0xFF060613)
    val Bg1 = Color(0xFF0B0B1C)
    val Bg2 = Color(0xFF12122A)
    val Panel = Color(0xCC141428)
    val Border = Color(0x2A8C82FF)
    val Violet = Color(0xFF7C5CFF)
    val VioletSoft = Color(0xFFA78BFA)
    val Cyan = Color(0xFF22D3EE)
    val Text0 = Color(0xFFF4F3FF)
    val Text1 = Color(0xFFB9B6D6)
    val Text2 = Color(0xFF7C7893)
    val Danger = Color(0xFFFF6B6B)
    val Success = Color(0xFF4ADE80)
}

private val MeikoDarkScheme = darkColorScheme(
    primary = MeikoColors.Violet,
    secondary = MeikoColors.Cyan,
    background = MeikoColors.Bg0,
    surface = MeikoColors.Bg1,
    onPrimary = Color.White,
    onBackground = MeikoColors.Text0,
    onSurface = MeikoColors.Text0,
    error = MeikoColors.Danger,
)

@Composable
fun MeikoTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = MeikoDarkScheme,
        typography = MaterialTheme.typography,
        content = content,
    )
}
