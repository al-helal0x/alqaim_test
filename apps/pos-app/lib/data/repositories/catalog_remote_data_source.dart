import '../../core/network/api_client.dart';
import '../models/catalog_dto.dart';

/// قراءة فقط من `/products` (وحدة catalog، ليست ملكاً لـ pos-app) — تُستخدم
/// من شاشة السلة للبحث عن منتج وجلب سعره الحالي. راجع تعليق ProductDto
/// بخصوص عدم وجود تخزين محلي للكتالوج بعد.
class CatalogRemoteDataSource {
  CatalogRemoteDataSource(this._apiClient);

  final ApiClient _apiClient;

  Future<ProductPage> searchProducts({
    String? search,
    int page = 1,
    int pageSize = 30,
  }) async {
    final response = await _apiClient.dio.get<Map<String, dynamic>>(
      '/products',
      queryParameters: {
        if (search != null && search.isNotEmpty) 'search': search,
        'page': page,
        'page_size': pageSize,
        'sort': 'name',
      },
    );
    return ProductPage.fromJson(response.data!);
  }
}
