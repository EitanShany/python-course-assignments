"""
Tumor Volume Growth Analysis
----------------------------
Reads an Excel file with longitudinal tumor-volume measurements, calculates
summary statistics by group and day, classifies mice as responders or
non-responders, and writes an Excel report plus graphs.

Expected input structure:
- Sheet "TV"
  - Row 1 can contain a title.
  - Row 2 contains headers: Group, mouse, 0, 3, 6, 9, 12, ...
  - Each row after that represents one mouse.

- Sheet "experiment data"
  - Can include fields such as:
    Control group | A
    Responder threshold | 50
    Excluded mice | 28, 30

Responder definition:
Responder = mouse with final tumor volume increase <= 50% from Day 0.
Final tumor volume is the last available measurement for that mouse.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Iterable

import pandas as pd


TV_SHEET = "TV"
EXPERIMENT_DATA_SHEET = "experiment data"
DEFAULT_RESPONDER_THRESHOLD = 50.0
BASELINE_DAY = 0


class TumorGrowthError(Exception):
    """Custom error for tumor growth analysis problems."""


def standard_error_of_mean(values: Iterable[float]) -> float:
    """Calculate SEM using sample standard deviation.

    Returns 0.0 when there is only one value, because there is no variation
    between animals to estimate.
    """
    clean_values = pd.Series(list(values)).dropna()
    n = len(clean_values)

    if n == 0:
        return math.nan
    if n == 1:
        return 0.0

    return clean_values.std(ddof=1) / math.sqrt(n)


def classify_response(percent_growth: float, threshold: float = DEFAULT_RESPONDER_THRESHOLD) -> str:
    """Classify one mouse as Responder or Non-responder."""
    if pd.isna(percent_growth):
        return "Unclassified"
    if percent_growth <= threshold:
        return "Responder"
    return "Non-responder"


def normalize_mouse_id(value):
    """Normalize mouse IDs so 28 and 28.0 are treated the same."""
    if pd.isna(value):
        return None
    try:
        numeric = float(value)
        if numeric.is_integer():
            return int(numeric)
        return numeric
    except (TypeError, ValueError):
        return str(value).strip()


def parse_day_column(column_name) -> int | None:
    """Return day number from a measurement column name.

    Supports columns named 0, 3, 6 or strings like 'Day 3'.
    Non-day columns return None.
    """
    if isinstance(column_name, (int, float)) and not pd.isna(column_name):
        return int(column_name)

    text = str(column_name).strip().lower().replace("day", "").strip()
    if text.lstrip("-").isdigit():
        return int(text)

    return None


def find_day_columns(df: pd.DataFrame) -> dict:
    """Find all day-measurement columns and return {day: column_name}."""
    day_columns = {}
    for column in df.columns:
        day = parse_day_column(column)
        if day is not None:
            day_columns[day] = column

    if BASELINE_DAY not in day_columns:
        raise TumorGrowthError("Missing required Day 0 column in the TV sheet.")

    return dict(sorted(day_columns.items()))


def read_experiment_data(input_file: str | Path) -> dict:
    """Read optional experiment metadata from the experiment data sheet.

    The function is intentionally flexible. It searches for known parameter
    names instead of requiring a strict table structure.
    """
    metadata = {
        "control_group": None,
        "responder_threshold": DEFAULT_RESPONDER_THRESHOLD,
        "excluded_mice": set(),
    }

    try:
        raw = pd.read_excel(input_file, sheet_name=EXPERIMENT_DATA_SHEET, header=None)
    except ValueError:
        return metadata

    for _, row in raw.iterrows():
        first_cell = row.iloc[0]
        if pd.isna(first_cell):
            continue

        key = str(first_cell).strip().lower()
        values = [cell for cell in row.iloc[1:].tolist() if not pd.isna(cell)]

        if "control" in key and "group" in key and values:
            metadata["control_group"] = str(values[0]).strip()

        if "responder" in key and "threshold" in key and values:
            metadata["responder_threshold"] = float(values[0])

        if "exclude" in key or "excluded" in key:
            excluded = []
            for value in values:
                if isinstance(value, str) and "," in value:
                    excluded.extend(part.strip() for part in value.split(","))
                else:
                    excluded.append(value)

            metadata["excluded_mice"] = {
                normalize_mouse_id(mouse) for mouse in excluded
            }

    return metadata


def read_tv_data(input_file: str | Path) -> tuple[pd.DataFrame, dict, dict]:
    """Read and clean the TV sheet.

    Returns:
    - cleaned TV dataframe
    - day column mapping {day: column_name}
    - metadata dictionary
    """
    metadata = read_experiment_data(input_file)

    # header=1 because the template has a title in row 1 and real headers in row 2.
    df = pd.read_excel(input_file, sheet_name=TV_SHEET, header=1)

    required_columns = {"Group", "mouse"}
    missing = required_columns.difference(df.columns)
    if missing:
        raise TumorGrowthError(
            f"Missing required columns in TV sheet: {sorted(missing)}"
        )

    df = df.dropna(subset=["Group", "mouse"], how="any").copy()
    df["mouse"] = df["mouse"].apply(normalize_mouse_id)
    df["Group"] = df["Group"].astype(str).str.strip()

    excluded_mice = metadata["excluded_mice"]
    if excluded_mice:
        df = df[~df["mouse"].isin(excluded_mice)].copy()

    day_columns = find_day_columns(df)

    for column in day_columns.values():
        df[column] = pd.to_numeric(df[column], errors="coerce")

    return df, day_columns, metadata


def create_long_table(df: pd.DataFrame, day_columns: dict) -> pd.DataFrame:
    """Convert TV data from wide format to long format."""
    long_rows = []

    for _, row in df.iterrows():
        for day, column in day_columns.items():
            tv = row[column]
            if pd.isna(tv):
                continue

            long_rows.append(
                {
                    "Group": row["Group"],
                    "Mouse": row["mouse"],
                    "Day": day,
                    "Tumor Volume": float(tv),
                }
            )

    return pd.DataFrame(long_rows)


def calculate_general_summary(long_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Mean, SD, n and SEM for each group at each time point."""
    if long_df.empty:
        return pd.DataFrame(columns=["Group", "Day", "Mean TV", "SD", "n", "SEM"])

    summary = (
        long_df.groupby(["Group", "Day"])["Tumor Volume"]
        .agg(
            **{
                "Mean TV": "mean",
                "SD": lambda values: values.std(ddof=1)
                if len(values.dropna()) > 1
                else 0.0,
                "n": "count",
                "SEM": standard_error_of_mean,
            }
        )
        .reset_index()
        .sort_values(["Group", "Day"])
    )

    return summary


