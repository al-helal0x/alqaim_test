import 'package:flutter/material.dart';

import 'tokens.dart';

/// يبني ThemeData من [PosColors]/[PosSpacing] — نقطة التجميع الوحيدة بين
/// الرموز الخام (tokens) ومكوّنات Material التي تُبنى المكوّنات المخصّصة
/// (design/widgets/) فوقها.
class PosTheme {
  PosTheme._();

  static ThemeData light() {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: PosColors.primary,
      primary: PosColors.primary,
      surface: PosColors.surface,
      error: PosColors.danger,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: PosColors.surfaceAlt,
      textTheme: _textTheme,
      appBarTheme: const AppBarTheme(
        backgroundColor: PosColors.surface,
        foregroundColor: PosColors.textPrimary,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: PosColors.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(PosRadii.md),
          side: const BorderSide(color: PosColors.border),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: PosColors.surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(PosRadii.sm),
          borderSide: const BorderSide(color: PosColors.border),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: PosSpacing.md,
          vertical: PosSpacing.sm,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          minimumSize: const Size.fromHeight(PosTouchTargets.button),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(PosRadii.sm),
          ),
        ),
      ),
    );
  }

  static const _textTheme = TextTheme(
    headlineSmall: TextStyle(
      fontSize: 22,
      fontWeight: FontWeight.w700,
      color: PosColors.textPrimary,
    ),
    titleMedium: TextStyle(
      fontSize: 16,
      fontWeight: FontWeight.w600,
      color: PosColors.textPrimary,
    ),
    bodyMedium: TextStyle(fontSize: 14, color: PosColors.textPrimary),
    bodySmall: TextStyle(fontSize: 12, color: PosColors.textSecondary),
  );
}
