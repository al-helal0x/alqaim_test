import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:pos_app/core/auth/tenant_context.dart';

/// يبني JWT وهمي (بلا توقيع فعلي — الاختبار يغطي فك تشفير الحمولة فقط،
/// تماماً كما يفعل العميل الفعلي؛ التحقق من التوقيع مسؤولية السيرفر وحده).
String _fakeJwt(Map<String, dynamic> payload) {
  String segment(Object data) =>
      base64Url.encode(utf8.encode(jsonEncode(data))).replaceAll('=', '');
  return '${segment({
        'alg': 'HS256'
      })}.${segment(payload)}.fakesignature';
}

void main() {
  group('TenantContext.fromAccessToken', () {
    test('يستخرج company_id/user_id(sub)/branch_id من حمولة التوكن', () {
      final token = _fakeJwt({
        'company_id': 'c1',
        'sub': 'u1',
        'branch_id': 'b1',
      });

      final ctx = TenantContext.fromAccessToken(token);

      expect(ctx.companyId, 'c1');
      expect(ctx.userId, 'u1');
      expect(ctx.branchId, 'b1');
    });

    test('branch_id اختياري — null إن غاب عن الحمولة (يطابق auth_middleware.py)', () {
      final token = _fakeJwt({'company_id': 'c1', 'sub': 'u1'});

      final ctx = TenantContext.fromAccessToken(token);

      expect(ctx.branchId, isNull);
    });

    test('يرمي FormatException لتوكن بنية غير صالحة', () {
      expect(
        () => TenantContext.fromAccessToken('not-a-jwt'),
        throwsFormatException,
      );
    });

    test('يرمي FormatException عند غياب company_id أو sub', () {
      final token = _fakeJwt({'company_id': 'c1'});

      expect(
        () => TenantContext.fromAccessToken(token),
        throwsFormatException,
      );
    });
  });
}
