import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../data/models/catalog_dto.dart';
import '../../../../data/models/partner_dto.dart';
import '../../../../data/models/pos_sync_dto.dart';

/// بند واحد في سلة البيع الحالية على الشاشة (قبل الحفظ محلياً في
/// PosRepository.createDraftSale) — منفصل عمداً عن [PosSaleLineDto]
/// (الأخير DTO شبكة صارم بلا اسم/معلومات عرض).
class CartLine {
  final ProductDto product;
  final double quantity;

  /// السعر الفعلي المستخدم لهذا البند (يبدأ من `product.salePrice`، قابل
  /// للتجاوز اليدوي من الكاشير — راجع تعليق PosSaleLineDto).
  final double unitPrice;

  const CartLine({
    required this.product,
    required this.quantity,
    required this.unitPrice,
  });

  double get lineTotal => quantity * unitPrice;

  CartLine copyWith({double? quantity, double? unitPrice}) => CartLine(
        product: product,
        quantity: quantity ?? this.quantity,
        unitPrice: unitPrice ?? this.unitPrice,
      );
}

class CartState {
  final List<CartLine> lines;
  final PartnerDto? partner;
  final double discountAmount;

  const CartState({
    this.lines = const [],
    this.partner,
    this.discountAmount = 0,
  });

  double get subtotal => lines.fold(0, (sum, l) => sum + l.lineTotal);
  double get total => (subtotal - discountAmount).clamp(0, double.infinity);
  bool get isEmpty => lines.isEmpty;

  CartState copyWith({
    List<CartLine>? lines,
    PartnerDto? partner,
    bool clearPartner = false,
    double? discountAmount,
  }) {
    return CartState(
      lines: lines ?? this.lines,
      partner: clearPartner ? null : (partner ?? this.partner),
      discountAmount: discountAmount ?? this.discountAmount,
    );
  }
}

/// حالة سلة البيع الحالية على الشاشة فقط — تُفرَّغ بعد كل عملية بيع ناجحة
/// (`PosRepository.createDraftSale` هو من يخزّن فعلياً ويضيف لطابور
/// المزامنة؛ هذا الكنترولر لا يلمس القاعدة المحلية إطلاقاً).
class CartController extends StateNotifier<CartState> {
  CartController() : super(const CartState());

  void addProduct(ProductDto product) {
    final existingIndex = state.lines.indexWhere(
      (l) => l.product.id == product.id,
    );
    if (existingIndex != -1) {
      final existing = state.lines[existingIndex];
      _replaceLine(existingIndex, existing.copyWith(quantity: existing.quantity + 1));
      return;
    }

    state = state.copyWith(
      lines: [
        ...state.lines,
        CartLine(product: product, quantity: 1, unitPrice: product.salePrice),
      ],
    );
  }

  void updateQuantity(int index, double quantity) {
    if (quantity <= 0) {
      removeLine(index);
      return;
    }
    _replaceLine(index, state.lines[index].copyWith(quantity: quantity));
  }

  void overrideUnitPrice(int index, double unitPrice) {
    if (unitPrice < 0) return;
    _replaceLine(index, state.lines[index].copyWith(unitPrice: unitPrice));
  }

  void removeLine(int index) {
    final lines = [...state.lines]..removeAt(index);
    state = state.copyWith(lines: lines);
  }

  void selectPartner(PartnerDto partner) {
    state = state.copyWith(partner: partner);
  }

  void setDiscount(double amount) {
    state = state.copyWith(discountAmount: amount < 0 ? 0 : amount);
  }

  void reset() {
    state = const CartState();
  }

  void _replaceLine(int index, CartLine line) {
    final lines = [...state.lines];
    lines[index] = line;
    state = state.copyWith(lines: lines);
  }
}

final cartControllerProvider =
    StateNotifierProvider.autoDispose<CartController, CartState>(
  (ref) => CartController(),
);
