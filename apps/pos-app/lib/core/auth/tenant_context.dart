import 'dart:convert';

/// يطابق شكل TenantContext المستقر المستخدم عبر النظام بالكامل
/// (company_id, user_id, branch_id) — مُتحقَّق مباشرة مقابل
/// `platform_core/auth_middleware.py`: `branch_id` **اختياري** فعلياً
/// (`str | None`) في التوكن نفسه، لذا يجب أن يكون كذلك هنا أيضاً — جهاز
/// POS قد يُشغَّل بحساب غير مربوط بفرع محدد.
///
/// تصحيح جوهري (مهمة #13): الجولة السابقة افترضت أن استجابة `/auth/login`
/// تحتوي حقل `tenant_context` صريحاً. تأكَّد الآن مقابل
/// `identity_dto.TokenResponse` أن هذا غير صحيح — الاستجابة الفعلية
/// `{access_token, refresh_token, token_type}` فقط، بلا أي معلومة مستأجر.
/// المصدر الوحيد لـ company_id/user_id/branch_id فعلياً هو **حمولة الـ JWT
/// نفسها** (`auth_middleware.get_current_context`: `company_id`، `sub`
/// لـ user_id، `branch_id`) — العميل لا يتحقق من التوقيع (السيرفر وحده
/// يفعل ذلك)، فقط يقرأ الحمولة لعرض السياق محلياً وإرفاقه بالطلبات.
class TenantContext {
  final String companyId;
  final String userId;
  final String? branchId;

  const TenantContext({
    required this.companyId,
    required this.userId,
    this.branchId,
  });

  /// يفك تشفير حمولة JWT (بلا تحقق توقيع — القراءة فقط) لاستخراج السياق.
  /// يرمي [FormatException] إن كان التوكن مشوَّهاً أو ناقص الحقول الإلزامية.
  factory TenantContext.fromAccessToken(String accessToken) {
    final parts = accessToken.split('.');
    if (parts.length != 3) {
      throw const FormatException('توكن JWT غير صالح: بنية غير متوقعة');
    }

    final normalized = base64Url.normalize(parts[1]);
    final payload =
        jsonDecode(utf8.decode(base64Url.decode(normalized)))
            as Map<String, dynamic>;

    final companyId = payload['company_id'] as String?;
    final userId = payload['sub'] as String?;
    if (companyId == null || userId == null) {
      throw const FormatException(
        'توكن JWT ناقص: company_id أو sub (user_id) مفقودان',
      );
    }

    return TenantContext(
      companyId: companyId,
      userId: userId,
      branchId: payload['branch_id'] as String?,
    );
  }

  /// للتخزين المحلي فقط (SessionStorage) — لا علاقة له بشكل استجابة السيرفر.
  factory TenantContext.fromJson(Map<String, dynamic> json) {
    return TenantContext(
      companyId: json['company_id'] as String,
      userId: json['user_id'] as String,
      branchId: json['branch_id'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'company_id': companyId,
        'user_id': userId,
        'branch_id': branchId,
      };

  @override
  String toString() =>
      'TenantContext(company_id: $companyId, user_id: $userId, branch_id: $branchId)';
}
