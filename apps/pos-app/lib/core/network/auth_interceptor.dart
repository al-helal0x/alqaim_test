import 'dart:async';

import 'package:dio/dio.dart';

import '../auth/session_storage.dart';

/// يُرفق Authorization: Bearer <JWT> على كل طلب، ويحاول تجديد التوكن
/// تلقائياً مرة واحدة عند 401 قبل إعادة إرسال الطلب الأصلي — Access Token
/// عمره 15 دقيقة فقط افتراضياً (`platform_core/security.py`)، وكاشير قد
/// يبقى في نفس الشاشة لفترة أطول أثناء نقطة بيع Offline، فالتجديد التلقائي
/// مهم فعلياً وليس تفصيلاً ثانوياً (راجع STATUS.md/AuthRepository).
class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._sessionStorage);

  final SessionStorage _sessionStorage;

  /// يُضبَط لاحقاً من DI (ApiClient.attachRefreshHandler) — لا اعتمادية
  /// مباشرة على AuthRepository هنا لتجنّب حلقة إنشاء (AuthRepository نفسه
  /// يعتمد على ApiClient).
  Future<String?> Function()? refreshAccessToken;

  /// يمنع تجديدات متوازية عند فشل عدة طلبات بـ 401 في نفس اللحظة (مثال:
  /// دفعة مزامنة كاملة تُرسَل والتوكن ينتهي أثناءها) — الكل ينتظر نفس
  /// عملية التجديد الوحيدة بدل كل طلب يجدّد بشكل منفصل.
  Completer<String?>? _refreshInFlight;

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await _sessionStorage.readAccessToken();
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    final isUnauthorized = err.response?.statusCode == 401;
    final handler401 = refreshAccessToken;
    // نتجنّب إعادة محاولة تجديد لنفس الطلب أكثر من مرة (يمنع حلقة لا
    // نهائية إن كان refresh_token نفسه منتهياً/مرفوضاً).
    final alreadyRetried = err.requestOptions.extra['posRetriedAfterRefresh'] == true;

    if (!isUnauthorized || handler401 == null || alreadyRetried) {
      handler.next(err);
      return;
    }

    try {
      final newToken = await _refreshOnce(handler401);
      if (newToken == null) {
        handler.next(err);
        return;
      }

      final retryOptions = err.requestOptions
        ..headers['Authorization'] = 'Bearer $newToken'
        ..extra['posRetriedAfterRefresh'] = true;

      final retryDio = Dio(BaseOptions(baseUrl: err.requestOptions.baseUrl));
      final response = await retryDio.fetch<dynamic>(retryOptions);
      handler.resolve(response);
    } catch (_) {
      // فشل التجديد نفسه (refresh_token منتهٍ/مرفوض) — نمرّر الخطأ الأصلي.
      // الشاشة العليا (root shell) تتحقق من AuthRepository.hasActiveSession()
      // وتعيد التوجيه لتسجيل الدخول عند الحاجة؛ هذا المعترض لا يفرض تنقّلاً.
      handler.next(err);
    }
  }

  Future<String?> _refreshOnce(Future<String?> Function() refresh) {
    final inFlight = _refreshInFlight;
    if (inFlight != null && !inFlight.isCompleted) {
      return inFlight.future;
    }

    final completer = Completer<String?>();
    _refreshInFlight = completer;

    refresh().then((token) {
      if (!completer.isCompleted) completer.complete(token);
    }).catchError((Object error) {
      if (!completer.isCompleted) completer.completeError(error);
    });

    return completer.future;
  }
}
