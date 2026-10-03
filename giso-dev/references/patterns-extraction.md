# Pattern & Architecture Extraction

Purpose: the proposed change must be the *next variation of the existing
pattern*, not a new architecture.

## Procedure

1. **Nearest-neighbor read** — pick the closest existing sibling feature in
   the same module (or same layer) and read it top to bottom: route → view →
   service call → schema access → template → static asset → bot handler (if
   any) → panel views (if any). Note the exact convention each seam uses.
2. **Convention table** — fill, per seam actually touched by the change:

   | Seam | House pattern (with file evidence) | What the change will do |
   |---|---|---|
   | DB access | e.g. shared conn helper from `db_core`/`db_engine` | reuse it, do not create a second helper |
   | Auth/role guard | which decorator/helper guards this view type | reuse it |
   | CSRF handling | how forms in this section carry tokens | follow the same form shape |
   | Notification hook | event name + registration point | register the new event the same way |
   | Bot flow | state machine / menu conventions | extend, do not fork |
   | Template/CSS | naming + base-template usage | extend existing blocks/partials |
   | AI call | runtime entry + proxy manager + credits | reuse entry points |

   Evidence = file + symbol name, read in this session. No "as I recall".
3. **Drift detection** — if the target section already deviates from the
   house pattern, record it. The change follows the *local* pattern of the
   section being edited; fixing global drift is out of scope and goes to the
   "found but not changed" list.
4. **No new abstractions** — no new base class, no new module folder, no new
   service file unless the goal itself requires it. When unsure, prefer a
   function inside the existing module.
5. **Output** — the convention table plus a 2-5 line "current architecture
   summary" of the target section, with file evidence, ready to paste into the
   plan.
