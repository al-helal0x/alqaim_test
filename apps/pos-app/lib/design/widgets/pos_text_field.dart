import 'package:flutter/material.dart';

/// حقل نص موحّد — يفوّض التنسيق البصري بالكامل لـ InputDecorationTheme
/// (design/theme.dart) كي لا يتكرر أي تنسيق يدوي داخل الشاشات.
class PosTextField extends StatelessWidget {
  const PosTextField({
    super.key,
    this.controller,
    this.label,
    this.hint,
    this.keyboardType,
    this.obscureText = false,
    this.autofocus = false,
    this.onChanged,
    this.onSubmitted,
    this.prefixIcon,
    this.enabled = true,
  });

  final TextEditingController? controller;
  final String? label;
  final String? hint;
  final TextInputType? keyboardType;
  final bool obscureText;
  final bool autofocus;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final IconData? prefixIcon;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      obscureText: obscureText,
      autofocus: autofocus,
      enabled: enabled,
      onChanged: onChanged,
      onSubmitted: onSubmitted,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: prefixIcon == null ? null : Icon(prefixIcon),
      ),
    );
  }
}
