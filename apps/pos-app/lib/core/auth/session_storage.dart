import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'tenant_context.dart';

/// تخزين آمن لبيانات الجلسة (JWT + TenantContext) على الجهاز.
/// ضروري لأن POS يعمل Offline-first: يجب أن تبقى الجلسة صالحة محلياً
/// حتى بلا اتصال.
class SessionStorage {
  SessionStorage({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static const _kAccessToken = 'pos_access_token';
  static const _kRefreshToken = 'pos_refresh_token';
  static const _kTenantContext = 'pos_tenant_context';

  Future<void> saveSession({
    required String accessToken,
    required String refreshToken,
    required TenantContext tenantContext,
  }) async {
    await Future.wait([
      _storage.write(key: _kAccessToken, value: accessToken),
      _storage.write(key: _kRefreshToken, value: refreshToken),
      _storage.write(
        key: _kTenantContext,
        value: jsonEncode(tenantContext.toJson()),
      ),
    ]);
  }

  Future<String?> readAccessToken() => _storage.read(key: _kAccessToken);

  Future<String?> readRefreshToken() => _storage.read(key: _kRefreshToken);

  Future<TenantContext?> readTenantContext() async {
    final raw = await _storage.read(key: _kTenantContext);
    if (raw == null) return null;
    return TenantContext.fromJson(
      jsonDecode(raw) as Map<String, dynamic>,
    );
  }

  Future<void> clear() async {
    await Future.wait([
      _storage.delete(key: _kAccessToken),
      _storage.delete(key: _kRefreshToken),
      _storage.delete(key: _kTenantContext),
    ]);
  }
}
