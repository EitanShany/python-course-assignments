from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .fcs_reader import read_fcs_events


DEFAULT_GATE_MARKER = "CD20"
DEFAULT_SIGNAL_MARKER = "pS6"
DEFAULT_GATE_PERCENTILE = 75.0


def analyze_fcs_samples(
    fcs_dir: str | Path,
    plate_map_df: pd.DataFrame,
    gate_marker: str = DEFAULT_GATE_MARKER,
    signal_marker: str = DEFAULT_SIGNAL_MARKER,
    gate_percentile: float = DEFAULT_GATE_PERCENTILE,
) -> pd.DataFrame:
    """Calculate simple sample-level CyTOF metrics from FCS files."""
    _validate_gate_percentile(gate_percentile)
    required_columns = {"Sample_ID", "Subject_ID", "Treatment", "FCS_File"}
    missing_columns = required_columns - set(plate_map_df.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(f"Plate_Map is missing required column(s): {missing_text}")

    fcs_path = Path(fcs_dir)
    rows = []
    for _, sample in plate_map_df.iterrows():
        file_name = str(sample["FCS_File"]).strip()
        events = read_fcs_events(fcs_path / file_name)
        transformed = arcsinh_transform(events)
        _validate_markers(transformed, [gate_marker, signal_marker], file_name)

        gate_threshold = float(transformed[gate_marker].quantile(gate_percentile / 100))
        gated_events = transformed[transformed[gate_marker] >= gate_threshold]
        total_events = len(transformed)
        gated_count = len(gated_events)

        rows.append(
            {
                "Sample_ID": str(sample["Sample_ID"]).strip(),
                "Subject_ID": str(sample["Subject_ID"]).strip(),
                "Treatment": str(sample["Treatment"]).strip(),
                "FCS_File": file_name,
                "Total_Events": total_events,
                "Gate_Marker": gate_marker,
                "Gate_Percentile": gate_percentile,
                "Gate_Threshold_Arcsinh": round(gate_threshold, 6),
                "Gated_Events": gated_count,
                "Gated_Percent": round(gated_count / total_events * 100, 3),
                f"Median_{signal_marker}_All_Cells": round(float(transformed[signal_marker].median()), 6),
                f"Median_{signal_marker}_{gate_marker}_High": round(float(gated_events[signal_marker].median()), 6),
            }
        )

    return pd.DataFrame(rows)


def compare_treatment_pairs(
    sample_metrics_df: pd.DataFrame,
    reference_group: str = "Reference",
    treatment_group: str = "BCR-XL",
    signal_marker: str = DEFAULT_SIGNAL_MARKER,
    gate_marker: str = DEFAULT_GATE_MARKER,
) -> pd.DataFrame:
    """Compare treatment and reference sample metrics per subject."""
    metric_column = f"Median_{signal_marker}_{gate_marker}_High"
    required_columns = {"Subject_ID", "Treatment", metric_column}
    missing_columns = required_columns - set(sample_metrics_df.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(f"Sample metrics are missing required column(s): {missing_text}")

    rows = []
    for subject_id, subject_df in sample_metrics_df.groupby("Subject_ID"):
        reference_values = subject_df.loc[
            subject_df["Treatment"] == reference_group,
            metric_column,
        ]
        treatment_values = subject_df.loc[
            subject_df["Treatment"] == treatment_group,
            metric_column,
        ]
        if reference_values.empty or treatment_values.empty:
            continue

        reference_value = float(reference_values.iloc[0])
        treatment_value = float(treatment_values.iloc[0])
        rows.append(
            {
                "Subject_ID": subject_id,
                "Reference_Group": reference_group,
                "Treatment_Group": treatment_group,
                "Metric": metric_column,
                "Reference_Value": round(reference_value, 6),
                "Treatment_Value": round(treatment_value, 6),
                "Delta": round(treatment_value - reference_value, 6),
                "Fold_Change": _safe_fold_change(treatment_value, reference_value),
            }
        )

    return pd.DataFrame(rows)


def arcsinh_transform(events_df: pd.DataFrame, cofactor: float = 5.0) -> pd.DataFrame:
    """Apply the common CyTOF arcsinh transformation."""
    if cofactor <= 0:
        raise ValueError("Cofactor must be positive.")
    numeric_events = events_df.apply(pd.to_numeric, errors="coerce")
    return np.arcsinh(numeric_events / cofactor)


def _validate_gate_percentile(gate_percentile: float) -> None:
    if not 0 < gate_percentile < 100:
        raise ValueError("Gate percentile must be between 0 and 100.")


def _validate_markers(events_df: pd.DataFrame, markers: list[str], file_name: str) -> None:
    missing_markers = [marker for marker in markers if marker not in events_df.columns]
    if missing_markers:
        missing_text = ", ".join(missing_markers)
        raise ValueError(f"{file_name} is missing marker(s): {missing_text}")


def _safe_fold_change(treatment_value: float, reference_value: float) -> float | None:
    if reference_value <= 0:
        return None
    return round(treatment_value / reference_value, 6)
