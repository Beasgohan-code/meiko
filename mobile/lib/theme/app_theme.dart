import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Meiko App — shared design tokens, mirroring the web app's dark
/// violet/cyan aesthetic.
class MeikoColors {
  static const bg0 = Color(0xFF060613);
  static const bg1 = Color(0xFF0B0B1C);
  static const bg2 = Color(0xFF12122A);
  static const panel = Color(0xCC141428);
  static const border = Color(0x2A8C82FF);
  static const violet = Color(0xFF7C5CFF);
  static const violetSoft = Color(0xFFA78BFA);
  static const cyan = Color(0xFF22D3EE);
  static const text0 = Color(0xFFF4F3FF);
  static const text1 = Color(0xFFB9B6D6);
  static const text2 = Color(0xFF7C7893);
  static const danger = Color(0xFFFF6B6B);
  static const success = Color(0xFF4ADE80);
}

ThemeData buildMeikoTheme() {
  final base = ThemeData.dark(useMaterial3: true);
  return base.copyWith(
    scaffoldBackgroundColor: MeikoColors.bg0,
    primaryColor: MeikoColors.violet,
    colorScheme: base.colorScheme.copyWith(
      primary: MeikoColors.violet,
      secondary: MeikoColors.cyan,
      surface: MeikoColors.bg1,
      error: MeikoColors.danger,
    ),
    textTheme: GoogleFonts.interTextTheme(base.textTheme).apply(
      bodyColor: MeikoColors.text0,
      displayColor: MeikoColors.text0,
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      elevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardTheme(
      color: MeikoColors.panel,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: MeikoColors.border),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white.withOpacity(0.04),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: MeikoColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: MeikoColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: MeikoColors.violet),
      ),
    ),
  );
}

LinearGradient meikoGradient() => const LinearGradient(
      colors: [MeikoColors.violet, MeikoColors.cyan],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    );
