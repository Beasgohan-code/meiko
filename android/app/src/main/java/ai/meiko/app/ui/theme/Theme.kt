package ai.meiko.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color

enum class MeikoThemeMode { DARK, LIGHT }

/**
 * A single mutable color palette that every screen already reads via
 * `MeikoColors.Bg0`, `MeikoColors.Text0`, etc. (112 call sites across the
 * app). Rather than threading a theme value through every composable, we
 * make the palette itself observable Compose state: flipping [current]
 * updates every property in place and any composable reading them
 * automatically recomposes -- the same trick as the web app's CSS custom
 * properties, just done in Kotlin.
 */
object MeikoColors {
    private val darkPalette = Palette(
        Bg0 = Color(0xFF060613),
        Bg1 = Color(0xFF0B0B1C),
        Bg2 = Color(0xFF12122A),
        Panel = Color(0xCC141428),
        Border = Color(0x2A8C82FF),
        Violet = Color(0xFF7C5CFF),
        VioletSoft = Color(0xFFA78BFA),
        Cyan = Color(0xFF22D3EE),
        Text0 = Color(0xFFF4F3FF),
        Text1 = Color(0xFFB9B6D6),
        Text2 = Color(0xFF7C7893),
        Danger = Color(0xFFFF6B6B),
        Success = Color(0xFF4ADE80),
    )

    private val lightPalette = Palette(
        Bg0 = Color(0xFFF5F4FB),
        Bg1 = Color(0xFFFFFFFF),
        Bg2 = Color(0xFFECE9FB),
        Panel = Color(0xE6FFFFFF),
        Border = Color(0x2E7C5CFF),
        Violet = Color(0xFF6D4AEF),
        VioletSoft = Color(0xFF7C5CFF),
        Cyan = Color(0xFF0891B2),
        Text0 = Color(0xFF201F36),
        Text1 = Color(0xFF4A4768),
        Text2 = Color(0xFF79768F),
        Danger = Color(0xFFDC2626),
        Success = Color(0xFF16A34A),
    )

    private var mode by mutableStateOf(MeikoThemeMode.DARK)
    private var palette by mutableStateOf(darkPalette)

    fun setMode(m: MeikoThemeMode) {
        mode = m
        palette = if (m == MeikoThemeMode.DARK) darkPalette else lightPalette
    }

    fun currentMode(): MeikoThemeMode = mode

    val Bg0 get() = palette.Bg0
    val Bg1 get() = palette.Bg1
    val Bg2 get() = palette.Bg2
    val Panel get() = palette.Panel
    val Border get() = palette.Border
    val Violet get() = palette.Violet
    val VioletSoft get() = palette.VioletSoft
    val Cyan get() = palette.Cyan
    val Text0 get() = palette.Text0
    val Text1 get() = palette.Text1
    val Text2 get() = palette.Text2
    val Danger get() = palette.Danger
    val Success get() = palette.Success

    private data class Palette(
        val Bg0: Color,
        val Bg1: Color,
        val Bg2: Color,
        val Panel: Color,
        val Border: Color,
        val Violet: Color,
        val VioletSoft: Color,
        val Cyan: Color,
        val Text0: Color,
        val Text1: Color,
        val Text2: Color,
        val Danger: Color,
        val Success: Color,
    )
}

@Composable
fun MeikoTheme(darkMode: Boolean, content: @Composable () -> Unit) {
    MeikoColors.setMode(if (darkMode) MeikoThemeMode.DARK else MeikoThemeMode.LIGHT)
    val scheme = if (darkMode) {
        darkColorScheme(
            primary = MeikoColors.Violet,
            secondary = MeikoColors.Cyan,
            background = MeikoColors.Bg0,
            surface = MeikoColors.Bg1,
            onPrimary = Color.White,
            onBackground = MeikoColors.Text0,
            onSurface = MeikoColors.Text0,
            error = MeikoColors.Danger,
        )
    } else {
        lightColorScheme(
            primary = MeikoColors.Violet,
            secondary = MeikoColors.Cyan,
            background = MeikoColors.Bg0,
            surface = MeikoColors.Bg1,
            onPrimary = Color.White,
            onBackground = MeikoColors.Text0,
            onSurface = MeikoColors.Text0,
            error = MeikoColors.Danger,
        )
    }
    MaterialTheme(
        colorScheme = scheme,
        typography = MaterialTheme.typography,
        content = content,
    )
}
