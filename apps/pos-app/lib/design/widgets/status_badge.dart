import 'package:flutter/material.dart';

import '../tokens.dart';

enum PosStatusTone { neutral, success, warning, danger }

/// شارة نصية صغيرة (حالة مزامنة، حالة جلسة، ...).
class PosStatusBadge extends StatelessWidget {
  const PosStatusBadge({
    super.key,
    required this.label,
    this.tone = PosStatusTone.neutral,
  });

  final String label;
  final PosStatusTone tone;

  Color get _color {
    switch (tone) {
      case PosStatusTone.neutral:
        return PosColors.textSecondary;
      case PosStatusTone.success:
        return PosColors.success;
      case PosStatusTone.warning:
        return PosColors.warning;
      case PosStatusTone.danger:
        return PosColors.danger;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _color;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: PosSpacing.sm,
        vertical: PosSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(PosRadii.sm),
      ),
      child: Text(
        label,
        style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 12),
      ),
    );
  }
}
