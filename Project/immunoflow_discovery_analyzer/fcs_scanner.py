from pathlib import Path

import pandas as pd


def scan_fcs_files(fcs_dir: str | Path) -> list[dict[str, str]]:
    """Return all .fcs files in a folder without reading file contents."""
    path = Path(fcs_dir)
    if not path.exists():
        raise FileNotFoundError(f"FCS folder was not found: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"FCS path is not a folder: {path}")

    fcs_files = []
    for file_path in sorted(path.iterdir()):
        if file_path.is_file() and file_path.suffix.lower() == ".fcs":
            fcs_files.append(
                {
                    "file_name": file_path.name,
                    "file_path": str(file_path),
                }
            )

    return fcs_files


def scan_fcs_folder(fcs_dir: str | Path) -> list[dict[str, str]]:
    """Backward-compatible wrapper for older code."""
    return scan_fcs_files(fcs_dir)


def match_fcs_to_plate_map(
    plate_map_df: pd.DataFrame,
    fcs_files_df: pd.DataFrame | list[dict[str, str]],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Match Plate_Map rows to scanned FCS files.

    Returns:
    1. matched samples
    2. missing files listed in Plate_Map but not found in the folder
    3. extra files found in the folder but not listed in Plate_Map
    """
    _validate_match_inputs(plate_map_df, fcs_files_df)

    fcs_df = _as_dataframe(fcs_files_df)
    plate_map = plate_map_df.copy()
    fcs_files = fcs_df.copy()

    plate_map["plate_map_row"] = plate_map.index + 2
    plate_map["_match_name"] = plate_map["FCS_File"].astype(str).str.strip().str.casefold()
    fcs_files["_match_name"] = fcs_files["file_name"].astype(str).str.strip().str.casefold()

    matched_samples = plate_map.merge(
        fcs_files[["file_name", "file_path", "_match_name"]],
        on="_match_name",
        how="inner",
    ).drop(columns=["_match_name"])

    missing_files = plate_map[
        ~plate_map["_match_name"].isin(fcs_files["_match_name"])
    ].drop(columns=["_match_name"])

    extra_files = fcs_files[
        ~fcs_files["_match_name"].isin(plate_map["_match_name"])
    ].drop(columns=["_match_name"])

    return (
        matched_samples.reset_index(drop=True),
        missing_files.reset_index(drop=True),
        extra_files.reset_index(drop=True),
    )


def _validate_match_inputs(
    plate_map_df: pd.DataFrame,
    fcs_files_df: pd.DataFrame | list[dict[str, str]],
) -> None:
    if "FCS_File" not in plate_map_df.columns:
        raise ValueError("Plate_Map must contain an FCS_File column.")

    fcs_df = _as_dataframe(fcs_files_df)
    required_columns = {"file_name", "file_path"}
    missing_columns = required_columns - set(fcs_df.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(f"FCS files table is missing required column(s): {missing_text}")


def _as_dataframe(data: pd.DataFrame | list[dict[str, str]]) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data
    return pd.DataFrame(data, columns=["file_name", "file_path"])
