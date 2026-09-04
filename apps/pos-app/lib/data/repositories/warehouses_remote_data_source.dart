import '../../core/network/api_client.dart';
import '../models/warehouse_dto.dart';

/// قراءة فقط من `/warehouses` (وحدة tenancy، ليست ملكاً لـ pos-app) — لشاشة
/// فتح جلسة POS. تُفلتَر حسب `branch_id` عند توفره في TenantContext (جهاز
/// POS مربوط بفرع محدد عادةً)، لكنه اختياري فعلياً على السيرفر والتوكن
/// معاً (راجع TenantContext).
class WarehousesRemoteDataSource {
  WarehousesRemoteDataSource(this._apiClient);

  final ApiClient _apiClient;

  Future<List<WarehouseDto>> listWarehouses({String? branchId}) async {
    final response = await _apiClient.dio.get<List<dynamic>>(
      '/warehouses',
      queryParameters: {if (branchId != null) 'branch_id': branchId},
    );
    return response.data!
        .map((e) => WarehouseDto.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
