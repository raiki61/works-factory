# Factory operations

This application runs on the Archon SDLC source pinned in `factory/pack.json`.

Shared workflow gates own every decision. Inspect a run's identity and status
before responding to a declared gate.

Project runtime scenarios: `tests/e2e/scenario.md`.
Holdout scenarios: `.factory/holdout/HOLDOUT.md`.
Ordinary checks: `uv run --isolated python3 tests/changed.py`.

Record this application's tested source SHA, candidate, run IDs, coverage,
fresh-environment evidence and open integration limits here after testing.
