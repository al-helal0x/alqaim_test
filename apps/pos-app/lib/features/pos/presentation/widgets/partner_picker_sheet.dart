import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../data/models/partner_dto.dart';
import '../../../../design/tokens.dart';
import '../../../../design/widgets/empty_state.dart';
import '../../../../design/widgets/pos_text_field.dart';
import 'offline_cache_banner.dart';

/// نافذة اختيار عميل — فلترة نصية **محلية** (السيرفر لا يدعم `search=` على
/// `/partners`، راجع تعليق PartnersRemoteDataSource).
///
/// **fallback عند انقطاع الاتصال:** إن فشل تحميل قائمة العملاء من
/// `/partners`، نُحاول كاش الكتالوج المحلي (راجع
/// CatalogRepository/CatalogSyncManager) قبل عرض رسالة خطأ.
Future<PartnerDto?> showPartnerPickerSheet(BuildContext context) {
  return showModalBottomSheet<PartnerDto>(
    context: context,
    isScrollControlled: true,
    builder: (_) => const _PartnerPickerSheet(),
  );
}

class _PartnerPickerSheet extends ConsumerStatefulWidget {
  const _PartnerPickerSheet();

  @override
  ConsumerState<_PartnerPickerSheet> createState() => _PartnerPickerSheetState();
}

class _PartnerPickerSheetState extends ConsumerState<_PartnerPickerSheet> {
  final _searchController = TextEditingController();
  List<PartnerDto>? _all;
  bool _loading = true;
  bool _fromLocalCache = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _fromLocalCache = false;
    });
    try {
      final page = await ref.read(partnersRemoteDataSourceProvider).listPartners();
      setState(() => _all = page.items);
    } catch (_) {
      await _loadLocalFallback();
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  /// يُستدعى فقط بعد فشل التحميل الحي — يحاول كاش الكتالوج المحلي (كل
  /// العملاء المخزَّنين، الفلترة النصية تبقى محلية دائماً في `_filtered`
  /// بصرف النظر عن مصدر `_all`).
  Future<void> _loadLocalFallback() async {
    try {
      final local =
          await ref.read(catalogRepositoryProvider).searchLocalPartners('');
      if (local.isNotEmpty) {
        setState(() {
          _all = local;
          _fromLocalCache = true;
        });
        return;
      }
    } catch (_) {
      // تجاهل — نسقط لرسالة الخطأ العادية أدناه.
    }
    setState(() => _error = 'تعذّر تحميل قائمة العملاء — تحقق من الاتصال');
  }

  List<PartnerDto> get _filtered {
    final all = _all ?? const [];
    final query = _searchController.text.trim();
    if (query.isEmpty) return all;
    return all
        .where((p) => p.name.toLowerCase().contains(query.toLowerCase()))
        .toList();
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
              Text('اختيار عميل', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: PosSpacing.md),
              PosTextField(
                controller: _searchController,
                hint: 'ابحث بالاسم...',
                prefixIcon: Icons.search,
                autofocus: true,
                onChanged: (_) => setState(() {}),
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
    final results = _filtered;
    if (results.isEmpty) {
      return const PosEmptyState(icon: Icons.people_outline, message: 'لا نتائج مطابقة');
    }

    return ListView.separated(
      controller: scrollController,
      itemCount: results.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final partner = results[index];
        return ListTile(
          title: Text(partner.name),
          subtitle: partner.phone == null ? null : Text(partner.phone!),
          onTap: () => Navigator.of(context).pop(partner),
        );
      },
    );
  }
}
