# Internal Version 01

Internal name: `Day05 Tumor Growth Analysis - version 01`

Date saved: 2026-05-16

This version includes:

- Core tumor-growth analysis from Excel input
- Responder classification by final growth from Day 0
- Excel report output
- Mean tumor volume graph with SEM
- Responder percentage graph with Y axis from 0 to 120%
- Tkinter GUI launcher
- Pytest test coverage for core analysis functions
- README and requirements file

Validation at save time:

```text
python -m py_compile tumor_growth_analysis.py gui_tumor_growth_analysis.py
python -m pytest Day05 -q
9 passed
```
