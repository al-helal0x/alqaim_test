// PKG-D2 — Widget tests: LoginScreen.
//
// نطاق مقصود ومحدود (جزء "بسيط" فقط من PKG-D2، وفق 00_TASK_PACKAGE.md):
// - عرض الشاشة بنجاح (build بلا استثناء).
// - الحقول الأساسية تقبل الإدخال.
// - زر "دخول" يستدعي AuthRepository.login فعلياً (نجاح/فشل).
//
// لا نستخدم AuthRepository الحقيقي (يفتح Dio نحو شبكة فعلية عبر
// EnvConfig.apiBaseUrl) — بدلاً منه نموذج مزيّف بسيط (fake) يُدرَج عبر
// authRepositoryProvider.overrideWithValue، لأن AuthRepository صنف عادي
// غير final/sealed ويمكن اشتقاقه دون تعديل REFERENCE_ONLY.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pos_app/core/auth/auth_repository.dart';
import 'package:pos_app/core/auth/session_storage.dart';
import 'package:pos_app/core/auth/tenant_context.dart';
import 'package:pos_app/core/di/providers.dart';
import 'package:pos_app/core/network/api_client.dart';
import 'package:pos_app/features/auth/presentation/screens/login_screen.dart';

/// AuthRepository مزيّف — يتجاوز login() بلا أي اتصال شبكة حقيقي.
/// الاستدعاء الفائق (super) يتطلب ApiClient/SessionStorage حقيقيين لكن
/// بناءهما فقط (بلا استدعاء أي دالة I/O) آمن تماماً هنا.
class _FakeAuthRepository extends AuthRepository {
  _FakeAuthRepository({required this.behavior})
      : super(apiClient: ApiClient(), sessionStorage: SessionStorage());

  final Future<LoginResult> Function({
    required String email,
    required String password,
  }) behavior;

  String? lastEmail;
  String? lastPassword;

  @override
  Future<LoginResult> login({
    required String email,
    required String password,
    String? companyId,
  }) {
    lastEmail = email;
    lastPassword = password;
    return behavior(email: email, password: password);
  }
}

Widget _wrap(Widget child, {required AuthRepository authRepository}) {
  return ProviderScope(
    overrides: [
      authRepositoryProvider.overrideWithValue(authRepository),
    ],
    child: MaterialApp(
      home: Directionality(textDirection: TextDirection.rtl, child: child),
    ),
  );
}

void main() {
  group('LoginScreen', () {
    testWidgets('تُعرض بنجاح مع الحقول والزر الأساسيين', (tester) async {
      final fakeRepo = _FakeAuthRepository(
        behavior: ({required email, required password}) async {
          return const LoginResult(
            accessToken: 'a',
            refreshToken: 'b',
            tenantContext:
                TenantContext(companyId: 'c1', userId: 'u1', branchId: 'b1'),
          );
        },
      );

      await tester.pumpWidget(
        _wrap(const LoginScreen(), authRepository: fakeRepo),
      );

      expect(find.text('AlQaim POS'), findsOneWidget);
      expect(find.text('البريد الإلكتروني'), findsOneWidget);
      expect(find.text('كلمة المرور'), findsOneWidget);
      expect(find.widgetWithText(ElevatedButton, 'دخول'), findsOneWidget);
    });

    testWidgets('الحقول تقبل إدخال المستخدم فعلياً', (tester) async {
      final fakeRepo = _FakeAuthRepository(
        behavior: ({required email, required password}) async {
          return const LoginResult(
            accessToken: 'a',
            refreshToken: 'b',
            tenantContext:
                TenantContext(companyId: 'c1', userId: 'u1', branchId: 'b1'),
          );
        },
      );

      await tester.pumpWidget(
        _wrap(const LoginScreen(), authRepository: fakeRepo),
      );

      await tester.enterText(
        find.widgetWithText(TextField, 'البريد الإلكتروني'),
        'cashier@alqaim.example',
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'كلمة المرور'),
        's3cr3t',
      );
      await tester.pump();

      expect(find.text('cashier@alqaim.example'), findsOneWidget);
    });

    testWidgets('زر دخول يستدعي AuthRepository.login بالحقول الصحيحة عند النجاح',
        (tester) async {
      final fakeRepo = _FakeAuthRepository(
        behavior: ({required email, required password}) async {
          // تأخير حقيقي بسيط (لا microtask بحت) ليبقى مؤشر التحميل
          // ملتقَطاً بعد pump() واحدة بدل أن يكتمل كل شيء في نفس الدورة.
          await Future.delayed(const Duration(milliseconds: 10));
          return const LoginResult(
            accessToken: 'a',
            refreshToken: 'b',
            tenantContext:
                TenantContext(companyId: 'c1', userId: 'u1', branchId: 'b1'),
          );
        },
      );

      await tester.pumpWidget(
        _wrap(const LoginScreen(), authRepository: fakeRepo),
      );

      await tester.enterText(
        find.widgetWithText(TextField, 'البريد الإلكتروني'),
        'cashier@alqaim.example',
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'كلمة المرور'),
        's3cr3t',
      );

      await tester.tap(find.widgetWithText(ElevatedButton, 'دخول'));
      await tester.pump(); // بداية التحميل
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      await tester.pumpAndSettle(); // انتهاء Future.login()
      expect(fakeRepo.lastEmail, 'cashier@alqaim.example');
      expect(fakeRepo.lastPassword, 's3cr3t');
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('يعرض رسالة خطأ عند فشل تسجيل الدخول ولا يترك مؤشر تحميل عالقاً',
        (tester) async {
      final fakeRepo = _FakeAuthRepository(
        behavior: ({required email, required password}) async {
          throw Exception('تعذّر الاتصال');
        },
      );

      await tester.pumpWidget(
        _wrap(const LoginScreen(), authRepository: fakeRepo),
      );

      await tester.tap(find.widgetWithText(ElevatedButton, 'دخول'));
      await tester.pumpAndSettle();

      expect(
        find.text('تعذّر تسجيل الدخول — تحقق من البريد وكلمة المرور'),
        findsOneWidget,
      );
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });
  });
}
