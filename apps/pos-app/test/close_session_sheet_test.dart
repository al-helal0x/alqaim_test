// PKG-D2 — Widget tests: showCloseSessionSheet (close_session_sheet.dart).
//
// نطاق مقصود ومحدود: نغطي عرض الورقة، التحقق المحلي من صحة الإدخال (رصيد
// إغلاق سالب/فارغ يُرفض قبل أي استدعاء لأي مستودع بيانات)، وتحذير المبيعات
// المعلَّقة (الميزة المضافة الآن — راجع تعليق close_session_sheet.dart).
// **لا نختبر هنا مسار النجاح الفعلي** (يستدعي posSessionRepositoryProvider
// .closeSession → appDatabaseProvider drift حقيقية + شبكة) — خارج نطاق
// "الجزء البسيط" المطلوب هنا، راجع ملاحظة النطاق في نهاية الملف.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pos_app/core/di/providers.dart';
import 'package:pos_app/data/local/app_database.dart';
import 'package:pos_app/data/repositories/pos_repository.dart';
import 'package:pos_app/design/widgets/pos_button.dart';
import 'package:pos_app/features/pos/presentation/screens/close_session_sheet.dart';

/// PosRepository مزيّف — يتجاوز pendingSyncCountForSession() فقط بقيمة
/// ثابتة، بلا أي لمسة لقاعدة بيانات حقيقية (AppDatabase() هنا لا تُستخدَم
/// فعلياً أبداً — drift كسول (Lazy) ولا يفتح اتصالاً حتى أول استعلام حقيقي،
/// وهذا التزييف لا يُجري أي استعلام).
class _FakePosRepository extends PosRepository {
  _FakePosRepository(this._pendingCount) : super(database: AppDatabase());

  final int _pendingCount;

  @override
  Future<int> pendingSyncCountForSession(String sessionId) async =>
      _pendingCount;
}

Widget _hostApp({int pendingCount = 0}) {
  return ProviderScope(
    overrides: [
      posRepositoryProvider.overrideWithValue(
        _FakePosRepository(pendingCount),
      ),
    ],
    child: const MaterialApp(
      home: Directionality(
        textDirection: TextDirection.rtl,
        child: _OpenSheetButtonHost(),
      ),
    ),
  );
}

/// شاشة مضيفة بسيطة تفتح الورقة بنفس الطريقة التي تستدعيها sale_screen
/// فعلياً (Builder لأخذ BuildContext صحيح تحت MaterialApp).
class _OpenSheetButtonHost extends ConsumerWidget {
  const _OpenSheetButtonHost();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: Builder(
        builder: (innerContext) => Center(
          child: ElevatedButton(
            onPressed: () => showCloseSessionSheet(
              innerContext,
              ref,
              sessionId: 's1',
            ),
            child: const Text('افتح ورقة الإغلاق'),
          ),
        ),
      ),
    );
  }
}

