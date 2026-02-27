"""Fallback catalog data when upstream CKAN is blocked/unavailable."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import yaml

FALLBACK_REPORT_PATH = Path("reports/govsa_ministries_registry.json")
FALLBACK_ENTITIES_DIR = Path("contrib/entities")


def _read_fallback_report() -> Dict[str, Any]:
    if not FALLBACK_REPORT_PATH.exists():
        return {}
    try:
        loaded: Any = json.loads(FALLBACK_REPORT_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            return cast(Dict[str, Any], loaded)
        return {}
    except json.JSONDecodeError:
        return {}


def load_fallback_ministries() -> Tuple[Optional[str], List[Dict[str, Any]]]:
    report = _read_fallback_report()
    source = report.get("source", {}) if isinstance(report, dict) else {}
    generated_at = source.get("generated_at_utc") if isinstance(source, dict) else None
    raw_ministries = report.get("ministries", []) if isinstance(report, dict) else []
    ministries = [item for item in raw_ministries if isinstance(item, dict)]
    if ministries:
        return generated_at if isinstance(generated_at, str) else None, ministries
    return datetime.now(timezone.utc).isoformat(), _read_entity_fallback_ministries()


def _read_entity_fallback_ministries() -> List[Dict[str, Any]]:
    if not FALLBACK_ENTITIES_DIR.exists():
        return []

    ministries: List[Dict[str, Any]] = []
    for path in sorted(FALLBACK_ENTITIES_DIR.glob("*.yaml")):
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            continue
        if not isinstance(loaded, dict):
            continue
        if not bool(loaded.get("is_ministry")):
            continue

        locales = loaded.get("locales", {})
        if not isinstance(locales, dict):
            locales = {}
        ministries.append(
            {
                "entity_id": loaded.get("entity_id"),
                "slug": loaded.get("slug"),
                "locales": locales,
            }
        )
    return ministries


def _ministry_identity(ministry: Dict[str, Any]) -> Tuple[int, str, str, str]:
    entity_id = int(ministry.get("entity_id", 0))
    slug = str(ministry.get("slug", f"{entity_id}-entity"))
    locales = ministry.get("locales", {})
    en = locales.get("en", {}) if isinstance(locales, dict) else {}
    ar = locales.get("ar", {}) if isinstance(locales, dict) else {}
    name_en = str(en.get("name") or f"Entity {entity_id}")
    name_ar = str(ar.get("name") or "")
    return entity_id, slug, name_en, name_ar


def _official_website(ministry: Dict[str, Any]) -> str:
    locales = ministry.get("locales", {})
    en = locales.get("en", {}) if isinstance(locales, dict) else {}
    ar = locales.get("ar", {}) if isinstance(locales, dict) else {}
    website = en.get("official_website") or ar.get("official_website") or ""
    return str(website)


def _detail_url(ministry: Dict[str, Any], locale: str) -> str:
    locales = ministry.get("locales", {})
    view = locales.get(locale, {}) if isinstance(locales, dict) else {}
    detail = view.get("detail_url", "")
    return str(detail)


def _publisher_name_from_slug(slug: str) -> str:
    parts = slug.split("-", 1)
    return parts[1] if len(parts) == 2 else slug


def fallback_publishers(query: str, limit: int) -> List[Dict[str, Any]]:
    _, ministries = load_fallback_ministries()
    q = (query or "").strip().lower()
    out: List[Dict[str, Any]] = []
    for ministry in ministries:
        entity_id, slug, name_en, name_ar = _ministry_identity(ministry)
        publisher_name = _publisher_name_from_slug(slug)
        haystack = f"{publisher_name} {name_en} {name_ar}".lower()
        if q and q not in haystack:
            continue
        website = _official_website(ministry)
        out.append(
            {
                "id": str(entity_id),
                "name": publisher_name,
                "title": name_en,
                "package_count": 1,
                "description": f"Fallback publisher profile. Official website: {website}",
            }
        )
        if len(out) >= limit:
            break
    return out


def _fallback_dataset(ministry: Dict[str, Any], generated_at: Optional[str]) -> Dict[str, Any]:
    entity_id, slug, name_en, name_ar = _ministry_identity(ministry)
    publisher_name = _publisher_name_from_slug(slug)
    website = _official_website(ministry)
    return {
        "id": f"fallback-{entity_id}",
        "name": f"open-data-{publisher_name}",
        "title": f"{name_en} Open Data Profile",
        "publisher": name_en,
        "metadata_modified": generated_at,
        "tags": ["fallback", "ministry", "govsa"],
        "resources": [
            {
                "id": f"fallback-resource-{entity_id}",
                "name": "official_website",
                "format": "HTML",
                "url": website,
            },
            {
                "id": f"fallback-detail-en-{entity_id}",
                "name": "agency_detail_en",
                "format": "HTML",
                "url": _detail_url(ministry, "en"),
            },
        ],
        "_fallback_locale_name_ar": name_ar,
        "_fallback_slug": slug,
    }


def fallback_search_datasets(
    query: str,
    publisher: Optional[str],
    rows: int,
    start: int,
) -> Dict[str, Any]:
    generated_at, ministries = load_fallback_ministries()
    q = (query or "").strip().lower()
    q_any = q in {"", "*:*"}
    publisher_filter = (publisher or "").strip().lower()

    candidates = [_fallback_dataset(ministry, generated_at) for ministry in ministries]
    filtered: List[Dict[str, Any]] = []
    for dataset in candidates:
        haystack = " ".join(
            [
                str(dataset.get("name", "")),
                str(dataset.get("title", "")),
                str(dataset.get("_fallback_locale_name_ar", "")),
                str(dataset.get("_fallback_slug", "")),
            ]
        ).lower()
        if not q_any and q not in haystack:
            continue
        if publisher_filter:
            publisher_hay = " ".join(
                [
                    str(dataset.get("publisher", "")),
                    str(dataset.get("_fallback_slug", "")),
                    str(dataset.get("name", "")),
                ]
            ).lower()
            if publisher_filter not in publisher_hay:
                continue
        filtered.append(dataset)

    safe_start = max(0, start)
    safe_rows = max(1, min(rows, 50))
    page = filtered[safe_start : safe_start + safe_rows]
    sanitized = [
        {key: value for key, value in dataset.items() if not key.startswith("_fallback_")}
        for dataset in page
    ]
    return {
        "count": len(filtered),
        "start": safe_start,
        "rows": safe_rows,
        "datasets": sanitized,
    }


def fallback_dataset_detail(dataset_id_or_name: str) -> Dict[str, Any]:
    generated_at, ministries = load_fallback_ministries()
    needle = (dataset_id_or_name or "").strip().lower()

    for ministry in ministries:
        entity_id, slug, name_en, name_ar = _ministry_identity(ministry)
        publisher_name = _publisher_name_from_slug(slug)
        if needle in {
            f"fallback-{entity_id}",
            f"open-data-{publisher_name}",
            slug,
            str(entity_id),
            name_en.lower(),
            name_ar.lower(),
        }:
            website = _official_website(ministry)
            return {
                "id": f"fallback-{entity_id}",
                "name": f"open-data-{publisher_name}",
                "title": f"{name_en} Open Data Profile",
                "notes": (
                    "Fallback dataset profile generated from GOV.SA ministry registry because "
                    "CKAN endpoint is currently unavailable from this network."
                ),
                "license_id": "n/a",
                "metadata_created": generated_at,
                "metadata_modified": generated_at,
                "publisher": {"id": str(entity_id), "name": publisher_name, "title": name_en},
                "tags": ["fallback", "ministry", "govsa"],
                "groups": ["ministries"],
                "resources": [
                    {
                        "id": f"fallback-resource-{entity_id}",
                        "name": "official_website",
                        "description": "Official website extracted from GOV.SA.",
                        "format": "HTML",
                        "mimetype": "text/html",
                        "url": website,
                        "size": None,
                        "last_modified": generated_at,
                    },
                    {
                        "id": f"fallback-detail-en-{entity_id}",
                        "name": "agency_detail_en",
                        "description": "GOV.SA agency detail page (English).",
                        "format": "HTML",
                        "mimetype": "text/html",
                        "url": _detail_url(ministry, "en"),
                        "size": None,
                        "last_modified": generated_at,
                    },
                ],
            }

    return {
        "id": dataset_id_or_name,
        "name": dataset_id_or_name,
        "title": f"Fallback dataset placeholder for '{dataset_id_or_name}'",
        "notes": (
            "Dataset not found in fallback registry. CKAN upstream appears unavailable from this "
            "network; try again when upstream access is restored."
        ),
        "license_id": "n/a",
        "metadata_created": generated_at,
        "metadata_modified": generated_at,
        "publisher": {"id": "fallback", "name": "fallback", "title": "Fallback"},
        "tags": ["fallback"],
        "groups": [],
        "resources": [],
    }


def fallback_resource_detail(resource_id: str) -> Dict[str, Any]:
    generated_at, ministries = load_fallback_ministries()
    needle = (resource_id or "").strip().lower()

    for ministry in ministries:
        entity_id, slug, name_en, _ = _ministry_identity(ministry)
        if needle in {f"fallback-resource-{entity_id}", f"fallback-detail-en-{entity_id}"}:
            if needle.startswith("fallback-detail-en-"):
                url = _detail_url(ministry, "en")
                title = "agency_detail_en"
            else:
                url = _official_website(ministry)
                title = "official_website"
            return {
                "id": needle,
                "name": title,
                "description": f"Fallback resource for {name_en}",
                "format": "HTML",
                "mimetype": "text/html",
                "url": url,
                "size": None,
                "last_modified": generated_at,
                "_fallback_dataset_slug": slug,
            }

    return {
        "id": resource_id,
        "name": "fallback_resource_placeholder",
        "description": "Fallback resource placeholder. Upstream CKAN is unavailable.",
        "format": "HTML",
        "mimetype": "text/html",
        "url": "",
        "size": None,
        "last_modified": generated_at,
    }


def fallback_publisher_summary(publisher: str, sample_rows: int) -> Dict[str, Any]:
    search = fallback_search_datasets(
        query="*:*",
        publisher=publisher,
        rows=max(1, min(sample_rows, 200)),
        start=0,
    )
    datasets = search.get("datasets", [])
    resource_count = sum(len(item.get("resources", [])) for item in datasets)
    return {
        "publisher": publisher,
        "total_datasets": search.get("count", 0),
        "sampled_datasets": len(datasets),
        "top_formats": [("html", resource_count or len(datasets))],
        "top_tags": [("fallback", len(datasets)), ("ministry", len(datasets))],
    }


def fallback_datastore_search(
    resource_id: str,
    limit: int,
    offset: int,
) -> Dict[str, Any]:
    _, ministries = load_fallback_ministries()
    safe_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)
    records: List[Dict[str, Any]] = []

    target_entity_id = None
    if resource_id.startswith("fallback-resource-"):
        try:
            target_entity_id = int(resource_id.split("fallback-resource-", 1)[1])
        except ValueError:
            target_entity_id = None

    for ministry in ministries:
        entity_id, slug, name_en, name_ar = _ministry_identity(ministry)
        if target_entity_id is not None and entity_id != target_entity_id:
            continue
        records.append(
            {
                "entity_id": entity_id,
                "slug": slug,
                "name_en": name_en,
                "name_ar": name_ar,
                "official_website": _official_website(ministry),
                "detail_url_en": _detail_url(ministry, "en"),
                "detail_url_ar": _detail_url(ministry, "ar"),
            }
        )

    paged = records[safe_offset : safe_offset + safe_limit]
    fields = [
        {"id": "entity_id", "type": "int"},
        {"id": "slug", "type": "text"},
        {"id": "name_en", "type": "text"},
        {"id": "name_ar", "type": "text"},
        {"id": "official_website", "type": "text"},
        {"id": "detail_url_en", "type": "text"},
        {"id": "detail_url_ar", "type": "text"},
    ]
    return {
        "help": "fallback datastore payload",
        "success": True,
        "result": {
            "resource_id": resource_id,
            "fields": fields,
            "records": paged,
            "limit": safe_limit,
            "offset": safe_offset,
            "total_estimation_threshold": None,
            "records_truncated": False,
            "total_was_estimated": False,
            "total": len(records),
        },
    }
