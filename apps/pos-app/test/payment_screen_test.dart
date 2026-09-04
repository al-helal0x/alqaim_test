// PKG-D2 — Widget tests: PaymentScreen.
//
// نطاق: عرض ملخّص الفاتورة (عميل/بنود/مجموع)، تحديث الإجمالي فعلياً عند
// تعديل حقل الخصم، ونجاح/فشل `PosRepository.createDraftSale()` عبر زر
// "تأكيد الدفع" (بمزيّفات fake — بلا قاعدة drift حقيقية ولا شبكة).
//
// اختبار مسار النجاح الكامل يحتاج مكدّس Navigator بعمق ≥3 (الشاشة تستدعي
// `Navigator.pop()` مرتين + `ScaffoldMessenger.of(context)` بعدهما مباشرة
// — نفس نمط استدعاء السلة الفعلي لهذه الشاشة عبر `MaterialPageRoute`)،
// لذا بُني مضيف صغير يحاكي هذا العمق بدل استضافة PaymentScreen وحدها.
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pos_app/core/auth/session_storage.dart';
import 'package:pos_app/core/auth/tenant_context.dart';
import 'package:pos_app/core/di/providers.dart';
import 'package:pos_app/data/local/app_database.dart';
import 'package:pos_app/data/models/catalog_dto.dart';
import 'package:pos_app/data/models/partner_dto.dart';
import 'package:pos_app/data/models/pos_sync_dto.dart';
import 'package:pos_app/data/repositories/pos_repository.dart';
import 'package:pos_app/features/pos/presentation/controllers/cart_controller.dart';
import 'package:pos_app/features/pos/presentation/screens/payment_screen.dart';

class _FakeSessionStorage extends SessionStorage {
  _FakeSessionStorage(this._tenantContext);

  final TenantContext? _tenantContext;

  @override
  Future<TenantContext?> readTenantContext() async => _tenantContext;
}

/// PosRepository مزيّف — يتجاوز createDraftSale() فقط، ويسجّل آخر معاملات
/// استُدعيت بها للتحقق منها لاحقاً.
class _FakePosRepository extends PosRepository {
  _FakePosRepository(this._behavior)
      : super(database: AppDatabase.forTesting(NativeDatabase.memory()));

  final Future<String> Function({
    required TenantContext tenantContext,
    required String partnerId,
    required List<PosSaleLineDto> lines,
    required double discountAmount,
  }) _behavior;

  TenantContext? lastTenantContext;
  String? lastPartnerId;
  List<PosSaleLineDto>? lastLines;
  double? lastDiscountAmount;

  @override
  Future<String> createDraftSale({
    required TenantContext tenantContext,
    required String partnerId,
    required List<PosSaleLineDto> lines,
    String currency = 'IQD',
    double discountAmount = 0,
  }) {
    lastTenantContext = tenantContext;
    lastPartnerId = partnerId;
    lastLines = lines;
    lastDiscountAmount = discountAmount;
    return _behavior(
      tenantContext: tenantContext,
      partnerId: partnerId,
      lines: lines,
      discountAmount: discountAmount,
    );
  }
}

const _tenant = TenantContext(companyId: 'c1', userId: 'u1', branchId: 'b1');
const _product = ProductDto(
  id: 'p1',
  sku: 'SKU-1',
  name: 'قهوة عربية',
  salePrice: 3000,
  trackInventory: false,
  isActive: true,
);
const _partner = PartnerDto(id: 'c1', name: 'أحمد محمد');

List<Override> _overrides(_FakePosRepository fakeRepo) => [
      sessionStorageProvider.overrideWithValue(_FakeSessionStorage(_tenant)),
      posRepositoryProvider.overrideWithValue(fakeRepo),
      cartControllerProvider.overrideWith(
        (ref) => CartController()
          ..addProduct(_product)
          ..selectPartner(_partner),
      ),
    ];

