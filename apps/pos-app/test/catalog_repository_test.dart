// PKG-D2 — Unit tests: CatalogRepository (catalog_repository.dart).
//
// نطاق: منطق الترحيل عبر الصفحات (pagination loop) + الاستبدال الكامل
// للكاش المحلي (Full Replace) + البحث المحلي بعد المزامنة — كلها عبر
// قاعدة بيانات drift حقيقية بالذاكرة (لا AppDatabase() الحقيقية، لا
// path_provider). مصدرا البيانات البعيدان مُزيَّفان بالكامل (بلا أي نداء
// شبكة) لعزل منطق الصفحات نفسه عن أي تفاصيل HTTP.
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pos_app/core/network/api_client.dart';
import 'package:pos_app/data/local/app_database.dart';
import 'package:pos_app/data/models/catalog_dto.dart';
import 'package:pos_app/data/models/partner_dto.dart';
import 'package:pos_app/data/repositories/catalog_remote_data_source.dart';
import 'package:pos_app/data/repositories/catalog_repository.dart';
import 'package:pos_app/data/repositories/partners_remote_data_source.dart';

/// يُرجع صفحات مُعدَّة مسبقاً حسب رقم الصفحة المطلوب — يُحاكي سيرفراً
/// حقيقياً بصفحات متعددة بلا أي نداء HTTP فعلي.
class _FakeCatalogRemoteDataSource extends CatalogRemoteDataSource {
  _FakeCatalogRemoteDataSource(this._pages) : super(ApiClient());

  final Map<int, ProductPage> _pages;
  int callCount = 0;

  @override
  Future<ProductPage> searchProducts({
    String? search,
    int page = 1,
    int pageSize = 30,
  }) async {
    callCount++;
    return _pages[page] ?? const ProductPage(items: [], total: 0);
  }
}

class _FakePartnersRemoteDataSource extends PartnersRemoteDataSource {
  _FakePartnersRemoteDataSource(this._pages) : super(ApiClient());

  final Map<int, PartnerPage> _pages;
  int callCount = 0;

  @override
  Future<PartnerPage> listPartners({int page = 1, int pageSize = 200}) async {
    callCount++;
    return _pages[page] ?? const PartnerPage(items: [], total: 0);
  }
}

class _ThrowingPartnersRemoteDataSource extends PartnersRemoteDataSource {
  _ThrowingPartnersRemoteDataSource() : super(ApiClient());

  @override
  Future<PartnerPage> listPartners({int page = 1, int pageSize = 200}) async {
    throw Exception('network down');
  }
}

ProductDto _product(String id) => ProductDto(
      id: id,
      sku: 'SKU-$id',
      name: 'منتج $id',
      salePrice: 1000,
      trackInventory: false,
      isActive: true,
    );

void main() {
  late AppDatabase database;

  setUp(() {
    database = AppDatabase.forTesting(NativeDatabase.memory());
  });

  tearDown(() async {
    await database.close();
  });

  group('CatalogRepository.syncProducts', () {
    test('يمرّ عبر كل الصفحات ويستبدل الكاش المحلي بالكامل', () async {
      final remote = _FakeCatalogRemoteDataSource({
        1: ProductPage(items: [_product('p1'), _product('p2')], total: 3),
        2: ProductPage(items: [_product('p3')], total: 3),
      });
      final repository = CatalogRepository(
        database: database,
        catalogRemoteDataSource: remote,
        partnersRemoteDataSource: _FakePartnersRemoteDataSource({}),
      );

      final count = await repository.syncProducts();

      expect(count, 3);
      expect(remote.callCount, 2); // توقّف عند total، لا صفحة ثالثة زائدة
      final cached = await repository.searchLocalProducts('');
      expect(cached.map((p) => p.id).toSet(), {'p1', 'p2', 'p3'});
    });

    test('مزامنة ثانية تستبدل الكاش القديم بالكامل (لا تراكم)', () async {
      final repository = CatalogRepository(
        database: database,
        catalogRemoteDataSource: _FakeCatalogRemoteDataSource({
          1: ProductPage(items: [_product('old')], total: 1),
        }),
        partnersRemoteDataSource: _FakePartnersRemoteDataSource({}),
      );
      await repository.syncProducts();

      final repository2 = CatalogRepository(
        database: database,
        catalogRemoteDataSource: _FakeCatalogRemoteDataSource({
          1: ProductPage(items: [_product('new')], total: 1),
        }),
        partnersRemoteDataSource: _FakePartnersRemoteDataSource({}),
      );
      await repository2.syncProducts();

      final cached = await repository2.searchLocalProducts('');
      expect(cached.map((p) => p.id).toList(), ['new']);
    });
  });

  group('CatalogRepository.searchLocalProducts', () {
    test('يُطابق بالاسم أو SKU، ويستبعد غير المفعَّل', () async {
      final repository = CatalogRepository(
        database: database,
        catalogRemoteDataSource: _FakeCatalogRemoteDataSource({
          1: const ProductPage(
            items: [
              ProductDto(
                id: 'p1',
                sku: 'ABC-1',
                name: 'قهوة عربية',
                salePrice: 3000,
                trackInventory: false,
                isActive: true,
              ),
              ProductDto(
                id: 'p2',
                sku: 'XYZ-2',
                name: 'شاي أحمر',
                salePrice: 1500,
                trackInventory: false,
                isActive: false, // غير مفعَّل — يجب استبعاده من البحث
              ),
            ],
            total: 2,
          ),
        }),
        partnersRemoteDataSource: _FakePartnersRemoteDataSource({}),
      );
      await repository.syncProducts();

      expect((await repository.searchLocalProducts('قهوة')).length, 1);
      expect((await repository.searchLocalProducts('ABC')).length, 1);
      expect((await repository.searchLocalProducts('شاي')).length, 0);
    });
  });

  group('CatalogRepository.syncPartners', () {
    test('يمرّ عبر كل الصفحات ويستبدل الكاش المحلي بالكامل', () async {
      final repository = CatalogRepository(
        database: database,
        catalogRemoteDataSource: _FakeCatalogRemoteDataSource({}),
        partnersRemoteDataSource: _FakePartnersRemoteDataSource({
          1: const PartnerPage(
            items: [
              PartnerDto(id: 'c1', name: 'أحمد'),
              PartnerDto(id: 'c2', name: 'سارة'),
            ],
            total: 2,
          ),
        }),
      );

      final count = await repository.syncPartners();

      expect(count, 2);
      final cached = await repository.searchLocalPartners('');
      expect(cached.map((p) => p.id).toSet(), {'c1', 'c2'});
    });
  });

  group('CatalogRepository.syncAll', () {
    test('فشل مزامنة العملاء لا يمنع نجاح مزامنة المنتجات (والعكس)',
        () async {
      final repository = CatalogRepository(
        database: database,
        catalogRemoteDataSource: _FakeCatalogRemoteDataSource({
          1: ProductPage(items: [_product('p1')], total: 1),
        }),
        partnersRemoteDataSource: _ThrowingPartnersRemoteDataSource(),
      );

      // لا يجوز أن يرمي syncAll استثناءً حتى لو فشل أحد الجانبين.
      await repository.syncAll();

      final cachedProducts = await repository.searchLocalProducts('');
      expect(cachedProducts, hasLength(1));
    });
  });
}
