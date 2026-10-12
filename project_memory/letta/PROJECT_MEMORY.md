# Giso4 Project Memory — Current Handoff

## 1. Last Update

- **Date/time:** 2026-10-12, approximately 14:41
- **User timezone:** Asia/Tehran
- **Last Agent:** Manus
- **Last Model:** not recorded / model-agnostic

## 2. Git State

- **Branch:** `arena/7f567e47-giso4`
- **HEAD before this memory-only update:** `cb53d58135bec2ab861be8ec3fc50bd00e5f8929` — `Update Buti AI handoff for successor agent`
- **Remote:** `origin/arena/7f567e47-giso4` was at the same commit before this update.
- **Working tree:** clean before the current documentation update; audit and memory changes are being prepared for one docs-only commit/push.
- **Paths changed in this update:** `project_memory/letta/BUTI_AI_UPLOAD_ANALYSIS_RECOMMENDATION_AUDIT_2026-10-12.md`, `PROJECT_MEMORY.md`, and `PROJECT_MEMORY.json` only.
- The final commit hash and push result are reported in the task completion message; no source-code change is part of this update.

## 3. `sena.md` Status

- `sena.md`: absent locally.
- No remote `sena.md` ref/blob was consulted.
- No scenario was inferred or executed from `sena.md`.

## 4. Current Scenario

- **User asked:** continue the Buti AI upload → analysis → recommendation → confirmation → final-output work; rerun the documented test plan; verify real provider readiness without guessing; update audit/memory; commit and push to the authorized branch if safe.
- **Allowed scope:** `giso/buti_ai/`, Buti AI tests, and `project_memory/letta/`.
- **Protected:** `web/`, `bot_edu/`, `main.py`, `giso/bot.py`; no refactor outside Buti AI.
- **Current-turn code/config changes:** none. Test runs used a temporary git worktree and temporary virtualenv outside the main checkout.

## 5. Current Stage

- **Completed:** full Buti AI suite: 137 passed, 4 skipped; focused Vision/provider-registry suite: 32 passed; JS syntax, Python compilation and diff checks passed.
- **Also observed:** two unrelated `giso/tests/test_ai_runtime.py` tests fail and reproduce individually; details are in the audit. No code outside Buti AI was changed.
- **In progress:** docs-only audit/memory update, then commit and push to the authorized branch.
- **Blocked/unverified:** live Cloudflare Vision/inpainting and admin-panel readiness. This checkout has no `giso/data/giso.db` or `giso/data/.env`, there is no authenticated superadmin panel session, and no real test photo was supplied in this turn.

## 6. Next Action

1. Run the pre-commit checks and secret/scope scan on the three documentation changes; commit them and push to `origin/arena/7f567e47-giso4` if checks pass.
2. For live readiness, use an authenticated `/admin/ai` session and a non-sensitive test photo; do not create a parallel provider or bypass the current panel contract.
3. Re-run the real Vision/inpainting matrix only after those prerequisites are available; direct-env history does not establish current panel readiness.
4. Keep production activation blocked until documented cost-ledger, provider-attempt audit, charge, idempotency, quota, circuit-breaker, consent and worker-queue controls are addressed.

## 7. Architecture / Guide Findings

- `giso/buti_ai/routes.py`: staged wizard routing, session ownership checks and private uploaded-file/download routes.
- `giso/buti_ai/eyebrow/flow.py`: quality + Vision analysis at upload; final generation is deferred until user confirmation.
- `giso/buti_ai/eyebrow/final_design.py`: keeps `selected_style`, `recommended_style` and `final_style` distinct; only confirmed `final_style` controls prompt/generation.
- `giso/buti_ai/generic_service.py`: shares the contract; recommendation confirmation UI is limited to `lip_shading` in this change.
- `giso/buti_ai/downloads.py`: creates an in-memory private PDF; routes validate ownership and candidate-bound paths.
- `giso/buti_ai/service_catalog.py`: runtime catalog labels eyebrow/nail/hair_color/lip_shading active. Higher-level docs differ; blush/eyeliner are not implemented in the current runtime catalog/routes.
- Focused provider-registry tests use temporary DB/config and mocks; they do not prove a configured production provider or panel readiness.

## 8. Graphify Findings

- No Graphify artifact was regenerated in this task.
- Historical graph information does not cover this current test-only/documentation update.

## 9. Letta Status

- Letta reference documents were used as the canonical task handoff.
- `letta --version` produced no available version output in this environment.
- Cloud auth/API key, local backend and project-agent initialization were not required or verified.
- MCP was not required for Letta itself.

## 10. Known Issues

- **Live provider/panel not verified:** current checkout contains neither `giso/data/giso.db` nor `giso/data/.env`; no authenticated superadmin panel session or real photo was available. No live provider call was made. The provider state described in the user prompt is historical and was not rechecked in this workspace.
- **Four real-photo tests skipped:** close-up lip and real-hair photo inputs are absent; mocked contract tests are not evidence of live image quality.
- **Out-of-scope runtime tests:** `test_failover_cooldown_skips_recently_failed_provider` expects missing `_PROVIDER_FAIL_COOLDOWNS` (`test_ai_runtime.py:209`); `test_superadmin_ai_setting_actions_and_user_delete` expects `pending` but receives `message` (`:432`). Both were reproduced individually and left unchanged because they are outside the Buti AI boundary.
- **Production gate incomplete:** cost ledger, provider-attempt audit, charge, idempotency, quota, circuit breaker, explicit consent and worker queue remain documented prerequisites.
- **Warnings:** test runs emitted existing deprecation/runtime warnings; no cleanup outside scope was attempted.

## 11. Decisions

- Did not use the supplied credential for a live call: current provider settings and admin readiness are not accessible here, and no real test image was supplied.
- Did not fake panel state or treat mock-provider tests as live AI success.
- Did not change product code or unrelated runtime tests; focused safe backend testing and documentation updates remained within scope.
- Continued to distinguish local non-AI fallback from actual AI output.

## 12. Completed Work

- Re-ran `node --check giso/buti_ai/static/buti_ai.js` — passed.
- Compiled relevant Python route, flow, generation, download, panel and provider modules — passed.
- Upload/recommendation/download/output-format tests — 11 passed.
- Eyebrow mask/detection/request/ROI/recolor tests — 22 passed.
- New-service/fallback/four-service tests — 38 passed, 4 skipped.
- Full suite `giso/tests/test_buti_ai*.py` — **137 passed, 4 skipped, 153 warnings in 88.02s**.
- Focused Cloudflare Vision/provider-registry tests — **32 passed in 1.82s**.
- `git diff --check` — passed in the isolated test worktree; the main checkout remains unmodified outside this documentation update.
- No real Vision/image-generation or browser smoke test was performed; image/PDF download code paths are covered by backend tests.
- This current turn changes only the audit and Project Memory documentation; it makes no Python/JavaScript or provider-setting changes.

## 13. JSON Synchronization

Durable findings are mirrored in `project_memory/letta/PROJECT_MEMORY.json`. No credentials, database files, uploads or generated assets are recorded.
