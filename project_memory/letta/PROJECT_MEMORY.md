# Giso4 Project Memory — Current Handoff

## 1. Last Update

- **Date/time:** 2026-10-12, approximately 17:43
- **User timezone:** Asia/Tehran
- **Last Agent:** Manus
- **Last Model:** not recorded / model-agnostic

## 2. Git State

- **Branch:** `arena/7f567e47-giso4`
- **Branch:** `arena/7f567e47-giso4` (verified in the active workspace).
- **Working tree:** stage 1/2 salon changes and stage 3 Booking Bridge changes remain uncommitted; stage 3 regressions passed. Full-suite rerun is in progress before the requested GitHub push.
- **Current-turn code change:** Mirror service-card preview entry, same-center/same-service reservation return path, real active service ID selection, server-side final-design ownership/type checks, and explicit no-photo-sharing copy.
- **Protected paths:** `web/`, `bot_edu/`, `main.py`, and `giso/bot.py` remain unchanged.

## 3. `sena.md` Status

- `sena.md`: absent locally in the prior check.
- No remote `sena.md` ref/blob was consulted.
- No scenario was inferred or executed from `sena.md`.

## 4. Current Scenario

- **Current user request:** complete roadmap stages 1–3, run health/regression tests, and push the result to `arena/7f567e47-giso4`; pause for approval before continuing to stage 4.
- **Stage 1:** reservation CTA and selected-service highlight were implemented in the center listing/detail experience.
- **Stage 2:** gallery capacity/metadata/moderation and owner controls were implemented; pending items are not public before moderation.
- **Stage 3:** compatible active service cards now offer Mirror preview; the result links back to the same center/service. Reservation GET/POST validates design ownership, type and active service mapping. The customer's photo is not exposed to the center.
- **Historical AI note:** the earlier synthetic Cloudflare Vision test and transport/parser fix remain recorded below; no production provider configuration was changed in the current center work.

## 5. Current Stage

- **Stage 3 implementation:** done locally; tests for booking security, center CTA, gallery, cards and Buti AI passed (**51 passed**, 132 existing deprecation warnings). Python compile checks passed.
- **Full suite:** first collection attempt identified the requirements-listed Telegram dependency was absent; it was installed and a complete rerun is in progress. Do not report a result until the process completes.
- **Privacy:** only internal `final_design_id` and service/style metadata are linked to reservations. The salon does not receive the customer's photo; the reservation UI states this explicitly.
- **Not started:** stage 4 Instagram/social click tracking.

## 6. Next Action

- Finish the full-suite rerun, inspect `git diff --check` and final worktree, then commit/push requested stages 1–3 to `arena/7f567e47-giso4`.
- After the push, report stage 3 and ask for explicit approval before beginning stage 4. Do not silently proceed to later roadmap stages.
- Keep public launch blocked until documented cost ledger, provider-attempt audit, charge, idempotency, quota, circuit breaker, consent and worker queue requirements are addressed.

## 7. Architecture / Guide Findings

- `giso/buti_ai/routes.py`: staged routes, session ownership checks, and private download routes.
- `giso/buti_ai/eyebrow/flow.py`: quality + Vision analysis at upload; final generation is deferred until confirmation.
- `giso/buti_ai/eyebrow/final_design.py`: keeps `selected_style`, `recommended_style`, and `final_style` distinct; only confirmed `final_style` controls prompt/generation.
- `giso/buti_ai/generic_service.py`: shares the recommendation contract; confirmation UI is limited to `lip_shading`.
- `giso/buti_ai/downloads.py`: creates private in-memory PDF reports.
- `giso/buti_ai/service_catalog.py`: runtime catalog labels eyebrow/nail/hair_color/lip_shading active; blush and eyeliner remain absent from runtime modules/routes.
- `giso/ai_brain.py::_cloudflare_vision_payloads`: the tested Workers AI REST request for the registered Llama Vision model uses `prompt` plus an 8-bit image byte array. Combining `prompt` and `messages` in the same request was rejected by the live endpoint's schema.
- `giso/ai_brain.py::_ai_text_cloudflare`: Cloudflare `result` may be a structured list; it is now serialized as JSON text.

