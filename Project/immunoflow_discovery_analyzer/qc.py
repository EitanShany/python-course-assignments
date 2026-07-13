import pandas as pd

from .config import REQUIRED_COLUMNS, REQUIRED_EXCEL_SHEETS
from .fcs_scanner import match_fcs_to_plate_map
from .flowkit_adapter import get_fcs_parameters

QC_COLUMNS = ["Severity", "Check", "Message", "Affected_Item"]


def run_basic_qc(
    sheets: dict[str, pd.DataFrame],
    fcs_files_df: pd.DataFrame | list[dict[str, str]],
    flowjo_results_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Run basic workbook and FCS-file QC checks."""
    rows: list[dict[str, str]] = []

    _check_required_sheets(sheets, rows)
    _check_required_columns(sheets, rows)

    plate_map = sheets.get("Plate_Map")
    if plate_map is not None and "FCS_File" in plate_map.columns:
        _check_fcs_file_matching(plate_map, fcs_files_df, rows)
        _check_required_fcs_parameters(
            plate_map,
            sheets.get("Panel_Definition", pd.DataFrame()),
            fcs_files_df,
            rows,
        )
        _check_missing_values(plate_map, "Treatment", "Missing_Treatment", rows)
        _check_missing_values(plate_map, "Sample_ID", "Missing_Sample_ID", rows)
        _check_duplicates(plate_map, "Well", "Duplicate_Well", rows)
        _check_duplicates(plate_map, "Sample_ID", "Duplicate_Sample_ID", rows)

    acquisition = sheets.get("Acquisition_Processing")
    if acquisition is not None:
        _check_spectral_unmixed(acquisition, rows)

    if flowjo_results_df is not None:
        _check_flowjo_results(sheets.get("Plate_Map", pd.DataFrame()), flowjo_results_df, rows)

    return pd.DataFrame(rows, columns=QC_COLUMNS)


def run_qc_checks(
    workbook: dict[str, pd.DataFrame],
    fcs_files: pd.DataFrame | list[dict[str, str]],
) -> list[str]:
    """Backward-compatible wrapper that returns QC messages only."""
    report = run_basic_qc(workbook, fcs_files)
    return report["Message"].tolist()


def _check_flowjo_results(
    plate_map: pd.DataFrame,
    flowjo_results: pd.DataFrame,
    rows: list[dict[str, str]],
) -> None:
    if flowjo_results.empty:
        _add_row(
            rows,
            "WARNING",
            "FlowJo_Results_Empty",
            "FlowJo export was loaded but did not contain usable sample-level rows.",
            "FlowJo export",
        )
        return

    if "Sample_ID" in plate_map.columns:
        expected_samples = _clean_value_set(plate_map["Sample_ID"])
        observed_samples = _clean_value_set(flowjo_results["Sample_ID"])

        for sample_id in sorted(expected_samples - observed_samples):
            _add_row(
                rows,
                "WARNING",
                "Missing_FlowJo_Result",
                f"Sample is listed in Plate_Map but has no FlowJo result: {sample_id}",
                sample_id,
            )

        for sample_id in sorted(observed_samples - expected_samples):
            _add_row(
                rows,
                "WARNING",
                "Extra_FlowJo_Result",
                f"FlowJo result has a sample not listed in Plate_Map: {sample_id}",
                sample_id,
            )

    duplicate_mask = flowjo_results.duplicated(subset=["Sample_ID", "Exploratory_Path"], keep=False)
    duplicate_rows = flowjo_results[duplicate_mask]
    for _, row in duplicate_rows.drop_duplicates(subset=["Sample_ID", "Exploratory_Path"]).iterrows():
        _add_row(
            rows,
            "ERROR",
            "Duplicate_FlowJo_Result",
            "Duplicate FlowJo result for Sample_ID and population/path.",
            f"{row['Sample_ID']}:{row['Exploratory_Path']}",
        )

    _check_numeric_flowjo_column(flowjo_results, "Count", rows, minimum=0)
    _check_numeric_flowjo_column(flowjo_results, "Percent_of_Parent", rows, minimum=0, maximum=100)


def _check_numeric_flowjo_column(
    flowjo_results: pd.DataFrame,
    column: str,
    rows: list[dict[str, str]],
    minimum: float,
    maximum: float | None = None,
) -> None:
    values = pd.to_numeric(flowjo_results[column], errors="coerce")
    invalid_mask = values.isna() | (values < minimum)
    if maximum is not None:
        invalid_mask = invalid_mask | (values > maximum)

    for row_index, row in flowjo_results[invalid_mask].iterrows():
        affected_item = f"{row.get('Sample_ID', f'row {row_index + 2}')}:{row.get('Exploratory_Path', column)}"
        _add_row(
            rows,
            "ERROR",
            f"Invalid_FlowJo_{column}",
            f"FlowJo {column} value is missing or outside the expected range.",
            affected_item,
        )


def _clean_value_set(values: pd.Series) -> set[str]:
    return {
        str(value).strip()
        for value in values.dropna()
        if str(value).strip()
    }


def _check_required_sheets(
    sheets: dict[str, pd.DataFrame],
    rows: list[dict[str, str]],
) -> None:
    for sheet_name in REQUIRED_EXCEL_SHEETS:
        if sheet_name not in sheets:
            _add_row(
                rows,
                "ERROR",
                "Missing_Required_Sheet",
                f"Missing required Excel sheet: {sheet_name}",
                sheet_name,
            )


def _check_required_columns(
    sheets: dict[str, pd.DataFrame],
    rows: list[dict[str, str]],
) -> None:
    for sheet_name, required_columns in REQUIRED_COLUMNS.items():
        if sheet_name not in sheets:
            continue

        existing_columns = set(sheets[sheet_name].columns)
        for column in required_columns:
            if column not in existing_columns:
                _add_row(
                    rows,
                    "ERROR",
                    "Missing_Required_Column",
                    f"{sheet_name} is missing required column: {column}",
                    f"{sheet_name}.{column}",
                )


def _check_fcs_file_matching(
    plate_map: pd.DataFrame,
    fcs_files_df: pd.DataFrame | list[dict[str, str]],
    rows: list[dict[str, str]],
) -> None:
    _matched, missing_files, extra_files = match_fcs_to_plate_map(plate_map, fcs_files_df)

    for _, row in missing_files.iterrows():
        _add_row(
            rows,
            "ERROR",
            "Missing_FCS_File",
            f"FCS file listed in Plate_Map was not found: {row['FCS_File']}",
            str(row["FCS_File"]),
        )

    for _, row in extra_files.iterrows():
        _add_row(
            rows,
            "WARNING",
            "Extra_FCS_File",
            f"FCS file found in folder but not listed in Plate_Map: {row['file_name']}",
            str(row["file_name"]),
        )


def _check_required_fcs_parameters(
    plate_map: pd.DataFrame,
    panel_definition: pd.DataFrame,
    fcs_files_df: pd.DataFrame | list[dict[str, str]],
    rows: list[dict[str, str]],
) -> None:
    if "Parameter_in_FCS" not in panel_definition.columns:
        return

    required_parameters = {
        str(value).strip()
        for value in panel_definition["Parameter_in_FCS"].dropna()
        if str(value).strip()
    }
    if not required_parameters:
        return

    matched_samples, _missing_files, _extra_files = match_fcs_to_plate_map(plate_map, fcs_files_df)
    for _, row in matched_samples.iterrows():
        result = get_fcs_parameters(row["file_path"])
        if result.warning:
            _add_row(
                rows,
                "WARNING",
                "FCS_Parameter_Check_Skipped",
                result.warning,
                str(row["file_name"]),
            )
            continue

        missing_parameters = sorted(required_parameters - result.parameters)
        for parameter in missing_parameters:
            _add_row(
                rows,
                "ERROR",
                "Missing_FCS_Parameter",
                f"Required FCS parameter was not found in {row['file_name']}: {parameter}",
                f"{row['file_name']}:{parameter}",
            )


def _check_missing_values(
    plate_map: pd.DataFrame,
    column: str,
    check_name: str,
    rows: list[dict[str, str]],
) -> None:
    if column not in plate_map.columns:
        return

    missing_mask = plate_map[column].isna() | (plate_map[column].astype(str).str.strip() == "")
    for row_index, row in plate_map[missing_mask].iterrows():
        affected_item = _row_affected_item(row, row_index)
        _add_row(
            rows,
            "ERROR",
            check_name,
            f"Plate_Map row {row_index + 2} is missing {column}.",
            affected_item,
        )


def _check_duplicates(
    plate_map: pd.DataFrame,
    column: str,
    check_name: str,
    rows: list[dict[str, str]],
) -> None:
    if column not in plate_map.columns:
        return

    values = plate_map[column].dropna().astype(str).str.strip()
    values = values[values != ""]
    duplicated_values = sorted(values[values.duplicated()].unique())

    for value in duplicated_values:
        _add_row(
            rows,
            "ERROR",
            check_name,
            f"Duplicate {column} value in Plate_Map: {value}",
            value,
        )


def _check_spectral_unmixed(
    acquisition: pd.DataFrame,
    rows: list[dict[str, str]],
) -> None:
    for row_index, row in acquisition.iterrows():
        mode = _first_existing_value(row, ["Acquisition_Mode", "Mode"])
        status = _first_existing_value(
            row,
            ["Preprocessing_Status", "Spectral_Unmixed", "Unmixed"],
        )

        if "spectral" in str(mode).strip().casefold() and str(status).strip().casefold() != "unmixed":
            _add_row(
                rows,
                "ERROR",
                "Spectral_Not_Unmixed",
                f"Acquisition_Processing row {row_index + 2} is spectral but preprocessing status is not Unmixed.",
                f"Acquisition_Processing row {row_index + 2}",
            )


def _first_existing_value(row: pd.Series, column_names: list[str]) -> object:
    for column in column_names:
        if column in row:
            return row[column]
    return ""


def _row_affected_item(row: pd.Series, row_index: int) -> str:
    sample_id = row.get("Sample_ID", "")
    if pd.notna(sample_id) and str(sample_id).strip():
        return str(sample_id).strip()
    return f"Plate_Map row {row_index + 2}"


def _add_row(
    rows: list[dict[str, str]],
    severity: str,
    check: str,
    message: str,
    affected_item: str,
) -> None:
    rows.append(
        {
            "Severity": severity,
            "Check": check,
            "Message": message,
            "Affected_Item": affected_item,
        }
    )
