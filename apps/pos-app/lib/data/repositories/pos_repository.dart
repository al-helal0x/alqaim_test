import 'package:drift/drift.dart';
import 'package:uuid/uuid.dart';

import '../../core/auth/tenant_context.dart';
import '../local/app_database.dart';
import '../models/pos_sync_dto.dart';
import 'pos_session_repository.dart';

/// نقطة الحقيقة الوحيدة لبيانات المبيعات من منظور الواجهة (لاحقاً):
/// كل قراءة/كتابة تمر من هنا وتضرب القاعدة المحلية أولاً (Offline-first)،
/// ثم تُضاف عملية لطابور المزامنة ليستهلكها SyncManager عند توفر الاتصال.
///
/// يتطلب **جلسة POS مفتوحة محلياً** (راجع PosSessionRepository) — البيع لا
/// معنى له بلا جلسة، تماماً كما في السيرفر (SyncPosSalesUseCase يرفض
/// المزامنة على جلسة غير موجودة/مغلقة).
///
/// تُستدعى من `SaleController` (`features/pos/presentation/controllers/`)
/// عند إتمام الدفع في شاشة السلة/الدفع — راجع مهمة #13.
class PosRepository {
  PosRepository({required AppDatabase database, Uuid? uuid})
      : _database = database,
        _uuid = uuid ?? const Uuid();

  final AppDatabase _database;
  final Uuid _uuid;

  /// ينشئ فاتورة محلياً فوراً (بلا انتظار شبكة) ويضيفها لطابور المزامنة.
  /// [partnerId] إلزامي حسب `PosSaleRequest` على السيرفر — لا "عميل نقدي
  /// افتراضي" في العقد الفعلي (`PartnerType` لا يملك قيمة كهذه)، لذا شاشة
  /// السلة (مهمة #13) تُلزم الكاشير باختيار عميل صراحةً قبل تفعيل زر الدفع
  /// بدل افتراض قيمة وهمية. إضافة مفهوم "عميل نقدي" جاهز مسبقاً (لو أراده
  /// المنتج) قرار يخص فريق Partners، خارج نطاق apps/pos-app/**.
  Future<String> createDraftSale({
    required TenantContext tenantContext,
    required String partnerId,
    required List<PosSaleLineDto> lines,
    String currency = 'IQD',
    double discountAmount = 0,
  }) async {
    final activeSession = await _database.activeSession();
    if (activeSession == null) {
      throw NoActiveSessionError(
        'لا يمكن إنشاء فاتورة بلا جلسة POS مفتوحة — افتح جلسة أولاً',
      );
    }

    final saleId = _uuid.v4(); // = client_reference عند المزامنة
    final now = DateTime.now();
    final displayTotal = lines.fold<double>(
      0,
      (sum, line) => sum + line.quantity * line.unitPrice,
    );

    await _database.into(_database.localSales).insert(
          LocalSalesCompanion.insert(
            id: saleId,
            sessionId: activeSession.id,
            companyId: tenantContext.companyId,
            userId: tenantContext.userId,
            partnerId: partnerId,
            currency: Value(currency),
            discountAmount: Value(discountAmount),
            displayTotal: displayTotal,
            createdAt: now,
          ),
        );

    for (final line in lines) {
      await _database.into(_database.localSaleItems).insert(
            LocalSaleItemsCompanion.insert(
              id: _uuid.v4(),
              saleId: saleId,
              productId: line.productId,
              quantity: line.quantity,
              unitPrice: line.unitPrice,
            ),
          );
    }

    await _database.enqueue(
      id: _uuid.v4(),
      sessionId: activeSession.id,
      saleId: saleId,
    );

    return saleId;
  }

  Future<List<LocalSale>> listRecentSales({int limit = 50}) {
    return (_database.select(_database.localSales)
          ..orderBy([(t) => OrderingTerm.desc(t.createdAt)])
          ..limit(limit))
        .get();
  }

  Future<List<LocalSaleItem>> lineItemsFor(String saleId) {
    return (_database.select(_database.localSaleItems)
          ..where((t) => t.saleId.equals(saleId)))
        .get();
  }

  Stream<int> watchPendingSyncCount() {
    return _database.select(_database.syncQueueEntries).watch().map(
          (rows) => rows.length,
        );
  }

  /// عدد عمليات المزامنة المعلَّقة **لجلسة محددة** فقط (بخلاف
  /// [watchPendingSyncCount] الذي يُرجع الإجمالي عبر كل الجلسات) — يُستخدم
  /// من نافذة إغلاق الجلسة (`close_session_sheet.dart`) لتحذير الكاشير قبل
  /// إغلاق جلسة لديها مبيعات لم تُزامَن بعد مع السيرفر.
  Future<int> pendingSyncCountForSession(String sessionId) async {
    final rows = await (_database.select(_database.syncQueueEntries)
          ..where((t) => t.sessionId.equals(sessionId)))
        .get();
    return rows.length;
  }

  /// يبني DTO الطلب من الصفوف المحلية — يُستخدم من SyncManager عند بناء
  /// دفعة /pos/sync. مُبقى هنا (وليس في SyncManager) لأنه تحويل بيانات
  /// خاص بشكل التخزين المحلي، ينتمي منطقياً لهذا المستودع.
  Future<PosSaleRequestDto> buildSyncPayload(String saleId) async {
    final sale = await (_database.select(_database.localSales)
          ..where((t) => t.id.equals(saleId)))
        .getSingle();
    final items = await lineItemsFor(saleId);

    return PosSaleRequestDto(
      clientReference: sale.id,
      partnerId: sale.partnerId,
      currency: sale.currency,
      discountAmount: sale.discountAmount,
      lines: items
          .map((i) => PosSaleLineDto(
                productId: i.productId,
                quantity: i.quantity,
                unitPrice: i.unitPrice,
              ))
          .toList(),
    );
  }
}
