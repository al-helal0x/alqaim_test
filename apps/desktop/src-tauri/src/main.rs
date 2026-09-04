// يمنع نافذة الطرفية الإضافية على Windows في نسخة الإصدار (Release) فقط —
// نمط Tauri القياسي.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    alqaim_desktop_lib::run();
}
