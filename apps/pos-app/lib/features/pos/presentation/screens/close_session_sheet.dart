import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../design/tokens.dart';
import '../../../../design/widgets/pos_button.dart';
import '../../../../design/widgets/pos_text_field.dart';

/// نافذة إغلاق الجلسة (نهاية الوردية) — تُفتح من شريط شاشة السلة. تتطلب
/// اتصالاً (راجع تعليق PosSessionRepository).
///
/// **تحذير مبيعات معلَّقة (قرار منتج محسوم الآن):** لا نمنع الإغلاق نهائياً
/// — بيع لم يُزامَن بعد يبقى في طابور المزامنة (`SyncQueueEntries`) ويُعاد
/// إرساله تلقائياً لاحقاً بصرف النظر عن حالة الجلسة (Idempotent عبر
/// client_reference، راجع تعليق AppDatabase). لكن نُحذّر الكاشير صراحةً
/// ونُلزمه بإقرار واعٍ (checkbox) قبل تفعيل زر التأكيد، بدل السماح بإغلاق
/// صامت قد يُخفي مشكلة اتصال حقيقية عن الكاشير في وقتها.
Future<void> showCloseSessionSheet(
  BuildContext context,
  WidgetRef ref, {
  required String sessionId,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) => _CloseSessionSheet(sessionId: sessionId),
  );
}

class _CloseSessionSheet extends ConsumerStatefulWidget {
  const _CloseSessionSheet({required this.sessionId});

  final String sessionId;

  @override
  ConsumerState<_CloseSessionSheet> createState() => _CloseSessionSheetState();
}

class _CloseSessionSheetState extends ConsumerState<_CloseSessionSheet> {
  final _closingCashController = TextEditingController();
  bool _submitting = false;
  String? _error;

  /// null = لا يزال يُحمَّل. 0 = لا شيء معلّق (لا تحذير). >0 = يلزم تحذير
  /// + إقرار صريح قبل تفعيل زر التأكيد. فشل التحميل يُعامَل بصمت كـ 0
  /// (Fail-open) — خطأ محلي عابر بقراءة العدّاد لا يجوز أن يمنع الكاشير من
  /// إغلاق وردية فعلياً.
  int? _pendingCount;
  bool _acknowledgedPending = false;

  @override
  void initState() {
    super.initState();
    _loadPendingCount();
  }

  Future<void> _loadPendingCount() async {
    try {
      final count = await ref
          .read(posRepositoryProvider)
          .pendingSyncCountForSession(widget.sessionId);
      if (mounted) setState(() => _pendingCount = count);
    } catch (_) {
      if (mounted) setState(() => _pendingCount = 0);
    }
  }

  @override
  void dispose() {
    _closingCashController.dispose();
    super.dispose();
  }

  bool get _hasPendingWarning => (_pendingCount ?? 0) > 0;

  Future<void> _submit() async {
    final closingCash = double.tryParse(_closingCashController.text);
    if (closingCash == null || closingCash < 0) {
      setState(() => _error = 'أدخل رصيد إغلاق صحيح');
      return;
    }
    if (_hasPendingWarning && !_acknowledgedPending) {
      // لا يُفترض الوصول هنا عملياً (الزر معطَّل بهذه الحالة) — حارس دفاعي
      // فقط، لا رسالة مستخدم إضافية مطلوبة.
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await ref.read(posSessionRepositoryProvider).closeSession(
            sessionId: widget.sessionId,
            closingCash: closingCash,
          );
      if (mounted) Navigator.of(context).pop();
    } on DioException catch (e) {
      final detail = e.response?.data is Map
          ? (e.response!.data as Map)['detail']?.toString()
          : null;
      setState(() => _error = detail ?? 'تعذّر إغلاق الجلسة — تحقق من الاتصال');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: PosSpacing.lg,
        right: PosSpacing.lg,
        top: PosSpacing.lg,
        bottom: MediaQuery.of(context).viewInsets.bottom + PosSpacing.lg,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('إغلاق الجلسة', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: PosSpacing.md),
          PosTextField(
            controller: _closingCashController,
            label: 'الرصيد الختامي (نقدي)',
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            autofocus: true,
          ),
          if (_hasPendingWarning) ...[
            const SizedBox(height: PosSpacing.md),
            _PendingSyncWarning(
              count: _pendingCount!,
              acknowledged: _acknowledgedPending,
              onAcknowledgedChanged: (v) =>
                  setState(() => _acknowledgedPending = v),
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: PosSpacing.sm),
            Text(_error!, style: const TextStyle(color: PosColors.danger)),
          ],
          const SizedBox(height: PosSpacing.lg),
          PosButton(
            label: 'تأكيد الإغلاق',
            variant: PosButtonVariant.danger,
            loading: _submitting,
            onPressed: _hasPendingWarning && !_acknowledgedPending
                ? null
                : _submit,
          ),
        ],
      ),
    );
  }
}

/// تحذير + إقرار صريح يظهر فقط عند وجود عمليات مزامنة معلَّقة لهذه الجلسة.
/// لا يمنع الإغلاق نهائياً — يُلزم الكاشير فقط بقراءة التحذير والموافقة
/// الواعية عليه (checkbox) قبل تفعيل زر التأكيد.
class _PendingSyncWarning extends StatelessWidget {
  const _PendingSyncWarning({
    required this.count,
    required this.acknowledged,
    required this.onAcknowledgedChanged,
  });

  final int count;
  final bool acknowledged;
  final ValueChanged<bool> onAcknowledgedChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(PosSpacing.md),
      decoration: BoxDecoration(
        color: PosColors.warning.withOpacity(0.1),
        borderRadius: BorderRadius.circular(PosRadii.md),
        border: Border.all(color: PosColors.warning.withOpacity(0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.warning_amber_rounded,
                  color: PosColors.warning, size: 20),
              const SizedBox(width: PosSpacing.sm),
              Expanded(
                child: Text(
                  count == 1
                      ? 'يوجد عملية بيع واحدة لم تُزامَن بعد مع السيرفر'
                      : 'يوجد $count عمليات بيع لم تُزامَن بعد مع السيرفر',
                  style: const TextStyle(
                    color: PosColors.textPrimary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: PosSpacing.xs),
          const Text(
            'ستبقى هذه العمليات في طابور المزامنة وتُرسَل تلقائياً عند '
            'توفر الاتصال، حتى بعد إغلاق الجلسة — لكن يُفضَّل التأكد من '
            'الاتصال قبل الإغلاق لتفادي تأخير غير ضروري.',
            style: TextStyle(color: PosColors.textSecondary, fontSize: 12),
          ),
          const SizedBox(height: PosSpacing.xs),
          CheckboxListTile(
            value: acknowledged,
            onChanged: (v) => onAcknowledgedChanged(v ?? false),
            controlAffinity: ListTileControlAffinity.leading,
            contentPadding: EdgeInsets.zero,
            dense: true,
            title: const Text(
              'أدرك ذلك وأرغب بإغلاق الجلسة رغم وجود عمليات معلَّقة',
              style: TextStyle(fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}
