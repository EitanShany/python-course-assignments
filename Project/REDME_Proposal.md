# ImmunoFlow Discovery Analyzer

A Python-based analysis tool for structured and exploratory analysis of conventional and spectral flow cytometry experiments in preclinical immuno-oncology research.

Flow cytometry experiments can produce large numbers of FCS files containing multi-marker immune-cell measurements. In preclinical immuno-oncology studies, these data are often analyzed through repeated manual steps: associating files with samples and treatments, applying a gating strategy, extracting cell-population frequencies, comparing treatment groups, reviewing quality issues, and searching for biologically interesting changes that were not part of the initial hypothesis.

This project aims to build a reusable analysis tool that combines FCS files with a structured Excel experiment-definition workbook. The tool will support standardized hypothesis-driven analysis and a systematic downstream exploratory search for unexpected treatment-associated immune phenotypes, beginning only from user-defined approved parent populations.

The primary intended use case is analysis of tumor-infiltrating immune-cell data generated in preclinical studies, including experiments acquired on a Beckman Coulter CytoFLEX instrument equipped with a CytoFLEX mosaic Spectral Detection Module.

---

## Scientific and Practical Motivation

A typical immuno-oncology flow cytometry experiment may ask a predefined question, such as whether a treatment increases the frequency of CD8 effector-phenotype cells in tumor, spleen, or lymph-node samples. However, modern high-parameter panels can contain additional information that is not fully explored when the analysis is restricted only to the originally selected gates.

The central goal of this project is therefore to separate the analysis into two clearly defined stages:

1. **Closed, predefined analysis** — a validated gating sequence is applied to establish reliable parent populations, for example:

   `Cells → Singlets → Live → CD45+ → CD3+ → CD4+ / CD8+`

2. **Systematic downstream exploratory analysis from a defined branching point** — after an approved parent population has been reached, the tool evaluates all downstream marker-defined paths that can be generated from the available phenotype-marker gates in the panel, including paths not explicitly listed in the Excel workbook. For example, within `CD8+` cells with downstream gates for `CD44`, `PD-1`, and `TIM-3`, the search may include:

   * `CD44+`
   * `CD44-`
   * `PD-1+ TIM-3+`
   * `CD44+ PD-1+ TIM-3+`
   * `CD44- PD-1+ TIM-3-`

This design allows unexpected candidate findings to be identified without changing upstream biological definitions or requiring the user to specify each downstream path in advance. The available downstream paths are determined from the panel markers and their predefined positivity gates, while expert review remains essential. Exploratory findings will be reported as candidates for follow-up and not as confirmed biological conclusions.

---

## Main Objectives

The tool will be designed to:

* Load FCS files from a flow cytometry experiment.
* Read a structured Excel workbook describing the experiment, panel, plate layout, treatment groups, preprocessing status, gating workflow, and exploratory-analysis settings.
* Support both conventional flow cytometry data and spectral flow cytometry data that have already been processed for downstream analysis.
* Apply a predefined gating workflow up to approved parent populations.
* Quantify planned populations and compare treatment groups.
* Perform a systematic exploratory search of all marker-defined downstream paths from approved parent populations, including paths not listed in advance in the Excel workbook.
* Generate quantitative summaries, visual outputs, and quality-control warnings.
* Record sufficient analysis provenance to make the output understandable and reproducible later.

---

## Scope of the First Implementation

### Included in the first implementation

The first version is intended to support:

* Conventional compensated FCS files.
* Spectral FCS files exported after spectral unmixing.
* One experimental Excel workbook per analysis run.
* A 96-well plate map linking samples, FCS files, subjects, and treatment groups.
* Panel definition linking FCS parameters, fluorophores, and biological markers.
* A predefined gating workflow defining the closed analysis portion.
* Approved exploratory parent populations such as `CD8+` and/or `CD4+`.
* User-defined exploratory starting populations, such as `CD8+` and/or `CD4+`, from which downstream discovery begins.
* Positivity gates for downstream phenotype markers present in the panel.
* Systematic testing of all downstream marker-defined paths available after each selected starting population, subject to quality-control and statistical-reporting rules.
* Sample-level and group-level output tables.
* Basic treatment-group plots and plate-based visual summaries.
* Quality-control flags for missing files, missing required parameters, inappropriate preprocessing status, low event counts, and other input inconsistencies.
* Clear separation between pre-planned results and exploratory candidate findings.

### Outside the first implementation scope

The first version will not attempt to:

* Perform spectral unmixing from raw spectral detector data.
* Replace acquisition software or fully replace expert flow cytometry analysis software.
* Automatically determine the biologically correct upstream gating workflow.
* Produce definitive biological interpretations of exploratory findings.
* Perform exploratory searches upstream of the approved parent population or alter the predefined closed gating workflow.
* Implement fully unsupervised clustering or dimensionality-reduction discovery as a required feature.

These functions may be considered future extensions after the primary analysis workflow has been implemented and validated.

---

## Supported Flow Cytometry Data Types

### Conventional flow cytometry

