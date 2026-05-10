# Day 03 - Tumor Volume Calculator

## Description

This project calculates subcutaneous tumor volume in mice using the formula:

Tumor Volume = (width^2 * length) / 2

The calculation logic was moved into a separate module so it can be reused by different versions of the program.

## Files

- `tumor_volume.py` - contains the shared calculation function.
- `input_version.py` - gets length and width from the user using the `input()` function.
- `argv_version.py` - gets length and width from command line arguments using `sys.argv`.
- `gui_version.py` - provides a graphical user interface using `tkinter`.
- `test_tumor_volume.py` - contains tests for the calculation function.

## How to run the input version

```bash
py input_version.py