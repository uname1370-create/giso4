# Giso4 Project Memory — Current Handoff

## 1. Last Update

- **Date/time:** 2026-10-12, approximately 14:08
- **User timezone:** Asia/Tehran
- **Last Agent:** Manus
- **Last Model:** not recorded / model-agnostic

## 2. Git State

- **Branch:** `arena/7f567e47-giso4`
- **Local HEAD:** `e49945b` — `Implement Buti AI upload recommendation confirmation flow`
- **Status:** implementation committed locally; the commit is being pushed in this task.
- **Local/remote discrepancy:** remote remains at `1f96ffa` until the requested push completes.
- **Intentionally changed/new paths:**
  - `giso/buti_ai/{routes.py,generic_service.py,downloads.py}`
  - `giso/buti_ai/eyebrow/{flow.py,result.py,final_design.py}`
  - `giso/buti_ai/static/{buti_ai.js,buti_ai.css}`
  - `giso/buti_ai/templates/buti_ai/{eyebrow_wizard.html,eyebrow_final_design.html,generic_service_wizard.html,generic_final_design.html}`
  - `giso/tests/{test_buti_ai_phase1.py,test_buti_ai_new_services.py,test_buti_ai_upload_recommendation.py}`
  - `project_memory/letta/{BUTI_AI_UPLOAD_ANALYSIS_RECOMMENDATION_TEST_PLAN.md,BUTI_AI_UPLOAD_ANALYSIS_RECOMMENDATION_AUDIT_2026-10-12.md,PROJECT_MEMORY.md,PROJECT_MEMORY.json}`

## 3. `sena.md` Status

- `sena.md`: absent locally.
- No remote `sena.md` ref/blob was consulted.
- No scenario was inferred or executed from `sena.md`.

## 4. Current Scenario

- **User asked:** read the canonical Letta start file and each referenced file in order; implement the documented upload → analysis → recommendation → confirmation → final-output flow; verify real status of services; test as far as possible; report blockers without guessing.
- **Allowed scope:** Buti AI code, Buti AI tests and Letta Project Memory.
- **Forbidden/protected:** `web/`, `bot_edu/`, `main.py`, `giso/bot.py`; no refactor outside `giso/buti_ai/`.
- **Locked-path result:** protected paths were not modified.

## 5. Current Stage

- **Completed:** browser and backend two-stage flow for eyebrow and lip; protected image/PDF downloads; honest AI/non-AI labels; tests and browser smoke.
- **In progress:** none.
- **Blocked by:** no configured production Vision/image-edit provider in the active environment; production preconditions (ledger/quota/idempotency/queue/consent) are not in this task’s implementation scope.

## 6. Next Action

1. Configure one real, server-to-server Vision/image-edit provider in the project’s AI-management source; do not use a browser-only credential.
2. Run the real-provider matrix in `BUTI_AI_UPLOAD_ANALYSIS_RECOMMENDATION_TEST_PLAN.md` with a non-sensitive test image.
3. Before public activation, implement the documented cost ledger, provider-attempt audit, quota/idempotency/circuit breaker, explicit consent and queued generation prerequisites.
4. Before committing, re-run:
   ```bash
   node --check giso/buti_ai/static/buti_ai.js
   .venv/bin/python -m py_compile giso/buti_ai/routes.py giso/buti_ai/generic_service.py giso/buti_ai/downloads.py giso/buti_ai/eyebrow/flow.py giso/buti_ai/eyebrow/result.py giso/buti_ai/eyebrow/final_design.py
   SECRET_KEY=arena-test-secret-for-buti-ai-tests-32chars .venv/bin/python -m pytest -q giso/tests/test_buti_ai_phase1.py giso/tests/test_buti_ai_new_services.py giso/tests/test_buti_ai_upload_recommendation.py
   git diff --check
   ```

## 7. Architecture / Guide Findings

- `giso/buti_ai/routes.py`: owns staged wizard routing, session ownership checks and private uploaded-file/download routes.
- `giso/buti_ai/eyebrow/flow.py`: now does quality + Vision analysis at upload; it must not trigger final generation.
- `giso/buti_ai/eyebrow/final_design.py`: preserves the user’s selected style, holds the AI recommendation separately and sends only the confirmed `final_style` to prompt/generation.
- `giso/buti_ai/generic_service.py`: shares the contract; the recommendation confirmation UI is enabled only for `lip_shading` in this change.
- `giso/buti_ai/downloads.py`: creates an in-memory private PDF; routes validate candidate ownership and candidate-bound paths first.
- `giso/buti_ai/service_catalog.py`: runtime catalog labels eyebrow/nail/hair_color/lip_shading active. This conflicts with higher-level docs that name brow/lip/blush/eyeliner; do not call blush or eyeliner implemented without code.
- Browser smoke log recorded Vision provider count `0`; code must label fallback non-AI in that condition.

## 8. Graphify Findings

- No Graphify artifact was regenerated in this task.
- Historical graph information in earlier memory was built before this working-tree implementation; it does not cover the new uncommitted flow.

## 9. Letta Status

- Letta reference documents were used as the canonical task handoff.
- `letta --version` produced no available version output in this environment.
- Cloud auth/API key, local backend and project-agent initialization were not required or verified.
- MCP was not required for Letta itself.

## 10. Known Issues

- **No real provider configured:** connector inspection found no matching connector and browser log showed zero Vision-capable providers. **Risk:** only `ai_unavailable`/guided fallback can be verified. **Next:** configure and benchmark provider.
- **Browser download check incomplete:** the browser tool became unavailable after reaching final; protected route tests passed for both eyebrow and lip. **Risk:** browser-session download UX needs rerun when browser is available.
- **Production gate incomplete:** ledger/quota/idempotency/circuit breaker/consent/queue are documented prerequisites but unimplemented here. **Risk:** public launch must remain blocked.
- **Deprecated timestamps:** existing `datetime.utcnow()` calls produce pytest warnings. **Next:** separate timezone-aware cleanup task.

## 11. Decisions

- Kept recommendation and final selection separate: AI proposes; the user confirms; `final_style` alone controls generation.
- Chose no-AI continuation when provider unavailable; no synthetic AI success signal is emitted.
- Added downloads only for the requested eyebrow/lip scenario. Nail and hair behavior remains unchanged.
- Used FPDF + project dependencies in-memory for a PDF instead of retaining duplicate media.

## 12. Completed Work

- Implemented the documented two-POST analysis/confirmation flow for eyebrow and lip.
- Added same-origin validation feedback, preview, recommendation cards and cache-busted JS/CSS.
- Added protected downloads for final image and PDF.
- Added/updated contract tests, including provider success/unavailable mocks, explicit confirmation, candidate ownership and PDF routes.
- **Validation:** 53 tests passed in 35.60s; JS syntax, Python compilation and `git diff --check` passed.
- **Browser:** actual eyebrow fallback flow reached final before/after and rendered download links; real provider not configured.

## 13. JSON Synchronization

Durable findings are mirrored in `project_memory/letta/PROJECT_MEMORY.json`. No secrets, credentials, database files, uploads or generated assets were recorded.
