import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../design/tokens.dart';
import '../../../../design/widgets/empty_state.dart';
import '../../../../design/widgets/money_text.dart';
import '../../../../design/widgets/pos_button.dart';
import '../../../../design/widgets/pos_scaffold.dart';
import '../../../../design/widgets/status_badge.dart';
import '../controllers/cart_controller.dart';
import '../widgets/partner_picker_sheet.dart';
import '../widgets/product_picker_sheet.dart';
import 'close_session_sheet.dart';
import 'payment_screen.dart';

/// الشاشة الرئيسية لنقطة البيع — سلة البيع الحالية للجلسة المفتوحة.
/// البيع نفسه Offline-first بالكامل (راجع PosRepository) — هذه الشاشة لا
/// تحتاج اتصالاً إلا لبحث المنتجات/العملاء (بيانات القراءة)، وليس لإتمام
/// البيع نفسه.
class SaleScreen extends ConsumerWidget {
  const SaleScreen({super.key, required this.sessionId});

  final String sessionId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cart = ref.watch(cartControllerProvider);
    final controller = ref.read(cartControllerProvider.notifier);
    final pendingSyncCount = ref.watch(_pendingSyncCountProvider);

    return PosScaffold(
      title: 'نقطة البيع',
      actions: [
        pendingSyncCount.when(
          data: (count) => count == 0
              ? const SizedBox.shrink()
              : Padding(
                  padding: const EdgeInsets.symmetric(horizontal: PosSpacing.sm),
                  child: Center(
                    child: PosStatusBadge(
                      label: 'بانتظار المزامنة: $count',
                      tone: PosStatusTone.warning,
                    ),
                  ),
                ),
          loading: () => const SizedBox.shrink(),
          error: (_, __) => const SizedBox.shrink(),
        ),
        IconButton(
          icon: const Icon(Icons.logout),
          tooltip: 'إغلاق الجلسة',
          onPressed: () => showCloseSessionSheet(context, ref, sessionId: sessionId),
        ),
      ],
      body: Column(
        children: [
          _PartnerBar(
            partnerName: cart.partner?.name,
            onTap: () async {
              final partner = await showPartnerPickerSheet(context);
              if (partner != null) controller.selectPartner(partner);
            },
          ),
          const Divider(height: 1),
          Expanded(
            child: cart.isEmpty
                ? PosEmptyState(
                    icon: Icons.shopping_cart_outlined,
                    message: 'السلة فارغة — أضف منتجاً للبدء',
                  )
                : ListView.separated(
                    padding: const EdgeInsets.symmetric(vertical: PosSpacing.sm),
                    itemCount: cart.lines.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final line = cart.lines[index];
                      return _CartLineTile(
                        line: line,
                        onQuantityChanged: (q) => controller.updateQuantity(index, q),
                        onRemove: () => controller.removeLine(index),
                      );
                    },
                  ),
          ),
          _CartSummaryBar(
            cart: cart,
            onAddProduct: () async {
              final product = await showProductPickerSheet(context);
              if (product != null) controller.addProduct(product);
            },
            onPay: cart.isEmpty || cart.partner == null
                ? null
                : () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => PaymentScreen(sessionId: sessionId),
                      ),
                    ),
          ),
        ],
      ),
    );
  }
}

final _pendingSyncCountProvider = StreamProvider.autoDispose((ref) {
  return ref.watch(posRepositoryProvider).watchPendingSyncCount();
});

class _PartnerBar extends StatelessWidget {
  const _PartnerBar({required this.partnerName, required this.onTap});

  final String? partnerName;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: const Icon(Icons.person_outline, color: PosColors.primary),
      title: Text(partnerName ?? 'اختر عميلاً'),
      subtitle: partnerName == null
          ? const Text('مطلوب قبل الدفع', style: TextStyle(color: PosColors.textSecondary))
          : null,
      trailing: const Icon(Icons.chevron_left),
      onTap: onTap,
    );
  }
}

class _CartLineTile extends StatelessWidget {
  const _CartLineTile({
    required this.line,
    required this.onQuantityChanged,
    required this.onRemove,
  });

  final CartLine line;
  final ValueChanged<double> onQuantityChanged;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(line.product.name),
      subtitle: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.remove_circle_outline, size: 20),
            onPressed: () => onQuantityChanged(line.quantity - 1),
            visualDensity: VisualDensity.compact,
          ),
          Text('${line.quantity.toStringAsFixed(line.quantity.truncateToDouble() == line.quantity ? 0 : 2)}'),
          IconButton(
            icon: const Icon(Icons.add_circle_outline, size: 20),
            onPressed: () => onQuantityChanged(line.quantity + 1),
            visualDensity: VisualDensity.compact,
          ),
          const SizedBox(width: PosSpacing.sm),
          Text('× ${line.unitPrice.toStringAsFixed(2)}',
              style: const TextStyle(color: PosColors.textSecondary)),
        ],
      ),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          MoneyText(line.lineTotal, style: Theme.of(context).textTheme.bodyMedium),
          IconButton(
            icon: const Icon(Icons.delete_outline, color: PosColors.danger),
            onPressed: onRemove,
          ),
        ],
      ),
    );
  }
}

class _CartSummaryBar extends StatelessWidget {
  const _CartSummaryBar({
    required this.cart,
    required this.onAddProduct,
    required this.onPay,
  });

  final CartState cart;
  final VoidCallback onAddProduct;
  final VoidCallback? onPay;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(PosSpacing.md),
      decoration: const BoxDecoration(
        color: PosColors.surface,
        border: Border(top: BorderSide(color: PosColors.border)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: PosButton(
                  label: 'إضافة منتج',
                  icon: Icons.add_shopping_cart,
                  variant: PosButtonVariant.secondary,
                  onPressed: onAddProduct,
                ),
              ),
            ],
          ),
          const SizedBox(height: PosSpacing.md),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('الإجمالي', style: Theme.of(context).textTheme.titleMedium),
              MoneyText(cart.total, style: Theme.of(context).textTheme.headlineSmall),
            ],
          ),
          const SizedBox(height: PosSpacing.md),
          PosButton(label: 'الدفع', icon: Icons.payments_outlined, onPressed: onPay),
        ],
      ),
    );
  }
}
