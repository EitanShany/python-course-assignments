# ImmunoFlow Discovery Analyzer

Initial Python project structure for validating an experiment workbook, scanning
mock FCS files, running simple QC checks, and generating exploratory marker paths.

FlowKit gating is not implemented yet.

## Current Implementation Status

- Excel validation works.
- FCS folder scanning works.
- QC report generation works.
- Exploratory path generation works.
- Real FCS gating is not implemented yet.
- FlowKit integration will be added later.

## Install

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
python -m immunoflow_discovery_analyzer `
  --fcs-dir path\to\fcs `
  --excel path\to\template.xlsx `
  --output-dir path\to\results
```

Optional FlowJo statistics export:

```powershell
python -m immunoflow_discovery_analyzer `
  --fcs-dir path\to\fcs `
  --excel path\to\template.xlsx `
  --flowjo-export path\to\flowjo_statistics.csv `
  --output-dir path\to\results
```

When `--flowjo-export` is provided, `sample_level_results.csv` is created from
the FlowJo table. Without it, the file is still generated with temporary mock
values.

## Test

```powershell
pytest
```
