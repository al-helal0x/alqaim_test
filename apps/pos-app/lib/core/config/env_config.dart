/// إعدادات البيئة لتطبيق نقطة البيع.
///
/// القيم تُمرَّر عبر `--dart-define` عند البناء/التشغيل، مثال:
/// flutter run --dart-define=API_BASE_URL=https://api.alqaim.example
///
/// لا قيم افتراضية للإنتاج هنا عمداً — فقط قيمة محلية للتطوير.
class EnvConfig {
  EnvConfig._();

  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    // محاكي أندرويد -> Docker على المضيف. لا بادئة /v1 على core-api فعلياً
    // (main.dart: app.include_router بلا أي prefix عام) والمنفذ 8000 وليس
    // 8080 (Dockerfile.core-api / docker-compose: CMD uvicorn --port 8000).
    // كانت القيمة السابقة (.../8080/v1) ستُفشل كل نداء بـ 404 فور اختبار
    // فعلي ضد سيرفر حقيقي — صُححت هنا (مهمة #13).
    defaultValue: 'http://10.0.2.2:8000',
  );

  /// مهلة الاتصال والاستقبال بالميلي ثانية.
  static const int connectTimeoutMs = 10000;
  static const int receiveTimeoutMs = 15000;

  /// الفاصل الزمني الأدنى بين محاولات المزامنة التلقائية عند استعادة الاتصال.
  static const Duration syncDebounce = Duration(seconds: 2);
}
