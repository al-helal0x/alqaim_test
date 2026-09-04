import 'dart:async';

import '../../data/repositories/catalog_repository.dart';
import '../connectivity/connectivity_service.dart';

/// يُشغِّل مزامنة كاش الكتالوج (منتجات + عملاء، راجع CatalogRepository)
/// مرة عند بدء التطبيق، ثم في كل مرة يُستعاد فيها الاتصال — بنفس نمط
/// [SyncManager] تماماً لكن لكاش القراءة فقط (لا طابور، لا تعارضات).
///
/// فشل المزامنة (مثال: لا اتصال عند بدء التطبيق) صامت عمداً — الكاش
/// يبقى بحالته السابقة (فارغاً في أول تشغيل) وتُعاد المحاولة تلقائياً
/// عند أول استعادة اتصال فعلية؛ هذا مسار طوارئ (راجع تعليق
/// CatalogRepository)، لا داعي لإزعاج المستخدم برسالة خطأ عنه في الخلفية.
class CatalogSyncManager {
  CatalogSyncManager({
    required CatalogRepository catalogRepository,
    required ConnectivityService connectivityService,
  })  : _catalogRepository = catalogRepository,
        _connectivityService = connectivityService;

  final CatalogRepository _catalogRepository;
  final ConnectivityService _connectivityService;

  StreamSubscription<void>? _reconnectSub;

  void start() {
    // محاولة أولى صامتة عند بدء التطبيق (مفيدة إن كان الجهاز متصلاً فعلاً
    // من اللحظة الأولى — لا داعي لانتظار "إعادة" اتصال لم تنقطع أصلاً).
    unawaited(_catalogRepository.syncAll());

    _reconnectSub = _connectivityService.onReconnected.listen((_) {
      unawaited(_catalogRepository.syncAll());
    });
  }

  Future<void> dispose() async {
    await _reconnectSub?.cancel();
  }
}
