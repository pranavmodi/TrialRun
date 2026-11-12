# Working agreement
Keep this project standalone. Never import code at runtime from sibling repositories or copy credentials or runtime databases.
Every UI feature must have API and CLI parity via the operation registry, tests, and documentation.
Update SPEC.md, README.md, and API_CLI.md when behavior changes. Distinguish simulation from real delivery and reference fixture runs from AI evaluations.
Use temporary data roots in tests. Never reset the user's demo world as part of automated tests.
After each verified project change, commit it with its tests and documentation, and push to the project's GitHub repository. Keep credentials and runtime data out of commits.
Do not grant evaluated agents controller credentials or filesystem access to world/evaluator files.
