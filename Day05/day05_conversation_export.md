# Day 5 Assignment — Conversation Export

## Original assignment

Find one or more interesting files in the lab, current or previous.  
Come up with a useful analysis for the data and implement it.

Input files can be Excel, CSV, image, FASTA, etc.  
Output can be numbers, graphs, Excel files, etc.

If the data is private, create a copy with fake but reasonable values.

In the `day05` folder, provide:

- Input files
- Code that runs the analysis
- Tests that verify the program
- README.md
- requirements.txt if needed

---

## Project selected

**Tumor Volume Growth Analysis**

The input file is an Excel workbook with longitudinal tumor-volume measurements from a mouse experiment.

The analysis uses a tumor-volume table over time, divided by treatment group.

---

## Main analysis

For each treatment group and each time point, calculate:

- Mean tumor volume
- Standard deviation
- Number of mice
- SEM: standard error of the mean

The main graph should show:

```text
Mean Tumor Volume ± SEM
```

---

## Responder analysis

Responder definition agreed in the conversation:

```text
Responder = mouse with final tumor volume increase <= 50% from Day 0
```

Percent growth:

```text
((Final TV - Day 0 TV) / Day 0 TV) * 100
```

The final tumor volume is the last available tumor-volume measurement for that mouse.

This allows the code to handle mice that stop having measurements after a certain day.

---

## Missing data rules

1. Day 0 is required.
2. Missing values in the middle of the experiment are skipped.
3. If a mouse has no data after a certain day, the last available measurement is used as final TV.
4. The final measured day is recorded.
5. Responder status is calculated from Day 0 to the last available measurement.
6. Missing Day 0 creates a warning/error entry, but the program continues.
7. No need to add notes, death reasons, or detailed exclusion reasons at this stage.

---

## Expected Excel structure

### Sheet 1: `TV`

The first row may contain a title.  
The second row should contain the real headers.

Example:

| Group | mouse | 0 | 3 | 6 | 9 | 12 |
|---|---:|---:|---:|---:|---:|---:|
| A | 1 | 100 | 120 | 150 | 180 | 220 |
| A | 2 | 90 | 100 | 130 | 160 | 210 |
| B | 3 | 100 | 95 | 110 | 120 | 130 |

### Sheet 2: `experiment data`

Optional fields:

| Parameter | Value |
|---|---|
| Control group | A |
| Responder threshold | 50 |
| Excluded mice | 28, 30 |

---

## Output files

The program creates an `output` folder and saves:

```text
tumor_growth_results.xlsx
mean_tumor_volume_sem.png
responder_percentage_by_group.png
```

The Excel report contains these sheets:

- `General_Summary`
- `Mouse_Growth`
- `Response_Summary`
- `Responder_TV_Summary`
- `Errors`

---

## Suggested folder structure

```text
day05/
│
├── input/
│   └── TV_template.xlsx
│
├── output/
│   ├── tumor_growth_results.xlsx
│   ├── mean_tumor_volume_sem.png
│   └── responder_percentage_by_group.png
│
├── tumor_growth_analysis.py
├── gui_tumor_growth_analysis.py
├── test_tumor_growth_analysis.py
├── requirements.txt
└── README.md
```

---

## Command line usage

From inside the `day05` folder:

```bash
python tumor_growth_analysis.py input/TV_template.xlsx --output-dir output
```

If running from the parent folder:

```bash
python day05/tumor_growth_analysis.py day05/input/TV_template.xlsx --output-dir day05/output
```

---

## GUI usage

A separate GUI launcher was added:

```text
day05/gui_tumor_growth_analysis.py
```

Run it with:

```bash
python gui_tumor_growth_analysis.py
```

The GUI allows:

1. Typing or pasting the Excel input path.
2. Selecting the Excel file using Browse.
3. Selecting an output folder.
4. Running the analysis.
5. Optional drag and drop if `tkinterdnd2` is installed.

---

## requirements.txt

```text
pandas
openpyxl
matplotlib
pytest
tkinterdnd2
```

---

## Running tests

From the `day05` folder:

```bash
pytest
```

The tests should cover:

- SEM calculation
- Responder classification
- Missing Day 0 error
- General summary statistics
- Response summary

---

## Important project decisions

- Keep the project focused on code that analyzes data.
- Do not overload the input file with unnecessary notes or biological metadata.
- Use `Errors` sheet for missing Day 0 and other classification problems.
- Keep GUI code separate from the core analysis code.
- The code should continue running even if one mouse has a problem.
- The responder analysis should be in a separate output sheet from the general analysis.

---

## Files created in the conversation

The conversation produced content for these files:

```text
day05/tumor_growth_analysis.py
day05/gui_tumor_growth_analysis.py
day05/test_tumor_growth_analysis.py
day05/requirements.txt
day05/README.md
```

The full code was written in the canvas during the conversation. This export summarizes the full project decisions and structure so the project can be recreated or reviewed in VS Code/Codex.
