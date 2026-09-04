"""اختبارات المطابقة الضبابية (Fuzzy) — القسم 7.4 Baseline."""
from services.entity_matching.entity_matcher import FuzzyEntityMatcher

matcher = FuzzyEntityMatcher()


def test_matches_close_spelling_variants():
    candidates = [
        ("p1", "Coca Cola 330ml"), ("p2", "Pepsi 330ml"), ("p3", "Sprite 330ml"),
    ]
    results = matcher.match("Coca-Cola 330 ml", candidates)
    assert results[0].entity_id == "p1"
    assert results[0].confidence > 0.7


def test_empty_query_returns_no_matches():
    assert matcher.match("", [("p1", "Coca Cola")]) == []


def test_no_candidates_returns_empty():
    assert matcher.match("anything", []) == []
