// PKG-D2 — Integration test: التدفّق الكامل لنقطة البيع ضد سيرفر core-api
// **حقيقي فعلياً قيد التشغيل** (لا mocks، لا fakes — هذا بالضبط ما ينقص
// STATUS.md حالياً: "لم تُختبَر الشاشات فعلياً ضد سيرفر حقيقي").
//
// ⚠️ ملاحظة صدق مهمة: هذا الملف **لم يُشغَّل فعلياً** في بيئة إعداده (لا
// SDK فلاتر، لا سيرفر core-api، لا اتصال شبكة متاح هناك) — راجعتُ كل خطوة
// يدوياً بعناية مقابل الكود الفعلي الحالي لكل شاشة (نصوص الأزرار/الحقول،
// تسلسل التنقّل، شروط تفعيل الأزرار) لضمان تطابقها، لكن التشغيل الفعلي
// الأول عندك قد يكشف تفاصيل بيئة لم أستطع توقّعها (توقيت شبكة حقيقي،
// اختلاف طفيف بالنصوص لو عُدِّلت لاحقاً، ...). شغّله وأرسل لي أي فشل
// لأصلحه فوراً — تماماً كما فعلنا مع بقية هذه الجولة.
//
// ============================================================================
// المتطلبات المسبقة (يوفّرها المُشغِّل، وليست جزءاً من هذا الملف):
// ============================================================================
// 1. سيرفر core-api يعمل فعلياً ويستجيب على API_BASE_URL أدناه.
// 2. بيانات مُهيَّأة (seed) في قاعدة بياناته:
//    - مستخدم واحد بالضبط عضو في شركة واحدة (email/password) — لو كان
//      عضواً في أكثر من شركة سيفشل تسجيل الدخول هنا عمداً (شاشة تسجيل
//      الدخول الحالية لا تعرض حقل اختيار شركة، راجع login_screen.dart).
//    - مستودع (warehouse) واحد نشط على الأقل ضمن فرع ذلك المستخدم.
//    - منتج نشط واحد على الأقل يُطابقه TEST_PRODUCT_QUERY (فارغ = أول
//      نتيجة من `/products` بلا فلترة).
//    - عميل (partner) واحد على الأقل يُطابقه TEST_PARTNER_QUERY (فارغ =
//      أول نتيجة من `/partners`).
// 3. جهاز/محاكي فعلي متصل (`flutter devices`) — integration_test لا يعمل
//    على Dart VM المجرَّدة.
//
// ============================================================================
// طريقة التشغيل:
// ============================================================================
//   flutter test integration_test/pos_flow_test.dart \
//     --dart-define=API_BASE_URL=http://localhost:8000 \
//     --dart-define=TEST_EMAIL=cashier@example.com \
//     --dart-define=TEST_PASSWORD=secret123 \
//     --dart-define=TEST_PRODUCT_QUERY=coffee \
//     --dart-define=TEST_PARTNER_QUERY=ahmad \
//     -d <device-id>
//
// TEST_EMAIL/TEST_PASSWORD إلزاميان — بلا قيمة لهما يُتخطَّى الاختبار
// (markTestSkipped) بدل أن يفشل بلا سبب واضح (يسمح بإبقاء الملف ضمن
// `flutter test` العادي في CI بلا كسره، إلى أن يُموَّل بمتغيرات بيئة حقيقية
// في خط أنابيب integration منفصل).
//
// ============================================================================
// ما يُغطّى فعلياً (سيناريو واحد متسلسل، ليس اختبارات معزولة):
// ============================================================================
// تسجيل دخول حقيقي (POST /auth/login) → فتح جلسة حقيقي (POST
// /pos/sessions) → بحث/اختيار عميل حقيقي (GET /partners) → بحث/اختيار
// منتج حقيقي (GET /products) → إنشاء بيع محلياً (Offline-first، بلا شبكة
// بهذه الخطوة تحديداً) → دفع مزامنة يدوي **صريح** عبر syncManagerProvider
// (راجع الملاحظة الحرجة أدناه) → التحقق من استهلاك طابور المزامنة فعلياً
// (POST /pos/sync حقيقي، لا عناصر متبقية في SyncQueueEntries) → إغلاق
// الجلسة (POST /pos/sessions/{id}/close).
//
// ============================================================================
// ⚠️ ملاحظة معمارية مهمة اكتُشِفت أثناء كتابة هذا الاختبار (وليست مجرد
// تفصيل اختبار — أثر فعلي على سلوك التطبيق الحقيقي):
// ============================================================================
// SyncManager.start() يستمع فقط لحدث "الانتقال من غير متصل إلى متصل"
// (ConnectivityService.onReconnected) ليستهلك طابور المزامنة — **لا يوجد
// أي مسار آخر يستهلكه تلقائياً** (لا نداء syncNow() بعد إنشاء بيع مباشرة،
// ولا زر "مزامنة الآن" يدوي في الواجهة). يعني هذا عملياً: جهاز POS يبقى
// **متصلاً باستمرار** طوال الوردية (السيناريو الأكثر شيوعاً فعلياً لجهاز
// كاشير بمتجر عادي بلا انقطاعات) لن يُزامِن أي بيع تلقائياً حتى يحدث
// انقطاع فعلي ثم عودة اتصال — قد تبقى المبيعات "معلَّقة" لساعات دون سبب
// ظاهر للكاشير. هذا الاختبار يتحايل على القيد بنداء صريح
// `container.read(syncManagerProvider).syncNow()` ليختبر فعلياً أن نداء
// /pos/sync يعمل ويُفرِغ الطابور بنجاح — لكنه **لا يختبر ولا يُصلح** غياب
// المُحفِّز التلقائي في الاستخدام الفعلي. هذا TODO حقيقي منفصل يستحق
// معالجة خاصة (مثال: مؤقّت دوري كل N دقائق بجانب حدث إعادة الاتصال) —
// موثَّق أيضاً في STATUS.md.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:pos_app/core/di/providers.dart';
import 'package:pos_app/design/widgets/pos_button.dart';
import 'package:pos_app/main.dart';

