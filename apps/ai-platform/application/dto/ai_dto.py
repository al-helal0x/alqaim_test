from pydantic import BaseModel


class AnalyzeDocumentResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    engine_used: str | None = None
    confidence_score: float | None = None
    error_message: str | None = None
    draft_id: str | None = None


class DraftResponse(BaseModel):
    id: str
    status: str
    extracted_payload: dict
    matched_supplier_id: str | None = None


class CorrectionRequest(BaseModel):
    field_name: str
    ai_predicted_value: str | None = None
    user_corrected_value: str


class EntitySuggestionItem(BaseModel):
    entity_id: str
    entity_text: str
    confidence: float
