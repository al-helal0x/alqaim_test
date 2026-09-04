// PKG-D2 — Widget tests: OpenSessionScreen.
//
// نطاق مقصود ومحدود: نغطي فقط مسار التحميل الأولي واختيار المستودع
// وتفعيل/تعطيل الزر الرئيسي بناءً عليه، والحقل الأساسي. **لا نستدعي فعلياً
// posSessionRepositoryProvider.openSession()** هنا عمداً — ذلك يتطلب
// appDatabaseProvider (drift/NativeDatabase حقيقية) وهو خارج نطاق "الجزء
// البسيط" المطلوب؛ راجع ملاحظة النطاق في نهاية الملف.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pos_app/core/auth/session_storage.dart';
import 'package:pos_app/core/auth/tenant_context.dart';
import 'package:pos_app/core/di/providers.dart';
import 'package:pos_app/core/network/api_client.dart';
import 'package:pos_app/data/models/warehouse_dto.dart';
import 'package:pos_app/data/repositories/warehouses_remote_data_source.dart';
import 'package:pos_app/design/widgets/pos_button.dart';
import 'package:pos_app/features/pos/presentation/screens/open_session_screen.dart';

/// SessionStorage مزيّف — يتجاوز readTenantContext() فقط (كل ما تستخدمه
/// هذه الشاشة) بلا أي لمسة لـ FlutterSecureStorage الحقيقي.
class _FakeSessionStorage extends SessionStorage {
  _FakeSessionStorage(this._tenantContext);

  final TenantContext? _tenantContext;

  @override
  Future<TenantContext?> readTenantContext() async => _tenantContext;
}

/// WarehousesRemoteDataSource مزيّف — يتجاوز listWarehouses() فقط، بلا
/// أي نداء شبكة حقيقي عبر ApiClient.dio.
class _FakeWarehousesRemoteDataSource extends WarehousesRemoteDataSource {
  _FakeWarehousesRemoteDataSource(this._result) : super(ApiClient());

  final Future<List<WarehouseDto>> Function() _result;

  @override
  Future<List<WarehouseDto>> listWarehouses({String? branchId}) => _result();
}

Widget _wrap({
  required Future<List<WarehouseDto>> Function() warehouses,
}) {
  return ProviderScope(
    overrides: [
      sessionStorageProvider.overrideWithValue(
        _FakeSessionStorage(
          const TenantContext(companyId: 'c1', userId: 'u1', branchId: 'b1'),
        ),
      ),
      warehousesRemoteDataSourceProvider.overrideWithValue(
        _FakeWarehousesRemoteDataSource(warehouses),
      ),
    ],
    child: const MaterialApp(
      home: Directionality(
        textDirection: TextDirection.rtl,
        child: OpenSessionScreen(),
      ),
    ),
  );
}

void main() {
  group('OpenSessionScreen', () {
    testWidgets('تُعرض بنجاح وتحمّل قائمة المستودعات النشطة', (tester) async {
      await tester.pumpWidget(_wrap(
        warehouses: () async {
          // تأخير حقيقي بسيط ليبقى مؤشر التحميل ملتقَطاً بعد pump() واحدة.
          await Future.delayed(const Duration(milliseconds: 10));
          return const [
            WarehouseDto(id: 'w1', name: 'المستودع الرئيسي', isActive: true),
            WarehouseDto(id: 'w2', name: 'مستودع الفرع', isActive: true),
          ];
        },
      ));

      await tester.pump(); // بداية التحميل
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      await tester.pumpAndSettle();
      expect(find.text('المستودع الرئيسي'), findsOneWidget);
      expect(find.text('مستودع الفرع'), findsOneWidget);
      expect(find.text('الرصيد الافتتاحي (نقدي)'), findsOneWidget);
    });

    testWidgets('زر "فتح الجلسة" معطَّل حتى يُختار مستودع، ثم يُفعَّل',
        (tester) async {
      await tester.pumpWidget(_wrap(
        warehouses: () async => const [
          WarehouseDto(id: 'w1', name: 'المستودع الرئيسي', isActive: true),
          WarehouseDto(id: 'w2', name: 'مستودع الفرع', isActive: true),
        ],
      ));
      await tester.pumpAndSettle();

      final buttonFinder = find.widgetWithText(PosButton, 'فتح الجلسة');
      expect(buttonFinder, findsOneWidget);
      expect(tester.widget<PosButton>(buttonFinder).onPressed, isNull);

      await tester.tap(find.text('المستودع الرئيسي'));
      await tester.pump();

      expect(tester.widget<PosButton>(buttonFinder).onPressed, isNotNull);
    });

    testWidgets('حقل الرصيد الافتتاحي يقبل الإدخال ويبدأ بقيمة صفر',
        (tester) async {
      await tester.pumpWidget(_wrap(
        warehouses: () async => const [
          WarehouseDto(id: 'w1', name: 'المستودع الرئيسي', isActive: true),
        ],
      ));
      await tester.pumpAndSettle();

      expect(find.text('0'), findsOneWidget);

      await tester.enterText(
        find.widgetWithText(TextField, 'الرصيد الافتتاحي (نقدي)'),
        '50000',
      );
      await tester.pump();

      expect(find.text('50000'), findsOneWidget);
    });

    testWidgets('حالة فارغة: تُعرض رسالة واضحة عند عدم وجود مستودعات نشطة',
        (tester) async {
      await tester.pumpWidget(_wrap(warehouses: () async => const []));
      await tester.pumpAndSettle();

      expect(
        find.text('لا توجد مستودعات نشطة متاحة لفتح جلسة عليها'),
        findsOneWidget,
      );
      expect(find.widgetWithText(PosButton, 'إعادة المحاولة'), findsOneWidget);
    });

    testWidgets('يعرض رسالة خطأ واضحة عند فشل تحميل المستودعات', (tester) async {
      await tester.pumpWidget(_wrap(
        warehouses: () async => throw Exception('network down'),
      ));
      await tester.pumpAndSettle();

      expect(
        find.text('تعذّر تحميل قائمة المستودعات — تحقق من الاتصال'),
        findsOneWidget,
      );
    });
  });
}

// ملاحظة نطاق (Scope Note):
// - لم تُغطَّ هنا حالة النجاح الكاملة لـ "فتح الجلسة" (تستدعي
//   posSessionRepositoryProvider.openSession → appDatabaseProvider drift
//   حقيقية) — هذا خارج الجزء "البسيط" من PKG-D2 المطلوب هنا تحديداً؛
//   يُترك لتوسعة لاحقة بعد PKG-B3 وفق 00_TASK_PACKAGE.md.
