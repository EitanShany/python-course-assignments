# Day06 - Cancer Target Antibody Search

This assignment searches for therapeutic antibodies against a cancer-related
target chosen by the user. The user can enter a target gene or antigen such as
`PD1`, `PDL1`, `EGFR`, `HER2`, `MUC16`, `CD276`, or `MSLN`. The program
downloads antibody data from an online database, processes the matching rows,
counts PubMed references for each antibody, ranks the results by literature
support, and saves a CSV or Excel table.

The search looks mainly in the Thera-SAbDab `Target` column. It also handles a
few common cancer-target aliases, for example `hEpCAM` matches `EPCAM/CD326`,
`5T4` matches `TPBG/WAIF1`, and `PD-1` matches `PD1/PDCD1/CD279`.
Before filtering the antibody table, the program also queries NCBI Gene with
Biopython and writes the aliases it found to `target_aliases.txt`. These
aliases are added to the search terms, which helps when a target is known by
more than one biological name. To avoid unrelated aliases, the code keeps only
NCBI Gene records that match the original query or the built-in cancer-target
alias list.

The final results are sorted by `pubmed_reference_count` from highest to
lowest, so antibodies with more literature support appear first.

## Data sources

The main database is **Thera-SAbDab**, a web-based database of therapeutic
antibodies maintained by the Oxford Protein Informatics Group. It contains
antibody names, targets, antibody formats, clinical-development stages,
approved/active/discontinued indications, and heavy/light variable-region
sequences when available.

The program also uses **PubMed** through **Biopython's `Bio.Entrez`** module.
For each antibody name, it searches PubMed and counts how many papers mention
that antibody in the title or abstract.

## Output table

The output CSV contains 11 columns that are useful for thinking about antibody
engineering and cancer targets:

1. `antibody_name`
2. `target_antigen_or_gene`
3. `target_category`
4. `cancer_indication`
5. `antibody_species_or_type`
6. `antibody_format`
7. `highest_clinical_trial`
8. `estimated_status`
9. `pubmed_reference_count`
10. `heavy_variable_region_sequence`
11. `light_variable_region_sequence`

## Code structure

The project was split into several files so that each file has a clear role:

- `data_sources.py` downloads Thera-SAbDab data and queries PubMed with
  Biopython. It also queries NCBI Gene for target aliases and can load local
  CSV/XLSX files.
- `antibody_processing.py` contains the filtering, classification, and
  CSV/Excel-writing functions.
- `antibody_search.py` is the command-line version of the program.
- `gui_antibody_search.py` is a Tkinter graphical user interface.
- `test_antibody_processing.py` contains pytest tests for the processing code.
- `requirements.txt` lists the required external packages.

## Installation

Install the required packages:

```bash
pip install -r Day06/requirements.txt
```

The required packages are:

- `biopython`
- `openpyxl`
- `pytest`

## Command-line use

Example search for antibodies against PD1:

```bash
python Day06/antibody_search.py --target PD1 --limit 10
```

This creates:

```text
antibody_results.csv
```

You can also choose a different output file:

```bash
python Day06/antibody_search.py --target EGFR --limit 20 --output egfr_antibodies.xlsx
```

Optional species/type filtering:

```bash
python Day06/antibody_search.py --target PD1 --species Human,Humanized
```

The built-in species/type filters are:

- `Human`
- `Humanized`
- `Mouse / murine`
- `Chimeric`
- `Unknown`

These built-in filters use exact matching. For example, `Human` does not also
match `Humanized`.

Optional local input file instead of downloading the table again:

```bash
python Day06/antibody_search.py --target 5T4 --input-file previous_results.xlsx
```

CSV input files are also supported:

```bash
python Day06/antibody_search.py --target EPCAM --input-file previous_results.csv
```

## GUI use

Run the graphical version:

```bash
python Day06/gui_antibody_search.py
```

The GUI lets the user enter a target, choose the number of results, view the
table, filter by antibody species/type using built-in options plus an `Other`
field, load a local CSV/XLSX file, and save the results as CSV or Excel.
The `Other` species/type field is useful for custom text filters that are not
included in the built-in options.

## Tests

Run the tests with pytest:

```bash
pytest Day06
```

The tests check the processing functions without depending on live internet
access. This makes the code easier to debug and more reliable.

## AI interaction

I used AI to help plan the project structure, choose suitable data sources, and
compare IEDB with antibody-focused databases. We decided that Thera-SAbDab is
better for antibody names, clinical status, and variable-region sequences,
while PubMed is useful for counting references. AI also helped split the code
into separate modules, add a GUI version, and write pytest tests.
