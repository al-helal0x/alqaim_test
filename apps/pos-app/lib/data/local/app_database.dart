import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:meta/meta.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqlite3_flutter_libs/sqlite3_flutter_libs.dart'; // ignore: unused_import

part 'app_database.g.dart';

/// نسخة محلية من جلسة POS (`pos_sessions` على السيرفر). فتح/إغلاق الجلسة
/// يتطلب اتصالاً (راجع PosSessionRepository)، لذا `id` هنا هو **معرّف
/// السيرفر نفسه** مباشرة (لا يوجد id محلي مؤقت كما في LocalSales) —
/// الجلسة لا تُنشأ إلا بعد نجاح الطلب على /pos/sessions.
class LocalPosSessions extends Table {
  TextColumn get id => text()();
  TextColumn get companyId => text()();
  TextColumn get warehouseId => text()();
  TextColumn get openedBy => text()();
  RealColumn get openingCash => real()();
  RealColumn get closingCash => real().nullable()();
  TextColumn get status => text()(); // open | closed (PosSessionStatus)
  DateTimeColumn get openedAt => dateTime()();
  DateTimeColumn get closedAt => dateTime().nullable()();

  @override
  Set<Column> get primaryKey => {id};
}

/// فواتير البيع المُنشأة محلياً. `id` هو UUID محلي يُستخدم أيضاً كـ
/// `client_reference` عند الإرسال لِـ /pos/sync (مفتاح Idempotency، القسم
/// 41) — يبقى ثابتاً عبر كل محاولات إعادة المزامنة.
class LocalSales extends Table {
  TextColumn get id => text()(); // = client_reference عند المزامنة
  TextColumn get sessionId => text().references(LocalPosSessions, #id)();
  TextColumn get companyId => text()();
  TextColumn get userId => text()();
  TextColumn get partnerId => text()();
  TextColumn get currency => text().withDefault(const Constant('IQD'))();
  RealColumn get discountAmount => real().withDefault(const Constant(0))();

  /// إجمالي مبني محلياً للعرض فقط (Σ quantity × unitPrice للبنود) — السيرفر
  /// هو مصدر الحقيقة الفعلي للسعر النهائي (يُحسَب عبر الكتالوج)، هذا الحقل
  /// لا يُرسَل ضمن الطلب.
  RealColumn get displayTotal => real()();

  DateTimeColumn get createdAt => dateTime()();

  /// pending (لم تُرسَل بعد أو بانتظار نتيجة) | processed | failed
  /// — تُحدَّث من نتيجة /pos/sync لكل client_reference.
  TextColumn get syncStatus => text().withDefault(const Constant('pending'))();
  TextColumn get serverInvoiceId => text().nullable()();
  TextColumn get invoiceNumber => text().nullable()();
  TextColumn get lastSyncError => text().nullable()();

  @override
  Set<Column> get primaryKey => {id};
}

/// بنود الفاتورة.
class LocalSaleItems extends Table {
  TextColumn get id => text()();
  TextColumn get saleId => text().references(LocalSales, #id)();
  TextColumn get productId => text()();
  RealColumn get quantity => real()();

  /// السعر الفعلي وقت البيع (من الكتالوج أو تجاوز يدوي من الكاشير) —
  /// إلزامي دائماً (راجع تعليق PosSaleLineDto في مهمة #13؛ السيرفر لا
  /// يحسبه تلقائياً من الكتالوج، يتطلبه صراحةً في كل طلب).
  RealColumn get unitPrice => real()();

  @override
  Set<Column> get primaryKey => {id};
}

/// طابور المزامنة: كل فاتورة محلية `pending` أو `failed` لها إدخال هنا،
/// يُستهلَك دفعةً واحدة لكل جلسة (SyncManager يجمّعها حسب sessionId قبل
/// نداء /pos/sync، لأن الـ endpoint يقبل دفعة لجلسة واحدة فقط في كل مرة).
/// إدخالات `failed` **تبقى في الطابور عمداً** لإعادة المحاولة تلقائياً —
/// السيرفر نفسه Idempotent ويُعيد معالجة نفس client_reference إن لم يكن
/// قد نجح سابقاً (راجع SyncPosSalesUseCase._process_one).
class SyncQueueEntries extends Table {
  TextColumn get id => text()();
  TextColumn get sessionId => text()();
  TextColumn get saleId => text().references(LocalSales, #id)(); // = client_reference
  DateTimeColumn get createdAt => dateTime()();
  IntColumn get attemptCount => integer().withDefault(const Constant(0))();

  @override
  Set<Column> get primaryKey => {id};
}

/// نسخة محلية مخزَّنة (Cache) من كتالوج المنتجات النشطة — تُملأ بمزامنة
/// كاملة دورية (راجع CatalogRepository/CatalogSyncManager)، وتُستخدم فقط
/// كـ fallback عند تعذّر الوصول لِـ `/products` مباشرة (بحث حي أثناء
/// الاتصال يبقى دائماً المصدر الأساسي — هذا الجدول للطوارئ فقط، وقد لا
/// يعكس آخر الأسعار/الكميات لحظياً).
class LocalProducts extends Table {
  TextColumn get id => text()();
  TextColumn get sku => text()();
  TextColumn get name => text()();
  RealColumn get salePrice => real()();
  BoolColumn get trackInventory => boolean()();
  BoolColumn get isActive => boolean()();

