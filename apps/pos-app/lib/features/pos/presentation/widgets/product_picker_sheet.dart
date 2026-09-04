import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../data/models/catalog_dto.dart';
import '../../../../design/tokens.dart';
import '../../../../design/widgets/empty_state.dart';
import '../../../../design/widgets/money_text.dart';
import '../../../../design/widgets/pos_text_field.dart';
import 'offline_cache_banner.dart';

/// نافذة بحث/اختيار منتج لإضافته للسلة — بحث مباشر على `/products`
/// (`search=`، مدعوم فعلياً على السيرفر بخلاف `/partners`).
///
/// **fallback عند انقطاع الاتصال:** إن فشل نداء البحث الحي، نُحاول كاش
/// الكتالوج المحلي (راجع CatalogRepository/CatalogSyncManager) قبل عرض
/// رسالة خطأ — نتائج الكاش قد لا تعكس آخر سعر/حالة تفعيل لحظياً، لذا
/// تُعرض مع تنبيه صريح "غير متصل".
Future<ProductDto?> showProductPickerSheet(BuildContext context) {
  return showModalBottomSheet<ProductDto>(
    context: context,
    isScrollControlled: true,
    builder: (_) => const _ProductPickerSheet(),
  );
}

class _ProductPickerSheet extends ConsumerStatefulWidget {
  const _ProductPickerSheet();

  @override
  ConsumerState<_ProductPickerSheet> createState() => _ProductPickerSheetState();
}

class _ProductPickerSheetState extends ConsumerState<_ProductPickerSheet> {
  final _searchController = TextEditingController();
  Timer? _debounce;
  List<ProductDto>? _results;
  bool _loading = true;
  bool _fromLocalCache = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _search('');
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () => _search(value));
  }

  Future<void> _search(String query) async {
    setState(() {
      _loading = true;
      _error = null;
      _fromLocalCache = false;
    });
    try {
      final page = await ref
          .read(catalogRemoteDataSourceProvider)
          .searchProducts(search: query);
      setState(() => _results = page.items.where((p) => p.isActive).toList());
    } catch (_) {
      await _searchLocalFallback(query);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  /// يُستدعى فقط بعد فشل البحث الحي — يحاول كاش الكتالوج المحلي. نتائج
  /// فارغة من الكاش (لم تحدث مزامنة ناجحة بعد، أو لا نتائج مطابقة فعلاً)
  /// تُعامَل كخطأ اتصال عادي، لا فرق ظاهري للمستخدم في هذه الحالة تحديداً.
  Future<void> _searchLocalFallback(String query) async {
    try {
      final local =
          await ref.read(catalogRepositoryProvider).searchLocalProducts(query);
      if (local.isNotEmpty) {
        setState(() {
          _results = local;
          _fromLocalCache = true;
        });
        return;
      }
    } catch (_) {
      // تجاهل — نسقط لرسالة الخطأ العادية أدناه.
    }
    setState(() => _error = 'تعذّر البحث عن المنتجات — تحقق من الاتصال');
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (context, scrollController) {
        return Padding(
          padding: const EdgeInsets.all(PosSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('إضافة منتج', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: PosSpacing.md),
              PosTextField(
                controller: _searchController,
                hint: 'ابحث بالاسم أو رمز المنتج (SKU)...',
                prefixIcon: Icons.search,
                autofocus: true,
                onChanged: _onChanged,
              ),
              const SizedBox(height: PosSpacing.md),
              if (_fromLocalCache) ...[
                const OfflineCacheBanner(),
                const SizedBox(height: PosSpacing.sm),
              ],
              Expanded(child: _buildResults(scrollController)),
            ],
          ),
        );
      },
    );
  }

  Widget _buildResults(ScrollController scrollController) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return PosEmptyState(icon: Icons.wifi_off, message: _error!);
    }
    final results = _results ?? const [];
    if (results.isEmpty) {
      return const PosEmptyState(
        icon: Icons.inventory_2_outlined,
        message: 'لا نتائج مطابقة',
      );
    }

    return ListView.separated(
      controller: scrollController,
      itemCount: results.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final product = results[index];
        return ListTile(
          title: Text(product.name),
          subtitle: Text(product.sku, style: const TextStyle(color: PosColors.textSecondary)),
          trailing: MoneyText(product.salePrice),
          onTap: () => Navigator.of(context).pop(product),
        );
      },
    );
  }
}
