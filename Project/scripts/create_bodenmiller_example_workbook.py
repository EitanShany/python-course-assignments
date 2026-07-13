from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from immunoflow_discovery_analyzer.config import REQUIRED_EXCEL_SHEETS


DATASET_NAME = "Bodenmiller_BCR_XL"


def main() -> None:
    dataset_dir = PROJECT_ROOT / "example_data" / "bodenmiller_bcr_xl"
    fcs_dir = dataset_dir / "fcs"
    manifest_path = dataset_dir / "manifest.csv"
    workbook_path = dataset_dir / "template.xlsx"

    fcs_files = sorted(fcs_dir.glob("*.fcs"))
    if not fcs_files:
        raise FileNotFoundError(f"No FCS files found in: {fcs_dir}")
    if manifest_path.exists() or workbook_path.exists():
        raise FileExistsError("Refusing to overwrite existing manifest.csv or template.xlsx.")

    manifest = build_manifest(fcs_files)
    panel = build_panel_definition(fcs_files[0])
    workbook = build_workbook(manifest, panel)

    manifest.to_csv(manifest_path, index=False)
    with pd.ExcelWriter(workbook_path) as writer:
        for sheet_name in REQUIRED_EXCEL_SHEETS:
            workbook[sheet_name].to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"Created manifest: {manifest_path}")
    print(f"Created workbook: {workbook_path}")


def build_manifest(fcs_files: list[Path]) -> pd.DataFrame:
    rows = []
    for index, fcs_file in enumerate(fcs_files, start=1):
        patient_id, treatment = parse_bodenmiller_file_name(fcs_file.name)
        rows.append(
            {
                "Well": f"A{index:02d}",
                "Sample_ID": f"{patient_id}_{treatment}",
                "Subject_ID": patient_id,
                "Treatment": treatment,
                "Tissue": "PBMC",
                "Replicate": 1,
                "FCS_File": fcs_file.name,
            }
        )
    return pd.DataFrame(rows)


def parse_bodenmiller_file_name(file_name: str) -> tuple[str, str]:
    if not file_name.lower().endswith(".fcs"):
        raise ValueError(f"Expected an FCS file name: {file_name}")

    stem = file_name[:-4]
    parts = stem.split("_")
    if len(parts) < 4 or not parts[-2].startswith("patient"):
        raise ValueError(f"Unexpected Bodenmiller file name: {file_name}")

    patient_id = parts[-2]
    treatment = parts[-1]
    if treatment not in {"Reference", "BCR-XL"}:
        raise ValueError(f"Unexpected treatment group in file name: {file_name}")
    return patient_id, treatment


def build_panel_definition(fcs_file: Path) -> pd.DataFrame:
    metadata = read_fcs_text_metadata(fcs_file)
    parameter_count = int(metadata["$PAR"])
    rows = []

    for index in range(1, parameter_count + 1):
        parameter_name = metadata.get(f"$P{index}N", "")
        marker_name = metadata.get(f"$P{index}S", parameter_name)
        if not parameter_name:
            continue
        rows.append(
            {
                "Parameter_in_FCS": parameter_name,
                "Fluorophore": "",
                "Marker": marker_name,
                "Marker_role": marker_role(marker_name),
            }
        )

    return pd.DataFrame(rows)


def read_fcs_text_metadata(fcs_file: Path) -> dict[str, str]:
    data = fcs_file.read_bytes()
    if data[:6] not in {b"FCS3.0", b"FCS3.1"}:
        raise ValueError(f"Unexpected FCS header in: {fcs_file}")

    header = data[:58].decode("ascii", errors="replace")
    text_start = int(header[10:18])
    text_end = int(header[18:26])
    text = data[text_start : text_end + 1].decode("latin1", errors="replace")
    delimiter = text[0]
    parts = text[1:].split(delimiter)
    return dict(zip(parts[0::2], parts[1::2]))


def marker_role(marker_name: str) -> str:
    functional_markers = {
        "pNFkB",
        "pp38",
        "pStat5",
        "pAkt",
        "pStat1",
        "pSHP2",
        "pZap70",
        "pStat3",
        "pSlp76",
        "pBtk",
        "pPlcg2",
        "pErk",
        "pLat",
        "pS6",
    }
    if marker_name in functional_markers:
        return "Functional"
    if marker_name in {"Time", "Cell_length", "Event_length", "DNA1", "DNA2", "cisplatin"}:
        return "QC"
    return "Lineage"


def build_workbook(manifest: pd.DataFrame, panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "Experiment_Info": pd.DataFrame(
            [
                {"Key": "Experiment_ID", "Value": DATASET_NAME},
                {"Key": "Source", "Value": "HDCytoData / Bodenmiller et al. 2012"},
                {"Key": "Description", "Value": "PBMC Reference vs BCR-XL stimulated paired samples"},
            ]
        ),
        "Acquisition_Processing": pd.DataFrame(
            [{"Acquisition_Mode": "CyTOF", "Transformation": "None in source FCS"}]
        ),
        "Panel_Definition": panel,
        "Plate_Map": manifest,
        "Gating_Workflow": pd.DataFrame(
            [
                {
                    "Gate_Name": "B_cells",
                    "Parent_Gate": "Live_cells",
                    "Gate_Type": "manual_or_flowjo",
                    "X_Parameter": "CD20",
                    "Y_Parameter": "",
                    "Analysis_Role": "Exploratory",
                }
            ]
        ),
        "Marker_Gates": pd.DataFrame(
            [
                {
                    "Marker": "pS6",
                    "Positive_Gate_Name": "pS6_high",
                    "Negative_Gate_Name": "pS6_low",
                    "Parent_Population": "B_cells",
                    "Gate_Source": "template",
                }
            ]
        ),
        "Exploratory_Search": pd.DataFrame(
            [
                {
                    "Search_ID": "BCRXL_vs_reference",
                    "Starting_Population": "B_cells",
                    "Compare_Groups": "BCR-XL vs Reference",
                    "Reference_Group": "Reference",
                    "Minimum_Events": 100,
                }
            ]
        ),
        "Planned_Comparisons": pd.DataFrame(
            [
                {
                    "Comparison_ID": "BCRXL_pS6_B_cells",
                    "Population": "B_cells",
                    "Parent_Population": "Live_cells",
                    "Treatment_Group": "BCR-XL",
                    "Reference_Group": "Reference",
                    "Metric": "pS6 median expression",
                }
            ]
        ),
    }


if __name__ == "__main__":
    main()
