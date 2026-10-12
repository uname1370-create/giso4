# Giso4 Project Memory — Current Handoff

## 1. Last Update

- **Date/time:** 2026-10-12, approximately 19:50
- **User timezone:** Asia/Tehran
- **Last Agent:** Manus
- **Last Model:** not recorded / model-agnostic

## 2. Git State

- **Branch:** `arena/7f567e47-giso4`; commit `525e80e` (`Implement beauty center mirror booking stages 1-3`) was pushed to `origin`.
- **Working tree:** Stage 4 Instagram and Stage 5 smart analytics changes are local and uncommitted. Remote remains at commit `525e80e`; no Stage 4/5 push was done.
- **Current-turn code change:** Stage 5 public demand board, event-level booking-start metric, owner analytics tab, admin city/service aggregation, dynamic current-service inventory, and related tests.
- **Protected paths:** `web/`, `bot_edu/`, `main.py`, and `giso/bot.py` remain unchanged.

## 3. `sena.md` Status

- `sena.md`: absent locally in the prior check.
- No remote `sena.md` ref/blob was consulted.
- No scenario was inferred or executed from `sena.md`.

## 4. Current Scenario

- **Current user request:** implement Stage 5 smart demand analytics and make displayed service labels dynamic. Implemented locally; pause before Stage 6 and do not push without request.
- **Stage 1:** reservation CTA and selected-service highlight were implemented in the center listing/detail experience.
- **Stage 2:** gallery capacity/metadata/moderation and owner controls were implemented; pending items are not public before moderation.
- **Stage 3:** compatible active service cards now offer Mirror preview; the result links back to the same center/service. Reservation GET/POST validates design ownership, type and active service mapping. The customer's photo is not exposed to the center.
- **Historical AI note:** the earlier synthetic Cloudflare Vision test and transport/parser fix remain recorded below; no production provider configuration was changed in the current center work.

## 5. Current Stage

- **Stage 3 implementation:** done and pushed in commit `525e80e`; tests for booking security, center CTA, gallery, cards and Buti AI passed (**51 passed**, 132 existing deprecation warnings). Python compile checks passed.
- **Stage 4 implementation:** done locally; supports canonical profile links, owner editing, public CTA, no-open-redirect tracking and aggregate events. Event rows do not store visitor IDs; service attribution is checked against active center inventory. No Instagram API or scraping is used.
- **Stage 4 tests:** dedicated module **7 passed**; combined center/gallery/CTA/Booking Bridge/Buti AI regression before Stage 5 **58 passed, 132 warnings**.
- **Stage 5 implementation:** done locally. Public center page retains the original four cards and adds an aggregate 30-day service-demand board before filters. Services are derived from active inventory at currently published centers, grouped by current service key or current service name fallback; it is not hardcoded to brow/lip/hair. The owner dashboard has a 7/30/90-day analytics tab scoped to the owner’s resolved center; it separates event counts from actual reservation rows/current statuses and lists current services dynamically. The super-admin dashboard adds city/service aggregation.
- **Stage 5 measurement/privacy:** valid reserve-form starts are logged as `booking_start`, once per signed browser session/day per center-service; owner opens are excluded. Events store aggregate center/service/source only (`user_id=0`), no photo, final-design ID, phone or visitor ID. Counts are form-start actions, not unique people or completed reservations. Public exact demand counts are suppressed below the configurable default sample size 5 (`BEAUTY_SERVICE_DEMAND_MIN_SAMPLE`, 1–100).
- **Stage 5 focused validation on current code:** **70 passed, 132 warnings** across Stage 5, CSRF contract, Instagram, Booking Bridge, gallery, CTA and Buti AI tests. Python compilation and Jinja compilation for public/owner/admin templates passed. Public `/beauty-centers` smoke returned **HTTP 200** and verified that all four old KPIs and the new demand section/empty-state text render together.
- **Wider beauty-center sweep:** **80 passed, 10 failed**. Remaining failures are older expectation/integration tests for stage 10, navigation stage 12, homepage card stage 13, SEO stage 14, notifications stage 7, and admin-bot stage 8. The lifecycle/media fixture and Stage 16 form-CSRF assertion that were affected by stale test setup/GET semantics are corrected and pass. No full repository suite was rerun after Stage 5.
- **Full suite (after Stage 3, before Stage 4):** complete run returned **727 passed, 69 failed, 4 skipped, 364 warnings**. Failures span several project areas and include missing `cv2`, stale UI/authorization expectations, environment/file errors and Buti AI tests. One beauty-center owner UI test expects the old label `افزایش دیده‌شدن آگهی`; it remains for separate review. Stage 4 has targeted/combined regressions, not a new full-suite rerun.
- **Privacy:** only internal `final_design_id` and service/style metadata are linked to reservations. The salon does not receive the customer's photo; the reservation UI states this explicitly.
- **Stage 4 and Stage 5:** local and uncommitted; remote branch still at `525e80e`. User requested Stage 5 coding; Stage 6 has not started and awaits confirmation.

## 6. Next Action

- Stage 4–5 were requested for GitHub publication; commit/push the accumulated changes and report 70 targeted passes plus 10 remaining wider-sweep failures. Do not claim the full repository suite is green; pause before Stage 6.
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
