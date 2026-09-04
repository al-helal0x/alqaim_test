import 'package:flutter/material.dart';

/// Scaffold موحّد بشريط علوي بسيط — يوفّر مكاناً ثابتاً لعرض شارة حالة
/// المزامنة (راجع SyncStatusBadge) عبر [actions] من كل شاشة POS رئيسية.
class PosScaffold extends StatelessWidget {
  const PosScaffold({
    super.key,
    required this.title,
    required this.body,
    this.actions,
    this.floatingActionButton,
    this.leading,
  });

  final String title;
  final Widget body;
  final List<Widget>? actions;
  final Widget? floatingActionButton;
  final Widget? leading;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: actions,
        leading: leading,
      ),
      body: SafeArea(child: body),
      floatingActionButton: floatingActionButton,
    );
  }
}
