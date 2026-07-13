# AGENTS.md

## General Instructions

- Answer in Hebrew unless the user asks otherwise.
- Explain code changes briefly and clearly.
- Do not make large structural changes unless necessary.
- Prefer simple beginner-friendly Python code.
- Keep existing file names and folder structure unless asked.
- Do not add external libraries unless they are clearly needed; explain why before adding one.
- For Python projects, update `requirements.txt` when dependencies change.
- When relevant, suggest how to run the code and tests on Windows using PowerShell.
- Do not implement real FlowKit gating until explicitly requested.

## QA Review Requirement

Before finishing code changes in this project, perform a QA review over the code that was written or affected.

The QA review should include:

1. Code simplicity and cleanup
   - Check whether there are unnecessary, duplicated, or overly complicated code sections.
   - Simplify code when it improves readability without changing behavior.
   - Remove dead code only when it is clearly unused and safe to remove.
   - Consider edge cases before changing logic, so cleanup does not break unusual but valid inputs.

2. Edge-case handling
   - Check empty inputs, missing columns, missing sheets, missing files, duplicated values, and unexpected data types.
   - Prefer returning clear validation/QC messages instead of crashing when the problem is user input or experiment data.
   - Keep errors explicit when continuing would hide a serious programming or configuration problem.

3. Security and data validation
   - Validate user-provided paths, workbook content, file names, and external data before using them.
   - Do not hard-code secrets, tokens, private URLs, or personal credentials.
   - Do not print or save sensitive information unless explicitly approved.
   - Do not open, execute, import, or download unknown files without checking the expected type and purpose.
   - Keep external integrations optional and fail safely when unavailable.

4. Bug check
   - Look for mismatched column names, stale function names, wrong return types, off-by-one row numbers, and inconsistent output schemas.
   - Check that new functions are covered by tests for normal behavior and at least one relevant edge case.
   - Confirm that CLI behavior still matches the documented command.

5. Tests
   - Run the test suite before the final response:

```powershell
pytest
```

   - If tests cannot be run, explain clearly why and what remains unverified.

## Final Response After QA

When reporting completion, mention:

- What changed.
- Which QA checks were performed.
- The test command that was run.
- Whether tests passed.
