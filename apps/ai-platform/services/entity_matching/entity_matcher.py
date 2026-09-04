"""IEntityMatcher — القسم 7.4: Product/Supplier Matching.

**حدود هذا التنفيذ:** الوثيقة توصي بمطابقة دلالية عبر Embeddings +
pgvector (القسم 7.12) — يتطلب نموذج تمثيل نصي متعدد اللغات محمَّل ذاتياً
غير متاح في هذه البيئة. هذا التنفيذ Baseline حقيقي وفعّال عبر **تشابه
نصي ضبابي (Fuzzy String Matching — rapidfuzz)** يتعامل جيداً مع فروقات
الكتابة والأخطاء الإملائية البسيطة (لكن ليس الترادف الدلالي الكامل مثل
"كولا" ↔ "Coca-Cola" بدون أي تشابه حروف). يُستبدَل خلف نفس IEntityMatcher
بمطابقة Embeddings عند توفر بنية تحتية ML (القسم 7.9 — استبدال دون لمس
الأنبوب المستهلك).
"""
from rapidfuzz import fuzz, process

from application.ports.ai_ports import MatchCandidate


class FuzzyEntityMatcher:
    def match(
        self, query_text: str, candidates: list[tuple[str, str]], *, top_k: int = 3
    ) -> list[MatchCandidate]:
        if not candidates or not query_text.strip():
            return []

        choices = dict(candidates)
        results = process.extract(
            query_text, choices, scorer=fuzz.WRatio, limit=top_k
        )
        # rapidfuzz.process.extract مع dict choices يُرجع (text, score, key)
        return [
            MatchCandidate(entity_id=str(entity_id), entity_text=text, confidence=round(score / 100.0, 4))
            for text, score, entity_id in results
        ]
