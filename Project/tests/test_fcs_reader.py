import pandas as pd
import pytest

from immunoflow_discovery_analyzer.fcs_reader import read_fcs_events, read_fcs_metadata

from fcs_test_helpers import write_test_fcs


def test_read_fcs_metadata_returns_text_keywords(tmp_path):
    fcs_path = tmp_path / "sample.fcs"
    write_test_fcs(fcs_path, ["CD20", "pS6"], [[1.0, 2.0]])

    metadata = read_fcs_metadata(fcs_path)

    assert metadata["$PAR"] == "2"
    assert metadata["$TOT"] == "1"
    assert metadata["$P1S"] == "CD20"


def test_read_fcs_events_returns_dataframe(tmp_path):
    fcs_path = tmp_path / "sample.fcs"
    write_test_fcs(
        fcs_path,
        ["CD20", "pS6"],
        [
            [1.0, 2.0],
            [3.0, 4.0],
        ],
    )

    events = read_fcs_events(fcs_path)

    expected = pd.DataFrame({"CD20": [1.0, 3.0], "pS6": [2.0, 4.0]})
    pd.testing.assert_frame_equal(events, expected)


def test_read_fcs_events_accepts_data_end_equal_to_file_size(tmp_path):
    fcs_path = tmp_path / "sample.fcs"
    write_test_fcs(fcs_path, ["CD20"], [[1.0]])
    data = bytearray(fcs_path.read_bytes())
    data_end = int(data[34:42].decode("ascii")) + 1
    data[34:42] = f"{data_end:>8}".encode("ascii")
    fcs_path.write_bytes(data)

    events = read_fcs_events(fcs_path)

    assert events.loc[0, "CD20"] == 1.0


def test_read_fcs_events_rejects_non_fcs_file(tmp_path):
    text_path = tmp_path / "sample.txt"
    text_path.write_text("not fcs", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected an .fcs file"):
        read_fcs_events(text_path)
