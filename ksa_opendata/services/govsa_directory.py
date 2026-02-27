"""Official GOV.SA directory extraction helpers."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import httpx

MINISTRY_TAXONOMY_ID = "17489"

_SCRIPT_TAG_PATTERN = re.compile(r"<script>(.*?)</script>", re.DOTALL)
_PUSH_PREFIX = "self.__next_f.push("


class DirectoryParseError(ValueError):
    """Raised when GOV.SA directory page payload cannot be parsed."""


class DirectoryFetchError(RuntimeError):
    """Raised when GOV.SA directory page cannot be fetched reliably."""


@dataclass(frozen=True)
class DirectoryCategory:
    id: str
    name: str


@dataclass(frozen=True)
class DirectoryPager:
    current_page: int
    total_items: int
    total_pages: int
    items_per_page: int


@dataclass(frozen=True)
class DirectoryEntityRow:
    entity_id: int
    name: str
    category_id: str
    category_name: str
    official_website: str | None
    detail_url: str


@dataclass(frozen=True)
class DirectoryPageData:
    categories: list[DirectoryCategory]
    rows: list[DirectoryEntityRow]
    pager: DirectoryPager


def extract_directory_page_data(html: str, locale: str) -> DirectoryPageData:
    payload = _extract_payload_object(html)

    raw_categories = payload.get("categories")
    raw_data = payload.get("data")
    if not isinstance(raw_categories, list) or not isinstance(raw_data, Mapping):
        raise DirectoryParseError("Malformed categories/data payload in GOV.SA page")

    categories = [_parse_category(item) for item in raw_categories]
    rows_raw = raw_data.get("rows")
    if not isinstance(rows_raw, list):
        raise DirectoryParseError("Missing rows list in GOV.SA directory payload")
    rows = [_parse_row(item, locale=locale) for item in rows_raw]

    pager = _parse_pager(raw_data.get("pager"))
    return DirectoryPageData(categories=categories, rows=rows, pager=pager)


class GovSaDirectoryClient:
    """Fetch and parse paginated GOV.SA directory listing pages."""

    def __init__(
        self,
        timeout_s: float = 30.0,
        max_retries: int = 5,
        retry_backoff_s: float = 1.5,
    ) -> None:
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.retry_backoff_s = retry_backoff_s

    def crawl_pages(
        self,
        *,
        locale: str = "en",
        extra_params: Mapping[str, str] | None = None,
    ) -> list[DirectoryPageData]:
        with httpx.Client(
            timeout=self.timeout_s,
            follow_redirects=True,
            headers={"User-Agent": "ksa-opendata-mcp/0.1"},
        ) as client:
            first_page = self._fetch_page(
                client=client,
                locale=locale,
                page=0,
                extra_params=extra_params,
            )
            pages = [first_page]
            for page in range(1, first_page.pager.total_pages):
                pages.append(
                    self._fetch_page(
                        client=client,
                        locale=locale,
                        page=page,
                        extra_params=extra_params,
                    )
                )
        return pages

    def fetch_page(
        self,
        *,
        locale: str = "en",
        page: int = 0,
        extra_params: Mapping[str, str] | None = None,
    ) -> DirectoryPageData:
        with httpx.Client(
            timeout=self.timeout_s,
            follow_redirects=True,
            headers={"User-Agent": "ksa-opendata-mcp/0.1"},
        ) as client:
            return self._fetch_page(
                client=client,
                locale=locale,
                page=page,
                extra_params=extra_params,
            )

    def _fetch_page(
        self,
        *,
        client: httpx.Client,
        locale: str,
        page: int,
        extra_params: Mapping[str, str] | None,
    ) -> DirectoryPageData:
        params = dict(extra_params or {})
        params["page"] = str(page)
        url = f"https://www.my.gov.sa/{locale}/agencies"

        for attempt in range(1, self.max_retries + 1):
            try:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = extract_directory_page_data(response.text, locale=locale)
                if data.pager.current_page != page:
                    raise DirectoryParseError(
                        f"Page mismatch for {url}: expected={page}, got={data.pager.current_page}"
                    )
                return data
            except (httpx.HTTPError, DirectoryParseError) as exc:
                if attempt == self.max_retries:
                    raise DirectoryFetchError(
                        f"Failed to fetch GOV.SA directory page locale={locale} page={page}"
                    ) from exc
                time.sleep(self.retry_backoff_s * attempt)

        raise AssertionError("unreachable")


def _extract_payload_object(html: str) -> dict[str, Any]:
    scripts = _SCRIPT_TAG_PATTERN.findall(html)
    candidates = [
        script
        for script in scripts
        if "__next_f.push([1," in script
        and "filterKey" in script
        and "agency_type" in script
        and "categories" in script
        and "pager" in script
    ]
    if not candidates:
        raise DirectoryParseError("Could not locate GOV.SA directory payload script")

    candidate = max(candidates, key=len)
    if not candidate.startswith(_PUSH_PREFIX) or not candidate.endswith(")"):
        raise DirectoryParseError("Unexpected GOV.SA payload script wrapper")

    push_args = candidate[len(_PUSH_PREFIX) : -1]
    try:
        parsed_push = json.loads(push_args)
    except json.JSONDecodeError as exc:
        raise DirectoryParseError("Failed to decode GOV.SA push payload JSON") from exc

    if (
        not isinstance(parsed_push, list)
        or len(parsed_push) < 2
        or parsed_push[0] != 1
        or not isinstance(parsed_push[1], str)
    ):
        raise DirectoryParseError("Unexpected GOV.SA push payload structure")

    serialized_payload = parsed_push[1]
    if ":" not in serialized_payload:
        raise DirectoryParseError("Malformed GOV.SA payload body")

    _, raw_object = serialized_payload.split(":", 1)
    try:
        parsed_object = json.loads(raw_object)
    except json.JSONDecodeError as exc:
        raise DirectoryParseError("Failed to parse GOV.SA directory object JSON") from exc

    if not isinstance(parsed_object, list) or len(parsed_object) < 4:
        raise DirectoryParseError("Unexpected GOV.SA directory object envelope")

    payload = parsed_object[3]
    if not isinstance(payload, dict):
        raise DirectoryParseError("Directory payload node is not a mapping")
    if payload.get("filterKey") != "agency_type":
        raise DirectoryParseError("Directory payload is not the agencies taxonomy payload")
    return payload


def _parse_category(raw: Any) -> DirectoryCategory:
    if not isinstance(raw, Mapping):
        raise DirectoryParseError(f"Invalid category payload type: {type(raw).__name__}")
    category_id = str(raw.get("id", "")).strip()
    category_name = str(raw.get("name", "")).strip()
    if not category_id or not category_name:
        raise DirectoryParseError("Category payload is missing id or name")
    return DirectoryCategory(id=category_id, name=category_name)


def _parse_row(raw: Any, *, locale: str) -> DirectoryEntityRow:
    if not isinstance(raw, Mapping):
        raise DirectoryParseError(f"Invalid row payload type: {type(raw).__name__}")

    entity_id = _extract_int_field(raw.get("nid"), field_name="nid")
    name = _extract_string_field(raw.get("title"), field_name="title")
    category_id, category_name = _extract_category_ref(raw.get("field_na_type"))
    official_website = _extract_website(raw.get("field_url_shrd"))
    detail_url = f"https://www.my.gov.sa/{locale}/agencies/{entity_id}"

    return DirectoryEntityRow(
        entity_id=entity_id,
        name=name,
        category_id=category_id,
        category_name=category_name,
        official_website=official_website,
        detail_url=detail_url,
    )


def _parse_pager(raw: Any) -> DirectoryPager:
    if not isinstance(raw, Mapping):
        raise DirectoryParseError("Missing pager metadata in GOV.SA payload")
    return DirectoryPager(
        current_page=_coerce_int(raw.get("current_page"), field_name="current_page"),
        total_items=_coerce_int(raw.get("total_items"), field_name="total_items"),
        total_pages=_coerce_int(raw.get("total_pages"), field_name="total_pages"),
        items_per_page=_coerce_int(raw.get("items_per_page"), field_name="items_per_page"),
    )


def _extract_int_field(raw: Any, *, field_name: str) -> int:
    value = _extract_string_field(raw, field_name=field_name)
    try:
        return int(value)
    except ValueError as exc:
        raise DirectoryParseError(f"Field '{field_name}' value is not an int: {value}") from exc


def _extract_string_field(raw: Any, *, field_name: str) -> str:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        raise DirectoryParseError(f"Field '{field_name}' must be a non-empty list")
    first = raw[0]
    if not isinstance(first, Mapping):
        raise DirectoryParseError(f"Field '{field_name}' first item must be a mapping")
    value = first.get("value")
    if not isinstance(value, (str, int, float)):
        raise DirectoryParseError(f"Field '{field_name}' value is missing")
    text = str(value).strip()
    if not text:
        raise DirectoryParseError(f"Field '{field_name}' resolved to an empty value")
    return text


def _extract_category_ref(raw: Any) -> tuple[str, str]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        raise DirectoryParseError("field_na_type must be a non-empty list")
    first = raw[0]
    if not isinstance(first, Mapping):
        raise DirectoryParseError("field_na_type first item must be a mapping")
    target_id = first.get("target_id")
    label = first.get("label")
    if target_id is None or not isinstance(label, str) or not label.strip():
        raise DirectoryParseError("field_na_type is missing target_id or label")
    return str(target_id), label.strip()


def _extract_website(raw: Any) -> str | None:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return None
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        uri = item.get("uri")
        if isinstance(uri, str) and uri.startswith(("http://", "https://")):
            return uri
    return None


def _coerce_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or value is None:
        raise DirectoryParseError(f"Pager field '{field_name}' is missing or invalid")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise DirectoryParseError(f"Pager field '{field_name}' is empty")
        try:
            return int(stripped)
        except ValueError as exc:
            raise DirectoryParseError(
                f"Pager field '{field_name}' is not a valid integer: {value}"
            ) from exc
    raise DirectoryParseError(f"Pager field '{field_name}' has unsupported type")
