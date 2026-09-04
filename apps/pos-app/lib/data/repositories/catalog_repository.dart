import 'package:drift/drift.dart';

import '../local/app_database.dart';
import '../models/catalog_dto.dart';
import '../models/partner_dto.dart';
import 'catalog_remote_data_source.dart';
import 'partners_remote_data_source.dart';

/// يدير كاش الكتالوج المحلي (منتجات + عملاء) — **فقط لطوارئ انقطاع
/// الاتصال**. البحث الحي عبر `/products` و`/partners` يبقى دائماً المصدر
/// الأساسي والأحدث (راجع CatalogRemoteDataSource/PartnersRemoteDataSource)؛
/// هذا المستودع يُستدعى فقط:
/// 1. للمزامنة الكاملة الدورية (عند استعادة الاتصال — راجع
///    CatalogSyncManager)، و
/// 2. كـ fallback من شاشات الاختيار (`product_picker_sheet.dart`،
///    `partner_picker_sheet.dart`) عند فشل نداء الشبكة تحديداً، وليس بديلاً
///    دائماً عن البحث الحي.
///
/// لا يوجد على السيرفر (حسب DTOs المؤكَّدة: `catalog_dto.py`,
/// `partner_dto.py`) أي معامل `updated_since` أو ما شابه لمزامنة تفاضلية،
/// لذا التنفيذ هنا "استبدال كامل" (Full Replace) بسيط عمداً — يجلب كل
/// الصفحات حتى نهاية القائمة ثم يستبدل الكاش المحلي دفعة واحدة.
class CatalogRepository {
  CatalogRepository({
    required AppDatabase database,
    required CatalogRemoteDataSource catalogRemoteDataSource,
    required PartnersRemoteDataSource partnersRemoteDataSource,
  })  : _database = database,
        _catalogRemoteDataSource = catalogRemoteDataSource,
        _partnersRemoteDataSource = partnersRemoteDataSource;

  final AppDatabase _database;
  final CatalogRemoteDataSource _catalogRemoteDataSource;
  final PartnersRemoteDataSource _partnersRemoteDataSource;

  /// حد أقصى لعدد الصفحات لكل مزامنة — حارس أمان يمنع حلقة طويلة جداً (أو
  /// غير منتهية نظرياً لو أرجع السيرفر `total` غير متّسق) من تعليق
  /// المزامنة إلى الأبد؛ 50 صفحة × 200 = حتى 10,000 عنصر، سقف معقول جداً
  /// لسيناريو POS محلي واحد.
  static const int _maxPages = 50;
  static const int _pageSize = 200;

  /// يجلب كامل كتالوج المنتجات (كل الصفحات) ويستبدل الكاش المحلي بالكامل.
  /// يُرجع عدد العناصر التي زُامنت (مفيد لعرض حالة آخر مزامنة لاحقاً).
  Future<int> syncProducts() async {
    final all = <ProductDto>[];
    var page = 1;
    while (page <= _maxPages) {
      final result = await _catalogRemoteDataSource.searchProducts(
        page: page,
        pageSize: _pageSize,
      );
      all.addAll(result.items);
      if (result.items.isEmpty || all.length >= result.total) break;
      page++;
    }

    await _database.replaceProductsCache(
      all
          .map((p) => LocalProductsCompanion.insert(
                id: p.id,
                sku: p.sku,
                name: p.name,
                salePrice: p.salePrice,
                trackInventory: p.trackInventory,
                isActive: p.isActive,
              ))
          .toList(),
    );
    return all.length;
  }

  /// نفس منطق [syncProducts] لكن للعملاء (`/partners`).
  Future<int> syncPartners() async {
    final all = <PartnerDto>[];
    var page = 1;
    while (page <= _maxPages) {
      final result = await _partnersRemoteDataSource.listPartners(
        page: page,
        pageSize: _pageSize,
      );
      all.addAll(result.items);
      if (result.items.isEmpty || all.length >= result.total) break;
      page++;
    }

    await _database.replacePartnersCache(
      all
          .map((p) => LocalPartnersCompanion.insert(
                id: p.id,
                name: p.name,
                phone: Value(p.phone),
              ))
          .toList(),
    );
    return all.length;
  }

  /// يُشغِّل مزامنة المنتجات والعملاء معاً. فشل أحدهما لا يُفشل الآخر —
  /// كاش منتجات محدَّث أفضل من لا شيء حتى لو فشلت مزامنة العملاء لسبب ما
  /// (والعكس صحيح).
  Future<void> syncAll() async {
    await Future.wait<int>([
      syncProducts().catchError((_) => 0),
      syncPartners().catchError((_) => 0),
    ]);
  }

  Future<List<ProductDto>> searchLocalProducts(String query) async {
    final rows = await _database.searchLocalProducts(query);
    return rows
        .map((r) => ProductDto(
              id: r.id,
              sku: r.sku,
              name: r.name,
              salePrice: r.salePrice,
              trackInventory: r.trackInventory,
              isActive: r.isActive,
            ))
        .toList();
  }

  Future<List<PartnerDto>> searchLocalPartners(String query) async {
    final rows = await _database.searchLocalPartners(query);
    return rows
        .map((r) => PartnerDto(id: r.id, name: r.name, phone: r.phone))
        .toList();
  }
}