def calculate_mouse_growth(
    df: pd.DataFrame,
    day_columns: dict,
    threshold: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate per-mouse growth and responder status.

    Day 0 is required for classification. Missing intermediate values are allowed.
    Final TV is the last available measurement for that mouse.
    """
    results = []
    errors = []
    baseline_column = day_columns[BASELINE_DAY]

    for _, row in df.iterrows():
        group = row["Group"]
        mouse = row["mouse"]
        baseline_tv = row[baseline_column]

        if pd.isna(baseline_tv):
            errors.append(
                {
                    "Group": group,
                    "Mouse": mouse,
                    "Issue": "Missing Day 0 value. Mouse cannot be classified.",
                }
            )
            continue

        available_measurements = []
        for day, column in day_columns.items():
            tv = row[column]
            if not pd.isna(tv):
                available_measurements.append((day, float(tv)))

        post_baseline_measurements = [
            (day, tv) for day, tv in available_measurements if day != BASELINE_DAY
        ]

        if not post_baseline_measurements:
            errors.append(
                {
                    "Group": group,
                    "Mouse": mouse,
                    "Issue": "No post-baseline measurements. Mouse cannot be classified.",
                }
            )
            continue

        final_day, final_tv = max(available_measurements, key=lambda item: item[0])
        change = final_tv - float(baseline_tv)
        percent_growth = (change / float(baseline_tv)) * 100
        response = classify_response(percent_growth, threshold)

        results.append(
            {
                "Group": group,
                "Mouse": mouse,
                "Initial TV": float(baseline_tv),
                "Final TV": final_tv,
                "Final Day": final_day,
                "Change": change,
                "Percent Growth": percent_growth,
                "Response": response,
            }
        )

    return pd.DataFrame(results), pd.DataFrame(errors)


def calculate_response_summary(mouse_growth: pd.DataFrame) -> pd.DataFrame:
    """Calculate responder counts and percentages by group."""
    if mouse_growth.empty:
        return pd.DataFrame(
            columns=["Group", "Responders", "Non-responders", "Total", "Responder %"]
        )

    counts = (
        mouse_growth.pivot_table(
            index="Group",
            columns="Response",
            values="Mouse",
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
    )

    if "Responder" not in counts.columns:
        counts["Responder"] = 0
    if "Non-responder" not in counts.columns:
        counts["Non-responder"] = 0

    counts["Total"] = counts["Responder"] + counts["Non-responder"]
    counts["Responder %"] = (counts["Responder"] / counts["Total"] * 100).round(2)

    return counts.rename(
        columns={
            "Responder": "Responders",
            "Non-responder": "Non-responders",
        }
    )[["Group", "Responders", "Non-responders", "Total", "Responder %"]]


def calculate_responder_tv_summary(
    long_df: pd.DataFrame,
    mouse_growth: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate Mean, SD, n and SEM by Group, Response and Day."""
    if long_df.empty or mouse_growth.empty:
        return pd.DataFrame(
            columns=["Group", "Response", "Day", "Mean TV", "SD", "n", "SEM"]
        )

    response_map = mouse_growth[["Group", "Mouse", "Response"]]
    merged = long_df.merge(response_map, on=["Group", "Mouse"], how="inner")

    summary = (
        merged.groupby(["Group", "Response", "Day"])["Tumor Volume"]
        .agg(
            **{
                "Mean TV": "mean",
                "SD": lambda values: values.std(ddof=1)
                if len(values.dropna()) > 1
                else 0.0,
                "n": "count",
                "SEM": standard_error_of_mean,
            }
        )
        .reset_index()
        .sort_values(["Group", "Response", "Day"])
    )

    return summary


def plot_mean_tv_sem(summary: pd.DataFrame, output_path: str | Path) -> None:
    """Create line graph of Mean Tumor Volume ± SEM by group."""
    if summary.empty:
        return

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.figure(figsize=(8, 5))

    for group, group_df in summary.groupby("Group"):
        group_df = group_df.sort_values("Day")
        plt.errorbar(
            group_df["Day"],
            group_df["Mean TV"],
            yerr=group_df["SEM"],
            marker="o",
            capsize=4,
            label=f"Group {group}",
        )

    plt.xlabel("Day")
    plt.ylabel("Mean Tumor Volume (mm³)")
    plt.title("Mean Tumor Volume ± SEM")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def plot_responder_percentage(
    response_summary: pd.DataFrame,
    output_path: str | Path,
) -> None:
    """Create bar graph of responder percentage by group."""
    if response_summary.empty:
        return

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.figure(figsize=(7, 5))
    plt.bar(response_summary["Group"], response_summary["Responder %"])
    plt.xlabel("Group")
    plt.ylabel("Responders (%)")
    plt.title("Responder Percentage by Group")
    plt.ylim(0, 120)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def write_excel_report(
    output_excel: str | Path,
    general_summary: pd.DataFrame,
    mouse_growth: pd.DataFrame,
    response_summary: pd.DataFrame,
    responder_tv_summary: pd.DataFrame,
    errors: pd.DataFrame,
) -> None:
    """Write analysis output into an Excel workbook with separate sheets."""
    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        general_summary.to_excel(writer, sheet_name="General_Summary", index=False)
        mouse_growth.to_excel(writer, sheet_name="Mouse_Growth", index=False)
        response_summary.to_excel(writer, sheet_name="Response_Summary", index=False)
        responder_tv_summary.to_excel(
            writer,
            sheet_name="Responder_TV_Summary",
            index=False,
        )

        if errors.empty:
            errors = pd.DataFrame([{"Issue": "No errors found."}])

        errors.to_excel(writer, sheet_name="Errors", index=False)


def analyze_tumor_growth(
    input_file: str | Path,
    output_dir: str | Path = "output",
) -> dict:
    """Run the full tumor growth analysis workflow."""
    input_file = Path(input_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df, day_columns, metadata = read_tv_data(input_file)
    threshold = metadata["responder_threshold"]

    long_df = create_long_table(df, day_columns)
    general_summary = calculate_general_summary(long_df)
    mouse_growth, errors = calculate_mouse_growth(df, day_columns, threshold)
    response_summary = calculate_response_summary(mouse_growth)
    responder_tv_summary = calculate_responder_tv_summary(long_df, mouse_growth)

    output_excel = output_dir / "tumor_growth_results.xlsx"
    mean_tv_graph = output_dir / "mean_tumor_volume_sem.png"
    responder_graph = output_dir / "responder_percentage_by_group.png"

    write_excel_report(
        output_excel,
        general_summary,
        mouse_growth,
        response_summary,
        responder_tv_summary,
        errors,
    )

    plot_mean_tv_sem(general_summary, mean_tv_graph)
    plot_responder_percentage(response_summary, responder_graph)

    return {
        "output_excel": output_excel,
        "mean_tv_graph": mean_tv_graph,
        "responder_graph": responder_graph,
        "num_mice_analyzed": len(mouse_growth),
        "num_errors": 0 if errors.empty else len(errors),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze tumor volume growth data from Excel."
    )
    parser.add_argument("input_file", help="Path to the input Excel file")
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for output files",
    )
    args = parser.parse_args()

    results = analyze_tumor_growth(args.input_file, args.output_dir)

    print("Analysis completed.")
    print(f"Excel report: {results['output_excel']}")
    print(f"Mean TV graph: {results['mean_tv_graph']}")
    print(f"Responder graph: {results['responder_graph']}")
    print(f"Mice analyzed: {results['num_mice_analyzed']}")
    print(f"Errors/warnings: {results['num_errors']}")


if __name__ == "__main__":
    main()
