import '../../core/network/api_client.dart';
import '../models/pos_session_dto.dart';
import '../models/pos_sync_dto.dart';

/// طبقة نداء مباشرة لِـ `/pos/*` (core-api) — مطابقة حرفياً لِـ
/// `pos_REFERENCE/presentation/routes/pos_router.py`:
///   POST /pos/sessions               → openSession
///   POST /pos/sessions/{id}/close    → closeSession
///   POST /pos/sync                   → syncSales (دفعة، Idempotent)
///
/// لا يوجد أي endpoint من نوع GET لقراءة المبيعات — القراءة محلية بالكامل
/// (PosRepository)، والسيرفر لا يُستخدَم إلا للكتابة/المزامنة.
class PosRemoteDataSource {
  PosRemoteDataSource(this._apiClient);

  final ApiClient _apiClient;

  Future<PosSessionDto> openSession(OpenSessionRequestDto request) async {
    final response = await _apiClient.dio.post<Map<String, dynamic>>(
      '/pos/sessions',
      data: request.toJson(),
    );
    return PosSessionDto.fromJson(response.data!);
  }

  Future<PosSessionDto> closeSession(
    String sessionId,
    CloseSessionRequestDto request,
  ) async {
    final response = await _apiClient.dio.post<Map<String, dynamic>>(
      '/pos/sessions/$sessionId/close',
      data: request.toJson(),
    );
    return PosSessionDto.fromJson(response.data!);
  }

  /// يرسل دفعة مبيعات تخص جلسة واحدة. الاستجابة تحتوي نتيجة مستقلة لكل
  /// عملية (بعضها قد ينجح وبعضها يفشل ضمن نفس الطلب) — لا رمي استثناء إلا
  /// عند فشل الطلب كله (مثال: الجلسة غير موجودة/مغلقة → 400).
  Future<PosSyncResponseDto> syncSales(PosSyncRequestDto request) async {
    final response = await _apiClient.dio.post<Map<String, dynamic>>(
      '/pos/sync',
      data: request.toJson(),
    );
    return PosSyncResponseDto.fromJson(response.data!);
  }
}