const _testEmail = String.fromEnvironment('TEST_EMAIL', defaultValue: '');
const _testPassword = String.fromEnvironment('TEST_PASSWORD', defaultValue: '');
const _testProductQuery =
    String.fromEnvironment('TEST_PRODUCT_QUERY', defaultValue: '');
const _testPartnerQuery =
    String.fromEnvironment('TEST_PARTNER_QUERY', defaultValue: '');
const _openingCash =
    String.fromEnvironment('TEST_OPENING_CASH', defaultValue: '100000');
const _closingCash =
    String.fromEnvironment('TEST_CLOSING_CASH', defaultValue: '100000');

/// يستطلع الحالة كل [step] حتى يتحقق [condition] أو تنتهي [timeout] —
/// بديل مقصود عن `tester.pumpAndSettle()` لأن الأخير يفشل بخطأ "timed
/// out" أمام أي مؤشر تحميل بحركة لا-نهائية (`CircularProgressIndicator`
/// الافتراضي هنا في كل الشاشات أثناء الانتظار الشبكي)، وهي بالضبط الحالة
/// الشائعة طوال هذا الاختبار.
Future<void> _pumpUntil(
  WidgetTester tester,
  bool Function() condition, {
  Duration timeout = const Duration(seconds: 20),
  Duration step = const Duration(milliseconds: 200),
  String? description,
}) async {
  final deadline = DateTime.now().add(timeout);
  while (DateTime.now().isBefore(deadline)) {
    await tester.pump(step);
    if (condition()) return;
  }
  fail(
    'انتهت المهلة (${timeout.inSeconds}ث) قبل تحقق الشرط'
    '${description == null ? '' : ': $description'}',
  );
}

