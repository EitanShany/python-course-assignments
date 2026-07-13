import pandas as pd
import pytest

from immunoflow_discovery_analyzer.simple_analysis import (
    analyze_fcs_samples,
    arcsinh_transform,
    compare_treatment_pairs,
)

from fcs_test_helpers import write_test_fcs


def test_analyze_fcs_samples_calculates_cd20_high_ps6_metrics(tmp_path):
    fcs_dir = tmp_path / "fcs"
    fcs_dir.mkdir()
    write_test_fcs(
        fcs_dir / "sample1.fcs",
        ["CD20", "pS6"],
        [
            [1.0, 5.0],
            [2.0, 10.0],
            [100.0, 50.0],
            [120.0, 60.0],
        ],
    )
    plate_map = pd.DataFrame(
        [
            {
                "Sample_ID": "S1",
                "Subject_ID": "patient1",
                "Treatment": "Reference",
                "FCS_File": "sample1.fcs",
            }
        ]
    )

    metrics = analyze_fcs_samples(fcs_dir, plate_map, gate_percentile=50)

    assert metrics.loc[0, "Total_Events"] == 4
    assert metrics.loc[0, "Gated_Events"] == 2
    assert metrics.loc[0, "Gated_Percent"] == 50.0
    assert metrics.loc[0, "Median_pS6_CD20_High"] > 2


def test_compare_treatment_pairs_returns_delta_per_subject():
    sample_metrics = pd.DataFrame(
        [
            {
                "Subject_ID": "patient1",
                "Treatment": "Reference",
                "Median_pS6_CD20_High": 1.0,
            },
            {
                "Subject_ID": "patient1",
                "Treatment": "BCR-XL",
                "Median_pS6_CD20_High": 3.0,
            },
        ]
    )

    comparison = compare_treatment_pairs(sample_metrics)

    assert comparison.loc[0, "Delta"] == 2.0
    assert comparison.loc[0, "Fold_Change"] == 3.0


def test_compare_treatment_pairs_skips_fold_change_when_reference_is_not_positive():
    sample_metrics = pd.DataFrame(
        [
            {
                "Subject_ID": "patient1",
                "Treatment": "Reference",
                "Median_pS6_CD20_High": -1.0,
            },
            {
                "Subject_ID": "patient1",
                "Treatment": "BCR-XL",
                "Median_pS6_CD20_High": 3.0,
            },
        ]
    )

    comparison = compare_treatment_pairs(sample_metrics)

    assert comparison.loc[0, "Delta"] == 4.0
    assert comparison.loc[0, "Fold_Change"] is None


def test_arcsinh_transform_rejects_invalid_cofactor():
    with pytest.raises(ValueError, match="Cofactor"):
        arcsinh_transform(pd.DataFrame({"CD20": [1.0]}), cofactor=0)
