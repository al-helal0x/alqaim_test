import '../../core/network/api_client.dart';
import '../models/partner_dto.dart';

/// قراءة فقط من `/partners` (وحدة partners، ليست ملكاً لـ pos-app) — لشاشة
/// اختيار العميل في السلة.
///
/// ملاحظة نطاق مهمة: `list_partners` لا يقبل معامل بحث نصي على السيرفر
/// (`partners_router.py`: فقط `partner_type`/pagination/sort) — بخلاف
/// `/products` الذي يدعم `search=`. لذا نجلب صفحة كبيرة نسبياً (حتى 200)
/// ونُطبّق الفلترة النصية محلياً في الشاشة. غير مثالي لعدد عملاء ضخم؛ إضافة
/// `search=` على `/partners` مقترح متابعة منفصل لملّاك وحدة partners، خارج
/// حدود apps/pos-app/**.
class PartnersRemoteDataSource {
  PartnersRemoteDataSource(this._apiClient);

  final ApiClient _apiClient;

  Future<PartnerPage> listPartners({int page = 1, int pageSize = 200}) async {
    final response = await _apiClient.dio.get<Map<String, dynamic>>(
      '/partners',
      queryParameters: {'page': page, 'page_size': pageSize, 'sort': 'name'},
    );
    return PartnerPage.fromJson(response.data!);
  }
}
