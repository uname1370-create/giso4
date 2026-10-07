# Testing & Regression Workflow

Run after implementation, inside the approved scope.

## 1. Targeted tests
- Discover: `Get-ChildItem giso/tests -Filter *.py | Select-String -Pattern <feature|module-name>` —
  test files in this project are named after the feature/phase
  (`test_<module>_<phase|topic>.py`).
- The project uses **pytest** (per `PROJECT_GUIDE.md` §8 and `GISO_GUIDE.md`
  §542-era notes): run
  `SECRET_KEY=<test-key> python -m pytest giso/tests/<name>.py -q`.
  Verify the exact invocation convention from the guides' current text; if
  the guide's recipe is stale, discover how tests are actually run
  (header docstrings of the test files often state the required env +
  run command — test files in this repo document their own coverage in the
  module docstring; read that first).
- Known caveat pattern (verify before relying): some legacy suites are out of
  sync with removed/refactored contracts (e.g. referral retirement, CSRF
  shape). A failing legacy test may be pre-existing: check `git stash`/
  clean-tree behavior or note the failure's origin in the report.

## 2. Import / boot check
- `python -c "import giso.wsgi"` (or the app module of the touched surface)
  to catch syntax/wiring breaks. Do NOT boot `main.py` for tests — it spawns
  bot services; test files that need a running app build it in-process.

## 3. Feature behavior check
- Follow the module's own test docstring for what is covered; run the listed
  covered paths and report pass/fail per path.

## 4. Regression sweep
- Run the sibling-feature test files identified in the council's Regression
  pass (minimum set), plus the shared-table/notification suites they name.
- If the change touched a shared symbol (DB helper, AI runtime entry,
  notification core): run all test files that import that symbol
  (`Select-String` in `giso/tests/`).

## 5. Diff review
- `git diff` (uncommitted) — walk every hunk; one-line justification per hunk
  mapped to the approved scope-lock entry.
- Any hunk outside the lock → STOP, report as out-of-scope drift, revert it
  or re-approve with the user.

## 6. Final report
- What changed / why / files / tests run + results / regression sweep
  results / out-of-scope drift (expected: none) / remaining issues /
  suggested follow-ups (e.g. `graphify update .`, project-memory update
  per `project_memory/letta/UPDATE_TEMPLATE.md`) — suggestions only, never
  executed without an explicit user instruction.
