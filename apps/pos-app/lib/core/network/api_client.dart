import 'package:dio/dio.dart';
import 'package:pretty_dio_logger/pretty_dio_logger.dart';

import '../auth/session_storage.dart';
import '../config/env_config.dart';
import 'auth_interceptor.dart';

/// نقطة الاتصال الوحيدة بالـ core-api من داخل pos-app.
/// يُبنى فوق `/pos/*` (مُختبَرة وجاهزة) و `/auth/*` لتوليد الجلسة.
class ApiClient {
  ApiClient({SessionStorage? sessionStorage})
      : _sessionStorage = sessionStorage ?? SessionStorage() {
    _dio = Dio(
      BaseOptions(
        baseUrl: EnvConfig.apiBaseUrl,
        connectTimeout: const Duration(milliseconds: EnvConfig.connectTimeoutMs),
        receiveTimeout: const Duration(milliseconds: EnvConfig.receiveTimeoutMs),
        headers: {'Content-Type': 'application/json'},
      ),
    );

    _authInterceptor = AuthInterceptor(_sessionStorage);
    _dio.interceptors.addAll([
      _authInterceptor,
      if (_kDebugLogging)
        PrettyDioLogger(
          requestBody: true,
          responseBody: true,
          compact: true,
        ),
    ]);
  }

  static const bool _kDebugLogging =
      bool.fromEnvironment('POS_DEBUG_LOGGING', defaultValue: false);

  late final Dio _dio;
  late final AuthInterceptor _authInterceptor;
  final SessionStorage _sessionStorage;

  Dio get dio => _dio;

  /// يربط منطق تجديد التوكن (AuthRepository.refreshTokenIfNeeded) بمعترض
  /// 401 دون اعتمادية دائرية (ApiClient لا يعرف AuthRepository — يعرف
  /// AuthRepository ApiClient لا العكس). يُستدعى مرة واحدة من DI عند
  /// تركيب authRepositoryProvider (راجع core/di/providers.dart).
  void attachRefreshHandler(Future<String?> Function() refreshAccessToken) {
    _authInterceptor.refreshAccessToken = refreshAccessToken;
  }
}