bool _hasText(String text) => find.text(text).evaluate().isNotEmpty;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'التدفّق الكامل: دخول → فتح جلسة → بيع → مزامنة → إغلاق جلسة',
    (tester) async {
      if (_testEmail.isEmpty || _testPassword.isEmpty) {
        markTestSkipped(
          'TEST_EMAIL/TEST_PASSWORD غير مُمرَّرين — راجع تعليق الملف '
          'لطريقة التشغيل الكاملة ضد سيرفر core-api حقيقي.',
        );
        return;
      }

      // نُنشئ ProviderContainer يدوياً (بدل الاعتماد فقط على ProviderScope
      // ضمن main()) كي نقدر نصل لاحقاً لـ syncManagerProvider مباشرة من
      // الاختبار نفسه — راجع الملاحظة المعمارية أعلى الملف.
      final container = ProviderContainer();
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const PosApp(),
        ),
      );
      await tester.pump();

      // -- 1. تسجيل الدخول --------------------------------------------
      expect(find.widgetWithText(TextField, 'البريد الإلكتروني'), findsOneWidget);
      await tester.enterText(
        find.widgetWithText(TextField, 'البريد الإلكتروني'),
        _testEmail,
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'كلمة المرور'),
        _testPassword,
      );
      await tester.tap(find.widgetWithText(PosButton, 'دخول'));

      await _pumpUntil(
        tester,
        () => _hasText('فتح جلسة POS') || _hasText('نقطة البيع'),
        description: 'الانتقال بعد تسجيل الدخول (فتح جلسة أو سلة إن كانت '
            'هناك جلسة مفتوحة مسبقاً لهذا المستخدم)',
      );

      // قد تكون هناك جلسة مفتوحة مسبقاً من تشغيل سابق للاختبار لم يُغلقها
      // (فشل التنظيف). في هذه الحالة الاختبار يتخطّى فتح الجلسة وينتقل
      // مباشرة لاستخدام الجلسة الموجودة — أوضح من فشل غامض لاحقاً.
      final alreadyOnSaleScreen = _hasText('نقطة البيع');

      if (!alreadyOnSaleScreen) {
        // -- 2. فتح جلسة ------------------------------------------------
        await _pumpUntil(
          tester,
          () => find.byType(RadioListTile).evaluate().isNotEmpty,
          description: 'تحميل قائمة المستودعات (يتطلب مستودعاً نشطاً '
              'واحداً على الأقل مُهيَّأً مسبقاً)',
        );
        await tester.tap(find.byType(RadioListTile).first);
        await tester.pump();

        await tester.enterText(
          find.widgetWithText(TextField, 'الرصيد الافتتاحي (نقدي)'),
          _openingCash,
        );
        await tester.tap(find.widgetWithText(PosButton, 'فتح الجلسة'));

        await _pumpUntil(
          tester,
          () => _hasText('نقطة البيع'),
          description: 'الانتقال لشاشة السلة بعد نجاح فتح الجلسة',
        );
      }

      // -- 3. اختيار عميل -----------------------------------------------
      await tester.tap(find.text('اختر عميلاً'));
      await tester.pump(); // فتح الـ modal bottom sheet

      await _pumpUntil(
        tester,
        () => find.byType(ListTile).evaluate().isNotEmpty ||
            _hasText('لا نتائج مطابقة') ||
            _hasText('تعذّر تحميل قائمة العملاء — تحقق من الاتصال'),
        description: 'تحميل قائمة العملاء من /partners',
      );
      if (_testPartnerQuery.isNotEmpty) {
        await tester.enterText(
          find.widgetWithText(TextField, 'ابحث بالاسم...'),
          _testPartnerQuery,
        );
        await tester.pump();
      }
      expect(
        find.byType(ListTile),
        findsWidgets,
        reason: 'لا يوجد عميل مطابق لـ TEST_PARTNER_QUERY="$_testPartnerQuery" '
            '— يلزم عميل واحد على الأقل مُهيَّأً مسبقاً على السيرفر',
      );
      await tester.tap(find.byType(ListTile).first);
      await tester.pump();

      // -- 4. إضافة منتج --------------------------------------------------
      await tester.tap(find.text('إضافة منتج'));
      await tester.pump(); // فتح الـ modal bottom sheet

      await _pumpUntil(
        tester,
        () => find.byType(ListTile).evaluate().isNotEmpty ||
            _hasText('لا نتائج مطابقة') ||
            _hasText('تعذّر البحث عن المنتجات — تحقق من الاتصال'),
        description: 'البحث الأولي (فارغ) في /products',
      );
      if (_testProductQuery.isNotEmpty) {
        await tester.enterText(
          find.widgetWithText(TextField, 'ابحث بالاسم أو رمز المنتج (SKU)...'),
          _testProductQuery,
        );
        // بحث المنتج فيه debounce 350ms (راجع product_picker_sheet.dart) —
        // ننتظره صراحة قبل التحقق من النتائج.
        await tester.pump(const Duration(milliseconds: 400));
        await _pumpUntil(
          tester,
          () => find.byType(ListTile).evaluate().isNotEmpty ||
              _hasText('لا نتائج مطابقة'),
          description: 'نتائج البحث بعد debounce',
        );
      }
      expect(
        find.byType(ListTile),
        findsWidgets,
        reason: 'لا يوجد منتج مطابق لـ TEST_PRODUCT_QUERY="$_testProductQuery" '
            '— يلزم منتج نشط واحد على الأقل مُهيَّأً مسبقاً على السيرفر',
      );
      await tester.tap(find.byType(ListTile).first);
      await tester.pump();

      // -- 5. الانتقال لشاشة الدفع وتأكيده -------------------------------
      final payButton = find.widgetWithText(PosButton, 'الدفع');
      expect(
        tester.widget<PosButton>(payButton).onPressed,
        isNotNull,
        reason: 'زر الدفع يجب أن يكون مفعَّلاً الآن (بند + عميل مُختاران)',
      );
      await tester.tap(payButton);
      await tester.pump();

      await _pumpUntil(
        tester,
        () => _hasText('تأكيد الدفع'),
        description: 'الانتقال لشاشة الدفع',
      );
      await tester.tap(find.widgetWithText(PosButton, 'تأكيد الدفع'));

      // إنشاء البيع محلي بالكامل (Offline-first، بلا نداء شبكة هنا) —
      // يكفي pump قصير، لا حاجة لانتظار شبكي فعلي بهذه الخطوة تحديداً.
      await _pumpUntil(
        tester,
        () => _hasText('نقطة البيع') && !_hasText('تأكيد الدفع'),
        description: 'العودة لشاشة السلة بعد حفظ البيع محلياً',
      );

      // -- 6. دفع المزامنة صراحة والتحقق من استهلاك الطابور فعلياً --------
      // راجع الملاحظة المعمارية أعلى الملف: بلا هذا النداء الصريح، لن
      // يحدث أي نداء /pos/sync تلقائياً ما لم يمرّ الجهاز فعلياً بانقطاع
      // اتصال ثم عودته أثناء تشغيل هذا الاختبار.
      await container.read(syncManagerProvider).syncNow();
      await tester.pump(const Duration(seconds: 1));

      final database = container.read(appDatabaseProvider);
      final remainingQueueEntries = await database.pendingSyncEntries();
      expect(
        remainingQueueEntries,
        isEmpty,
        reason: 'يُفترض أن /pos/sync الحقيقي استهلك كل عناصر الطابور بنجاح — '
            'إن بقيت عناصر، راجع رسالة الخطأ المخزَّنة '
            '(LocalSales.lastSyncError) لسبب الفشل الفعلي من السيرفر',
      );

      // -- 7. إغلاق الجلسة --------------------------------------------------
      await tester.tap(find.byIcon(Icons.logout));
      await tester.pump(); // فتح الـ modal bottom sheet

      // لا يُفترض ظهور تحذير مبيعات معلَّقة هنا (الطابور فارغ من الخطوة 6)،
      // لكن إن ظهر لأي سبب (تعذّر قراءة العدّاد محلياً مثلاً) الكود
      // Fail-open أصلاً (راجع close_session_sheet.dart) فلن يمنع المتابعة.
      await tester.enterText(
        find.widgetWithText(TextField, 'الرصيد الختامي (نقدي)'),
        _closingCash,
      );
      final confirmCloseButton = find.widgetWithText(PosButton, 'تأكيد الإغلاق');
      await tester.pump();
      expect(
        tester.widget<PosButton>(confirmCloseButton).onPressed,
        isNotNull,
        reason: 'زر تأكيد الإغلاق معطَّل — على الأغلب تحذير مبيعات معلَّقة '
            'لم يُتوقَّع (راجع نتيجة الخطوة 6 أعلاه)',
      );
      await tester.tap(confirmCloseButton);

      await _pumpUntil(
        tester,
        () => _hasText('فتح جلسة POS'),
        description: 'العودة لشاشة فتح الجلسة بعد نجاح الإغلاق فعلياً '
            'على السيرفر (POST /pos/sessions/{id}/close)',
      );
    },
    // مهلة إجمالية سخية — السيناريو يمرّ بعدة نداءات شبكة حقيقية متتالية
    // (دخول، فتح جلسة، بحث عميل، بحث منتج، مزامنة، إغلاق).
    timeout: const Timeout(Duration(minutes: 3)),
  );
}
