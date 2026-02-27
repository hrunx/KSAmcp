from __future__ import annotations

import json

import pytest

from ksa_opendata.services.govsa_directory import (
    DirectoryParseError,
    extract_directory_page_data,
)


def _build_sample_html() -> str:
    payload = [
        "$",
        "$L132",
        None,
        {
            "categories": [
                {"id": "17489", "name": "Ministries", "description": None},
                {"id": "17708", "name": "Authorities", "description": None},
            ],
            "data": {
                "rows": [
                    {
                        "nid": [{"value": "17606"}],
                        "title": [{"value": "Ministry of Commerce"}],
                        "field_na_type": [{"target_id": 17489, "label": "Ministries"}],
                        "field_url_shrd": [{"uri": "https://mc.gov.sa/"}],
                    }
                ],
                "pager": {
                    "current_page": 0,
                    "total_items": "363",
                    "total_pages": 41,
                    "items_per_page": "9",
                },
            },
            "filterKey": "agency_type",
        },
    ]
    push_payload = [1, "d:" + json.dumps(payload, ensure_ascii=False)]
    script = f"<script>self.__next_f.push({json.dumps(push_payload, ensure_ascii=False)})</script>"
    return f"<html><head></head><body>{script}</body></html>"


def test_extract_directory_page_data_success() -> None:
    html = _build_sample_html()
    data = extract_directory_page_data(html, locale="en")

    assert len(data.categories) == 2
    assert data.categories[0].id == "17489"
    assert data.pager.total_items == 363
    assert len(data.rows) == 1
    row = data.rows[0]
    assert row.entity_id == 17606
    assert row.name == "Ministry of Commerce"
    assert row.category_id == "17489"
    assert row.official_website == "https://mc.gov.sa/"
    assert row.detail_url == "https://www.my.gov.sa/en/agencies/17606"


def test_extract_directory_page_data_missing_payload() -> None:
    with pytest.raises(DirectoryParseError):
        extract_directory_page_data("<html><body>No payload</body></html>", locale="en")