void main() {
  group('close_session_sheet', () {
    testWidgets('تُفتح وتعرض الحقل وزر التأكيد', (tester) async {
      await tester.pumpWidget(_hostApp());

      await tester.tap(find.text('افتح ورقة الإغلاق'));
      await tester.pumpAndSettle();

      expect(find.text('إغلاق الجلسة'), findsOneWidget);
      expect(find.text('الرصيد الختامي (نقدي)'), findsOneWidget);
      expect(find.widgetWithText(ElevatedButton, 'تأكيد الإغلاق'), findsOneWidget);
    });

    testWidgets('ترفض رصيد إغلاق فارغاً بلا استدعاء أي مستودع بيانات',
        (tester) async {
      await tester.pumpWidget(_hostApp());
      await tester.tap(find.text('افتح ورقة الإغلاق'));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(ElevatedButton, 'تأكيد الإغلاق'));
      await tester.pump();

      expect(find.text('أدخل رصيد إغلاق صحيح'), findsOneWidget);
    });

    testWidgets('ترفض رصيد إغلاق سالباً بنفس رسالة التحقق', (tester) async {
      await tester.pumpWidget(_hostApp());
      await tester.tap(find.text('افتح ورقة الإغلاق'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextField, 'الرصيد الختامي (نقدي)'),
        '-500',
      );
      await tester.tap(find.widgetWithText(ElevatedButton, 'تأكيد الإغلاق'));
      await tester.pump();

      expect(find.text('أدخل رصيد إغلاق صحيح'), findsOneWidget);
    });

    testWidgets('حقل الرصيد الختامي يقبل إدخالاً صحيحاً', (tester) async {
      await tester.pumpWidget(_hostApp());
      await tester.tap(find.text('افتح ورقة الإغلاق'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextField, 'الرصيد الختامي (نقدي)'),
        '125000',
      );
      await tester.pump();

      expect(find.text('125000'), findsOneWidget);
    });

    testWidgets(
        'لا تحذير ولا تعطيل للزر عند عدم وجود عمليات معلَّقة (0)',
        (tester) async {
      await tester.pumpWidget(_hostApp(pendingCount: 0));
      await tester.tap(find.text('افتح ورقة الإغلاق'));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.warning_amber_rounded), findsNothing);

      await tester.enterText(
        find.widgetWithText(TextField, 'الرصيد الختامي (نقدي)'),
        '125000',
      );
      await tester.pump();

      final buttonFinder = find.widgetWithText(PosButton, 'تأكيد الإغلاق');
      expect(tester.widget<PosButton>(buttonFinder).onPressed, isNotNull);
    });

    testWidgets(
        'يعرض تحذيراً ويعطّل زر التأكيد عند وجود عملية معلَّقة واحدة',
        (tester) async {
      await tester.pumpWidget(_hostApp(pendingCount: 1));
      await tester.tap(find.text('افتح ورقة الإغلاق'));
      await tester.pumpAndSettle();

      expect(
        find.text('يوجد عملية بيع واحدة لم تُزامَن بعد مع السيرفر'),
        findsOneWidget,
      );

      await tester.enterText(
        find.widgetWithText(TextField, 'الرصيد الختامي (نقدي)'),
        '125000',
      );
      await tester.pump();

      final buttonFinder = find.widgetWithText(PosButton, 'تأكيد الإغلاق');
      expect(tester.widget<PosButton>(buttonFinder).onPressed, isNull);
    });

    testWidgets(
        'يعرض تحذيراً بصيغة الجمع عند وجود أكثر من عملية معلَّقة',
        (tester) async {
      await tester.pumpWidget(_hostApp(pendingCount: 3));
      await tester.tap(find.text('افتح ورقة الإغلاق'));
      await tester.pumpAndSettle();

      expect(
        find.text('يوجد 3 عمليات بيع لم تُزامَن بعد مع السيرفر'),
        findsOneWidget,
      );
    });

    testWidgets(
        'زر التأكيد يُفعَّل فقط بعد تفعيل مربّع الإقرار الصريح',
        (tester) async {
      await tester.pumpWidget(_hostApp(pendingCount: 2));
      await tester.tap(find.text('افتح ورقة الإغلاق'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextField, 'الرصيد الختامي (نقدي)'),
        '125000',
      );
      await tester.pump();

      final buttonFinder = find.widgetWithText(PosButton, 'تأكيد الإغلاق');
      expect(tester.widget<PosButton>(buttonFinder).onPressed, isNull);

      await tester.tap(find.byType(CheckboxListTile));
      await tester.pump();

      expect(tester.widget<PosButton>(buttonFinder).onPressed, isNotNull);

      // إلغاء التفعيل يُعطِّل الزر مجدداً — الإقرار ليس ذا اتجاه واحد فقط.
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pump();
      expect(tester.widget<PosButton>(buttonFinder).onPressed, isNull);
    });
  });
}

// ملاحظة نطاق (Scope Note):
// - لم يُغطَّ هنا مسار النجاح الكامل لتأكيد الإغلاق (يستدعي
//   posSessionRepositoryProvider.closeSession → appDatabaseProvider drift
//   حقيقية + PosRemoteDataSource) — خارج الجزء "البسيط" المطلوب هنا؛ يُترك
//   لتوسعة لاحقة، بنفس نمط ملاحظة النطاق في open_session_screen_test.dart.
