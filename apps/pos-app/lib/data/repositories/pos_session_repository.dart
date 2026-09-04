import 'package:drift/drift.dart';

import '../local/app_database.dart';
import '../models/pos_session_dto.dart';
import 'pos_remote_data_source.dart';

/// يُرمى عند محاولة بيع بلا جلسة مفتوحة، أو محاولة فتح جلسة والجهاز غير
/// متصل (فتح/إغلاق الجلسة **ليس** Offline-first عمداً — راجع تعليق
/// OpenSessionRequestDto).
class NoActiveSessionError implements Exception {
  final String message;
  const NoActiveSessionError([this.message = 'لا توجد جلسة POS مفتوحة']);
  @override
  String toString() => message;
}

/// يدير دورة حياة جلسة POS (فتح/إغلاق وردية) — يتطلب اتصالاً بالسيرفر
/// دائماً، بخلاف PosRepository الذي يعمل بلا اتصال بالكامل.
class PosSessionRepository {
  PosSessionRepository({
    required AppDatabase database,
    required PosRemoteDataSource remoteDataSource,
  })  : _database = database,
        _remoteDataSource = remoteDataSource;

  final AppDatabase _database;
  final PosRemoteDataSource _remoteDataSource;

  Future<LocalPosSession?> activeSession() => _database.activeSession();

  Future<PosSessionDto> openSession({
    required String warehouseId,
    double openingCash = 0,
  }) async {
    final dto = await _remoteDataSource.openSession(
      OpenSessionRequestDto(warehouseId: warehouseId, openingCash: openingCash),
    );
    await _persist(dto);
    return dto;
  }

  Future<PosSessionDto> closeSession({
    required String sessionId,
    required double closingCash,
  }) async {
    final dto = await _remoteDataSource.closeSession(
      sessionId,
      CloseSessionRequestDto(closingCash: closingCash),
    );
    await _persist(dto);
    return dto;
  }

  Future<void> _persist(PosSessionDto dto) {
    return _database.upsertSession(
      LocalPosSessionsCompanion.insert(
        id: dto.id,
        companyId: dto.companyId,
        warehouseId: dto.warehouseId,
        openedBy: dto.openedBy,
        openingCash: dto.openingCash,
        closingCash: Value(dto.closingCash),
        status: dto.status,
        openedAt: dto.openedAt,
        closedAt: Value(dto.closedAt),
      ),
    );
  }
}
