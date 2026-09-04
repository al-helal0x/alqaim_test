/// نسخة مختصرة من `ProductResponse` (`catalog_dto.py`) — فقط الحقول التي
/// تحتاجها شاشة السلة (بحث/عرض/سعر). لا نُخزّن هذا محلياً بعد (Riverpod
/// FutureProvider يعيد الجلب مباشرة من `/products`) — الكتالوج الكامل
/// offline-first مؤجَّل عمداً (راجع docs/pos-design-system.md، "خارج نطاق
/// هذه الجولة")، لأن ذلك يحتاج جدول drift جديد ومزامنة كتالوج دورية، وهو
/// أثر جانبي أكبر من نطاق شاشات POS الثلاث المطلوبة في مهمة #13.
class ProductDto {
  final String id;
  final String sku;
  final String name;
  final double salePrice;
  final bool trackInventory;
  final bool isActive;

  const ProductDto({
    required this.id,
    required this.sku,
    required this.name,
    required this.salePrice,
    required this.trackInventory,
    required this.isActive,
  });

  factory ProductDto.fromJson(Map<String, dynamic> json) {
    return ProductDto(
      id: json['id'] as String,
      sku: json['sku'] as String,
      name: json['name'] as String,
      salePrice: double.parse(json['sale_price'].toString()),
      trackInventory: json['track_inventory'] as bool,
      isActive: json['is_active'] as bool,
    );
  }
}

/// نسخة صفحة عامة (`shared_kernel.pagination.Page`) — `items/total/page/page_size`.
class ProductPage {
  final List<ProductDto> items;
  final int total;

  const ProductPage({required this.items, required this.total});

  factory ProductPage.fromJson(Map<String, dynamic> json) {
    return ProductPage(
      items: (json['items'] as List<dynamic>)
          .map((e) => ProductDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int,
    );
  }
}
