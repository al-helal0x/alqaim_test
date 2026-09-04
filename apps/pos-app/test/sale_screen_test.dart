// PKG-D2 — Widget tests: SaleScreen.
//
// نطاق مقصود ومحدود: نغطي عرض حالة السلة (فارغة/بها بنود)، شارة "بانتظار
// المزامنة"، وتفعيل/تعطيل زر "الدفع" بناءً على وجود بنود وعميل مُختار —
// وهو بالضبط السلوك **الموجود فعلياً في الكود الآن** (لا "عميل نقدي
// افتراضي" — راجع تعليق PosRepository.createDraftSale). **لا نختبر فتح
// منتقي المنتج/العميل (`showProductPickerSheet`/`showPartnerPickerSheet`)
// ولا الانتقال الفعلي لشاشة الدفع** — هذان جزء من تدفّق أعمق (بيانات
// كتالوج/شركاء عبر شبكة) خارج "الجزء البسيط" هنا.
//
// ⚠️ ملاحظة صريحة (نفس تحذير 00_TASK_PACKAGE.md): تفعيل زر "الدفع" هنا
// يشترط عميلاً مُختاراً صراحة لأن "عميل نقدي" (walk-in) **غير موجود بعد**
// في الكود (PKG-B3 لم يُنجَز). إن أضافت PKG-B3 مفهوم عميل نقدي افتراضي،
// فسلوك هذا الاختبار (الزر يبقى معطَّلاً بلا عميل) قد يحتاج مراجعة صريحة
// وقتها — موثَّق هنا كتحذير استباقي لا كافتراض حالي خاطئ.
import 'dart:async';

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pos_app/core/di/providers.dart';
import 'package:pos_app/data/local/app_database.dart';
import 'package:pos_app/data/models/catalog_dto.dart';
import 'package:pos_app/data/models/partner_dto.dart';
import 'package:pos_app/data/repositories/pos_repository.dart';
import 'package:pos_app/design/widgets/pos_button.dart';
import 'package:pos_app/features/pos/presentation/controllers/cart_controller.dart';
import 'package:pos_app/features/pos/presentation/screens/sale_screen.dart';

/// PosRepository مزيّف — يتجاوز watchPendingSyncCount() فقط، بلا أي لمسة
/// فعلية لقاعدة drift (AppDatabase() تُبنى هنا بلا فتح اتصال فعلي —
/// LazyDatabase لا يفتح الملف إلا عند أول استعلام حقيقي، وهو ما لا يحدث).
class _FakePosRepository extends PosRepository {
  _FakePosRepository(this._pendingCount)
      : super(database: AppDatabase.forTesting(NativeDatabase.memory()));

  final Stream<int> _pendingCount;

  @override
  Stream<int> watchPendingSyncCount() => _pendingCount;
}

const _product = ProductDto(
  id: 'p1',
  sku: 'SKU-1',
  name: 'قهوة عربية',
  salePrice: 3000,
  trackInventory: false,
  isActive: true,
);

const _partner = PartnerDto(id: 'c1', name: 'أحمد محمد');

Widget _wrap({
  required CartController Function() cartController,
  Stream<int>? pendingSyncCount,
}) {
  return ProviderScope(
    overrides: [
      cartControllerProvider.overrideWith((ref) => cartController()),
      posRepositoryProvider.overrideWithValue(
        _FakePosRepository(pendingSyncCount ?? const Stream<int>.empty()),
      ),
    ],
    child: const MaterialApp(
      home: Directionality(
        textDirection: TextDirection.rtl,
        child: SaleScreen(sessionId: 's1'),
      ),
    ),
  );
}

void main() {
  group('SaleScreen', () {
    testWidgets('سلة فارغة: تُعرض رسالة واضحة وزر الدفع معطَّل', (tester) async {
      await tester.pumpWidget(_wrap(cartController: () => CartController()));
      await tester.pump();

      expect(find.text('السلة فارغة — أضف منتجاً للبدء'), findsOneWidget);
      expect(find.text('اختر عميلاً'), findsOneWidget);

      final payButton = find.widgetWithText(PosButton, 'الدفع');
      expect(payButton, findsOneWidget);
      expect(tester.widget<PosButton>(payButton).onPressed, isNull);
    });

    testWidgets('سلة بها بند وعميل مُختار: تُعرض البنود ويُفعَّل زر الدفع',
        (tester) async {
      await tester.pumpWidget(_wrap(
        cartController: () => CartController()
          ..addProduct(_product)
          ..selectPartner(_partner),
      ));
      await tester.pump();

      expect(find.text('قهوة عربية'), findsOneWidget);
      expect(find.text('أحمد محمد'), findsOneWidget);
      expect(find.text('3000.00 IQD'), findsWidgets); // الإجمالي = سعر الوحدة × 1

      final payButton = find.widgetWithText(PosButton, 'الدفع');
      expect(tester.widget<PosButton>(payButton).onPressed, isNotNull);
    });

    testWidgets('زر الدفع يبقى معطَّلاً ببند بلا عميل (السلوك الحالي المؤكَّد)',
        (tester) async {
      await tester.pumpWidget(_wrap(
        cartController: () => CartController()..addProduct(_product),
      ));
      await tester.pump();

      final payButton = find.widgetWithText(PosButton, 'الدفع');
      expect(tester.widget<PosButton>(payButton).onPressed, isNull);
    });

    testWidgets('يعرض شارة "بانتظار المزامنة" عند وجود عمليات معلَّقة',
        (tester) async {
      await tester.pumpWidget(_wrap(
        cartController: () => CartController(),
        pendingSyncCount: Stream.value(3),
      ));
      await tester.pump();
      await tester.pump(); // استقرار StreamProvider

      expect(find.textContaining('بانتظار المزامنة: 3'), findsOneWidget);
    });
  });
}
