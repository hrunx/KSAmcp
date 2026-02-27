from __future__ import annotations

from ksa_opendata.services.entity_registry import EntityObservation, build_canonical_entities


def test_build_canonical_entities_merges_observations_by_entity_id() -> None:
    observations = [
        EntityObservation(
            entity_id=17606,
            locale="en",
            sort_order="DESC",
            category_id="17489",
            category_name="Ministries",
            name="Ministry of Commerce",
            official_website="https://mc.gov.sa/",
            detail_url="https://www.my.gov.sa/en/agencies/17606",
        ),
        EntityObservation(
            entity_id=17606,
            locale="en",
            sort_order="ASC",
            category_id="17489",
            category_name="Ministries",
            name="Ministry of Commerce",
            official_website="https://mc.gov.sa/",
            detail_url="https://www.my.gov.sa/en/agencies/17606",
        ),
        EntityObservation(
            entity_id=17606,
            locale="ar",
            sort_order="ASC",
            category_id="17489",
            category_name="الوزارات",
            name="وزارة التجارة",
            official_website="https://mc.gov.sa/",
            detail_url="https://www.my.gov.sa/ar/agencies/17606",
        ),
    ]

    entities = build_canonical_entities(observations)
    assert len(entities) == 1
    entity = entities[0]
    assert entity.entity_id == 17606
    assert entity.is_ministry is True
    assert entity.strategy_count == 3
    assert entity.observed_count == 3
    assert entity.slug.startswith("17606-ministry-of-commerce")
    assert set(entity.locale_views.keys()) == {"en", "ar"}
    assert entity.locale_views["ar"].name == "وزارة التجارة"


def test_slug_falls_back_when_ascii_name_missing() -> None:
    observations = [
        EntityObservation(
            entity_id=9000001,
            locale="ar",
            sort_order="DESC",
            category_id="17708",
            category_name="الهيئات",
            name="هيئة تجريبية",
            official_website=None,
            detail_url="https://www.my.gov.sa/ar/agencies/9000001",
        )
    ]
    entities = build_canonical_entities(observations)
    assert entities[0].slug == "9000001-entity"
