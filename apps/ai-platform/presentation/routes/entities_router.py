"""GET /ai/entities/{type}/suggestions — القسم 9.7: اقتراحات مطابقة فورية
أثناء الكتابة اليدوية أيضاً، وليس فقط بعد OCR."""
from fastapi import APIRouter, HTTPException, Query, status

from application.dto.ai_dto import EntitySuggestionItem
from services.entity_matching.entity_matcher import FuzzyEntityMatcher

router = APIRouter()
_matcher = FuzzyEntityMatcher()


@router.get("/{entity_type}/suggestions", response_model=list[EntitySuggestionItem])
async def get_entity_suggestions(
    entity_type: str,
    text: str = Query(min_length=1),
    candidate_id: list[str] = Query(default=[]),
    candidate_name: list[str] = Query(default=[]),
) -> list[EntitySuggestionItem]:
    """ملاحظة: في core-api الفعلي، المرشحون (candidates) يُجلَبون داخلياً من
    IProductLookup/IPartnerLookup (catalog/partners modules) بدل تمريرهم عبر
    query params — هنا واجهة اختبار مباشرة لخدمة ai-platform المعزولة."""
    if entity_type not in ("product", "supplier"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="نوع كيان غير مدعوم")
    if len(candidate_id) != len(candidate_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="عدد candidate_id يجب أن يطابق candidate_name"
        )

    candidates = list(zip(candidate_id, candidate_name, strict=True))
    matches = _matcher.match(text, candidates)
    return [
        EntitySuggestionItem(entity_id=m.entity_id, entity_text=m.entity_text, confidence=m.confidence)
        for m in matches
    ]
