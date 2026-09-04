import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../data/models/warehouse_dto.dart';
import '../../../../design/tokens.dart';
import '../../../../design/widgets/empty_state.dart';
import '../../../../design/widgets/pos_button.dart';
import '../../../../design/widgets/pos_scaffold.dart';
import '../../../../design/widgets/pos_text_field.dart';

/// فتح جلسة POS — **يتطلب اتصالاً دائماً** (ليست عملية Offline-first
/// بطبيعتها، راجع تعليق PosSessionRepository) — بداية الوردية.
class OpenSessionScreen extends ConsumerStatefulWidget {
  const OpenSessionScreen({super.key});

  @override
  ConsumerState<OpenSessionScreen> createState() => _OpenSessionScreenState();
}

class _OpenSessionScreenState extends ConsumerState<OpenSessionScreen> {
  final _openingCashController = TextEditingController(text: '0');
  WarehouseDto? _selectedWarehouse;
  List<WarehouseDto>? _warehouses;
  bool _loadingWarehouses = true;
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadWarehouses();
  }

  @override
  void dispose() {
    _openingCashController.dispose();
    super.dispose();
  }

  Future<void> _loadWarehouses() async {
    setState(() {
      _loadingWarehouses = true;
      _error = null;
    });
    try {
      final tenantContext = await ref.read(tenantContextProvider.future);
      final warehouses = await ref
          .read(warehousesRemoteDataSourceProvider)
          .listWarehouses(branchId: tenantContext?.branchId);
      final active = warehouses.where((w) => w.isActive).toList();
      setState(() {
        _warehouses = active;
        _selectedWarehouse = active.length == 1 ? active.first : null;
      });
    } catch (_) {
      setState(() => _error = 'تعذّر تحميل قائمة المستودعات — تحقق من الاتصال');
    } finally {
      if (mounted) setState(() => _loadingWarehouses = false);
    }
  }

  Future<void> _submit() async {
    final warehouse = _selectedWarehouse;
    if (warehouse == null) return;

    final openingCash = double.tryParse(_openingCashController.text) ?? 0;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await ref.read(posSessionRepositoryProvider).openSession(
            warehouseId: warehouse.id,
            openingCash: openingCash,
          );
      // activeSessionProvider (Stream) يلتقط الجلسة الجديدة تلقائياً من
      // القاعدة المحلية — root shell ينتقل لشاشة السلة دون تدخل هنا.
    } on DioException catch (e) {
      final detail = e.response?.data is Map
          ? (e.response!.data as Map)['detail']?.toString()
          : null;
      setState(() => _error = detail ?? 'تعذّر فتح الجلسة — تحقق من الاتصال');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return PosScaffold(
      title: 'فتح جلسة POS',
      body: _loadingWarehouses
          ? const Center(child: CircularProgressIndicator())
          : _buildForm(),
    );
  }

  Widget _buildForm() {
    final warehouses = _warehouses ?? const [];
    if (warehouses.isEmpty && _error == null) {
      return PosEmptyState(
        icon: Icons.warehouse_outlined,
        message: 'لا توجد مستودعات نشطة متاحة لفتح جلسة عليها',
        action: PosButton(label: 'إعادة المحاولة', onPressed: _loadWarehouses),
      );
    }

    return ListView(
      padding: const EdgeInsets.all(PosSpacing.lg),
      children: [
        Text('المستودع', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: PosSpacing.sm),
        ...warehouses.map(
          (w) => RadioListTile<WarehouseDto>(
            title: Text(w.name),
            value: w,
            groupValue: _selectedWarehouse,
            onChanged: (v) => setState(() => _selectedWarehouse = v),
          ),
        ),
        const SizedBox(height: PosSpacing.lg),
        PosTextField(
          controller: _openingCashController,
          label: 'الرصيد الافتتاحي (نقدي)',
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
        ),
        if (_error != null) ...[
          const SizedBox(height: PosSpacing.md),
          Text(_error!, style: const TextStyle(color: PosColors.danger)),
        ],
        const SizedBox(height: PosSpacing.lg),
        PosButton(
          label: 'فتح الجلسة',
          icon: Icons.play_circle_outline,
          loading: _submitting,
          onPressed: _selectedWarehouse == null ? null : _submit,
        ),
      ],
    );
  }
}