/// مضيف بعمق مكدّس 3 (Home → Sale placeholder → Payment) — يحاكي كيف
/// تصل PaymentScreen فعلياً في التطبيق الحقيقي (مدفوعة من SaleScreen).
Widget _navigationHost(List<Override> overrides) {
  return ProviderScope(
    overrides: overrides,
    child: MaterialApp(
      home: Directionality(
        textDirection: TextDirection.rtl,
        child: Builder(
          builder: (context) => Scaffold(
            body: Center(
              child: ElevatedButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (context) => Scaffold(
                      body: Center(
                        child: ElevatedButton(
                          onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => const PaymentScreen(sessionId: 's1'),
                            ),
                          ),
                          child: const Text('افتح الدفع'),
                        ),
                      ),
                    ),
                  ),
                ),
                child: const Text('افتح البيع'),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

Widget _directHost(List<Override> overrides) {
  return ProviderScope(
    overrides: overrides,
    child: const MaterialApp(
      home: Directionality(
        textDirection: TextDirection.rtl,
        child: PaymentScreen(sessionId: 's1'),
      ),
    ),
  );
}

void main() {
  group('PaymentScreen', () {
    testWidgets('تعرض ملخّص الفاتورة الصحيح (عميل/بنود/مجموع)', (tester) async {
      final fakeRepo = _FakePosRepository(
        ({required tenantContext, required partnerId, required lines, required discountAmount}) async => 'sale-1',
      );

      await tester.pumpWidget(_directHost(_overrides(fakeRepo)));
      await tester.pump();

      expect(find.text('أحمد محمد'), findsOneWidget);
      expect(find.text('1'), findsOneWidget); // عدد البنود
      expect(find.text('3000.00 IQD'), findsWidgets); // المجموع الفرعي والإجمالي معاً (خصم=0)
    });

    testWidgets('تعديل حقل الخصم يُحدِّث الإجمالي المستحق فعلياً', (tester) async {
      final fakeRepo = _FakePosRepository(
        ({required tenantContext, required partnerId, required lines, required discountAmount}) async => 'sale-1',
      );

      await tester.pumpWidget(_directHost(_overrides(fakeRepo)));
      await tester.pump();

      await tester.enterText(find.widgetWithText(TextField, 'الخصم'), '500');
      await tester.pump();

      expect(find.text('2500.00 IQD'), findsOneWidget); // الإجمالي بعد الخصم
      expect(find.text('3000.00 IQD'), findsOneWidget); // المجموع الفرعي يبقى كما هو
    });

    testWidgets('يعرض رسالة خطأ عند فشل حفظ البيع محلياً ولا يترك تحميلاً عالقاً',
        (tester) async {
      final fakeRepo = _FakePosRepository(
        ({required tenantContext, required partnerId, required lines, required discountAmount}) async {
          throw Exception('local db write failed');
        },
      );

      await tester.pumpWidget(_directHost(_overrides(fakeRepo)));
      await tester.pump();

      await tester.tap(find.widgetWithText(ElevatedButton, 'تأكيد الدفع'));
      await tester.pumpAndSettle();

      expect(find.text('تعذّر حفظ عملية البيع محلياً — حاول مجدداً'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets(
        'تأكيد الدفع الناجح يستدعي PosRepository.createDraftSale بالمعاملات '
        'الصحيحة، ويُفرِغ السلة، ويعود للشاشة السابقة', (tester) async {
      final fakeRepo = _FakePosRepository(
        ({required tenantContext, required partnerId, required lines, required discountAmount}) async => 'sale-1',
      );

      await tester.pumpWidget(_navigationHost(_overrides(fakeRepo)));
      await tester.pump();

      await tester.tap(find.text('افتح البيع'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('افتح الدفع'));
      await tester.pumpAndSettle();

      expect(find.text('الدفع'), findsOneWidget); // عنوان الشاشة (AppBar)
      expect(find.text('تأكيد الدفع'), findsOneWidget); // زر التأكيد

      await tester.tap(find.widgetWithText(ElevatedButton, 'تأكيد الدفع'));
      await tester.pumpAndSettle();

      expect(fakeRepo.lastTenantContext, _tenant);
      expect(fakeRepo.lastPartnerId, 'c1');
      expect(fakeRepo.lastDiscountAmount, 0);
      expect(fakeRepo.lastLines, hasLength(1));
      expect(fakeRepo.lastLines!.first.productId, 'p1');
      expect(fakeRepo.lastLines!.first.unitPrice, 3000);

      // بعد النجاح: pop مرتين تعيدنا لشاشة "افتح البيع"، والسلة أُفرِغت.
      expect(find.text('افتح البيع'), findsOneWidget);
      expect(find.text('تم حفظ البيع — سيُزامَن تلقائياً عند توفر الاتصال'),
          findsOneWidget);
    });
  });
}
