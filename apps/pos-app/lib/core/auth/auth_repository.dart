import 'package:dio/dio.dart';

import '../network/api_client.dart';
import 'session_storage.dart';
import 'tenant_context.dart';

/// نتيجة تسجيل الدخول: توكنات + TenantContext (مُشتَقّ من الـ JWT، راجع
/// TenantContext.fromAccessToken).
class LoginResult {
  final String accessToken;
  final String refreshToken;
  final TenantContext tenantContext;

  const LoginResult({
    required this.accessToken,
    required this.refreshToken,
    required this.tenantContext,
  });
}

/// طبقة رقيقة فوق /auth/* — لا تحتوي أي منطق واجهة.
///
/// تصحيح جوهري (مهمة #13) عن الجولة السابقة: العقد الفعلي مؤكَّد الآن
/// مقابل `identity_dto.py`/`auth_router.py`:
///   - `POST /auth/login` يقبل `{email, password, company_id?}` — **ليس**
///     `{username, password, branch_id?}` كما افترضت الجولة السابقة.
///     `company_id` اختياري ومطلوب فقط لمستخدم عضو في أكثر من شركة.
///   - الاستجابة `{access_token, refresh_token, token_type}` فقط — **بلا**
///     `tenant_context` (راجع تعليق TenantContext.fromAccessToken).
///   - `POST /auth/refresh` يقبل `{refresh_token}` فقط ويعيد نفس شكل
///     `TokenResponse` — عقد بسيط ومؤكَّد بالكامل، فعُطِّل TODO
///     `refreshTokenIfNeeded` سابقاً بلا داعٍ (راجع AuthInterceptor).
class AuthRepository {
  AuthRepository({
    required ApiClient apiClient,
    required SessionStorage sessionStorage,
  })  : _apiClient = apiClient,
        _sessionStorage = sessionStorage;

  final ApiClient _apiClient;
  final SessionStorage _sessionStorage;

  Future<LoginResult> login({
    required String email,
    required String password,
    /// مطلوب فقط إن كان المستخدم عضواً في أكثر من شركة (LoginRequest.company_id).
    String? companyId,
  }) async {
    final response = await _apiClient.dio.post<Map<String, dynamic>>(
      '/auth/login',
      data: {
        'email': email,
        'password': password,
        if (companyId != null) 'company_id': companyId,
      },
    );

    final result = _parseTokenResponse(response.data!);
    await _persist(result);
    return result;
  }

  Future<bool> hasActiveSession() async {
    final token = await _sessionStorage.readAccessToken();
    return token != null && token.isNotEmpty;
  }

  Future<void> logout() => _sessionStorage.clear();

  /// يجدّد access_token عبر /auth/refresh ويخزّن النتيجة. يُستدعى تلقائياً
  /// من [AuthInterceptor] عند 401، ويمكن استدعاؤه يدوياً أيضاً.
  /// يرمي [StateError] إن لم يوجد refresh_token محفوظ (لا جلسة أصلاً).
  Future<LoginResult> refreshTokenIfNeeded() async {
    final refreshToken = await _sessionStorage.readRefreshToken();
    if (refreshToken == null || refreshToken.isEmpty) {
      throw StateError('لا يوجد refresh_token محفوظ — يلزم تسجيل دخول جديد');
    }

    // نداء مباشر بلا AuthInterceptor (Dio عادي بلا هيدر Authorization قديم)
    // تجنباً لأي حلقة اعتراض غير مقصودة أثناء التجديد نفسه.
    final response = await Dio(_apiClient.dio.options).post<Map<String, dynamic>>(
      '/auth/refresh',
      data: {'refresh_token': refreshToken},
    );

    final result = _parseTokenResponse(response.data!);
    await _persist(result);
    return result;
  }

  LoginResult _parseTokenResponse(Map<String, dynamic> data) {
    final accessToken = data['access_token'] as String;
    final refreshToken = data['refresh_token'] as String;
    return LoginResult(
      accessToken: accessToken,
      refreshToken: refreshToken,
      tenantContext: TenantContext.fromAccessToken(accessToken),
    );
  }

  Future<void> _persist(LoginResult result) {
    return _sessionStorage.saveSession(
      accessToken: result.accessToken,
      refreshToken: result.refreshToken,
      tenantContext: result.tenantContext,
    );
  }
}
