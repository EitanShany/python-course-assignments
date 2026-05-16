# Day 5 Assignment - Tumor Volume Growth Analysis

This project analyzes longitudinal tumor-volume measurements from a mouse
experiment. The input is an Excel workbook with tumor-volume measurements over
time, split by treatment group.

## Assignment Goal

Find an interesting lab data file, design a useful analysis for it, and
implement the analysis with code, tests, documentation, and required packages.

## Input

The expected input is an Excel workbook with these sheets:

### `TV`

The first row may contain a title. The second row should contain the real
headers.

Required columns:

- `Group`
- `mouse`
- Day columns such as `0`, `3`, `6`, `9`, `12`

Example:

| Group | mouse | 0 | 3 | 6 | 9 | 12 |
|---|---:|---:|---:|---:|---:|---:|
| A | 1 | 100 | 120 | 150 | 180 | 220 |
| A | 2 | 90 | 100 | 130 | 160 | 210 |
| B | 3 | 100 | 95 | 110 | 120 | 130 |

### `experiment data`

This sheet is optional. Supported fields:

| Parameter | Value |
|---|---|
| Control group | A |
| Responder threshold | 50 |
| Excluded mice | 28, 30 |

## Analysis

For each group and each time point, the program calculates:

- Mean tumor volume
- Standard deviation
- Number of mice
- SEM: standard error of the mean

Responder definition:

```text
Responder = mouse with final tumor volume increase <= 50% from Day 0
```

Percent growth:

```text
((Final TV - Day 0 TV) / Day 0 TV) * 100
```

The final tumor volume is the last available measurement for that mouse.

## Missing Data Rules

1. Day 0 is required for responder classification.
2. Missing values in the middle of the experiment are skipped.
3. If a mouse has no data after a certain day, the last available measurement is used as final TV.
4. The final measured day is recorded.
5. Missing Day 0 creates an entry in the `Errors` sheet, but the program continues.

## Output

The program writes these files to the selected output folder:

```text
tumor_growth_results.xlsx
mean_tumor_volume_sem.png
responder_percentage_by_group.png
```

The Excel report contains:

- `General_Summary`
- `Mouse_Growth`
- `Response_Summary`
- `Responder_TV_Summary`
- `Errors`

## Command Line Usage

From inside the `Day05` folder:

```bash
python tumor_growth_analysis.py Input/TV_template.xlsx --output-dir Output
```

From the repository root:

```bash
python python-course-assignments/Day05/tumor_growth_analysis.py python-course-assignments/Day05/Input/TV_template.xlsx --output-dir python-course-assignments/Day05/Output
```

## GUI Usage

Run:

```bash
python gui_tumor_growth_analysis.py
```

The GUI allows selecting an Excel input file, selecting an output folder, and
running the analysis. Drag and drop is available when `tkinterdnd2` is installed.

## Install Requirements

```bash
pip install -r requirements.txt
```

## Run Tests

From inside the `Day05` folder:

```bash
pytest
```

From the repository root:

```bash
python -m pytest python-course-assignments/Day05 -q
```