  @override
  Set<Column> get primaryKey => {id};
}

/// نسخة محلية مخزَّنة من قائمة العملاء (partners) — لنفس غرض
/// [LocalProducts] بالضبط: fallback أثناء انقطاع الاتصال فقط.
class LocalPartners extends Table {
  TextColumn get id => text()();
  TextColumn get name => text()();
  TextColumn get phone => text().nullable()();

  @override
  Set<Column> get primaryKey => {id};
}

@DriftDatabase(
  tables: [
    LocalPosSessions,
    LocalSales,
    LocalSaleItems,
    SyncQueueEntries,
    LocalProducts,
    LocalPartners,
  ],
)
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  /// مُنشئ مخصّص للاختبارات — قاعدة بيانات في الذاكرة بلا أي لمسة لـ
  /// path_provider (لا يتطلب WidgetsFlutterBinding ولا قناة منصّة حقيقية).
  @visibleForTesting
  AppDatabase.forTesting(QueryExecutor executor) : super(executor);

  @override
  int get schemaVersion => 4; // كان 3 — إضافة LocalProducts/LocalPartners
  // (كاش كتالوج للطوارئ عند انقطاع الاتصال). لا حاجة لـ MigrationStrategy:
  // التطبيق قبل أول إصدار فعلي (STATUS.md)، لا تثبيتات قديمة يلزم ترحيلها.

  static QueryExecutor _openConnection() {
    return LazyDatabase(() async {
      final dbFolder = await getApplicationDocumentsDirectory();
      final file = File(p.join(dbFolder.path, 'pos_app.sqlite'));
      return NativeDatabase.createInBackground(file);
    });
  }

  // -- جلسات --

  Future<void> upsertSession(LocalPosSessionsCompanion session) =>
      into(localPosSessions).insertOnConflictUpdate(session);

  Future<LocalPosSession?> activeSession() =>
      (select(localPosSessions)..where((t) => t.status.equals('open')))
          .getSingleOrNull();

  /// نسخة تفاعلية من [activeSession] — تُستخدم من الشاشة الجذر لتقرير أي
  /// شاشة تُعرض (فتح جلسة/سلة) فور نجاح فتح/إغلاق جلسة، دون إعادة تحميل
  /// يدوية لأي Provider.
  Stream<LocalPosSession?> watchActiveSession() =>
      (select(localPosSessions)..where((t) => t.status.equals('open')))
          .watchSingleOrNull();

  // -- طابور المزامنة --