For conventional experiments, the expected input will be FCS files that are already compensated, or files for which an appropriate preprocessing reference has been provided according to the final implemented workflow.

### Spectral flow cytometry

For spectral experiments, such as experiments acquired using the CytoFLEX platform with the CytoFLEX mosaic Spectral Detection Module, the first version will accept **unmixed FCS files** exported after spectral processing in the acquisition software.

Spectral unmixing is considered a critical preprocessing step and will remain outside the first implementation scope. The Excel workbook will record information such as:

* acquisition mode;
* preprocessing status;
* software used for export/unmixing;
* unmixing algorithm, if known;
* autofluorescence extraction status, if known;
* availability of relevant controls or preprocessing records.

---

## Input Data

The project will use two major input sources:

### 1. FCS files

A folder containing one FCS file per analyzed sample or well. Supported input files for the first version will be:

* compensated conventional FCS files; or
* unmixed spectral FCS files.

### 2. Excel experiment-definition workbook

The user will provide an Excel workbook using a defined template. The initial template includes the following worksheets:

| Worksheet                | Purpose                                                                                               |
| ------------------------ | ----------------------------------------------------------------------------------------------------- |
| `Instructions`           | Explains how to prepare the input workbook.                                                           |
| `Experiment_Info`        | Describes the experiment, tissue, biological question, and general notes.                             |
| `Acquisition_Processing` | Records instrument, acquisition mode, software, and compensation/unmixing status.                     |
| `Panel_Definition`       | Links FCS parameters to fluorophores, biological markers, and their analysis roles.                   |
| `Plate_Map`              | Maps each 96-well position to sample ID, FCS file, subject, treatment group, and tissue.              |
| `Plate_Layout`           | Visual representation of the 96-well plate.                                                           |
| `Controls`               | Records unstained, single-stain, FMO, or other relevant controls.                                     |
| `Gating_Workflow`        | Defines the closed validated gating path and approved exploratory parent populations.                 |
| `Marker_Gates`           | Defines downstream marker positivity/negativity gates from which exploratory paths are generated.     |
| `Exploratory_Search`     | Defines approved branching points, comparison groups, QC thresholds, and statistical reporting rules. |
| `Planned_Comparisons`    | Defines the primary or secondary planned biological comparisons.                                      |
| `Expected_Outputs`       | Documents the intended output categories of the tool.                                                 |

---

## Analysis Workflow

### Stage 1: Input validation and quality control

The tool will check that:

* the required Excel worksheets exist;
* every included plate-map sample has a corresponding FCS file;
* every required gating marker is present in the data;
* the declared acquisition and preprocessing status are compatible with the input;
* spectral data are marked as unmixed before downstream analysis;
* relevant sample metadata and treatment assignments are available;
* samples with very low event counts or other predefined concerns are flagged for review.

### Stage 2: Closed predefined gating analysis

A predefined gating workflow will be applied to generate validated biological parent populations. An example workflow is:

`All Events → Cells → Singlets → Live → CD45+ → CD3+ → CD4+ / CD8+`

This portion is considered closed analysis: the tool will not search for alternative upstream definitions automatically. Its purpose is to ensure that the downstream exploratory phase begins only from populations defined by an approved biological workflow.

### Stage 3: Planned treatment-group analysis

The tool will quantify predefined outcomes, for example:

* frequency of `CD8+` cells within `CD3+` cells;
* frequency of `CD44+` cells within `CD8+` cells;
* frequency of a predefined effector-phenotype population;
* other selected outcomes declared in the `Planned_Comparisons` worksheet.

These results represent the hypothesis-driven part of the analysis.

### Stage 4: Systematic downstream exploratory phenotype search

The distinguishing feature of this project will be a structured search for candidate findings after an approved parent population has been reached.

The Excel workbook will define the **starting population** for discovery, for example `CD8+`, rather than requiring the user to list every downstream path to test. Once the search begins, the tool will use the downstream marker gates available in the panel to generate and compare all marker-defined paths that can be evaluated from that starting point.

For example, if the approved branching point is `CD8+` and the panel contains defined downstream positivity gates for `CD44`, `PD-1`, and `TIM-3`, the search may examine branches such as:

* `CD8+ → CD44+`;
* `CD8+ → CD44-`;
* `CD8+ → PD-1+ → TIM-3+`;
* `CD8+ → CD44+ → PD-1+ → TIM-3+`;
* `CD8+ → CD44- → PD-1+ → TIM-3-`;
* additional downstream paths generated from the same available marker gates.

The tool will not search upstream of the approved branching point and will not redefine the closed gating workflow. The exploratory search will be governed by user-defined reporting and QC settings, including:

* approved exploratory starting population;
* minimum event count required for reporting a candidate population;
* treatment groups to compare;
* reference group;
* statistical multiple-testing-control method, where implemented;
* rules for ranking or filtering candidate findings in the output.

Marker positivity/negativity definitions must be supplied through validated gates or other predefined analysis settings; the tool will search new downstream paths, but will not choose marker cutoffs based on which result appears most significant.

