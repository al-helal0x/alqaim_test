// PKG-D2 — Widget tests: ProductPickerSheet (product_picker_sheet.dart).
//
// نطاق مقصود ومحدود: نغطي فقط سلوك fallback الكاش المحلي عند فشل البحث
// الحي — الحالتان: 1) الكاش يحوي نتائج (تُعرض + شريط "غير متصل")، 2)
// الكاش فارغ أيضاً (رسالة الخطأ الاعتيادية). **لا نختبر مسار النجاح
// الحي الفعلي عبر شبكة حقيقية** — خارج نطاق هذا الملف، ولا حاجة له هنا
// (بحث حي مغطى ضمنياً بكون الكود نفسه بسيطاً ومباشراً: نداء واحد + معالجة
// النتيجة، والقيمة المضافة هنا تحديداً هي سلوك الـ fallback الجديد).
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pos_app/core/di/providers.dart';
import 'package:pos_app/core/network/api_client.dart';
import 'package:pos_app/data/local/app_database.dart';
import 'package:pos_app/data/models/catalog_dto.dart';
import 'package:pos_app/data/repositories/catalog_remote_data_source.dart';
import 'package:pos_app/data/repositories/catalog_repository.dart';
import 'package:pos_app/data/repositories/partners_remote_data_source.dart';
import 'package:pos_app/features/pos/presentation/widgets/product_picker_sheet.dart';

/// دائماً يفشل (يحاكي انقطاع الاتصال) — بلا أي نداء شبكة حقيقي فعلياً
/// (الاستثناء يُرمى مباشرة قبل أي لمسة لـ ApiClient.dio).
class _ThrowingCatalogRemoteDataSource extends CatalogRemoteDataSource {
  _ThrowingCatalogRemoteDataSource() : super(ApiClient());

  @override
  Future<ProductPage> searchProducts({
    String? search,
    int page = 1,
    int pageSize = 30,
  }) async {
    throw Exception('network down');
  }
}

/// CatalogRepository مزيّف — يتجاوز searchLocalProducts() فقط بقائمة
/// ثابتة. المُنشئ الأصلي يتطلب AppDatabase/CatalogRemoteDataSource/
/// PartnersRemoteDataSource حقيقية النوع (لا nullable)، لذا نمرّر نسخاً
/// "بلا تأثير فعلي" (قاعدة بيانات بالذاكرة لا تُفتح إلا عند استعلام حقيقي،
/// ومصدرا بيانات عبر ApiClient() لا يُجريان أي نداء ما لم تُستدعى طرقهما
/// صراحةً — وهي جميعاً مُتجاوَزة أو غير مُستخدَمة هنا).
class _FakeCatalogRepository extends CatalogRepository {
  _FakeCatalogRepository(this._localProducts)
      : super(
          database: AppDatabase.forTesting(NativeDatabase.memory()),
          catalogRemoteDataSource: _ThrowingCatalogRemoteDataSource(),
          partnersRemoteDataSource: PartnersRemoteDataSource(ApiClient()),
        );

  final List<ProductDto> _localProducts;

  @override
  Future<List<ProductDto>> searchLocalProducts(String query) async =>
      _localProducts;
}

const _cachedProduct = ProductDto(
  id: 'p1',
  sku: 'SKU-1',
  name: 'قهوة عربية',
  salePrice: 3000,
  trackInventory: false,
  isActive: true,
);

Future<void> _openSheet(
  WidgetTester tester, {
  required List<ProductDto> localCacheResults,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        catalogRemoteDataSourceProvider.overrideWithValue(
          _ThrowingCatalogRemoteDataSource(),
        ),
        catalogRepositoryProvider.overrideWithValue(
          _FakeCatalogRepository(localCacheResults),
        ),
      ],
      child: MaterialApp(
        home: Directionality(
          textDirection: TextDirection.rtl,
          child: Builder(
            builder: (context) => ElevatedButton(
              onPressed: () => showProductPickerSheet(context),
              child: const Text('افتح المنتقي'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('افتح المنتقي'));
  await tester.pumpAndSettle();
}

void main() {
  group('ProductPickerSheet — fallback الكاش المحلي', () {
    testWidgets(
        'يعرض نتائج الكاش المحلي وشريط "غير متصل" عند فشل البحث الحي',
        (tester) async {
      await _openSheet(tester, localCacheResults: const [_cachedProduct]);

      expect(find.text('قهوة عربية'), findsOneWidget);
      expect(find.byIcon(Icons.wifi_off), findsOneWidget);
      expect(
        find.textContaining('غير متصل — نتائج من آخر نسخة محفوظة محلياً'),
        findsOneWidget,
      );
    });

    testWidgets(
        'يعرض رسالة الخطأ الاعتيادية عندما يكون الكاش المحلي فارغاً أيضاً',
        (tester) async {
      await _openSheet(tester, localCacheResults: const []);

      expect(
        find.text('تعذّر البحث عن المنتجات — تحقق من الاتصال'),
        findsOneWidget,
      );
      expect(find.byIcon(Icons.wifi_off), findsOneWidget); // أيقونة PosEmptyState
      expect(
        find.textContaining('غير متصل — نتائج من آخر نسخة'),
        findsNothing,
      );
    });
  });
}
