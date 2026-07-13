from pathlib import Path

import pandas as pd

from .config import REQUIRED_COLUMNS, REQUIRED_EXCEL_SHEETS


def load_workbook_sheets(excel_path: str | Path) -> dict[str, pd.DataFrame]:
    """Load required sheets from the experiment-definition Excel workbook."""
    path = Path(excel_path)
    if not path.exists():
        raise FileNotFoundError(f"Excel workbook was not found: {path}")
    if path.suffix.lower() not in {".xlsx", ".xlsm", ".xls"}:
        raise ValueError("Excel workbook must be an .xlsx, .xlsm, or .xls file.")

    workbook = pd.read_excel(path, sheet_name=None)
    missing_sheets = [sheet for sheet in REQUIRED_EXCEL_SHEETS if sheet not in workbook]
    if missing_sheets:
        missing_text = ", ".join(missing_sheets)
        raise ValueError(f"Excel workbook is missing required sheet(s): {missing_text}")

    return {
        sheet_name: _clean_dataframe(workbook[sheet_name])
        for sheet_name in REQUIRED_EXCEL_SHEETS
    }


def load_excel_workbook(excel_path: str | Path) -> dict[str, pd.DataFrame]:
    """Backward-compatible wrapper for older code."""
    return load_workbook_sheets(excel_path)


def validate_excel_workbook(workbook: dict[str, pd.DataFrame]) -> list[str]:
    """Return validation messages for missing sheets and required columns."""
    messages: list[str] = []

    for sheet_name in REQUIRED_EXCEL_SHEETS:
        if sheet_name not in workbook:
            messages.append(f"ERROR: Missing required sheet: {sheet_name}")

    messages.extend(validate_required_columns(workbook))
    return messages


def validate_required_columns(sheets: dict[str, pd.DataFrame]) -> list[str]:
    """Return validation errors for missing required columns in loaded sheets."""
    errors: list[str] = []

    for sheet_name, required_columns in REQUIRED_COLUMNS.items():
        if sheet_name not in sheets:
            continue

        existing_columns = set(sheets[sheet_name].columns)
        for column in required_columns:
            if column not in existing_columns:
                errors.append(f"ERROR: {sheet_name} is missing required column: {column}")

    return errors


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [str(column).strip() for column in cleaned.columns]
    return cleaned.dropna(how="all").reset_index(drop=True)
