"""Generate authoritative GOV.SA entity and ministry contributor registry artifacts."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

from ksa_opendata.services.entity_registry import (
    CanonicalEntity,
    EntityObservation,
    build_canonical_entities,
)
from ksa_opendata.services.govsa_directory import MINISTRY_TAXONOMY_ID, GovSaDirectoryClient

LOCALES = ("en", "ar")
SORT_ORDERS = ("DESC", "ASC")
OUTPUT_REPORT_DIR = Path("reports")
OUTPUT_ENTITY_DIR = Path("contrib/entities")
OUTPUT_MINISTRY_DIR = Path("contrib/ministries")

_FILENAME_SANITIZE_RE = re.compile(r"[^\w]+", flags=re.UNICODE)
_MULTI_DASH_RE = re.compile(r"-{2,}")

SOURCE_BRIEFS: Dict[str, str] = {
    "ksa_open_data_platform": "National Data Bank open data catalog (baseline source).",
    "moh_hdp_api": "MOH Health Data Platform public API.",
    "shc_open_data_apis": "Saudi Health Council open data endpoints.",
    "mcit_open_api": "MCIT telecom and digital indicators API.",
    "sama_open_data_api": "SAMA financial open data API.",
    "cchi_odata": "CCHI health insurance OData source.",
    "gastat_api": "GASTAT statistical indicators.",
}


def generate() -> None:
    generated_at = datetime.now(timezone.utc).isoformat()
    client = GovSaDirectoryClient(timeout_s=30.0, max_retries=6, retry_backoff_s=1.5)

    observations: List[EntityObservation] = []
    strategy_stats: List[dict[str, Any]] = []
    category_names_by_id: Dict[str, Dict[str, str]] = defaultdict(dict)
    official_total_items: int | None = None

    for locale in LOCALES:
        first_page = client.fetch_page(
            locale=locale,
            page=0,
            extra_params={"sortOrder": SORT_ORDERS[0]},
        )
        for category in first_page.categories:
            category_names_by_id[category.id][locale] = category.name
        official_total_items = _assert_total_items(
            previous=official_total_items,
            current=first_page.pager.total_items,
        )

        category_ids = sorted(category.id for category in first_page.categories)
        for sort_order in SORT_ORDERS:
            for category_id in category_ids:
                pages = client.crawl_pages(
                    locale=locale,
                    extra_params={"sortOrder": sort_order, "agency_type": category_id},
                )
                strategy_rows = 0
                strategy_unique_ids: set[int] = set()
                for page in pages:
                    strategy_rows += len(page.rows)
                    for row in page.rows:
                        observations.append(
                            EntityObservation(
                                entity_id=row.entity_id,
                                locale=locale,
                                sort_order=sort_order,
                                category_id=row.category_id,
                                category_name=row.category_name,
                                name=row.name,
                                official_website=row.official_website,
                                detail_url=row.detail_url,
                            )
                        )
                        strategy_unique_ids.add(row.entity_id)
                strategy_stats.append(
                    {
                        "locale": locale,
                        "sort_order": sort_order,
                        "category_id": category_id,
                        "category_name": category_names_by_id[category_id].get(
                            locale,
                            category_id,
                        ),
                        "pages_crawled": len(pages),
                        "category_total_rows_reported": pages[0].pager.total_items if pages else 0,
                        "raw_rows_collected": strategy_rows,
                        "unique_entity_ids_collected": len(strategy_unique_ids),
                    }
                )

    entities = build_canonical_entities(observations)
    ministries = [entity for entity in entities if entity.is_ministry]

    OUTPUT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_ENTITY_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_MINISTRY_DIR.mkdir(parents=True, exist_ok=True)

    entity_file_names = _build_entity_file_names(entities)

    snapshot = {
        "source": {
            "name": "GOV.SA Agencies Directory",
            "url_en": "https://www.my.gov.sa/en/agencies",
            "url_ar": "https://www.my.gov.sa/ar/agencies",
            "ministry_taxonomy_id": MINISTRY_TAXONOMY_ID,
            "generated_at_utc": generated_at,
        },
        "stats": {
            "official_total_rows_reported": official_total_items,
            "raw_rows_collected": len(observations),
            "unique_entity_ids": len(entities),
            "ministry_entity_ids": len(ministries),
        },
        "category_taxonomy": _build_category_taxonomy(category_names_by_id),
        "crawl_strategies": strategy_stats,
        "entities": [
            _serialize_entity(entity, entity_file_name=entity_file_names[entity.entity_id])
            for entity in entities
        ],
    }
    ministries_payload = {
        "source": snapshot["source"],
        "stats": snapshot["stats"],
        "ministries": [
            _serialize_entity(entity, entity_file_name=entity_file_names[entity.entity_id])
            for entity in ministries
        ],
    }

    (OUTPUT_REPORT_DIR / "govsa_entity_registry.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT_REPORT_DIR / "govsa_ministries_registry.json").write_text(
        json.dumps(ministries_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_summary_markdown(
        snapshot=snapshot,
        ministries=ministries,
        entity_file_names=entity_file_names,
    )
    _write_contributor_scaffolds(
        entities=entities,
        ministries=ministries,
        entity_file_names=entity_file_names,
    )

    print("Generated entity registry artifacts:")
    print("- reports/govsa_entity_registry.json")
    print("- reports/govsa_ministries_registry.json")
    print("- reports/govsa_entity_registry.md")
    print("- contrib/entities/*.yaml")
    print("- contrib/entities/README.md")
    print("- contrib/ministries/README.md")


def _assert_total_items(*, previous: int | None, current: int) -> int:
    if previous is None:
        return current
    if previous != current:
        raise RuntimeError(
            f"Inconsistent official total rows across pages: previous={previous}, current={current}"
        )
    return previous


def _build_category_taxonomy(
    category_names_by_id: Dict[str, Dict[str, str]],
) -> List[dict[str, str | None]]:
    out: List[dict[str, str | None]] = []
    for category_id in sorted(category_names_by_id):
        names = category_names_by_id[category_id]
        out.append(
            {
                "id": category_id,
                "name_en": names.get("en"),
                "name_ar": names.get("ar"),
            }
        )
    return out


def _serialize_entity(entity: CanonicalEntity, *, entity_file_name: str) -> dict[str, Any]:
    locales = {
        locale: asdict(view)
        for locale, view in sorted(entity.locale_views.items(), key=lambda item: item[0])
    }
    return {
        "entity_id": entity.entity_id,
        "slug": entity.slug,
        "is_ministry": entity.is_ministry,
        "category_ids": entity.category_ids,
        "category_names": entity.category_names,
        "observed_count": entity.observed_count,
        "strategy_count": entity.strategy_count,
        "contrib_entity_file": f"contrib/entities/{entity_file_name}",
        "contrib_ministry_file": (
            f"contrib/ministries/{entity_file_name}" if entity.is_ministry else None
        ),
        "locales": locales,
    }


def _write_summary_markdown(
    *,
    snapshot: dict[str, Any],
    ministries: List[CanonicalEntity],
    entity_file_names: Dict[int, str],
) -> None:
    entities = snapshot["entities"]
    stats = snapshot["stats"]
    lines = [
        "# GOV.SA Entity Registry (Authoritative Crawl)",
        "",
        f"- Generated at (UTC): `{snapshot['source']['generated_at_utc']}`",
        f"- Official GOV.SA total rows reported: `{stats['official_total_rows_reported']}`",
        f"- Raw rows collected across strategies: `{stats['raw_rows_collected']}`",
        f"- Unique entity IDs captured: `{stats['unique_entity_ids']}`",
        f"- Ministry entity IDs captured: `{stats['ministry_entity_ids']}`",
        "",
        "## Ministry Pick List",
        "",
    ]

    for entity in ministries:
        en_view = entity.locale_views.get("en")
        ar_view = entity.locale_views.get("ar")
        en_name = en_view.name if en_view else ""
        ar_name = ar_view.name if ar_view else ""
        lines.append(
            f"- `{entity.entity_id}` | {en_name or '(no EN title)'} | "
            f"{ar_name or '(no AR title)'} | "
            f"`contrib/entities/{entity_file_names[entity.entity_id]}`"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This registry is generated from official GOV.SA directory payloads only.",
            "- No entity names or categories are fabricated or inferred outside source payloads.",
            "- Contributor files are machine-generated and safe to claim by PR.",
            "",
            "## All Entities",
            "",
        ]
    )
    for entity in entities:
        en_name = entity["locales"].get("en", {}).get("name", "")
        lines.append(
            f"- `{entity['entity_id']}` | {en_name or '(no EN title)'} | "
            f"`contrib/entities/{entity_file_names[int(entity['entity_id'])]}`"
        )

    (OUTPUT_REPORT_DIR / "govsa_entity_registry.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def _write_contributor_scaffolds(
    *,
    entities: List[CanonicalEntity],
    ministries: List[CanonicalEntity],
    entity_file_names: Dict[int, str],
) -> None:
    entity_files: List[str] = []
    ministry_files: List[str] = []

    _clean_existing_yaml_files(OUTPUT_ENTITY_DIR)
    _clean_existing_yaml_files(OUTPUT_MINISTRY_DIR)

    for entity in entities:
        file_name = entity_file_names[entity.entity_id]
        path = OUTPUT_ENTITY_DIR / file_name
        data = _entity_scaffold_yaml(entity, entity_file_name=file_name)
        path.write_text(
            "# Generated from official GOV.SA directory data.\n"
            "# Contributors: claim this file in your PR and complete integration sections.\n"
            + yaml.safe_dump(
                data,
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        entity_files.append(file_name)

    for ministry in ministries:
        file_name = entity_file_names[ministry.entity_id]
        ministry_path = OUTPUT_MINISTRY_DIR / file_name
        ministry_data = _ministry_scaffold_yaml(
            ministry,
            entity_file_name=file_name,
        )
        ministry_path.write_text(
            "# Generated ministry-specific scaffold from official GOV.SA data.\n"
            "# Keep this file aligned with the corresponding contrib/entities record.\n"
            + yaml.safe_dump(
                ministry_data,
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        ministry_files.append(file_name)

    entity_lines = [
        "# Entity Contribution Backlog",
        "",
        "Each file below maps to one official GOV.SA entity record:",
        "",
    ]
    for entity in entities:
        file_name = entity_file_names[entity.entity_id]
        display_name = _preferred_entity_name(entity)
        category = _preferred_category_name(entity)
        entity_lines.append(f"- `{file_name}` — {display_name} ({category})")
    (OUTPUT_ENTITY_DIR / "README.md").write_text("\n".join(entity_lines), encoding="utf-8")

    ministry_lines = [
        "# Ministry Contribution Backlog",
        "",
        "Start here if you want to contribute ministry connectors first.",
        "Every file links to an official ministry record and a baseline open-data profile.",
        "",
    ]
    for ministry in ministries:
        file_name = entity_file_names[ministry.entity_id]
        display_name = _preferred_entity_name(ministry)
        ministry_lines.append(
            f"- `{file_name}` — {display_name} | "
            f"`../entities/{file_name}`"
        )
    (OUTPUT_MINISTRY_DIR / "README.md").write_text("\n".join(ministry_lines), encoding="utf-8")


def _entity_scaffold_yaml(entity: CanonicalEntity, *, entity_file_name: str) -> dict[str, Any]:
    locale_payload: dict[str, dict[str, Any]] = {}
    for locale, view in sorted(entity.locale_views.items(), key=lambda item: item[0]):
        locale_payload[locale] = {
            "name": view.name,
            "category_id": view.category_id,
            "category_name": view.category_name,
            "detail_url": view.detail_url,
            "official_website": view.official_website,
        }

    return {
        "entity_id": entity.entity_id,
        "slug": entity.slug,
        "contrib_file_name": entity_file_name,
        "is_ministry": entity.is_ministry,
        "category_ids": entity.category_ids,
        "category_names": entity.category_names,
        "locales": locale_payload,
        "open_data_profile": {
            "core_catalog_source": "ksa_open_data_platform",
            "suggested_query_terms": _query_terms(entity),
            "recommended_sources": _recommended_sources_for_entity(entity),
        },
        "integration_backlog": {
            "status": "unclaimed",
            "owner": "",
            "priority": "medium",
            "candidate_sources": [],
            "candidate_endpoints": [],
            "notes": "",
            "required_tests": ["unit", "integration"],
        },
    }


def _ministry_scaffold_yaml(entity: CanonicalEntity, *, entity_file_name: str) -> dict[str, Any]:
    en_view = entity.locale_views.get("en")
    ar_view = entity.locale_views.get("ar")
    return {
        "entity_id": entity.entity_id,
        "contrib_entity_file": f"../entities/{entity_file_name}",
        "name": {
            "en": en_view.name if en_view else None,
            "ar": ar_view.name if ar_view else None,
        },
        "official_open_data": {
            "core_catalog_source": "ksa_open_data_platform",
            "recommended_sources": _recommended_sources_for_entity(entity),
            "source_notes": (
                "Validate publisher mapping in CKAN and then bind "
                "ministry-specific API sources."
            ),
        },
        "contribution_checklist": [
            "Map ministry publisher identifier(s) in CKAN.",
            "Validate available resources and formats.",
            "Attach any ministry-specific API source (if available).",
            "Add unit and integration tests.",
        ],
    }


def _build_entity_file_names(entities: List[CanonicalEntity]) -> Dict[int, str]:
    used: set[str] = set()
    names: Dict[int, str] = {}

    for entity in sorted(entities, key=lambda item: item.entity_id):
        base = _slugify_filename(_preferred_entity_name(entity))
        if not base:
            base = f"entity-{entity.entity_id}"

        candidate = base
        if candidate in used:
            candidate = f"{base}-{entity.entity_id}"
        while candidate in used:
            candidate = f"{candidate}-{entity.entity_id}"

        used.add(candidate)
        names[entity.entity_id] = f"{candidate}.yaml"
    return names


def _slugify_filename(value: str) -> str:
    normalized = value.strip().lower()
    sanitized = _FILENAME_SANITIZE_RE.sub("-", normalized).replace("_", "-").strip("-")
    return _MULTI_DASH_RE.sub("-", sanitized)


def _preferred_entity_name(entity: CanonicalEntity) -> str:
    en_view = entity.locale_views.get("en")
    if en_view and en_view.name.strip():
        return en_view.name.strip()
    ar_view = entity.locale_views.get("ar")
    if ar_view and ar_view.name.strip():
        return ar_view.name.strip()
    return f"entity-{entity.entity_id}"


def _preferred_category_name(entity: CanonicalEntity) -> str:
    en_view = entity.locale_views.get("en")
    if en_view and en_view.category_name.strip():
        return en_view.category_name.strip()
    ar_view = entity.locale_views.get("ar")
    if ar_view and ar_view.category_name.strip():
        return ar_view.category_name.strip()
    return "Unknown"


def _query_terms(entity: CanonicalEntity) -> List[str]:
    terms: List[str] = []
    en_view = entity.locale_views.get("en")
    ar_view = entity.locale_views.get("ar")
    if en_view and en_view.name.strip():
        terms.append(en_view.name.strip())
    if ar_view and ar_view.name.strip():
        terms.append(ar_view.name.strip())
    return terms


def _recommended_sources_for_entity(entity: CanonicalEntity) -> List[dict[str, str]]:
    query_text = " ".join(_query_terms(entity)).lower()
    source_ids: List[str] = ["ksa_open_data_platform"]

    if any(
        token in query_text
        for token in ["health", "medical", "hospital", "صحة", "صحي"]
    ):
        source_ids.extend(["moh_hdp_api", "shc_open_data_apis", "cchi_odata"])
    if any(
        token in query_text
        for token in ["communication", "digital", "technology", "اتصالات", "تقنية"]
    ):
        source_ids.append("mcit_open_api")
    if any(
        token in query_text
        for token in ["finance", "bank", "financial", "مالية", "بنك", "نقد"]
    ):
        source_ids.append("sama_open_data_api")
    if any(
        token in query_text
        for token in ["statistics", "economy", "population", "إحصاء", "اقتصاد"]
    ):
        source_ids.append("gastat_api")

    deduped: List[str] = []
    seen: set[str] = set()
    for source_id in source_ids:
        if source_id not in seen:
            deduped.append(source_id)
            seen.add(source_id)

    return [
        {
            "source_id": source_id,
            "reason": SOURCE_BRIEFS.get(source_id, "Recommended based on entity profile."),
        }
        for source_id in deduped
    ]


def _clean_existing_yaml_files(path: Path) -> None:
    for file in path.glob("*.yaml"):
        file.unlink()


if __name__ == "__main__":
    generate()
