import pandas as pd

import pytest

from immunoflow_discovery_analyzer.fcs_scanner import (
    match_fcs_to_plate_map,
    scan_fcs_folder,
    scan_fcs_files,
)


def test_scan_fcs_files_returns_file_name_and_path_without_reading_content(tmp_path):
    fcs_file = tmp_path / "sample1.fcs"
    fcs_file.write_text("this content should not be parsed", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")

    files = scan_fcs_files(tmp_path)

    assert files == [
        {
            "file_name": "sample1.fcs",
            "file_path": str(fcs_file),
        }
    ]


def test_scan_fcs_files_is_case_insensitive_for_extension(tmp_path):
    upper_case_file = tmp_path / "sample2.FCS"
    upper_case_file.write_text("content is ignored", encoding="utf-8")

    files = scan_fcs_files(tmp_path)

    assert files[0]["file_name"] == "sample2.FCS"


def test_scan_fcs_files_raises_when_folder_is_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="FCS folder was not found"):
        scan_fcs_files(tmp_path / "missing")


def test_scan_fcs_files_raises_when_path_is_not_directory(tmp_path):
    file_path = tmp_path / "sample.fcs"
    file_path.write_text("not a folder", encoding="utf-8")

    with pytest.raises(NotADirectoryError, match="FCS path is not a folder"):
        scan_fcs_files(file_path)


def test_scan_fcs_folder_wrapper_calls_scan_fcs_files(tmp_path):
    fcs_file = tmp_path / "sample1.fcs"
    fcs_file.write_text("content is ignored", encoding="utf-8")

    files = scan_fcs_folder(tmp_path)

    assert files[0]["file_name"] == "sample1.fcs"


def test_match_fcs_to_plate_map_returns_matched_missing_and_extra_files():
    plate_map = pd.DataFrame(
        [
            {"Sample_ID": "S1", "FCS_File": "sample1.fcs"},
            {"Sample_ID": "S2", "FCS_File": "sample2.fcs"},
        ]
    )
    fcs_files = pd.DataFrame(
        [
            {"file_name": "SAMPLE1.FCS", "file_path": "data/SAMPLE1.FCS"},
            {"file_name": "extra.fcs", "file_path": "data/extra.fcs"},
        ]
    )

    matched, missing, extra = match_fcs_to_plate_map(plate_map, fcs_files)

    assert matched["Sample_ID"].tolist() == ["S1"]
    assert matched["file_path"].tolist() == ["data/SAMPLE1.FCS"]
    assert missing["FCS_File"].tolist() == ["sample2.fcs"]
    assert extra["file_name"].tolist() == ["extra.fcs"]


def test_match_fcs_to_plate_map_accepts_scanner_list_output():
    plate_map = pd.DataFrame([{"Sample_ID": "S1", "FCS_File": "sample1.fcs"}])
    fcs_files = [{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}]

    matched, missing, extra = match_fcs_to_plate_map(plate_map, fcs_files)

    assert len(matched) == 1
    assert missing.empty
    assert extra.empty


def test_match_fcs_to_plate_map_handles_empty_fcs_scan():
    plate_map = pd.DataFrame([{"Sample_ID": "S1", "FCS_File": "sample1.fcs"}])

    matched, missing, extra = match_fcs_to_plate_map(plate_map, [])

    assert matched.empty
    assert missing["FCS_File"].tolist() == ["sample1.fcs"]
    assert missing["plate_map_row"].tolist() == [2]
    assert extra.empty


def test_match_fcs_to_plate_map_raises_when_plate_map_fcs_column_missing():
    plate_map = pd.DataFrame([{"Sample_ID": "S1"}])
    fcs_files = [{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}]

    with pytest.raises(ValueError, match="FCS_File column"):
        match_fcs_to_plate_map(plate_map, fcs_files)


def test_match_fcs_to_plate_map_raises_when_fcs_table_columns_missing():
    plate_map = pd.DataFrame([{"Sample_ID": "S1", "FCS_File": "sample1.fcs"}])
    fcs_files = pd.DataFrame([{"file_name": "sample1.fcs"}])

    with pytest.raises(ValueError, match="file_path"):
        match_fcs_to_plate_map(plate_map, fcs_files)
