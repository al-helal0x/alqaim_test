import 'package:flutter/material.dart';

import '../tokens.dart';

/// حالة فارغة موحّدة (بلا نتائج بحث، سلة فارغة، ...).
class PosEmptyState extends StatelessWidget {
  const PosEmptyState({
    super.key,
    required this.icon,
    required this.message,
    this.action,
  });

  final IconData icon;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(PosSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 56, color: PosColors.textSecondary),
            const SizedBox(height: PosSpacing.md),
            Text(
              message,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            if (action != null) ...[
              const SizedBox(height: PosSpacing.md),
              action!,
            ],
          ],
        ),
      ),
    );
  }
}
