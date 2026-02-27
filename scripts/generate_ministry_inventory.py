"""Produce a ministry catalog inventory report from the national portal."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from ksa_opendata.registry import load_registry
from ksa_opendata.sources.ckan import CKANClient, CKANConfig


def looks_like_ministry(value: str | None) -> bool:
    if not value:
        return False
    text = value.lower()
    return "ministry" in text or "وزارة" in text


async def main() -> None:
    registry = load_registry()
    source = registry.get("ksa_open_data_platform")
    client = CKANClient(CKANConfig(base_url=source.base_url, api_path=source.api_path or ""))
    try:
        orgs = await client.call("organization_list", {"all_fields": True})
        ministries = [
            org
            for org in orgs
            if looks_like_ministry(org.get("title"))
            or looks_like_ministry(org.get("name"))
        ]
        report: List[Dict[str, Any]] = []
        for org in ministries:
            name = org.get("name")
            title = org.get("title")
            if not name:
                continue
            pkg = await client.call(
                "package_search",
                {"q": "*:*", "fq": f"organization:{name}", "rows": 100, "start": 0},
            )
            fmt = Counter()
            tags = Counter()
            for ds in pkg.get("results", []):
                for t in ds.get("tags", []):
                    if tag_name := t.get("name"):
                        tags[tag_name] += 1
                for res in ds.get("resources", []):
                    fmt_name = (res.get("format") or "unknown").lower().strip() or "unknown"
                    fmt[fmt_name] += 1
            report.append(
                {
                    "publisher_name": name,
                    "publisher_title": title,
                    "dataset_count": pkg.get("count"),
                    "sampled_datasets": len(pkg.get("results", [])),
                    "top_formats": fmt.most_common(10),
                    "top_tags": tags.most_common(10),
                }
            )
        out_path = Path("reports")
        out_path.mkdir(parents=True, exist_ok=True)
        (out_path / "ministry_inventory.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        md_lines: List[str] = ["# KSA Ministry Open Data Inventory\n"]
        for entry in sorted(report, key=lambda x: (x["dataset_count"] or 0), reverse=True):
            md_lines.append(f"## {entry['publisher_title']} (`{entry['publisher_name']}`)")
            md_lines.append(
                f"- Datasets: {entry['dataset_count']} (sampled {entry['sampled_datasets']})"
            )
            md_lines.append(f"- Top formats: {entry['top_formats']}")
            md_lines.append(f"- Top tags: {entry['top_tags']}\n")
        (out_path / "ministry_inventory.md").write_text("\n".join(md_lines), encoding="utf-8")
        print("Wrote reports/ministry_inventory.{json,md}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
