import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../design/tokens.dart';
import '../../../../design/widgets/pos_button.dart';
import '../../../../design/widgets/pos_text_field.dart';

/// شاشة تسجيل الدخول — تمهيدية لازمة للوصول لشاشات POS الثلاث (مهمة #13
/// تطلب الشاشات الثلاث مباشرة، لكن بلا نقطة دخول للتطبيق لا معنى لها).
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await ref.read(authRepositoryProvider).login(
            email: _emailController.text.trim(),
            password: _passwordController.text,
          );
      ref.invalidate(hasSessionProvider);
      ref.invalidate(tenantContextProvider);
    } on DioException catch (e) {
      // نعرض تفصيل السيرفر كما هو عند توفره (401 برسالة عربية واضحة من
      // LoginUseCase — مثال: حساب عضو في أكثر من شركة يحتاج company_id،
      // حالة نادرة لجهاز POS لكن رسالة السيرفر تشرحها مباشرة بلا حاجة
      // لبناء شاشة اختيار شركة كاملة لهذا الاستثناء).
      final detail = e.response?.data is Map
          ? (e.response!.data as Map)['detail']?.toString()
          : null;
      setState(() => _error = detail ?? 'تعذّر تسجيل الدخول — تحقق من الاتصال');
    } catch (_) {
      setState(() => _error = 'تعذّر تسجيل الدخول — تحقق من البريد وكلمة المرور');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 380),
            child: Padding(
              padding: const EdgeInsets.all(PosSpacing.lg),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.point_of_sale, size: 56, color: PosColors.primary),
                  const SizedBox(height: PosSpacing.sm),
                  Text('AlQaim POS', style: Theme.of(context).textTheme.headlineSmall),
                  const SizedBox(height: PosSpacing.xl),
                  PosTextField(
                    controller: _emailController,
                    label: 'البريد الإلكتروني',
                    keyboardType: TextInputType.emailAddress,
                    prefixIcon: Icons.mail_outline,
                  ),
                  const SizedBox(height: PosSpacing.md),
                  PosTextField(
                    controller: _passwordController,
                    label: 'كلمة المرور',
                    obscureText: true,
                    prefixIcon: Icons.lock_outline,
                    onSubmitted: (_) => _submit(),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: PosSpacing.md),
                    Text(
                      _error!,
                      style: const TextStyle(color: PosColors.danger),
                      textAlign: TextAlign.center,
                    ),
                  ],
                  const SizedBox(height: PosSpacing.lg),
                  PosButton(
                    label: 'دخول',
                    loading: _loading,
                    onPressed: _submit,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
