/// بند واحد ضمن فاتورة بيع — مطابقة مؤكَّدة لِـ `LineItemRequest`
/// (`modules.sales.application.dto.sales_dto`، ملك العضو 4). تصحيح جوهري
/// (مهمة #13): الجولة السابقة جعلت `unitPrice` اختيارياً على افتراض أن
/// السيرفر يحسب السعر من الكتالوج عند غيابه — تأكَّد الآن من التوقيع
/// الفعلي (`unit_price: Decimal = Field(ge=0)`, **بلا** قيمة افتراضية) أن
/// الحقل **إلزامي دائماً**؛ لا حساب تلقائي من الكتالوج في `SyncPosSalesUseCase`
/// (يمرَّر `sale.lines` كما هي مباشرة لِـ `CreateSalesInvoiceUseCase`). لذا
/// شاشة السلة (مهمة #13) تجلب سعر المنتج من `/products` وقت الإضافة للسلة
/// وتُلزم الكاشير بسعر معروف دائماً (مع إمكانية تجاوز يدوي إن احتاج).
class PosSaleLineDto {
  final String productId;
  final double quantity;
  final double unitPrice;

  const PosSaleLineDto({
    required this.productId,
    required this.quantity,
    required this.unitPrice,
  });

  factory PosSaleLineDto.fromJson(Map<String, dynamic> json) {
    return PosSaleLineDto(
      productId: json['product_id'] as String,
      quantity: (json['quantity'] as num).toDouble(),
      unitPrice: (json['unit_price'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'product_id': productId,
        'quantity': quantity,
        'unit_price': unitPrice,
      };
}

/// مطابقة حرفية لِـ `PosSaleRequest`. `clientReference` هو مفتاح الـ
/// Idempotency (القسم 41: Simulated Offline resilience) — **يجب أن يبقى
/// ثابتاً عبر إعادة المحاولة**، لذا نستخدم نفس معرّف الفاتورة المحلي
/// (UUID) ولا نولّد واحداً جديداً عند كل محاولة مزامنة.
class PosSaleRequestDto {
  final String clientReference;
  final String partnerId;
  final String currency;
  final double discountAmount;
  final List<PosSaleLineDto> lines;

  const PosSaleRequestDto({
    required this.clientReference,
    required this.partnerId,
    this.currency = 'IQD',
    this.discountAmount = 0,
    required this.lines,
  });

  factory PosSaleRequestDto.fromJson(Map<String, dynamic> json) {
    return PosSaleRequestDto(
      clientReference: json['client_reference'] as String,
      partnerId: json['partner_id'] as String,
      currency: json['currency'] as String? ?? 'IQD',
      discountAmount: (json['discount_amount'] as num?)?.toDouble() ?? 0,
      lines: (json['lines'] as List<dynamic>)
          .map((e) => PosSaleLineDto.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'client_reference': clientReference,
        'partner_id': partnerId,
        'currency': currency,
        'discount_amount': discountAmount,
        'lines': lines.map((e) => e.toJson()).toList(),
      };
}

/// مطابقة حرفية لِـ `PosSyncRequest`: دفعة من عمليات البيع تخص جلسة واحدة
/// مفتوحة (`session_id`). هذا هو المسار الوحيد للمزامنة — **لا يوجد**
/// endpoint من نوع GET /pos/sales في السيرفر الفعلي (كنت افترضتها خطأً
/// في الجولة السابقة قبل توفر هذا المرجع — تم تصحيحها).
class PosSyncRequestDto {
  final String sessionId;
  final List<PosSaleRequestDto> sales;

  const PosSyncRequestDto({required this.sessionId, required this.sales});

  Map<String, dynamic> toJson() => {
        'session_id': sessionId,
        'sales': sales.map((e) => e.toJson()).toList(),
      };
}

/// مطابقة حرفية لِـ `PosSyncResultItem`. `status` قيم `PosSyncItemStatus`:
/// pending | processed | failed (نص خام لنفس سبب PosSessionDto.status).
class PosSyncResultItemDto {
  final String clientReference;
  final String status;
  final String? salesInvoiceId;
  final String? invoiceNumber;
  final String? error;

  const PosSyncResultItemDto({
    required this.clientReference,
    required this.status,
    this.salesInvoiceId,
    this.invoiceNumber,
    this.error,
  });

  bool get isProcessed => status == 'processed';
  bool get isFailed => status == 'failed';

  factory PosSyncResultItemDto.fromJson(Map<String, dynamic> json) {
    return PosSyncResultItemDto(
      clientReference: json['client_reference'] as String,
      status: json['status'] as String,
      salesInvoiceId: json['sales_invoice_id'] as String?,
      invoiceNumber: json['invoice_number'] as String?,
      error: json['error'] as String?,
    );
  }
}

/// مطابقة حرفية لِـ `PosSyncResponse`: **لا يفشل الطلب كله** إن فشلت عملية
/// بيع واحدة ضمن الدفعة — كل عملية لها نتيجتها الخاصة (القسم 41). أي منطق
/// عميل يتعامل مع "فشل المزامنة" كخطأ واحد شامل خطأ من حيث المبدأ.
class PosSyncResponseDto {
  final List<PosSyncResultItemDto> results;

  const PosSyncResponseDto({required this.results});

  factory PosSyncResponseDto.fromJson(Map<String, dynamic> json) {
    return PosSyncResponseDto(
      results: (json['results'] as List<dynamic>)
          .map((e) => PosSyncResultItemDto.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
