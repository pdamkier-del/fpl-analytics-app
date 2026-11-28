# Agent workflow

## Before working
- Inspect current branch, HEAD, working tree and relevant existing documentation. Do not overwrite unrelated changes or assume main is the active research branch.
- Read existing local AGENTS.md files and project-specific instructions; preserve more specific rules.
- Identify the requested outcome, scope and validation plan.

## Project-specific rules
Preserve current MM/PM/TS behavior and locked parameters unless explicitly asked. Verify actual model versions, data timestamps, forecast archives and live app routes from code. Prevent temporal leakage; use chronological validation, regression tests and baseline comparisons. Never commit private user data or runtime artifacts.

## Validation and handoff
- Run relevant existing tests when possible; report commands, results and any unavailable checks honestly.
- Record decisions, changed files, commit/branch, tests, unresolved issues and next reproducible step in the existing project log or status document. If no such document exists, use STATUS.md when recording the first real handoff.
- Reuse existing theory, roadmap and research logs rather than create competing copies. Keep documentation aligned with the actual branch.
- Do not silently change model parameters, delete files, expose credentials, deploy or merge branches outside the requested scope.
- Provide a concise handoff so another agent can resume from the recorded state.
