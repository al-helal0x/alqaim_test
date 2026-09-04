import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/di/providers.dart';
import '../../auth/presentation/screens/login_screen.dart';
import 'screens/open_session_screen.dart';
import 'screens/sale_screen.dart';

/// نقطة القرار الوحيدة: تسجيل دخول → فتح جلسة → نقطة البيع. يستمع
/// لمصدرين تفاعليين (activeSessionProvider مبني على Stream من القاعدة
/// المحلية، hasSessionProvider يُعاد تقييمه يدوياً بعد دخول/خروج) بدل أي
/// منطق تنقّل (Navigator) صريح — التبديل بين الشاشات الثلاث يحدث تلقائياً
/// فور تغيّر الحالة (نجاح تسجيل دخول، نجاح فتح/إغلاق جلسة).
class RootShell extends ConsumerWidget {
  const RootShell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // يضمن إنشاء مدير المزامنة ومراقب الاتصال عند الإقلاع بغض النظر عن
    // الشاشة المعروضة (يجب أن يعملا حتى أثناء تسجيل الدخول لو كانت هناك
    // مبيعات سابقة معلَّقة من جلسة لم تُغلق).
    ref.watch(syncManagerProvider);

    final hasSession = ref.watch(hasSessionProvider);

    return hasSession.when(
      loading: () => const _LoadingScreen(),
      error: (_, __) => const LoginScreen(),
      data: (loggedIn) {
        if (!loggedIn) return const LoginScreen();

        // مزامنة كاش الكتالوج (منتجات/عملاء) تحتاج جلسة مسجَّل دخول فيها
        // فعلياً (بيانات خاصة بالمستأجر Tenant عبر التوكن) — بخلاف
        // syncManagerProvider أعلاه لا فائدة من تشغيلها قبل تسجيل الدخول،
        // وتشغيلها هنا فقط يتجنب نداءات شبكة فاشلة (401) بلا داعٍ في شاشة
        // الدخول.
        ref.watch(catalogSyncManagerProvider);

        final activeSession = ref.watch(activeSessionProvider);
        return activeSession.when(
          loading: () => const _LoadingScreen(),
          error: (_, __) => const _LoadingScreen(),
          data: (session) {
            if (session == null) return const OpenSessionScreen();
            return SaleScreen(sessionId: session.id);
          },
        );
      },
    );
  }
}

class _LoadingScreen extends StatelessWidget {
  const _LoadingScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: CircularProgressIndicator()));
  }
}
