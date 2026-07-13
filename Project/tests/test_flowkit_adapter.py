import sys
import types

import pandas as pd

from immunoflow_discovery_analyzer.flowkit_adapter import (
    _extract_parameter_names,
    get_fcs_parameters,
)


def test_get_fcs_parameters_warns_when_flowkit_is_not_installed(monkeypatch):
    monkeypatch.delitem(sys.modules, "flowkit", raising=False)

    result = get_fcs_parameters("sample.fcs")

    assert result.parameters == set()
    assert "FlowKit is not installed" in result.warning


def test_get_fcs_parameters_warns_when_flowkit_loading_fails(monkeypatch):
    fake_flowkit = types.SimpleNamespace(
        Sample=lambda _path: (_ for _ in ()).throw(RuntimeError("bad fcs"))
    )
    monkeypatch.setitem(sys.modules, "flowkit", fake_flowkit)

    result = get_fcs_parameters("sample.fcs")

    assert result.parameters == set()
    assert "Could not load FCS file" in result.warning


def test_get_fcs_parameters_returns_parameter_names_from_flowkit_sample(monkeypatch):
    class FakeSample:
        pnn_labels = ["FSC-A", " CD8-A ", ""]

    fake_flowkit = types.SimpleNamespace(Sample=lambda _path: FakeSample())
    monkeypatch.setitem(sys.modules, "flowkit", fake_flowkit)

    result = get_fcs_parameters("sample.fcs")

    assert result.warning is None
    assert result.parameters == {"FSC-A", "CD8-A"}


def test_get_fcs_parameters_warns_when_flowkit_finds_no_parameters(monkeypatch):
    class FakeSample:
        pnn_labels = []

    fake_flowkit = types.SimpleNamespace(Sample=lambda _path: FakeSample())
    monkeypatch.setitem(sys.modules, "flowkit", fake_flowkit)

    result = get_fcs_parameters("sample.fcs")

    assert result.parameters == set()
    assert "no parameter names" in result.warning


def test_extract_parameter_names_supports_channels_attribute():
    sample = types.SimpleNamespace(channels=["FSC-A", "SSC-A"])

    assert _extract_parameter_names(sample) == {"FSC-A", "SSC-A"}


def test_extract_parameter_names_supports_get_channel_info_dataframe():
    class FakeSample:
        def get_channel_info(self):
            return pd.DataFrame({"pnn": ["FSC-A", None, "CD8-A"]})

    assert _extract_parameter_names(FakeSample()) == {"FSC-A", "CD8-A"}


def test_extract_parameter_names_returns_empty_set_for_unknown_sample_shape():
    assert _extract_parameter_names(types.SimpleNamespace()) == set()
