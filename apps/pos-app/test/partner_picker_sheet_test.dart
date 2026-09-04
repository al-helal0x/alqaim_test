// PKG-D2 — Widget tests: PartnerPickerSheet (partner_picker_sheet.dart).
//
// نطاق مقصود ومحدود: نغطي فقط سلوك fallback الكاش المحلي عند فشل تحميل
// قائمة العملاء الحي — بنفس منطق product_picker_sheet_test.dart تماماً.
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pos_app/core/di/providers.dart';
import 'package:pos_app/core/network/api_client.dart';
import 'package:pos_app/data/local/app_database.dart';
import 'package:pos_app/data/models/partner_dto.dart';
import 'package:pos_app/data/repositories/catalog_remote_data_source.dart';
import 'package:pos_app/data/repositories/catalog_repository.dart';
import 'package:pos_app/data/repositories/partners_remote_data_source.dart';
import 'package:pos_app/features/pos/presentation/widgets/partner_picker_sheet.dart';

/// دائماً يفشل (يحاكي انقطاع الاتصال) — بلا أي نداء شبكة حقيقي.
class _ThrowingPartnersRemoteDataSource extends PartnersRemoteDataSource {
  _ThrowingPartnersRemoteDataSource() : super(ApiClient());

  @override
  Future<PartnerPage> listPartners({int page = 1, int pageSize = 200}) async {
    throw Exception('network down');
  }
}

/// CatalogRepository مزيّف — يتجاوز searchLocalPartners() فقط بقائمة
/// ثابتة (راجع تعليق النسخة المطابقة في product_picker_sheet_test.dart).
class _FakeCatalogRepository extends CatalogRepository {
  _FakeCatalogRepository(this._localPartners)
      : super(
          database: AppDatabase.forTesting(NativeDatabase.memory()),
          catalogRemoteDataSource: CatalogRemoteDataSource(ApiClient()),
          partnersRemoteDataSource: _ThrowingPartnersRemoteDataSource(),
        );

  final List<PartnerDto> _localPartners;

  @override
  Future<List<PartnerDto>> searchLocalPartners(String query) async =>
      _localPartners;
}

const _cachedPartner = PartnerDto(id: 'c1', name: 'أحمد محمد');

Future<void> _openSheet(
  WidgetTester tester, {
  required List<PartnerDto> localCacheResults,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        partnersRemoteDataSourceProvider.overrideWithValue(
          _ThrowingPartnersRemoteDataSource(),
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
              onPressed: () => showPartnerPickerSheet(context),
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
  group('PartnerPickerSheet — fallback الكاش المحلي', () {
    testWidgets(
        'يعرض نتائج الكاش المحلي وشريط "غير متصل" عند فشل التحميل الحي',
        (tester) async {
      await _openSheet(tester, localCacheResults: const [_cachedPartner]);

      expect(find.text('أحمد محمد'), findsOneWidget);
      expect(find.byIcon(Icons.wifi_off), findsOneWidget);
      expect(
        find.textContaining('غير متصل — نتائج من آخر نسخة محفوظة محلياً'),
        findsOneWidget,
      );
    });

    testWidgets(
        'الفلترة النصية المحلية تعمل فوق نتائج الكاش أيضاً',
        (tester) async {
      await _openSheet(
        tester,
        localCacheResults: const [
          _cachedPartner,
          PartnerDto(id: 'c2', name: 'سارة علي'),
        ],
      );

      expect(find.text('أحمد محمد'), findsOneWidget);
      expect(find.text('سارة علي'), findsOneWidget);

      await tester.enterText(find.byType(TextField), 'سارة');
      await tester.pump();

      expect(find.text('أحمد محمد'), findsNothing);
      expect(find.text('سارة علي'), findsOneWidget);
    });

    testWidgets(
        'يعرض رسالة الخطأ الاعتيادية عندما يكون الكاش المحلي فارغاً أيضاً',
        (tester) async {
      await _openSheet(tester, localCacheResults: const []);

      expect(
        find.text('تعذّر تحميل قائمة العملاء — تحقق من الاتصال'),
        findsOneWidget,
      );
      expect(
        find.textContaining('غير متصل — نتائج من آخر نسخة'),
        findsNothing,
      );
    });
  });
}
