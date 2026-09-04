/** @type {import('next').NextConfig} */
const isDesktopBuild = process.env.TAURI_BUILD === "true";

const nextConfig = {
  reactStrictMode: true,
  // Tauri (العضو 10) يخدم ملفات ساكنة من القرص المحلي — لا خادم Node يعمل
  // داخل التطبيق المُوزَّع. نشر الويب/PWA العادي (Cloud) لا يتأثر إطلاقاً:
  // هذا الفرع مشروط بمتغيّر بيئة لا يُضبَط إلا في `apps/desktop` تحديداً.
  ...(isDesktopBuild
    ? {
        output: "export",
        images: { unoptimized: true }, // next/image لا يعمل بدون خادم تحسين صور
        trailingSlash: true, // مسارات ثابتة متوافقة مع خادم ملفات Tauri المحلي
      }
    : {}),
};

module.exports = nextConfig;
