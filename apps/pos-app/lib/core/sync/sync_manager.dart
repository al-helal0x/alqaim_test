import 'dart:async';

import 'package:dio/dio.dart';

import '../../data/local/app_database.dart';
import '../../data/models/pos_sync_dto.dart';
import '../../data/repositories/pos_remote_data_source.dart';
import '../../data/repositories/pos_repository.dart';
import '../config/env_config.dart';
import '../connectivity/connectivity_service.dart';

/// نتيجة مزامنة فردية تحتاج انتباه المستخدم (كاشير/مدير) — أي عملية بيع
/// رجعت بحالة `failed` من /pos/sync (مثال شائع: `InsufficientStockError`
/// من السيرفر — رصيد غير كافٍ، وهو أقرب تجسيد فعلي حالياً لسياسة "تنبيه
/// عند تعارض الكميات السالبة" في القسم 6.11؛ السيرفر لا يُرجعها كرمز HTTP
/// مستقل، بل ضمن نتيجة العنصر — نُبقي المعالجة عامة لأي سبب فشل وليس فقط
/// نقص الرصيد، لأن رسالة الخطأ نص حر غير مُصنَّف من السيرفر).
class SyncConflict {
  final String saleId; // = client_reference
  final String message;
  const SyncConflict({required this.saleId, required this.message});
}

/// يُشغَّل مرة واحدة عند بدء التطبيق، ويستمع لأحداث [ConnectivityService]
/// لاستهلاك طابور المزامنة تلقائياً عند استعادة الاتصال، عبر دفعات لكل
/// جلسة POS مفتوحة (POST /pos/sync يقبل جلسة واحدة في كل نداء).
///
/// ملاحظة نطاق: هذا هيكل أساسي للمزامنة (اتصال بالـ API + طابور محلي).
/// شاشات عرض حالة المزامنة للمستخدم (UI) مؤجَّلة حتى إشعار العضو 7 —
/// راجع STATUS.md.
class SyncManager {
  SyncManager({
    required AppDatabase database,
    required PosRepository posRepository,
    required PosRemoteDataSource remoteDataSource,
    required ConnectivityService connectivityService,
  })  : _database = database,
        _posRepository = posRepository,
        _remoteDataSource = remoteDataSource,
        _connectivityService = connectivityService;

  final AppDatabase _database;
  final PosRepository _posRepository;
  final PosRemoteDataSource _remoteDataSource;
  final ConnectivityService _connectivityService;

  StreamSubscription<void>? _reconnectSub;
  bool _isSyncing = false;

  final _conflictsController = StreamController<SyncConflict>.broadcast();
  Stream<SyncConflict> get conflicts => _conflictsController.stream;

  void start() {
    _reconnectSub = _connectivityService.onReconnected.listen((_) async {
      await Future.delayed(EnvConfig.syncDebounce);
      await syncNow();
    });
  }

  /// يمكن استدعاؤها يدوياً (مثلاً من زر "مزامنة الآن" لاحقاً في الواجهة)
  /// أو تلقائياً من مستمع الاتصال أعلاه.
  Future<void> syncNow() async {
    if (_isSyncing) return;
    _isSyncing = true;
    try {
      final pending = await _database.pendingSyncEntries();
      final bySession = <String, List<SyncQueueEntry>>{};
      for (final entry in pending) {
        bySession.putIfAbsent(entry.sessionId, () => []).add(entry);
      }
      for (final sessionEntry in bySession.entries) {
        await _syncSessionBatch(sessionEntry.key, sessionEntry.value);
      }
    } finally {
      _isSyncing = false;
    }
  }

  Future<void> _syncSessionBatch(
    String sessionId,
    List<SyncQueueEntry> entries,
  ) async {
    final sales = <PosSaleRequestDto>[];
    for (final entry in entries) {
      sales.add(await _posRepository.buildSyncPayload(entry.saleId));
    }

    try {
      final response = await _remoteDataSource.syncSales(
        PosSyncRequestDto(sessionId: sessionId, sales: sales),
      );
      await _applyResults(entries, response.results);
    } on DioException {
      // فشل الطلب كله (مثال: الجلسة أُغلقت أو حُذفت على السيرفر بين
      // نداءين) — تبقى كل عناصر هذه الدفعة في الطابور للمحاولة القادمة.
      for (final entry in entries) {
        await _database.incrementAttempt(entry.id);
      }
    }
  }

  Future<void> _applyResults(
    List<SyncQueueEntry> entries,
    List<PosSyncResultItemDto> results,
  ) async {
    final resultsByRef = {for (final r in results) r.clientReference: r};

    for (final entry in entries) {
      final result = resultsByRef[entry.saleId];
      if (result == null) {
        // لم يرد ضمن النتائج لأي سبب — نُبقيه في الطابور، ونزيد عداد المحاولات.
        await _database.incrementAttempt(entry.id);
        continue;
      }

      await _database.applySyncResult(
        saleId: entry.saleId,
        status: result.status,
        serverInvoiceId: result.salesInvoiceId,
        invoiceNumber: result.invoiceNumber,
        errorMessage: result.error,
      );

      if (result.isProcessed) {
        // نجحت — تُحذَف من الطابور نهائياً.
        await _database.removeQueueEntriesForSale(entry.saleId);
      } else if (result.isFailed) {
        // تبقى في الطابور عمداً لإعادة المحاولة (السيرفر Idempotent عبر
        // نفس client_reference)، وتُبلَّغ كتعارض يحتاج انتباهاً.
        await _database.incrementAttempt(entry.id);
        _conflictsController.add(
          SyncConflict(
            saleId: entry.saleId,
            message: result.error ?? 'فشلت المزامنة لسبب غير معروف',
          ),
        );
      }
    }
  }

  Future<void> dispose() async {
    await _reconnectSub?.cancel();
    await _conflictsController.close();
  }
}
