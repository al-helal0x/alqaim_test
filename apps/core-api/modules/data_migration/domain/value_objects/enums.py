"""Value Objects صرفة لموديول data_migration — بدون أي اعتماد على DB/Framework
(القسم 6.4 من الوثيقة المعمارية — نفس القيد المطبَّق على كل موديول آخر)."""
from enum import StrEnum


class SourceType(StrEnum):
    """نوع مصدر البيانات. كل قيمة هنا تقابل تنفيذاً واحداً لـ SourceConnector
    في infrastructure/connectors/ — إضافة مصدر جديد = قيمة جديدة هنا +
    connector جديد، بدون تعديل use_cases."""

    ALAMEEN_MSSQL = "alameen_mssql"  # اتصال مباشر أو استعادة .bak لقاعدة الأمين
    GENERIC_MSSQL = "generic_mssql"  # أي SQL Server آخر بنفس الآلية
    GENERIC_POSTGRES = "generic_postgres"
    CSV = "csv"
    XLSX = "xlsx"


class ImportStatus(StrEnum):
    """حالة ImportJob — تنتقل بالترتيب التالي فقط (يُفرَض في domain/rules):
    connected → discovered → mapped → previewed → committing → completed
    ويمكن الانتقال لـ failed من أي حالة."""

    CONNECTED = "connected"
    DISCOVERED = "discovered"
    MAPPED = "mapped"
    PREVIEWED = "previewed"
    COMMITTING = "committing"
    COMPLETED = "completed"
    FAILED = "failed"


class TargetEntity(StrEnum):
    """الكيانات المستهدَفة داخل AlQaim V2 — بنفس ترتيب الاعتماديات الإلزامي
    الموثَّق في خطة الميزة (§4.4): لا يجوز استيراد فاتورة تشير لعميل غير
    موجود بعد، لذلك الترتيب هنا هو نفسه ترتيب التنفيذ الفعلي."""

    CHART_OF_ACCOUNTS = "chart_of_accounts"       # accounting
    PARTNERS = "partners"                          # partners
    CATALOG_ITEMS = "catalog_items"                # catalog
    OPENING_BALANCES_INVENTORY = "opening_balances_inventory"   # inventory
    OPENING_BALANCES_ACCOUNTING = "opening_balances_accounting"  # accounting
    HISTORICAL_JOURNAL_ENTRIES = "historical_journal_entries"    # accounting (اختياري)
