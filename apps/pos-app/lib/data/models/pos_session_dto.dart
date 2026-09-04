/// مطابقة حرفية لِـ `OpenSessionRequest` في
/// `_reference_read_only/.../pos_REFERENCE/application/dto/pos_dto.py`.
///
/// فتح/إغلاق الجلسة **يتطلب اتصالاً** بطبيعته (نقطة بداية/نهاية وردية،
/// وليست عملية Offline-first) — البيع نفسه هو ما يعمل بلا اتصال، وليس
/// إدارة الجلسة. راجع PosSessionRepository.
class OpenSessionRequestDto {
  final String warehouseId;
  final double openingCash;

  const OpenSessionRequestDto({
    required this.warehouseId,
    this.openingCash = 0,
  });

  Map<String, dynamic> toJson() => {
        'warehouse_id': warehouseId,
        'opening_cash': openingCash,
      };
}

/// مطابقة حرفية لِـ `CloseSessionRequest`.
class CloseSessionRequestDto {
  final double closingCash;

  const CloseSessionRequestDto({required this.closingCash});

  Map<String, dynamic> toJson() => {'closing_cash': closingCash};
}

/// مطابقة حرفية لِـ `SessionResponse`. `status` نص خام ('open' | 'closed')
/// مطابقةً لِـ `PosSessionStatus` في `domain/rules/__init__.py` — أُبقيت
/// كـ String بدل enum Dart كي لا ينكسر العميل إن أُضيفت حالة جديدة لاحقاً
/// من طرف السيرفر دون تنسيق مسبق.
class PosSessionDto {
  final String id;
  final String companyId;
  final String warehouseId;
  final String openedBy;
  final double openingCash;
  final double? closingCash;
  final String status;
  final DateTime openedAt;
  final DateTime? closedAt;

  const PosSessionDto({
    required this.id,
    required this.companyId,
    required this.warehouseId,
    required this.openedBy,
    required this.openingCash,
    this.closingCash,
    required this.status,
    required this.openedAt,
    this.closedAt,
  });

  bool get isOpen => status == 'open';

  factory PosSessionDto.fromJson(Map<String, dynamic> json) {
    return PosSessionDto(
      id: json['id'] as String,
      companyId: json['company_id'] as String,
      warehouseId: json['warehouse_id'] as String,
      openedBy: json['opened_by'] as String,
      openingCash: (json['opening_cash'] as num).toDouble(),
      closingCash: (json['closing_cash'] as num?)?.toDouble(),
      status: json['status'] as String,
      openedAt: DateTime.parse(json['opened_at'] as String),
      closedAt: json['closed_at'] == null
          ? null
          : DateTime.parse(json['closed_at'] as String),
    );
  }
}
