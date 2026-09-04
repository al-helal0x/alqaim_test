import 'dart:async';

import 'package:drift/drift.dart';

/// يُشغَّل تلقائياً من Flutter قبل أي ملف اختبار بهذا المجلد (اتفاقية
/// اسم الملف نفسها كافية — لا حاجة لاستيراده يدوياً في أي test).
///
/// السبب: بعض الاختبارات (payment_screen_test.dart، sale_screen_test.dart)
/// تُنشئ AppDatabase.forTesting(...) أكثر من مرة عبر عدة اختبارات، فيُصدر
/// drift تحذيراً عاماً حول تعدد النسخ (مخصّص أصلاً لحالة قواعد بيانات حقيقية
/// تتشارك نفس الملف/الاتصال). هنا كل اختبار يستخدم QueryExecutor منفصلاً
/// بالذاكرة، فلا يوجد خطر تضارب فعلي — هذا السطر يوقف التحذير غير المفيد
/// فقط، بدون أي تأثير على سلوك الاختبارات نفسها.
Future<void> testExecutable(FutureOr<void> Function() testMain) async {
  driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;
  await testMain();
}
