import os

import pandas as pd
import pytest

from tumor_volume_excel import process_excel_file


def test_excel_file_is_processed_correctly(excel_temp_dir):
    """
    Test that the code reads an Excel file,
    calculates T.V. correctly,
    and creates a new output Excel file.
    """

    input_file = excel_temp_dir / "Measurements.xlsx"

    test_data = pd.DataFrame({
        "Mouse ID": [1, 2, 3],
        "L": [10, 6, 10.5],
        "W": [5, 6, 5.2]
    })

    test_data.to_excel(input_file, index=False)

    output_file = process_excel_file(input_file)

    assert os.path.exists(output_file)

    result_data = pd.read_excel(output_file)

    assert "T.V." in result_data.columns

    assert result_data.loc[0, "T.V."] == 125
    assert result_data.loc[1, "T.V."] == 108
    assert result_data.loc[2, "T.V."] == pytest.approx(141.96)


def test_excel_file_marks_error_when_width_is_greater_than_length(excel_temp_dir):
    """
    Test that when W > L, the code does not stop.
    Instead, it marks the problematic row with an error message.
    """

    input_file = excel_temp_dir / "Measurements.xlsx"

    test_data = pd.DataFrame({
        "Mouse ID": [1, 2, 3],
        "L": [10, 5, 8],
        "W": [5, 10, 4]
    })

    test_data.to_excel(input_file, index=False)

    output_file = process_excel_file(input_file)

    assert os.path.exists(output_file)

    result_data = pd.read_excel(output_file)

    assert "T.V." in result_data.columns
    assert "Error" in result_data.columns

    assert result_data.loc[0, "T.V."] == 125
    assert result_data.loc[2, "T.V."] == 64

    assert (
        pd.isna(result_data.loc[1, "T.V."])
        or result_data.loc[1, "T.V."] == ""
    )

    assert "Width cannot be greater than length" in str(result_data.loc[1, "Error"])


def test_original_excel_file_is_not_overwritten(excel_temp_dir):
    """
    Test that the original Excel file remains unchanged
    and the result is saved to a new file.
    """

    input_file = excel_temp_dir / "Measurements.xlsx"

    test_data = pd.DataFrame({
        "Mouse ID": [1],
        "L": [10],
        "W": [5]
    })

    test_data.to_excel(input_file, index=False)

    output_file = process_excel_file(input_file)

    assert input_file != output_file
    assert os.path.exists(input_file)
    assert os.path.exists(output_file)

    original_data = pd.read_excel(input_file)
    result_data = pd.read_excel(output_file)

    assert "T.V." not in original_data.columns
    assert "T.V." in result_data.columns


def test_output_file_name_contains_TV_suffix(excel_temp_dir):
    """
    Test that the new file name includes '_TV',
    for example Measurements.xlsx -> Measurements_TV.xlsx.
    """

    input_file = excel_temp_dir / "Measurements.xlsx"

    test_data = pd.DataFrame({
        "Mouse ID": [1],
        "L": [10],
        "W": [5]
    })

    test_data.to_excel(input_file, index=False)

    output_file = process_excel_file(input_file)

    assert str(output_file).endswith("_TV.xlsx")
