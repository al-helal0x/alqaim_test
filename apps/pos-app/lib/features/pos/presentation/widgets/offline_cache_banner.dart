import 'package:flutter/material.dart';

import '../../../../design/tokens.dart';

/// شريط تنبيه صغير يظهر أعلى نتائج البحث عندما تكون قادمة من الكاش
/// المحلي (لا اتصال حالياً) بدل البحث الحي — راجع تعليقي
/// CatalogRepository و product_picker_sheet.dart/partner_picker_sheet.dart.
class OfflineCacheBanner extends StatelessWidget {
  const OfflineCacheBanner({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: PosSpacing.md,
        vertical: PosSpacing.sm,
      ),
      decoration: BoxDecoration(
        color: PosColors.warning.withOpacity(0.1),
        borderRadius: BorderRadius.circular(PosRadii.sm),
      ),
      child: const Row(
        children: [
          Icon(Icons.wifi_off, size: 16, color: PosColors.warning),
          SizedBox(width: PosSpacing.xs),
          Expanded(
            child: Text(
              'غير متصل — نتائج من آخر نسخة محفوظة محلياً، قد لا تكون محدَّثة',
              style: TextStyle(fontSize: 12, color: PosColors.textSecondary),
            ),
          ),
        ],
      ),
    );
  }
}
