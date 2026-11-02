# Minglefield – risk-based test stages

Decision: 2026-11-02. Applies to local development, agent contributions and CI. Full conformance runs are **not** required after each small commit.

| Stage | Trigger | Minimum evidence |
| --- | --- | --- |
| T1 Focused | Every code change | Relevant unit/conformance test files and directly affected contracts |
| T2 Extended regression | End of a related feature slice; shared interface changes | Tests of changed component and adjacent callers/security boundaries |
| T3 Full conformance | Before PR merge, milestone acceptance, release; earlier for significant architectural/security changes | `python -B -m unittest discover -s tests/conformance -p "test_*.py"` |
| T4 End-to-end | Functional milestone with real external dependencies | Manual or automated real workflow, explicit environment, observable outcome |

## Rules

- Select tests by changed behavior and risk, not just filenames. Auth, authorization, payments, job execution, asset isolation and persistent state may require T2/T3 immediately.
- A test not run must never be reported as passed. Record the exact commands and outcomes. T1 passing does not imply T3 passing.
- When a targeted test fails, fix it and rerun that test before proceeding. Before milestone acceptance, run T3 and relevant T4.
- For the current Game-project slice, start with:
  `python -B -m unittest discover -s tests/conformance -p "test_game_project*.py" -v`
- CI should eventually select T1 automatically on pushes and run T3 on pull requests; until CI is configured and verified, this is a **policy target**, not a claim about existing automation.
- Do not alter the working local ComfyUI execution path merely to accelerate testing.