## 8. Graphify Findings

- No Graphify artifact was regenerated in this stage.
- Historical graph information was not used to establish the live endpoint behavior; the behavior was confirmed against Cloudflare's official model schema and a live synthetic request.

## 9. Letta Status

- Letta reference documents were used as the canonical project handoff.
- `letta --version` produced no available version output in the prior check.
- Cloud auth/API key, local backend, project agent initialization, memory import, and MCP were not required or verified.

## 10. Known Issues

- **Production panel/configuration:** no authenticated production `/admin/ai` session was used; temporary local settings do not establish production readiness.
- **End-to-end product flow:** synthetic Vision succeeded, but full eyebrow/lip analysis, recommendation, generation, and browser download were not run in this stage. The model added a prose preamble before its JSON-looking count output, so downstream strict-JSON behavior needs a real-prompt test.
- **Browser download:** the earlier browser tool failed during the download click; backend ownership and PDF tests still pass, but the browser smoke gap remains.
- **Unrelated runtime failures:** `test_failover_cooldown_skips_recently_failed_provider` expects missing `_PROVIDER_FAIL_COOLDOWNS`; `test_superadmin_ai_setting_actions_and_user_delete` received `message` rather than expected `pending`. These are outside the Vision fix and remain unchanged.
- **Warnings:** `datetime.utcnow()` and Pyparsing deprecation warnings remain.
- **Production gate:** cost ledger, provider-attempt audit, charge, idempotency, quota, circuit breaker, explicit consent, and worker queue remain required.
- **Credential handling:** the user's credential was used only in the disposable local DB for the approved test. The DB key was cleared and provider disabled. Rotate the credential because it was shared in this conversation.

## 11. Decisions

- Sent the exact user-approved agreement payload once. Cloudflare returned HTTP 403/code 5016 with a message explicitly confirming acceptance; no retry was sent, and a subsequent model request succeeded.
- Used only `@cf/meta/llama-3.2-11b-vision-instruct` and a synthetic diagram; no fallback model or user photo was used.
- Made a minimal generic provider-transport correction in `giso/ai_brain.py`, with a regression test. No product-specific prompt logic was moved outside `giso/buti_ai/`.
- Cleared the temporary API key and disabled the temporary provider after the test. Production settings were not changed.

## 12. Completed Work

- `giso/ai_brain.py`: Cloudflare Vision payload uses the live-tested `prompt` + byte-array image schema; structured-list responses are parsed.
- `giso/tests/test_ai_cloudflare_vision.py`: tests assert the request schema and structured-list parser behavior.
- `project_memory/letta/BUTI_AI_UPLOAD_ANALYSIS_RECOMMENDATION_AUDIT_2026-10-12.md`: appended live Vision findings and remaining limitations.
- Live synthetic Vision call: success on `@cf/meta/llama-3.2-11b-vision-instruct`, approximately 4.53 seconds; detected two red rectangles and one green circle.
- Focused Cloudflare Vision tests: **2 passed**.
- `py_compile` for changed Python files and `git diff --check`: passed.
- Broader related suite: **55 passed, 2 failed, 36 warnings**; both failures were the unrelated `giso/tests/test_ai_runtime.py` cases listed above.
- Temporary DB cleanup: provider disabled and API key length verified as zero; no secret is recorded in this memory.
- **Stage 3 Booking Bridge:** active center-service cards start the matching Mirror flow; a user-bound one-hour context returns the user to the same salon/service, and reservation GET/POST revalidate ownership/type/service. No customer photo is shared with the salon. `py_compile` passed; related regressions: **51 passed, 132 warnings**; latest focused rerun: **4 passed**.
- Full-suite rerun was started after installing the project-declared Telegram dependency; record its terminal result before committing/pushing.

## 13. JSON Synchronization

- Mirror durable findings into `project_memory/letta/PROJECT_MEMORY.json`.
- Never include credentials, DB files, uploads, or generated assets.
