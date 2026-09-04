//! القائم — AlQaim ERP Desktop Client.
//!
//! هذا الملف يبقى بسيطاً عمداً: لا أوامر Rust مخصّصة (`#[tauri::command]`)
//! حالياً لأن كل تواصل مع الخادم يمر عبر `fetch()` القياسي داخل الواجهة
//! (apps/web) مباشرة إلى core-api HTTP — القسم 6.2 (Thin Client). أي حاجة
//! مستقبلية لقدرات Native حقيقية (إشعارات نظام، طباعة مباشرة، قارئ باركود
//! USB لنقطة بيع سطح مكتب) تُضاف هنا كأوامر جديدة عند ظهور الحاجة الفعلية،
//! وليس استباقاً.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("خطأ أثناء تشغيل تطبيق Tauri");
}
