import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pos_app/core/auth/tenant_context.dart';
import 'package:pos_app/data/local/app_database.dart';
import 'package:pos_app/data/models/pos_sync_dto.dart';
import 'package:pos_app/data/repositories/pos_repository.dart';
import 'package:pos_app/data/repositories/pos_session_repository.dart';

const _tenant = TenantContext(companyId: 'c1', userId: 'u1', branchId: 'b1');

Future<void> _seedOpenSession(AppDatabase database, {String id = 's1'}) {
  return database.upsertSession(
    LocalPosSessionsCompanion.insert(
      id: id,
      companyId: _tenant.companyId,
      warehouseId: 'w1',
      openedBy: _tenant.userId,
      openingCash: 0,
      status: 'open',
      openedAt: DateTime.now(),
    ),
  );
}

/// يُحدِّث جلسة موجودة مسبقاً (بنفس id) إلى 'closed' — يُستخدم لضمان
/// عدم وجود أكثر من جلسة 'open' واحدة في آنٍ واحد أثناء الاختبار
/// (activeSession() تفترض دائماً صفاً واحداً كحد أقصى بحالة open).
Future<void> _closeSession(AppDatabase database, String id) {
  return database.upsertSession(
    LocalPosSessionsCompanion.insert(
      id: id,
      companyId: _tenant.companyId,
      warehouseId: 'w1',
      openedBy: _tenant.userId,
      openingCash: 0,
      status: 'closed',
      openedAt: DateTime.now(),
    ),
  );
}

void main() {
  group('PosRepository (offline-first, يتطلب جلسة مفتوحة)', () {
    late AppDatabase database;
    late PosRepository repository;

    setUp(() {
      database = AppDatabase.forTesting(NativeDatabase.memory());
      repository = PosRepository(database: database);
    });

    tearDown(() async {
      await database.close();
    });

    test('createDraftSale يرفض العملية بلا جلسة POS مفتوحة', () async {
      await expectLater(
        repository.createDraftSale(
          tenantContext: _tenant,
          partnerId: 'p1',
          lines: const [
            PosSaleLineDto(productId: 'prod1', quantity: 1, unitPrice: 1000),
          ],
        ),
        throwsA(isA<NoActiveSessionError>()),
      );
    });

    test(
        'createDraftSale يخزّن الفاتورة محلياً ويضيفها لطابور المزامنة '
        'عند وجود جلسة مفتوحة', () async {
      await _seedOpenSession(database);

      final saleId = await repository.createDraftSale(
        tenantContext: _tenant,
        partnerId: 'p1',
        lines: const [
          PosSaleLineDto(productId: 'prod1', quantity: 2, unitPrice: 1500),
        ],
      );

      final sales = await repository.listRecentSales();
      expect(sales, hasLength(1));
      expect(sales.first.id, saleId);
      expect(sales.first.sessionId, 's1');
      expect(sales.first.displayTotal, 3000);
      expect(sales.first.syncStatus, 'pending');

      final pending = await database.pendingSyncEntries();
      expect(pending, hasLength(1));
      expect(pending.first.saleId, saleId);
      expect(pending.first.sessionId, 's1');

      final payload = await repository.buildSyncPayload(saleId);
      expect(payload.clientReference, saleId);
      expect(payload.partnerId, 'p1');
      expect(payload.lines, hasLength(1));
    });

    test(
        'pendingSyncCountForSession يُرجع صفراً بلا أي مبيعات لهذه الجلسة',
        () async {
      await _seedOpenSession(database);
      expect(await repository.pendingSyncCountForSession('s1'), 0);
    });

    test(
        'pendingSyncCountForSession يعدّ فقط طابور المزامنة الخاص بنفس '
        'الجلسة، ويتجاهل جلسات أخرى', () async {
      // بيعان لِـ s1 بينما هي الجلسة المفتوحة الوحيدة، ثم نُغلقها ونفتح
      // s2 لبيع ثالث — activeSession() تفترض جلسة "open" واحدة كحد أقصى
      // في أي وقت.
      await _seedOpenSession(database, id: 's1');
      await repository.createDraftSale(
        tenantContext: _tenant,
        partnerId: 'p1',
        lines: const [
          PosSaleLineDto(productId: 'prod1', quantity: 1, unitPrice: 1000),
        ],
      );
      await repository.createDraftSale(
        tenantContext: _tenant,
        partnerId: 'p1',
        lines: const [
          PosSaleLineDto(productId: 'prod2', quantity: 1, unitPrice: 500),
        ],
      );

      await _closeSession(database, 's1');
      await _seedOpenSession(database, id: 's2');
      await repository.createDraftSale(
        tenantContext: _tenant,
        partnerId: 'p1',
        lines: const [
          PosSaleLineDto(productId: 'prod3', quantity: 1, unitPrice: 750),
        ],
      );

      expect(await repository.pendingSyncCountForSession('s1'), 2);
      expect(await repository.pendingSyncCountForSession('s2'), 1);
      expect(await repository.pendingSyncCountForSession('unknown'), 0);
    });
  });
}
