# Project Memory Update Template

Use this checklist at the end of every future task before final response.

## 1. Last Update

- Date/time:
- User timezone if known:
- Last Agent:
- Last Model if explicitly known; otherwise record `not recorded / model-agnostic`:

## 2. Git State

Run and record:

```bash
git status --short --branch
git rev-parse HEAD
git log --oneline --decorate -n 5
```

If remote state matters, also record:

```bash
git rev-parse refs/remotes/origin/arena/01a0e0b8-giso4 2>/dev/null || true
git status -sb
```

Record:

- Branch:
- Local HEAD:
- Relevant remote ref/head:
- Status summary:
- Local/remote discrepancy:
- New/modified/untracked paths intentionally left:

## 3. `sena.md` Status

- Is `sena.md` present locally?
- If read from remote ref, record exact ref and blob SHA:
- Was the scenario executed? Expected answer unless user explicitly approved: no.
- Treat `sena.md` as scenario input only, not Project Memory replacement.

## 4. Current Scenario

- What user asked:
- Scope allowed:
- Scope forbidden:
- Any files/directories explicitly locked:

## 5. Current Stage

- Completed:
- In progress:
- Blocked by:

## 6. Next Action

- Immediate next command/file/action for successor agent:
- If checkout reconciliation is required, describe exact caution:
- If tests/checks remain, list exact commands:

## 7. Architecture / Guide Findings

Add only durable discoveries:

- File/path:
- Verified behavior:
- Evidence command or code location:

## 8. Graphify Findings

- Which Graphify artifact was used: local/remote/path/ref:
- Built-from commit according to report:
- What Graphify covers:
- What Graphify does not cover:
- Any `INFERRED` facts must be labelled and code-verified before becoming project facts.

## 9. Letta Status

- CLI installed/version:
- Cloud auth/API key available? Record presence only, never value:
- Local backend usable?
- Project agent created/initialized?
- Memory imported into Letta?
- MCP required now? Why/why not:
- Known dependency limitations such as `node-pty`:

## 10. Known Issues

Add only code-verified or clearly labeled issues:

- Issue:
- Evidence:
- Risk:
- Suggested next step:

## 11. Decisions

- Decision:
- Rationale:
- Alternatives rejected:

## 12. Completed Work

- Files changed:
- Non-functional docs/tooling changes:
- Functional code changes if any:
- Tests/checks run and results:
- Confirm locked paths were not modified if applicable:

## 13. Synchronize JSON

Mirror durable changes into:

- `project_memory/letta/PROJECT_MEMORY.json`

Do not include secrets, credentials, oversized generated artifacts, DB files, uploads, or `node_modules`.
