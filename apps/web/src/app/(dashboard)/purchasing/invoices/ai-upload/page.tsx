"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Banner, Button, Card, EmptyState, Field, PageHeader, SelectField } from "@/common/ui";
import { ApiError } from "@/api-client/http";
import { listPartners } from "@/features/partners/api";
import { listBranches } from "@/features/tenancy/api";
import type { BranchResponse, PartnerResponse } from "@/api-client/types";
import {
  analyzeDocument,
  confirmDraft,
  getDocumentJobStatus,
  getDraft,
  rejectDraft,
  submitDraftCorrections,
} from "@/features/ai-documents/ai-api";
import type { AiDocumentJob, AiInvoiceDraft } from "@/features/ai-documents/ai-documents-types";
import {
  applyManualEdit,
  applyManualLineEdit,
  buildCorrections,
  effectiveHeaderValue,
  effectiveLineValue,
  emptyLocalEdits,
  needsManualReview,
  type DraftHeaderField,
  type DraftLineField,
  type LocalEdits,
} from "@/features/ai-documents/ai-draft-merge";

const POLL_INTERVAL_MS = 2500;

const HEADER_FIELDS: { key: DraftHeaderField; label: string; type?: string }[] = [
  { key: "supplier_name", label: "اسم المورّد (كما ورد في المستند)" },
  { key: "invoice_number", label: "رقم الفاتورة" },
  { key: "invoice_date", label: "تاريخ الفاتورة", type: "date" },
  { key: "total_amount", label: "الإجمالي" },
];

const LINE_FIELDS: { key: DraftLineField; label: string }[] = [
  { key: "description", label: "الوصف" },
  { key: "quantity", label: "الكمية" },
  { key: "unit_price", label: "سعر الوحدة" },
];

