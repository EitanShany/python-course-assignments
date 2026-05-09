# Project Description

In the previous version of the project, I created a Python function called calculate_tumor_volume in the file tumor_volume.py.

This function calculates the tumor volume for a single pair of measurements: length and width.

As an improvement, I created an additional Python script called tumor_volume_excel.py.

This new script applies the same tumor volume calculation to a full list of measurements from an Excel file, instead of calculating only one mouse at a time.

Files in This Project
tumor_volume.py

This file contains the basic function for calculating tumor volume from one length value and one width value.

The function also checks for invalid input, such as:

Non-numeric values
Width greater than length
tumor_volume_excel.py

This file reads an Excel file that contains tumor measurements.

The Excel file should include the following columns:

L for length
W for width

The script calculates the tumor volume for each row and creates a new Excel file with the calculated results.

If an error is found in a specific row, for example if the width is greater than the length, the script does not stop. Instead, it writes an error message in the output file and continues processing the rest of the rows.

This makes the code more useful for working with real experimental data, where some rows may contain mistakes.

test_tumor_volume_Excel.py

This file contains unit tests for the basic tumor volume calculation function.

The tests check:

Normal values
Equal length and width values
Decimal values
Invalid input such as text instead of numbers
Cases where width is greater than length
test_excel_tumor_volume.py

This file contains tests for the Excel-processing code.

The tests check that:

The Excel file is processed correctly
Tumor volume values are calculated correctly
A new output Excel file is created
The original Excel file is not overwritten
Rows with errors are marked properly
The code continues running even when one or more rows contain errors
requirements.txt

## I use ChatGPT as web to wright the code and as Codex in VC code to fix problem and make change