from pathlib import Path

import pandas as pd

from .results import SAMPLE_LEVEL_RESULT_COLUMNS


FLOWJO_REQUIRED_NORMALIZED_COLUMNS = [
    "Sample_ID",
    "Population",
    "Count",
    "Percent_of_Parent",
]

FLOWJO_COLUMN_ALIASES = {
    "Sample_ID": ["Sample_ID", "Sample ID", "Sample", "Name"],
    "FCS_File": ["FCS_File", "FCS File", "File", "File Name", "Filename"],
    "Population": ["Population", "Population_Name", "Population Name", "Gate", "Gate_Name", "Gate Name"],
    "Parent_Population": ["Parent_Population", "Parent Population", "Parent", "Parent_Gate", "Parent Gate"],
    "Count": ["Count", "Events", "Event Count", "#Events", "Num Events"],
    "Percent_of_Parent": [
        "Percent_of_Parent",
        "Percent Parent",
        "%Parent",
        "% Parent",
        "Frequency",
        "Freq. of Parent",
    ],
    "Percent_of_Total": ["Percent_of_Total", "Percent Total", "%Total", "% Total", "Freq. of Total"],
}


def load_flowjo_results(flowjo_path: str | Path) -> pd.DataFrame:
    """Load a FlowJo statistics export and return the project sample-level schema."""
    raw_df = _read_flowjo_table(flowjo_path)
    normalized = normalize_flowjo_results(raw_df)
    return convert_flowjo_to_sample_level_results(normalized)


def normalize_flowjo_results(flowjo_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize common FlowJo export column names into one schema."""
    if flowjo_df.empty:
        return pd.DataFrame(columns=[*FLOWJO_REQUIRED_NORMALIZED_COLUMNS, "FCS_File", "Parent_Population"])

    renamed_columns = {}
    for normalized_name, aliases in FLOWJO_COLUMN_ALIASES.items():
        source_column = _find_column(flowjo_df, aliases)
        if source_column is not None:
            renamed_columns[source_column] = normalized_name

    normalized = flowjo_df.rename(columns=renamed_columns).copy()
    missing_columns = [
        column for column in FLOWJO_REQUIRED_NORMALIZED_COLUMNS if column not in normalized.columns
    ]
    if missing_columns:
        missing_text = ", ".join(missing_columns)
        raise ValueError(f"FlowJo export is missing required column(s): {missing_text}")

    if "FCS_File" not in normalized.columns:
        normalized["FCS_File"] = ""
    if "Parent_Population" not in normalized.columns:
        normalized["Parent_Population"] = ""
    if "Percent_of_Total" not in normalized.columns:
        normalized["Percent_of_Total"] = pd.NA

    return normalized


def convert_flowjo_to_sample_level_results(flowjo_df: pd.DataFrame) -> pd.DataFrame:
    """Convert normalized FlowJo statistics to sample_level_results.csv schema."""
    rows: list[dict[str, object]] = []

    for _, row in flowjo_df.iterrows():
        sample_id = str(row.get("Sample_ID", "")).strip()
        population = str(row.get("Population", "")).strip()
        parent_population = str(row.get("Parent_Population", "")).strip()

        if not sample_id or not population:
            continue

        rows.append(
            {
                "Sample_ID": sample_id,
                "FCS_File": str(row.get("FCS_File", "")).strip(),
                "Search_ID": "FlowJo",
                "Starting_Population": parent_population,
                "Exploratory_Path": population,
                "Count": _to_numeric_or_na(row.get("Count")),
                "Percent_of_Parent": _to_numeric_or_na(row.get("Percent_of_Parent")),
                "Result_Type": "FlowJo",
            }
        )

    return pd.DataFrame(rows, columns=SAMPLE_LEVEL_RESULT_COLUMNS)


def _read_flowjo_table(flowjo_path: str | Path) -> pd.DataFrame:
    path = Path(flowjo_path)
    if not path.exists():
        raise FileNotFoundError(f"FlowJo export file was not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path)
    if suffix in {".tsv", ".txt"}:
        return pd.read_csv(path, sep="\t")

    raise ValueError("FlowJo export must be .csv, .tsv, .txt, .xlsx, .xlsm, or .xls")


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    normalized_columns = {_normalize_name(column): column for column in df.columns}
    for alias in aliases:
        column = normalized_columns.get(_normalize_name(alias))
        if column is not None:
            return column
    return None


def _normalize_name(value: object) -> str:
    return str(value).strip().replace("_", "").replace(" ", "").casefold()


def _to_numeric_or_na(value: object) -> object:
    numeric_value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric_value):
        return pd.NA
    return numeric_value
