---
name: giso-dev
description: >-
  Use when working on the Giso repository (folders giso/, bot_edu/, web/, main.py)
  and the user asks to fix, add, change, or review any feature in that project.
  Enforces a discovery-first, approval-gated workflow: interpret the request,
  locate the relevant section from CURRENT code, analyze patterns and impact,
  run a 4-perspective council review, present a Plan + Scope Lock, stop for
  explicit user approval, then implement minimally and verify with tests,
  diff review, and regression checks. Read-only verbs (بررسی کن / گزارش بده /
  پیشنهاد بده) never modify files; the only exception is the giso-dev skill
  folder itself when the user explicitly asks to update the skill.
metadata:
  short-description: Giso approval-gated, code-first change workflow
---

# Giso Dev

A disciplined, project-aware change workflow for the Giso repository. The core
belief: **the agent must never guess from the user's description alone** — it
reads the real code first, derives the plan from what the project actually does
today, and only touches files after explicit user approval.

This skill stores **method, not facts**. It does NOT contain a file list,
line numbers, function signatures, table names, commit hashes, or feature
conclusions for this repository. Those change; re-derive them every time from
the live tree, following the discovery method below.

## When this skill applies

- Any request that will read or change files under the Giso repo
  (typical anchors: `giso/`, `bot_edu/`, `web/`, `main.py` — verify, do not trust).
- Any request like: fix a feature, add a feature, review a section,
  explain why something breaks, refactor a module, "ابرو را درست کن",
  "فلان بخش رو درست کن".

It does NOT apply to: unrelated repositories, generic Python questions,
deployment questions that do not touch this repo's code, or creating other
skills.

## The pipeline (mandatory order)

```
Understand Request → Project Freshness → Section Identification →
Pattern & Architecture Analysis → Dependency / Impact Analysis →
Graph / Memory / Docs Check → Council Review → Plan + Scope Lock →
STOP → Explicit User Approval → Implementation → Tests →
Diff Review → Regression Check → Final Report
```

Read-only requests (`بررسی کن`, `گزارش بده`, `پیشنهاد بده`) run the pipeline
through **Plan + Scope Lock** and stop there — no writes. Mutation verbs
(`اجرا کن`, `اعمال کن`, `تغییر بده`, `درستش کن`) run the pipeline, stop at the
Approval Gate, and only continue after the user explicitly approves THAT plan.

## Phase notes

1. **Understand Request** — restate: domain, surface (site / bot / user panel /
   admin panel), layer (UI / logic / schema / DB / AI / bot / notification),
   expected behavior. If one clarification removes the ambiguity, ask exactly
   one question; otherwise make low-risk assumptions and list them in the plan.
2. **Project Freshness** — always first: `references/phase-0-freshness.md`.
3. **Section Identification** — find the section in the CURRENT tree:
   `references/discovery-method.md`.
4. **Pattern & Architecture Analysis** — how sibling code in that section
   already does the same kind of thing; the change must mimic that pattern:
   `references/patterns-extraction.md`.
5. **Dependency / Impact Analysis** — imports, shared DB, notification hooks,
   AI runtime, panel auth paths, sibling features that share code.
6. **Graph / Memory / Docs Check** — only when relevant:
   `references/stale-handling.md` (freshness rules and divergence reporting).
7. **Council Review** — four internal passes before the final plan:
   `references/council-checklists.md`.
8. **Plan + Scope Lock** — the Approval Gate deliverable, exact structure:
   `references/scope-lock-template.md`.
9. **STOP** — no writes before the user says "تأیید / approve / بریم / اجرا کن"
   in response to THIS plan. A vague earlier "do it" does not count.
10. **Implementation** — re-check freshness; edit only in-scope files; follow
    local conventions; no unrelated refactor, no new abstractions unless the
    goal requires one; if a new file becomes necessary, stop and get re-approval
    (scope lock is additive-only after approval).
11. **Tests / Diff / Regression** — `references/test-regression.md`.
12. **Final Report** — what changed, why, which files, tests run and results,
    regression checks, any out-of-scope drift (should be none), remaining
    issues, and suggested follow-ups (memory/graph refresh — never performed
    unprompted).

## Hard rules

- **Code is the source of truth.** If Graphify, Project Memory, docs, or the
  user's description disagree with the live code, the code wins; report the
  divergence in the final report instead of silently following the stale source.
- **Never hard-code stale project facts** into any artifact this skill produces
  as permanent guidance. Reports may cite the current state with evidence.
- **Scope lock is binding.** Only files listed in the approved lock may change.
- **Read-only stays read-only.** No edits, no commits, no generated artifacts
  under the repo for `بررسی/گزارش/پیشنهاد` requests.
- **Restricted zones** (verify current state, but by project convention):
  `bot_edu/` is off-limits for giso development without an explicit user
  instruction; `web/` (port 5000) stays decoupled from `giso/`;
  `graphify-out/`, `project_memory/`, `data/`, `.env`, venv, and git history
  are never modified as part of a feature change.
