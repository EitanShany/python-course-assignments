# AGENTS.md

## General instructions
- Answer in Hebrew unless I ask otherwise.
- Explain code changes briefly and clearly.
- Do not make large structural changes unless necessary.
- Prefer simple beginner-friendly Python code.
- When changing code, keep existing file names and folder structure unless asked.
- Before adding a new external library, explain why it is needed.
- For Python projects, include or update requirements.txt when dependencies change.
- When relevant, suggest how to run the code and tests on Windows using PowerShell.
- Before asking the author/user for approval to run code with elevated permissions,
   first review the relevant code or command. Check that it does not perform harmful
   actions on the computer, such as deleting unrelated files, changing system settings,
   exposing secrets, installing unexpected software, or sending unexpected data to
   external services. Ask for permission only after the command looks necessary and
   reasonably safe.
- Organize each project into separate files/modules according to the project logic.
   For example: a file for shared functions, a file for searching each external
   database or information source, a file for calculations, a file for input/output
   processing, a file for security checks, and a file for tests when needed. If the
   project uses more than one database or data source, prefer a separate module for
   each source.
- Add information-security and data-validation checks when code receives data from
   files, users, databases, APIs, or websites. For example, in Day06 code that queries
   external databases, verify that returned fields, data types, identifiers, sequence
   values, lengths, and required columns match the expected format before using the
   data in calculations, saving it, or displaying it. Handle unexpected or malformed
   responses safely and clearly.