export default function AiInvoiceUploadPage() {
  const router = useRouter();

  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<AiDocumentJob | null>(null);
  const [draft, setDraft] = useState<AiInvoiceDraft | null>(null);
  const [edits, setEdits] = useState<LocalEdits>(emptyLocalEdits());
  const [error, setError] = useState<string | null>(null);

  const [isUploading, setIsUploading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);

  const [branches, setBranches] = useState<BranchResponse[]>([]);
  const [suppliers, setSuppliers] = useState<PartnerResponse[]>([]);

  // قوائم الفرع/المورّد — غير مستخرَجَين من AI إطلاقاً (راجع 00_CONTRACT، القسم "الأثر على التصميم").
  useEffect(() => {
    (async () => {
      try {
        const [branchesData, suppliersPage] = await Promise.all([
          listBranches(),
          listPartners({ partnerType: "supplier" }),
        ]);
        setBranches(branchesData);
        setSuppliers(suppliersPage.items);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "تعذّر تحميل قوائم الفروع/الموردين");
      }
    })();
  }, []);

  // Polling لحالة مهمة التحليل حتى تصبح "completed" أو "failed".
  useEffect(() => {
    if (!job || (job.status !== "pending" && job.status !== "processing")) return;
    const jobId = job.job_id;

    const intervalId = setInterval(async () => {
      try {
        const updated = await getDocumentJobStatus(jobId);
        setJob(updated);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "تعذّر التحقق من حالة المعالجة");
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [job?.job_id, job?.status]);

  // بعد اكتمال المهمة، جلب المسودة الكاملة عبر draft_id.
  useEffect(() => {
    if (!job || job.status !== "completed" || draft) return;
    if (!job.draft_id) {
      setError("اكتمل التحليل لكن لم يصل مُعرِّف المسودة (draft_id) من الخادم — راجع فريق ai-platform.");
      return;
    }
    (async () => {
      try {
        const result = await getDraft(job.draft_id as string);
        setDraft(result);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "تعذّر جلب المسودة");
      }
    })();
  }, [job?.status, job?.draft_id, draft]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setIsUploading(true);
    try {
      const result = await analyzeDocument(file);
      setJob(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر رفع المستند للتحليل");
    } finally {
      setIsUploading(false);
    }
  }

  function handleStartOver() {
    setFile(null);
    setJob(null);
    setDraft(null);
    setEdits(emptyLocalEdits());
    setError(null);
  }

  async function handleApprove() {
    if (!draft) return;
    setError(null);
    setIsSubmitting(true);
    try {
      const corrections = buildCorrections(edits);
      if (Object.keys(corrections).length > 0) {
        await submitDraftCorrections(draft.draft_id, corrections);
      }
      await confirmDraft(draft.draft_id);
      router.push("/purchasing/invoices");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر اعتماد المسودة");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleReject() {
    if (!draft) return;
    setError(null);
    setIsRejecting(true);
    try {
      await rejectDraft(draft.draft_id);
      handleStartOver();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "تعذّر رفض المسودة");
    } finally {
      setIsRejecting(false);
    }
  }

  const isProcessing = job && (job.status === "pending" || job.status === "processing");
  const isFailed = job && job.status === "failed";
  const isLoadingDraft = job && job.status === "completed" && !draft && !error;

  return (
    <div>
      <PageHeader
        title="رفع فاتورة عبر الذكاء الاصطناعي"
        description="ارفع صورة أو PDF لفاتورة شراء ليستخرج AI بياناتها، ثم راجعها واعتمدها"
      />

      {error && (
        <div className="mb-4">
          <Banner kind="error">{error}</Banner>
        </div>
      )}

      {!job && (
        <EmptyState
          title="ارفع مستنداً لبدء الاستخراج"
          description="يدعم ملفات PDF أو صور (JPG/PNG) — سيُستخرَج اسم المورّد ورقم الفاتورة وتاريخها والإجمالي وأسطر الفاتورة تلقائياً"
          action={
            <form onSubmit={handleUpload} className="flex flex-col items-stretch gap-3">
              <Field
                label="ملف الفاتورة"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <Button type="submit" disabled={!file || isUploading}>
                {isUploading ? "جارِ الرفع…" : "استخراج البيانات"}
              </Button>
            </form>
          }
        />
      )}

      {(isProcessing || isLoadingDraft) && (
        <Card>
          <p className="animate-pulse text-sm text-ink-soft">
            {isLoadingDraft ? "جارِ جلب بيانات المسودة…" : "جارِ تحليل المستند — قد يستغرق ذلك بضع ثوانٍ…"}
          </p>
        </Card>
      )}

      {isFailed && (
        <Card>
          <Banner kind="error">{job.error_message ?? "فشل تحليل المستند"}</Banner>
          <div className="mt-4">
            <Button variant="secondary" onClick={handleStartOver}>
              المحاولة برفع ملف آخر
            </Button>
          </div>
        </Card>
      )}

      {draft && (
        <div className="flex flex-col gap-6">
          <Card>
            <p className="mb-4 font-display text-lg text-ink">بيانات الفاتورة المستخرَجة</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {HEADER_FIELDS.map(({ key, label, type }) => {
                const field = draft[key];
                const isEdited = edits.header[key] !== undefined;
                return (
                  <div key={key} className="flex flex-col gap-1">
                    {field.confidence === "low" && !isEdited && (
                      <Banner kind="warning" className="py-1.5 text-xs">
                        ثقة الاستخراج منخفضة لهذا الحقل — يُرجى مراجعته يدوياً
                      </Banner>
                    )}
                    <Field
                      label={label}
                      type={type}
                      value={effectiveHeaderValue(draft, edits, key)}
                      onChange={(e) => setEdits((current) => applyManualEdit(current, key, e.target.value))}
                      required
                    />
                  </div>
                );
              })}

              <SelectField
                label="الفرع"
                required
                value={edits.branchId ?? ""}
                onChange={(e) => setEdits((current) => ({ ...current, branchId: e.target.value }))}
              >
                <option value="">اختر فرعاً</option>
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </SelectField>

              <SelectField
                label="المورّد"
                required
                value={edits.supplierId ?? ""}
                onChange={(e) => setEdits((current) => ({ ...current, supplierId: e.target.value }))}
              >
                <option value="">اختر مورّداً</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </SelectField>
            </div>
          </Card>

          <Card>
            <p className="mb-4 font-display text-lg text-ink">أسطر الفاتورة</p>
            {draft.lines.length === 0 ? (
              <p className="text-sm text-ink-soft">لم تُستخرَج أي أسطر — يمكنك المتابعة إن كانت الفاتورة بلا تفاصيل بنود.</p>
            ) : (
              <div className="flex flex-col gap-4">
                {draft.lines.map((line, index) => (
                  <div
                    key={index}
                    className="grid grid-cols-1 gap-3 border-b border-line pb-4 last:border-0 last:pb-0 sm:grid-cols-3"
                  >
                    {LINE_FIELDS.map(({ key, label }) => {
                      const field = line[key];
                      const isEdited = edits.lines[index]?.[key] !== undefined;
                      return (
                        <div key={key} className="flex flex-col gap-1">
                          {field.confidence === "low" && !isEdited && (
                            <Banner kind="warning" className="py-1.5 text-xs">
                              ثقة الاستخراج منخفضة — يُرجى مراجعته يدوياً
                            </Banner>
                          )}
                          <Field
                            label={label}
                            value={effectiveLineValue(draft, edits, index, key)}
                            onChange={(e) =>
                              setEdits((current) => applyManualLineEdit(current, index, key, e.target.value))
                            }
                          />
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
            )}
          </Card>

          <div className="flex items-center gap-3">
            <Button onClick={handleApprove} disabled={needsManualReview(draft, edits) || isSubmitting || isRejecting}>
              {isSubmitting ? "جارِ الاعتماد…" : "اعتماد وإنشاء الفاتورة"}
            </Button>
            <Button variant="secondary" onClick={handleReject} disabled={isSubmitting || isRejecting}>
              {isRejecting ? "جارِ الرفض…" : "رفض المسودة"}
            </Button>
            <Button variant="secondary" onClick={handleStartOver} disabled={isSubmitting || isRejecting}>
              إلغاء والبدء من جديد
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
