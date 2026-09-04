/// نسخة مختصرة من `PartnerResponse` (`partner_dto.py`) — لشاشة اختيار
/// العميل في السلة. لا فلترة حسب `partner_type` عمداً: `PartnerType.BOTH`
/// عميل وموردّ معاً، فاستبعاد غير "customer" سيُخفي شركاء صالحين فعلاً
/// كعملاء نقدية POS.
class PartnerDto {
  final String id;
  final String name;
  final String? phone;

  const PartnerDto({required this.id, required this.name, this.phone});

  factory PartnerDto.fromJson(Map<String, dynamic> json) {
    return PartnerDto(
      id: json['id'] as String,
      name: json['name'] as String,
      phone: json['phone'] as String?,
    );
  }
}

class PartnerPage {
  final List<PartnerDto> items;
  final int total;

  const PartnerPage({required this.items, required this.total});

  factory PartnerPage.fromJson(Map<String, dynamic> json) {
    return PartnerPage(
      items: (json['items'] as List<dynamic>)
          .map((e) => PartnerDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int,
    );
  }
}
