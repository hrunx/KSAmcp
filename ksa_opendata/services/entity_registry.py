"""Build canonical GOV.SA entity registry records from crawl observations."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List

from ksa_opendata.services.govsa_directory import MINISTRY_TAXONOMY_ID

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class EntityObservation:
    entity_id: int
    locale: str
    sort_order: str
    category_id: str
    category_name: str
    name: str
    official_website: str | None
    detail_url: str


@dataclass(frozen=True)
class LocaleView:
    locale: str
    name: str
    category_id: str
    category_name: str
    official_website: str | None
    detail_url: str


@dataclass(frozen=True)
class CanonicalEntity:
    entity_id: int
    slug: str
    is_ministry: bool
    category_ids: List[str]
    category_names: List[str]
    observed_count: int
    strategy_count: int
    locale_views: Dict[str, LocaleView]


def build_canonical_entities(observations: Iterable[EntityObservation]) -> List[CanonicalEntity]:
    by_entity: Dict[int, List[EntityObservation]] = defaultdict(list)
    for observation in observations:
        by_entity[observation.entity_id].append(observation)

    entities: List[CanonicalEntity] = []
    for entity_id in sorted(by_entity):
        group = by_entity[entity_id]
        category_ids = sorted({obs.category_id for obs in group})
        category_names = sorted({obs.category_name for obs in group})
        is_ministry = MINISTRY_TAXONOMY_ID in set(category_ids)
        locale_views = _build_locale_views(group)
        slug = _derive_slug(locale_views=locale_views, entity_id=entity_id)
        strategy_count = len({(obs.locale, obs.sort_order, obs.category_id) for obs in group})
        entities.append(
            CanonicalEntity(
                entity_id=entity_id,
                slug=slug,
                is_ministry=is_ministry,
                category_ids=category_ids,
                category_names=category_names,
                observed_count=len(group),
                strategy_count=strategy_count,
                locale_views=locale_views,
            )
        )
    return entities


def _build_locale_views(observations: List[EntityObservation]) -> Dict[str, LocaleView]:
    grouped: Dict[str, List[EntityObservation]] = defaultdict(list)
    for obs in observations:
        grouped[obs.locale].append(obs)

    views: Dict[str, LocaleView] = {}
    for locale, obs_group in grouped.items():
        name = _select_most_common([obs.name for obs in obs_group])
        category_id = _select_most_common([obs.category_id for obs in obs_group])
        category_name = _select_most_common([obs.category_name for obs in obs_group])
        detail_url = _select_most_common([obs.detail_url for obs in obs_group])
        websites = [obs.official_website for obs in obs_group if obs.official_website]
        official_website = _select_most_common(websites) if websites else None
        views[locale] = LocaleView(
            locale=locale,
            name=name,
            category_id=category_id,
            category_name=category_name,
            official_website=official_website,
            detail_url=detail_url,
        )
    return views


def _select_most_common(values: List[str]) -> str:
    counter = Counter(values)
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return ranked[0][0]


def _derive_slug(*, locale_views: Dict[str, LocaleView], entity_id: int) -> str:
    preferred_name = ""
    if "en" in locale_views:
        preferred_name = locale_views["en"].name
    elif "ar" in locale_views:
        preferred_name = locale_views["ar"].name

    ascii_name = preferred_name.encode("ascii", errors="ignore").decode("ascii")
    normalized = _SLUG_PATTERN.sub("-", ascii_name.lower()).strip("-")
    if normalized:
        return f"{entity_id}-{normalized[:80]}"
    return f"{entity_id}-entity"
