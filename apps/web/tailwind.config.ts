import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    // ⚠️ إلزامي: بلا هذا السطر، Tailwind لا يفحص `packages/ui-kit/src` أبداً
    // — فكل كلاس مُستخدَم فقط هناك (bg-ledger-600, border-line, bg-paper,
    // ...) لا يُولَّد في حزمة CSS النهائية، فتظهر كل أزرار/مكوّنات الـUI Kit
    // بخلفية شفافة (اكتُشف عبر فحص يدوي — أزرار "إغلاق"/"حفظ" غير مرئية على
    // عدة صفحات، 19 أغسطس 2026).
    "../../packages/ui-kit/src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: "#F1F0E9",
        ink: {
          DEFAULT: "#1C2321",
          soft: "#4A5450",
        },
        ledger: {
          50: "#EAF3EE",
          100: "#CFE4D8",
          400: "#3E8563",
          600: "#1F6B48",
          700: "#145C3A",
          900: "#0C3A25",
        },
        copper: {
          400: "#C9924C",
          500: "#B9752B",
          600: "#96601F",
        },
        brick: {
          500: "#B3392E",
          600: "#93251C",
        },
        line: "#DCD8CC",
      },
      fontFamily: {
        // ملاحظة: لا يوجد next/font/google هنا عمداً — بيئة CI/الإنتاج قد لا
        // تملك وصولاً مفتوحاً لجميع النطاقات وقت البناء (Sandbox هذا المشروع
        // مثال فعلي). الحل الصحيح لاحقاً: تحميل ملفات .woff2 محلياً في
        // public/fonts واستخدام next/font/local بدل الاعتماد على جلب شبكي
        // وقت البناء. الأسماء أدناه فقط Fallback Stacks آمنة بلا شبكة.
        display: ['"Segoe UI"', "Tahoma", "Geneva", "sans-serif"],
        body: ['"Segoe UI"', "Tahoma", "Geneva", "Arial", "sans-serif"],
        mono: ['"Courier New"', "monospace"],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "6px",
        md: "8px",
      },
    },
  },
  plugins: [],
};

export default config;