Any candidate result identified in this stage will be explicitly labelled as **exploratory** and will require expert review and biological validation.

---

## Expected Outputs

The tool is expected to generate a structured analysis output containing the following components:

### 1. Quality-control report

A report identifying input or analysis concerns, such as:

* missing FCS files;
* missing panel parameters;
* incompatible acquisition or preprocessing settings;
* unusually low event counts;
* unexpectedly low viability or other review flags;
* exploratory populations below the reporting threshold.

### 2. Sample-level population table

A table containing event counts and percentages for each analyzed population in every sample, including both planned populations and, where applicable, exploratory candidate phenotypes.

### 3. Treatment-group summary table

A table summarizing relevant populations across treatment groups, while distinguishing between:

* primary planned outcomes;
* secondary planned outcomes; and
* exploratory candidate findings.

### 4. Visual results

Possible first-version visual outputs include:

* plots comparing selected populations between treatment groups;
* a plate-based visualization displaying a selected result across the 96-well layout;
* an exploratory-candidate summary plot or ranked results table;
* QC-related visual summaries when useful.

### 5. Analysis provenance record

A summary recording important analysis details, including:

* instrument and acquisition mode;
* conventional compensation or spectral unmixing status;
* preprocessing software information supplied by the user;
* gating workflow version;
* exploratory settings applied;
* date of analysis output generation.

---

## Example Use Case

A researcher performs a tumor-infiltrating leukocyte experiment comparing `Vehicle` and `Treatment X` groups. The planned analysis asks whether `Treatment X` changes the frequency of CD8 effector-phenotype cells.

The user supplies:

* unmixed FCS files exported from a spectral flow cytometry experiment;
* the Excel experiment-definition workbook;
* a validated gating workflow ending in `CD4+` and `CD8+` parent populations;
* an exploratory-search definition identifying `CD8+` as an approved downstream discovery starting population.

The tool performs the planned analysis and reports whether the predefined CD8 effector-phenotype result differs between groups. In parallel, it generates and compares all downstream marker-defined CD8 paths available from the panel gates, and may identify a candidate observation such as an altered `PD-1+ TIM-3+` fraction that was not originally listed as a primary result or as a requested analysis path.

That result will be reported as an exploratory candidate for review rather than as a confirmed mechanism of treatment action.

---

## Planned Technical Approach

The detailed implementation will be finalized after feasibility testing with representative FCS files. The planned technical direction is:

* Python as the primary programming language.
* FlowKit as the primary candidate library for loading FCS data and applying structured gating workflows.
* An Excel-based experiment-definition template for user-provided metadata and analysis settings.
* Export of analysis summaries and visual outputs in user-friendly formats.
* Automated tests for input validation, mapping of samples to treatments, analysis-phase separation, and output logic.

Additional libraries will be selected only after confirming the final implementation requirements.

---

## Installation and Running the Project

The project is currently in the proposal stage. Once implementation begins, this section will be updated with exact commands for:

* cloning the repository;
* creating a Python environment;
* installing dependencies;
* running the analysis tool;
* running automated tests;
* preparing example input data.

Planned usage will involve selecting or providing:

1. a folder containing FCS files; and
2. a completed Excel experiment-definition workbook based on the supplied template.

---

## Testing Plan

The implemented project will include tests designed to verify that:

* required worksheets and fields are identified correctly;
* missing FCS files are reported;
* samples are correctly associated with treatment groups and plate wells;
* unsupported raw spectral input is flagged rather than analyzed incorrectly;
* closed gating and exploratory analysis remain separated according to the configured workflow;
* exploratory searching begins only from approved parent populations;
* all downstream marker-defined paths expected from the configured panel gates are evaluated without requiring each path to be listed manually;
* low-event candidate populations are flagged or excluded from reporting according to the configured threshold;
* planned and exploratory results are labelled distinctly in outputs.

Where possible, representative anonymized or synthetic input files will be included for demonstration and testing purposes.

---

## Future Extensions

Possible future extensions include:

* a graphical user interface for selecting input files and configuring an experiment;
* automated generation of a final PDF report;
* support for additional plate formats;
* more advanced exploratory visualizations and scalable strategies for panels in which exhaustive downstream path generation produces a very large number of candidate populations;
* clustering-based discovery approaches for high-dimensional panels;
* dimensionality-reduction visualizations such as UMAP;
* integration of additional QC metrics;
* support for broader experimental designs and multiple panels.

These extensions are intentionally separated from the first implementation so that the initial tool remains feasible, testable, and scientifically interpretable.

---

## Repository Contents During the Proposal Stage

The proposal-stage repository is expected to contain:

```text
ImmunoFlow-Discovery-Analyzer/
├── README.md
├── example_data/
│   └── ImmunoFlow_Discovery_Analyzer_Input_Template.xlsx
└── images/
    └── optional_workflow_diagram.png
```

The repository structure will expand during implementation.

---

## Course Context

This project is being proposed as a final project for the Python programming course. Once the project repository is created, a link to the course repository will be added here as requested in the project instructions.
