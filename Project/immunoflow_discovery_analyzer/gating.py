"""Placeholder gating interface for future FlowKit integration."""


class GatingEngine:
    """Stable mock gating interface.

    This class does not read FCS files or perform real biological gating yet.
    It only gives the rest of the project a stable API to call later.
    """

    def __init__(self, mode: str = "mock"):
        self.mode = mode

    def run_closed_gating(self, sample):
        """Return mock gated population counts for one sample."""
        sample_id = _get_sample_id(sample)
        return {
            "Sample_ID": sample_id,
            "Mode": self.mode,
            "Cells": 100000,
            "Singlets": 90000,
            "Live": 80000,
            "CD45+": 65000,
            "CD3+": 42000,
            "CD4+": 18000,
            "CD8+": 22000,
        }

    def run_exploratory_path(self, sample, path):
        """Return a mock count and percentage for one exploratory path."""
        sample_id = _get_sample_id(sample)
        path_text = str(path)
        mock_count = max(100, 10000 - len(path_text) * 50)
        mock_percentage = round(mock_count / 100000 * 100, 3)

        return {
            "Sample_ID": sample_id,
            "Mode": self.mode,
            "Exploratory_Path": path_text,
            "Mock_Count": mock_count,
            "Mock_Percentage": mock_percentage,
        }


def _get_sample_id(sample) -> str:
    if isinstance(sample, dict):
        return str(sample.get("Sample_ID", sample.get("sample_id", "unknown")))
    return str(getattr(sample, "Sample_ID", getattr(sample, "sample_id", "unknown")))
