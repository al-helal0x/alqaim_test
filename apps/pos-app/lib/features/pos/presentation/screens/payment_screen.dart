import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../data/models/pos_sync_dto.dart';
import '../../../../design/tokens.dart';
import '../../../../design/widgets/money_text.dart';
import '../../../../design/widgets/pos_button.dart';
import '../../../../design/widgets/pos_scaffold.dart';
import '../../../../design/widgets/pos_text_field.dart';
import '../controllers/cart_controller.dart';

/// شاشة تأكيد الدفع — تُنشئ الفاتورة محلياً فوراً عبر
/// `PosRepository.createDraftSale` (Offline-first بالكامل: لا انتظار شبكة
/// هنا، البيع يُخزَّن ويُضاف لطابور المزامنة حتى لو الجهاز غير متصل تماماً).
class PaymentScreen extends ConsumerStatefulWidget {
  const PaymentScreen({super.key, required this.sessionId});

  final String sessionId;

  @override
  ConsumerState<PaymentScreen> createState() => _PaymentScreenState();
}

class _PaymentScreenState extends ConsumerState<PaymentScreen> {
  final _discountController = TextEditingController(text: '0');
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _discountController.dispose();
    super.dispose();
  }

  Future<void> _confirm(CartState cart) async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final tenantContext = await ref.read(tenantContextProvider.future);
      if (tenantContext == null) {
        throw StateError('لا توجد جلسة دخول صالحة');
      }

      await ref.read(posRepositoryProvider).createDraftSale(
            tenantContext: tenantContext,
            partnerId: cart.partner!.id,
            discountAmount: cart.discountAmount,
            lines: cart.lines
                .map((l) => PosSaleLineDto(
                      productId: l.product.id,
                      quantity: l.quantity,
                      unitPrice: l.unitPrice,
                    ))
                .toList(),
          );

      if (!mounted) return;
      ref.read(cartControllerProvider.notifier).reset();
      Navigator.of(context)
        ..pop() // شاشة الدفع
        ..pop(); // العودة لشاشة السلة (السلة الآن فارغة)
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('تم حفظ البيع — سيُزامَن تلقائياً عند توفر الاتصال')),
      );
    } catch (_) {
      setState(() => _error = 'تعذّر حفظ عملية البيع محلياً — حاول مجدداً');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cart = ref.watch(cartControllerProvider);

    return PosScaffold(
      title: 'الدفع',
      body: Padding(
        padding: const EdgeInsets.all(PosSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(PosSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _SummaryRow(label: 'العميل', value: cart.partner?.name ?? '—'),
                    const SizedBox(height: PosSpacing.sm),
                    _SummaryRow(label: 'عدد البنود', value: '${cart.lines.length}'),
                    const SizedBox(height: PosSpacing.sm),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('المجموع الفرعي'),
                        MoneyText(cart.subtotal),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: PosSpacing.md),
            PosTextField(
              controller: _discountController,
              label: 'الخصم',
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              onChanged: (v) {
                final amount = double.tryParse(v) ?? 0;
                ref.read(cartControllerProvider.notifier).setDiscount(amount);
              },
            ),
            const SizedBox(height: PosSpacing.lg),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('الإجمالي المستحق', style: Theme.of(context).textTheme.titleMedium),
                MoneyText(cart.total, style: Theme.of(context).textTheme.headlineSmall),
              ],
            ),
            if (_error != null) ...[
              const SizedBox(height: PosSpacing.md),
              Text(_error!, style: const TextStyle(color: PosColors.danger)),
            ],
            const Spacer(),
            PosButton(
              label: 'تأكيد الدفع',
              icon: Icons.check_circle_outline,
              loading: _submitting,
              onPressed: () => _confirm(cart),
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  const _SummaryRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: PosColors.textSecondary)),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
      ],
    );
  }
}
