from pathlib import Path

import pytest

from scripts.create_bodenmiller_example_workbook import (
    build_manifest,
    marker_role,
    parse_bodenmiller_file_name,
)


def test_parse_bodenmiller_file_name_returns_patient_and_treatment():
    patient_id, treatment = parse_bodenmiller_file_name(
        "PBMC8_30min_patient4_BCR-XL.fcs"
    )

    assert patient_id == "patient4"
    assert treatment == "BCR-XL"


def test_parse_bodenmiller_file_name_rejects_unexpected_treatment():
    with pytest.raises(ValueError, match="Unexpected treatment"):
        parse_bodenmiller_file_name("PBMC8_30min_patient4_Treated.fcs")


def test_build_manifest_creates_required_plate_map_columns():
    manifest = build_manifest(
        [
            Path("PBMC8_30min_patient1_BCR-XL.fcs"),
            Path("PBMC8_30min_patient1_Reference.fcs"),
        ]
    )

    assert manifest["Sample_ID"].tolist() == ["patient1_BCR-XL", "patient1_Reference"]
    assert manifest["Subject_ID"].tolist() == ["patient1", "patient1"]
    assert manifest["Treatment"].tolist() == ["BCR-XL", "Reference"]
    assert manifest["FCS_File"].tolist() == [
        "PBMC8_30min_patient1_BCR-XL.fcs",
        "PBMC8_30min_patient1_Reference.fcs",
    ]


def test_marker_role_classifies_qc_lineage_and_functional_markers():
    assert marker_role("Time") == "QC"
    assert marker_role("CD20") == "Lineage"
    assert marker_role("pS6") == "Functional"
