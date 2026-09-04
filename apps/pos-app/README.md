# apps/pos-app

Flutter — يُشغَّل كجهاز نقطة بيع **مستقل تماماً** Offline-first (Blueprint §13.3،
وليس صفحة داخل `apps/web`)، قد يُدمَج لاحقاً مع `apps/mobile`. يعتمد على
`local_sync_queue` وسياسة تعارض "آخر تحديث فائز على مستوى الحقل + تنبيه عند
تعارض الكميات السالبة" (القسم 6.11).

نظام التصميم: Flutter محلي مستقل (`lib/design/`) — **قرار نهائي**، وليس
حلاً مؤقتاً بانتظار `packages/ui-kit` (React/TSX، غير قابل للاستخدام من
Flutter تقنياً). راجع `lib/design/README.md` والقسم المقابل في `STATUS.md`.

## البدء السريع
```bash
cd apps/pos-app
flutter pub get
dart run build_runner build --delete-conflicting-outputs   # يولّد ملفات drift (*.g.dart)
flutter test
flutter run --dart-define=API_BASE_URL=http://<core-api-host>:8000
```

## البنية
انظر `STATUS.md` لحالة تعريف الانتهاء (DoD) وشرح كل طبقة (`core/`, `data/`,
`design/`, `features/`).
