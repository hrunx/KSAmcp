from ksa_opendata.services.ranking import rank_datasets


def test_rank_datasets_matches_title():
    datasets = [
        {"title": "Ministry of Health Budget", "tags": ["health"], "notes": ""},
        {"title": "Education Plans", "tags": ["education"], "notes": ""},
    ]
    ranked = rank_datasets(datasets, "health")
    assert ranked[0]["title"] == "Ministry of Health Budget"
