import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'design/theme.dart';
import 'features/pos/presentation/root_shell.dart';

void main() {
  runApp(const ProviderScope(child: PosApp()));
}

class PosApp extends StatelessWidget {
  const PosApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AlQaim POS',
      debugShowCheckedModeBanner: false,
      theme: PosTheme.light(),
      // اتجاه RTL يدوي عبر Directionality — إضافة flutter_localizations
      // الكاملة (SDK package) خارج نطاق هذه المهمة (تغيير pubspec.yaml +
      // إعداد توليد الترجمات)، وواجهات pos-app نصوصها عربية ثابتة بلا
      // حاجة فعلية لتعدد لغات الآن.
      builder: (context, child) => Directionality(
        textDirection: TextDirection.rtl,
        child: child!,
      ),
      home: const RootShell(),
    );
  }
}
