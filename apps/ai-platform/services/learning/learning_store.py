"""ILearningStore — القسم 7.6: تسجيل كل تصحيح يجريه المستخدم كـ"زوج تصحيح"
في ai_learning_feedback. مبدأ العزل المؤسسي: التصحيحات تبقى ضمن company_id
نفسه ولا تُخلط مع شركات أخرى (لا استعلام هنا يتجاوز company_id مطلقاً).
"""
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_models import AiLearningFeedback


class SqlLearningStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_correction(
        self, *, company_id: str, draft_id: str, field_name: str,
        ai_predicted_value: str | None, user_corrected_value: str, corrected_by: str,
    ) -> None:
        self._session.add(
            AiLearningFeedback(
                company_id=company_id,
                extraction_draft_id=draft_id,
                field_name=field_name,
                ai_predicted_value=ai_predicted_value,
                user_corrected_value=user_corrected_value,
                corrected_by=corrected_by,
            )
        )
        await self._session.commit()
