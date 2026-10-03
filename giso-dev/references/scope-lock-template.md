# Scope Lock & Plan Template (Approval Gate deliverable)

Present exactly this structure, then STOP and ask for approval.

```
## ۱. Request interpretation
- Restated goal: ...
- Assumptions (explicit, low-risk only): ...
- If a clarification was asked and answered: ...

## ۲. Freshness
- HEAD/branch/graph/docs/memory lines (from phase-0 output)

## ۳. Current state & real problem location
- Where the problem actually lives (file + symbol, with short evidence)
- Divergences found (docs/graph/memory vs code): ...

## ۴. Architecture & current pattern
- Convention table (from patterns-extraction) for seams touched

## ۵. Dependencies & impact
- Internal imports touched, shared DB tables, notification events,
  AI runtime coupling, sibling features sharing code

## ۶. Proposed solution
- Minimal path, justified by the current pattern
- Explicitly NOT doing: (refactor/redesign/cleanup/beauty changes)

## ۷. Scope lock
- ALLOWED files: (full list, each with one-line reason)
- FORBIDDEN: everything else (default)
- Shared/caution files inside scope: ...
- Data: tables involved / migration needed? how (incremental, module style)
- Out of scope: (named neighbors, e.g. sibling services, bot_edu, web/)

## ۸. Council findings
- Architect / Domain / Security / Regression: pass or listed objections
  (each objection cites code evidence)

## ۹. Risks
## ۱۰. Tests to run
## ۱۱. Regression plan
## ۱۲. Found but not changed
- Anything observed that needs no action now

APPROVAL NEEDED: "تأیید می‌کنی؟"
```

Rules:
- Do not start editing until the user explicitly approves THIS plan.
- "درستش کن / اجرا کن" given BEFORE a plan exists = request for the plan,
  not permission to edit.
- After approval, any newly required file outside the lock → stop, extend the
  lock, ask again.
