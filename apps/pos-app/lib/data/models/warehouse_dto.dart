/// نسخة مختصرة من `WarehouseResponse` (`tenancy_dto.py`) — لاختيار المستودع
/// عند فتح جلسة POS (`OpenSessionRequest.warehouse_id`).
class WarehouseDto {
  final String id;
  final String name;
  final bool isActive;

  const WarehouseDto({
    required this.id,
    required this.name,
    required this.isActive,
  });

  factory WarehouseDto.fromJson(Map<String, dynamic> json) {
    return WarehouseDto(
      id: json['id'] as String,
      name: json['name'] as String,
      isActive: json['is_active'] as bool,
    );
  }
}
