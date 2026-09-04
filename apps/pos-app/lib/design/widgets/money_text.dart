import 'package:flutter/material.dart';

/// عرض موحّد للمبالغ — تنسيق بسيط بلا مكتبة intl إضافية (لا حاجة فعلية
/// لتنسيق أرقام معقّد؛ فاصلة عشرية ثابتة كافية لعملة IQD/USD في POS).
/// العملة نص حر (يطابق `PosSaleRequest.currency`، افتراضي 'IQD').
class MoneyText extends StatelessWidget {
  const MoneyText(
    this.amount, {
    super.key,
    this.currency = 'IQD',
    this.style,
    this.color,
  });

  final double amount;
  final String currency;
  final TextStyle? style;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final formatted = amount.toStringAsFixed(2);
    return Text(
      '$formatted $currency',
      style: (style ?? Theme.of(context).textTheme.titleMedium)?.copyWith(
        color: color,
        fontFeatures: const [FontFeature.tabularFigures()],
      ),
    );
  }
}
