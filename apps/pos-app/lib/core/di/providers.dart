import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../data/repositories/catalog_remote_data_source.dart';
import '../../data/repositories/catalog_repository.dart';
import '../../data/repositories/partners_remote_data_source.dart';
import '../../data/repositories/pos_remote_data_source.dart';
import '../../data/repositories/pos_repository.dart';
import '../../data/repositories/pos_session_repository.dart';
import '../../data/repositories/warehouses_remote_data_source.dart';
import '../auth/auth_repository.dart';
import '../auth/session_storage.dart';
import '../connectivity/connectivity_service.dart';
import '../network/api_client.dart';
import '../sync/catalog_sync_manager.dart';
import '../sync/sync_manager.dart';

/// جذر تركيب الاعتماديات. هذا كل ما تحتاجه أي شاشة مستقبلية للوصول
/// للمستودعات دون معرفة تفاصيل البنية التحتية.
final sessionStorageProvider = Provider<SessionStorage>((ref) {
  return SessionStorage();
});

final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient(sessionStorage: ref.watch(sessionStorageProvider));
});

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  final repo = AuthRepository(
    apiClient: apiClient,
    sessionStorage: ref.watch(sessionStorageProvider),
  );
  // يربط تجديد 401 التلقائي في AuthInterceptor بمنطق AuthRepository —
  // راجع تعليق ApiClient.attachRefreshHandler.
  apiClient.attachRefreshHandler(() async {
    try {
      return (await repo.refreshTokenIfNeeded()).accessToken;
    } catch (_) {
      return null;
    }
  });
  return repo;
});

final appDatabaseProvider = Provider<AppDatabase>((ref) {
  final db = AppDatabase();
  ref.onDispose(db.close);
  return db;
});

final posRemoteDataSourceProvider = Provider<PosRemoteDataSource>((ref) {
  return PosRemoteDataSource(ref.watch(apiClientProvider));
});

final posRepositoryProvider = Provider<PosRepository>((ref) {
  return PosRepository(database: ref.watch(appDatabaseProvider));
});

final posSessionRepositoryProvider = Provider<PosSessionRepository>((ref) {
  return PosSessionRepository(
    database: ref.watch(appDatabaseProvider),
    remoteDataSource: ref.watch(posRemoteDataSourceProvider),
  );
});

final connectivityServiceProvider = Provider<ConnectivityService>((ref) {
  final service = ConnectivityService();
  service.start();
  ref.onDispose(service.dispose);
  return service;
});

final catalogRemoteDataSourceProvider = Provider<CatalogRemoteDataSource>((ref) {
  return CatalogRemoteDataSource(ref.watch(apiClientProvider));
});

final partnersRemoteDataSourceProvider = Provider<PartnersRemoteDataSource>((ref) {
  return PartnersRemoteDataSource(ref.watch(apiClientProvider));
});

final warehousesRemoteDataSourceProvider = Provider<WarehousesRemoteDataSource>((ref) {
  return WarehousesRemoteDataSource(ref.watch(apiClientProvider));
});

/// كاش الكتالوج المحلي (منتجات/عملاء) — راجع تعليق CatalogRepository. يُستخدم
/// من شاشتَي اختيار المنتج/العميل كـ fallback عند انقطاع الاتصال فقط.
final catalogRepositoryProvider = Provider<CatalogRepository>((ref) {
  return CatalogRepository(
    database: ref.watch(appDatabaseProvider),
    catalogRemoteDataSource: ref.watch(catalogRemoteDataSourceProvider),
    partnersRemoteDataSource: ref.watch(partnersRemoteDataSourceProvider),
  );
});

final catalogSyncManagerProvider = Provider<CatalogSyncManager>((ref) {
  final manager = CatalogSyncManager(
    catalogRepository: ref.watch(catalogRepositoryProvider),
    connectivityService: ref.watch(connectivityServiceProvider),
  );
  manager.start();
  ref.onDispose(manager.dispose);
  return manager;
});

/// الجلسة المفتوحة محلياً حالياً (أو null) — تُحدَّد الشاشة الجذر بناءً
/// عليها (open-session vs sale). راجع AppDatabase.watchActiveSession.
final activeSessionProvider = StreamProvider.autoDispose((ref) {
  return ref.watch(appDatabaseProvider).watchActiveSession();
});

/// هل يوجد Access Token محفوظ؟ يُعاد تقييمه يدوياً عبر
/// `ref.invalidate(hasSessionProvider)` بعد تسجيل الدخول/الخروج (لا حدث
/// Stream طبيعي لتخزين آمن — FlutterSecureStorage لا يبثّ تغييراته).
final hasSessionProvider = FutureProvider.autoDispose((ref) {
  return ref.watch(authRepositoryProvider).hasActiveSession();
});

/// TenantContext المخزَّن محلياً (SessionStorage) — null إن لم تكن هناك
/// جلسة مسجَّل دخول فيها بعد.
final tenantContextProvider = FutureProvider.autoDispose((ref) {
  return ref.watch(sessionStorageProvider).readTenantContext();
});

final syncManagerProvider = Provider<SyncManager>((ref) {
  final manager = SyncManager(
    database: ref.watch(appDatabaseProvider),
    posRepository: ref.watch(posRepositoryProvider),
    remoteDataSource: ref.watch(posRemoteDataSourceProvider),
    connectivityService: ref.watch(connectivityServiceProvider),
  );
  manager.start();
  ref.onDispose(manager.dispose);
  return manager;
});