  Future<List<SyncQueueEntry>> pendingSyncEntries() =>
      (select(syncQueueEntries)
            ..orderBy([(t) => OrderingTerm.asc(t.createdAt)]))
          .get();

  Future<void> enqueue({
    required String id,
    required String sessionId,
    required String saleId,
  }) {
    return into(syncQueueEntries).insert(
      SyncQueueEntriesCompanion.insert(
        id: id,
        sessionId: sessionId,
        saleId: saleId,
        createdAt: DateTime.now(),
      ),
    );
  }

  Future<void> removeQueueEntriesForSale(String saleId) =>
      (delete(syncQueueEntries)..where((t) => t.saleId.equals(saleId))).go();

  Future<void> incrementAttempt(String queueEntryId) async {
    final entry = await (select(syncQueueEntries)
          ..where((t) => t.id.equals(queueEntryId)))
        .getSingleOrNull();
    if (entry == null) return;
    await (update(syncQueueEntries)..where((t) => t.id.equals(queueEntryId)))
        .write(SyncQueueEntriesCompanion(
      attemptCount: Value(entry.attemptCount + 1),
    ));
  }

  // -- تحديث نتيجة مزامنة فاتورة --

  Future<void> applySyncResult({
    required String saleId,
    required String status,
    String? serverInvoiceId,
    String? invoiceNumber,
    String? errorMessage,
  }) {
    return (update(localSales)..where((t) => t.id.equals(saleId))).write(
      LocalSalesCompanion(
        syncStatus: Value(status),
        serverInvoiceId: Value(serverInvoiceId),
        invoiceNumber: Value(invoiceNumber),
        lastSyncError: Value(errorMessage),
      ),
    );
  }

  // -- كاش الكتالوج (منتجات/عملاء) — راجع تعليق LocalProducts/LocalPartners --

  /// يستبدل الكاش المحلي بالكامل بأحدث نسخة من السيرفر (Full Replace، لا
  /// دمج جزئي) — بسيط ومتّسق دائماً مع آخر مزامنة ناجحة، على حساب فقدان
  /// أي حالة سابقة لعناصر حُذفت على السيرفر بين مزامنتين (مقبول لكاش
  /// طوارئ للقراءة فقط). يُنفَّذ ضمن معاملة واحدة (batch) لتفادي نافذة
  /// زمنية بكاش فارغ جزئياً لو فشل التنفيذ منتصفاً.
  Future<void> replaceProductsCache(
    List<LocalProductsCompanion> rows,
  ) {
    return batch((b) {
      b.deleteAll(localProducts);
      b.insertAll(localProducts, rows);
    });
  }

  Future<void> replacePartnersCache(
    List<LocalPartnersCompanion> rows,
  ) {
    return batch((b) {
      b.deleteAll(localPartners);
      b.insertAll(localPartners, rows);
    });
  }

  /// بحث محلي بالاسم أو رمز المنتج (SKU) — يُستخدم فقط عند تعذّر الوصول
  /// لِـ `/products` مباشرة (راجع product_picker_sheet.dart). فارغ الاستعلام
  /// يُرجع كل المنتجات النشطة (حتى 50، بنفس حد الصفحة الافتراضي للبحث الحي).
  Future<List<LocalProduct>> searchLocalProducts(String query) {
    final pattern = '%$query%';
    return (select(localProducts)
          ..where((t) =>
              t.isActive.equals(true) &
              (t.name.like(pattern) | t.sku.like(pattern)))
          ..orderBy([(t) => OrderingTerm.asc(t.name)])
          ..limit(50))
        .get();
  }

  /// بحث محلي بالاسم فقط — نفس منطق [searchLocalProducts] لكن للعملاء.
  Future<List<LocalPartner>> searchLocalPartners(String query) {
    final pattern = '%$query%';
    return (select(localPartners)
          ..where((t) => t.name.like(pattern))
          ..orderBy([(t) => OrderingTerm.asc(t.name)])
          ..limit(200))
        .get();
  }
}
