import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';

/// يراقب حالة الاتصال بالشبكة ويبثّ حدثاً عند "الانتقال من غير متصل إلى متصل"
/// فقط (وليس عند كل تغيير) — هذا هو المُحفِّز الذي يستخدمه [SyncManager]
/// لبدء المزامنة التلقائية (بند DoD: "مزامنة تلقائية عند استعادة الاتصال").
class ConnectivityService {
  ConnectivityService({Connectivity? connectivity})
      : _connectivity = connectivity ?? Connectivity();

  final Connectivity _connectivity;

  bool _wasOffline = true;
  StreamSubscription<List<ConnectivityResult>>? _subscription;
  final StreamController<void> _reconnectedController =
      StreamController<void>.broadcast();

  /// يُطلق حدثاً في كل مرة تُستعاد فيها القدرة على الوصول للشبكة.
  Stream<void> get onReconnected => _reconnectedController.stream;

  Future<void> start() async {
    final initial = await _connectivity.checkConnectivity();
    _wasOffline = _isOffline(initial);

    _subscription = _connectivity.onConnectivityChanged.listen((results) {
      final isOfflineNow = _isOffline(results);
      if (_wasOffline && !isOfflineNow) {
        _reconnectedController.add(null);
      }
      _wasOffline = isOfflineNow;
    });
  }

  bool _isOffline(List<ConnectivityResult> results) =>
      results.isEmpty || results.every((r) => r == ConnectivityResult.none);

  Future<void> dispose() async {
    await _subscription?.cancel();
    await _reconnectedController.close();
  }
}
