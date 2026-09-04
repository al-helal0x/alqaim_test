# migrations/ (Alembic)

قاعدة بيانات واحدة مشتركة؛ كل Module يضيف ملفات الهجرة الخاصة به.

**قاعدة تسمية إلزامية (القسم 15.2) لتفادي تعارض الدمج:**
`{module_name}_{timestamp}_{short_description}.py`
مثال: `accounting_20260810_create_journal_entries.py`

الهجرات تُدمَج تسلسلياً — لا يُعدّل عضو هجرة عضو آخر مباشرة.
