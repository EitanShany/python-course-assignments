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
   files, users, databases, APIs, or websites. Verify that returned fields, data
   types, identifiers, sequence values, lengths, and required columns match the
   expected format before using the data in calculations, saving it, or displaying
   it. Handle unexpected or malformed responses safely and clearly.
- Do not hard-code secrets such as API keys, passwords, tokens, private URLs, or
   personal credentials in the code. Use environment variables or local
   configuration files that are not committed to git.
- Validate all user input before using it in file paths, API requests, database
   queries, calculations, or command execution.
- Do not open, download, execute, or import files from unknown sources without
   checking their type, size, content format, and expected purpose.
- When saving output files, avoid overwriting existing files unless explicitly
   requested. Use clear file names and safe output folders.
- Do not print or save sensitive information such as tokens, passwords, personal
   identifiers, private file paths, or full API responses unless needed for
   debugging and explicitly approved.
- Add timeouts and error handling for external API/database requests so the program
   does not hang indefinitely or crash on malformed responses.
- Prefer HTTPS URLs for external requests and avoid disabling SSL/certificate
   verification.
