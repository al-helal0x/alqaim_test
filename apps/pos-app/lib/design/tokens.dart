import 'package:flutter/material.dart';

/// نظام تصميم Flutter محلي مستقل لِـ pos-app — راجع الحسم الصريح لمهمة
/// #13: `packages/ui-kit` هو React/TSX للويب فقط ولا يمكن لـ Flutter
/// استهلاكه تقنياً (لا جسر توليد كود من TSX إلى Flutter widgets، ولا هذا
/// مطروحاً في Blueprint). هذا القرار **نهائي وليس حلاً مؤقتاً بانتظار
/// شيء** — pos-app يملك نظام تصميمه الخاص من الآن فصاعداً، بشكل مستقل
/// تماماً عن أي تغيير مستقبلي في ui-kit.
///
/// القيم أدناه محافظة عمداً (بلا هوية بصرية "رسمية" موثَّقة لـ AlQaim حتى
/// الآن) — قابلة للتعديل لاحقاً بلا أثر على بنية الشاشات (كل شيء يمر من
/// هنا ومن [PosTheme] فقط، لا ألوان/مسافات مبعثرة داخل الشاشات).
class PosColors {
  PosColors._();

  static const Color primary = Color(0xFF1E3A5F); // كحلي — لوحة كاشير هادئة
  static const Color primaryContainer = Color(0xFFE3ECF7);
  static const Color success = Color(0xFF2E7D32);
  static const Color danger = Color(0xFFC62828);
  static const Color warning = Color(0xFFB8860B);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceAlt = Color(0xFFF4F6F9);
  static const Color border = Color(0xFFDDE3EA);
  static const Color textPrimary = Color(0xFF16202A);
  static const Color textSecondary = Color(0xFF5C6B7A);
}

/// وحدة أساسية 4px — كل مسافة في الشاشات مضاعف لهذه القيمة (يوافق شبكة
/// Material القياسية، اختيار عملي وليس هوية بصرية مقصودة).
class PosSpacing {
  PosSpacing._();

  static const double xs = 4;
  static const double sm = 8;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;
  static const double xxl = 48;
}

class PosRadii {
  PosRadii._();

  static const double sm = 6;
  static const double md = 12;
  static const double lg = 20;
}

/// أحجام لمس مريحة على تابلت الكاشير (بيئة استخدام POS النموذجية) — أكبر
/// من الافتراضي الهاتفي لتقليل أخطاء اللمس أثناء وردية سريعة.
class PosTouchTargets {
  PosTouchTargets._();

  static const double button = 52;
  static const double listItem = 64;
}
