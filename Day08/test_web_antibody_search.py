from pathlib import Path

from fastapi.testclient import TestClient

import web_antibody_search

client = TestClient(web_antibody_search.app)


def test_home_returns_search_form() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Antibody Target Search" in response.text
    assert "<form" in response.text


def test_api_search_returns_json(monkeypatch) -> None:
    monkeypatch.setattr(web_antibody_search, "safe_fetch_gene_aliases", lambda target: ["PD1"])
    monkeypatch.setattr(
        web_antibody_search,
        "search_all_sources",
        lambda **kwargs: [
            {
                "antibody_name": "Testimab",
                "target_antigen_or_gene": "PD1",
                "target_category": "Immune checkpoint",
                "cancer_indication": "Melanoma",
                "antibody_species_or_type": "Human",
                "antibody_format": "Whole mAb",
                "highest_clinical_trial": "Phase-II",
                "estimated_status": "Active",
                "pubmed_reference_count": 12,
                "data_source": "Thera-SAbDab",
                "sequence_page_url": "https://example.test/sequence",
                "heavy_variable_region_sequence": "QVQLVESGGG",
                "light_variable_region_sequence": "EIVMTQSPAT",
            }
        ],
    )

    response = client.get("/api/search?target=PD1&limit=1&species=Human")

    assert response.status_code == 200
    payload = response.json()
    assert payload["target"] == "PD1"
    assert payload["aliases"] == ["PD1"]
    assert len(payload["results"]) == 1
    assert payload["results"][0]["antibody_name"] == "Testimab"


def test_search_form_returns_html_with_results(monkeypatch) -> None:
    monkeypatch.setattr(web_antibody_search, "safe_fetch_gene_aliases", lambda target: ["PD1"])
    monkeypatch.setattr(
        web_antibody_search,
        "search_all_sources",
        lambda **kwargs: [
            {
                "antibody_name": "Testimab",
                "target_antigen_or_gene": "PD1",
                "target_category": "Immune checkpoint",
                "cancer_indication": "Melanoma",
                "antibody_species_or_type": "Human",
                "antibody_format": "Whole mAb",
                "highest_clinical_trial": "Phase-II",
                "estimated_status": "Active",
                "pubmed_reference_count": 12,
                "data_source": "Thera-SAbDab",
                "sequence_page_url": "https://example.test/sequence",
                "heavy_variable_region_sequence": "QVQLVESGGG",
                "light_variable_region_sequence": "EIVMTQSPAT",
            }
        ],
    )
    output_dir = Path(web_antibody_search.__file__).resolve().parent / "output_test"
    web_antibody_search.OUTPUT_DIR = output_dir

    response = client.post(
        "/search",
        data={"target": "PD1", "limit": "1", "species": "Human"},
    )

    assert response.status_code == 200
    assert "Testimab" in response.text
    assert "/download/csv" in response.text
    assert (output_dir / "antibody_results.csv").exists()
    assert (output_dir / "antibody_results.xlsx").exists()


def test_api_search_rejects_unsafe_target() -> None:
    response = client.get("/api/search?target=PD1;rm -rf&limit=1")

    assert response.status_code == 400
    assert "Unsupported target query" in response.text
