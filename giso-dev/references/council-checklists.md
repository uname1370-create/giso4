# Council Review — four internal passes

Run as four sequential passes over the draft plan before presenting it. No
subagents needed. Every objection or pass must cite code evidence
(file + symbol read this session), not vibes.

## Architect
- Does the change sit in the right domain folder (golden rule: module in its
  own folder)?
- Does it cross a layer boundary that project law forbids
  (giso→bot_edu, web↔giso coupling, direct DB outside the module seam)?
- Does it add coupling (new import, new shared table, new hook) that a
  narrower change could avoid?

## Domain
- Does the behavior match the feature's actual semantics as read from current
  code (not from the user's description or the docs)?
- Does it match sibling services' behavior for the same user action?
- Edge cases: empty states, permission states, duplicate/conflicting records,
  Persian/RTL specifics where the section handles them.

## Security
- AuthN/AuthZ: which guard protects each new/changed view? Is the guard the
  house one?
- CSRF on every state-changing form; step-up where the section requires it.
- Input validation at the boundary; upload path constraints; no secret in
  logs/errors/UI.
- Data exposure: does a public page surface a field that only panels should
  see?

## Regression
- Which sibling features share each touched symbol? List them.
- Shared DB tables touched: who else reads/writes them?
- Notification event changes: who consumes them?
- Which existing test files name this feature or its siblings
  (grep `giso/tests/`)? Those are the minimum set to run.

Resolution: an objection that the plan cannot satisfy → return to
Pattern/Architecture analysis and re-draft the plan; do not present a plan the
council already rejected.
