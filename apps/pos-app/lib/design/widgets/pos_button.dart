import 'package:flutter/material.dart';

import '../tokens.dart';

enum PosButtonVariant { primary, secondary, danger }

/// زر موحّد بأحجام لمس كافية لتابلت كاشير (راجع [PosTouchTargets.button]).
class PosButton extends StatelessWidget {
  const PosButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.variant = PosButtonVariant.primary,
    this.icon,
    this.loading = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final PosButtonVariant variant;
  final IconData? icon;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    final child = loading
        ? const SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(strokeWidth: 2.4),
          )
        : Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: 20),
                const SizedBox(width: PosSpacing.sm),
              ],
              Text(label),
            ],
          );

    final effectiveOnPressed = loading ? null : onPressed;

    switch (variant) {
      case PosButtonVariant.primary:
        return ElevatedButton(
          onPressed: effectiveOnPressed,
          style: ElevatedButton.styleFrom(
            backgroundColor: PosColors.primary,
            foregroundColor: Colors.white,
          ),
          child: child,
        );
      case PosButtonVariant.secondary:
        return OutlinedButton(
          onPressed: effectiveOnPressed,
          style: OutlinedButton.styleFrom(
            minimumSize: const Size.fromHeight(PosTouchTargets.button),
            foregroundColor: PosColors.primary,
            side: const BorderSide(color: PosColors.primary),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(PosRadii.sm),
            ),
          ),
          child: child,
        );
      case PosButtonVariant.danger:
        return ElevatedButton(
          onPressed: effectiveOnPressed,
          style: ElevatedButton.styleFrom(
            backgroundColor: PosColors.danger,
            foregroundColor: Colors.white,
          ),
          child: child,
        );
    }
  }
}
