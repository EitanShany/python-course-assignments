"""Optional FlowKit adapter.

FlowKit is not a required dependency for the current milestone. This module keeps
all optional FlowKit access in one place so the rest of the project can continue
in mock mode when FlowKit is not installed or FCS loading fails.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class FcsParameterReadResult:
    parameters: set[str]
    warning: str | None = None


def get_fcs_parameters(file_path: str | Path) -> FcsParameterReadResult:
    """Return FCS parameter names using FlowKit when available."""
    path = Path(file_path)

    try:
        import flowkit as fk
    except ImportError:
        return FcsParameterReadResult(
            parameters=set(),
            warning="FlowKit is not installed; FCS parameter validation was skipped in mock mode.",
        )

    try:
        sample = fk.Sample(str(path))
    except Exception as error:
        return FcsParameterReadResult(
            parameters=set(),
            warning=f"Could not load FCS file with FlowKit; parameter validation was skipped: {error}",
        )

    parameters = _extract_parameter_names(sample)
    if not parameters:
        return FcsParameterReadResult(
            parameters=set(),
            warning="FlowKit loaded the FCS file but no parameter names were found.",
        )

    return FcsParameterReadResult(parameters=parameters)


def _extract_parameter_names(sample) -> set[str]:
    for attribute_name in ["pnn_labels", "channels"]:
        value = getattr(sample, attribute_name, None)
        if value is not None:
            return {str(item).strip() for item in value if str(item).strip()}

    get_channel_info = getattr(sample, "get_channel_info", None)
    if callable(get_channel_info):
        channel_info = get_channel_info()
        if hasattr(channel_info, "columns") and "pnn" in channel_info.columns:
            return {
                str(item).strip()
                for item in channel_info["pnn"].dropna()
                if str(item).strip()
            }

    return set()
