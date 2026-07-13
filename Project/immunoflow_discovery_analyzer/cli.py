import argparse
from pathlib import Path

from .excel_loader import load_workbook_sheets
from .exploratory import create_mock_exploratory_report
from .export import (
    export_analysis_workbook,
    export_exploratory_report,
    export_qc_report,
    export_sample_level_results,
)
from .fcs_scanner import scan_fcs_files
from .flowjo_loader import load_flowjo_results
from .qc import run_basic_qc
from .results import create_mock_sample_level_results
from .simple_analysis import analyze_fcs_samples, compare_treatment_pairs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ImmunoFlow Discovery Analyzer")
    parser.add_argument("--fcs-dir", required=True, type=Path, help="Folder containing .fcs files")
    parser.add_argument("--excel", required=True, type=Path, help="Experiment-definition Excel workbook")
    parser.add_argument("--output-dir", required=True, type=Path, help="Folder for output reports")
    parser.add_argument(
        "--flowjo-export",
        type=Path,
        help="Optional FlowJo statistics export (.csv, .tsv, .txt, or Excel).",
    )
    parser.add_argument(
        "--analyze-fcs",
        action="store_true",
        help="Read FCS event data and export simple Python analysis reports.",
    )
    parser.add_argument(
        "--gate-marker",
        default="CD20",
        help="Marker used for the simple high-marker gate when --analyze-fcs is set.",
    )
    parser.add_argument(
        "--signal-marker",
        default="pS6",
        help="Marker summarized inside the simple gate when --analyze-fcs is set.",
    )
    parser.add_argument(
        "--gate-percentile",
        default=75.0,
        type=float,
        help="Percentile threshold for the high-marker gate when --analyze-fcs is set.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    sheets = load_workbook_sheets(args.excel)
    fcs_files = scan_fcs_files(args.fcs_dir)
    exploratory_report = create_mock_exploratory_report(
        sheets["Exploratory_Search"],
        sheets["Marker_Gates"],
    )
    if args.flowjo_export:
        sample_level_results = load_flowjo_results(args.flowjo_export)
    else:
        sample_level_results = create_mock_sample_level_results(
            sheets["Plate_Map"],
            exploratory_report,
        )

    qc_report = run_basic_qc(sheets, fcs_files, flowjo_results_df=sample_level_results if args.flowjo_export else None)
    qc_report_path = export_qc_report(qc_report, args.output_dir)
    exploratory_report_path = export_exploratory_report(exploratory_report, args.output_dir)
    sample_level_results_path = export_sample_level_results(sample_level_results, args.output_dir)
    analysis_output_paths = {}
    if args.analyze_fcs:
        fcs_sample_metrics = analyze_fcs_samples(
            args.fcs_dir,
            sheets["Plate_Map"],
            gate_marker=args.gate_marker,
            signal_marker=args.signal_marker,
            gate_percentile=args.gate_percentile,
        )
        fcs_group_comparison = compare_treatment_pairs(
            fcs_sample_metrics,
            signal_marker=args.signal_marker,
            gate_marker=args.gate_marker,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        sample_metrics_path = args.output_dir / "fcs_sample_metrics.csv"
        group_comparison_path = args.output_dir / "fcs_group_comparison.csv"
        fcs_sample_metrics.to_csv(sample_metrics_path, index=False)
        fcs_group_comparison.to_csv(group_comparison_path, index=False)
        analysis_output_paths = {
            "sample_metrics": sample_metrics_path,
            "group_comparison": group_comparison_path,
        }

    analysis_workbook_path = export_analysis_workbook(
        args.output_dir,
        qc_report,
        exploratory_report,
    )

    print("ImmunoFlow Discovery Analyzer")
    print(f"FCS directory: {args.fcs_dir}")
    print(f"Excel workbook: {args.excel}")
    if args.flowjo_export:
        print(f"FlowJo export: {args.flowjo_export}")
    print(f"Output directory: {args.output_dir}")
    print(f"QC report: {qc_report_path}")
    print(f"Exploratory report: {exploratory_report_path}")
    print(f"Sample-level results: {sample_level_results_path}")
    if args.analyze_fcs:
        print(f"FCS sample metrics: {analysis_output_paths['sample_metrics']}")
        print(f"FCS group comparison: {analysis_output_paths['group_comparison']}")
    print(f"Analysis workbook: {analysis_workbook_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
