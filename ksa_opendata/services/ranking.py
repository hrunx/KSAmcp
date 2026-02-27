"""Simple bilingual ranking helpers for catalog search results."""

from __future__ import annotations

from typing import Iterable, Mapping

ARABIC_SYNONYMS = {
    "health": ["صحة", "وزارة الصحة", "الصحة"],
    "education": ["تعليم", "وزارة التعليم"],
    "finance": ["مالية", "وزارة المالية"],
}


def rank_datasets(
    datasets: Iterable[Mapping[str, str]],
    query: str,
) -> list[Mapping[str, str]]:
    """Apply a lightweight scoring signal: title > tags > notes."""
    def score(dataset: Mapping[str, str]) -> int:
        title = dataset.get("title", "").lower()
        tags = " ".join(dataset.get("tags", []))
        notes = dataset.get("notes", "")
        total = 0
        lowered_query = query.lower().strip()
        if not lowered_query:
            return 0
        if lowered_query in title:
            total += 30
        if lowered_query in tags:
            total += 15
        if lowered_query in notes:
            total += 5
        for _, synonyms in ARABIC_SYNONYMS.items():
            if any(term in lowered_query for term in synonyms):
                total += 10
        return total

    ranked = sorted(datasets, key=score, reverse=True)
    return ranked
