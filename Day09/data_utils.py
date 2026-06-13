"""Shared data loading and validation helpers for Day09."""

from pathlib import Path

import numpy as np
import pandas as pd

COLUMN_NAMES = [
    "Pregnancies",
    "Glucose",
    "BloodPressure",
    "SkinThickness",
    "Insulin",
    "BMI",
    "DiabetesPedigreeFunction",
    "Age",
    "Outcome",
]
FEATURE_NAMES = COLUMN_NAMES[:-1]
OUTCOME_LABELS = {
    0: "Healthy",
    1: "Diabetes",
}


def outcome_label(value):
    """Return a readable Hebrew label for an outcome value."""
    try:
        return OUTCOME_LABELS[int(value)]
    except (KeyError, TypeError, ValueError):
        return f"Unknown outcome ({value})"


def validate_feature_frame(frame):
    """Return a numeric feature frame or raise a clear validation error."""
    missing = [name for name in FEATURE_NAMES if name not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    features = frame[FEATURE_NAMES].copy()
    for name in FEATURE_NAMES:
        features[name] = pd.to_numeric(features[name], errors="raise")

    if features.empty:
        raise ValueError("At least one data row is required.")
    if not np.isfinite(features.to_numpy(dtype=float)).all():
        raise ValueError("Feature values must be finite numbers.")
    if (features < 0).any().any():
        raise ValueError("Feature values cannot be negative.")

    return features


def load_dataset(path):
    """Load a headerless diabetes CSV and validate its basic structure."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")

    frame = pd.read_csv(path, header=None)
    if frame.shape[1] != len(COLUMN_NAMES):
        raise ValueError(
            f"Dataset must contain {len(COLUMN_NAMES)} columns; "
            f"found {frame.shape[1]}."
        )

    frame.columns = COLUMN_NAMES
    features = validate_feature_frame(frame)
    outcome = pd.to_numeric(frame["Outcome"], errors="raise")
    if outcome.isna().any() or not outcome.isin([0, 1]).all():
        raise ValueError("Outcome values must be 0 or 1.")

    validated = features.copy()
    validated["Outcome"] = outcome.astype(int)
    return validated


def sample_from_mapping(data):
    """Validate one JSON-like object and return it as a feature frame."""
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object.")
    return validate_feature_frame(pd.DataFrame([data]))
