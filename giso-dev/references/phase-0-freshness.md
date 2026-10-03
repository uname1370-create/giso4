# Phase 0 — Project Freshness

Run at the start of every giso-dev request, and re-run (fast form) before
implementing after approval.

## Full form

1. **Git state** — from the repo root:
   - `git branch --show-current`, `git rev-parse HEAD`, `git status --porcelain`
   - Note: untracked/modified files that overlap the target section.
2. **Graph freshness** — read the "Built from commit" line in
   `graphify-out/GRAPH_REPORT.md` (if present). Compare with current HEAD:
   - equal → graph usable for navigation;
   - different → mark graph **STALE**; use grep/import analysis only, and say
     so in the report.
   - missing → graph not available; proceed without it.
3. **Docs freshness** — check the "last updated" marker in `PROJECT_GUIDE.md`
   and `GISO_GUIDE.md` (first ~30 lines) against recent git history
   (`git log -5 --oneline`). If the guide predates significant changes, mark
   the relevant sections **STALE** and derive from code.
4. **Memory freshness** — read the "Last Update / Status" lines of
   `project_memory/letta/PROJECT_MEMORY.md` (if present). Note where the last
   session left off; treat as decision context, not structure.

## Output (4 lines, always)

```
Freshness: HEAD=<short> branch=<name> working-tree=<clean|dirty(n)>
Graph: <fresh|STALE (built at <short>)|absent>
Docs: <fresh|STALE (last <date>)>
Memory: <last update <date>|absent>
```

## Fast form (pre-implementation)

Re-check `git rev-parse HEAD` against the plan's recorded HEAD and
`git status --porcelain` against the plan's file list. If either changed, the
scope lock is void: re-run Section Identification and Pattern analysis on the
new tree, re-issue the plan, and ask for approval again.
