# Giso4 Project Memory — Current Handoff

Last Update: 2026-10-12 (Asia/Tehran)
Branch: arena/7f567e47-giso4
HEAD: 03f3733 Eyebrow output: port test-branch output handling (mask blur, PNG save, validated composite)
Agent: Manus technical audit / handoff
Status: Current product direction is the four-service Buti AI scenario: eyebrow, lip, blush, eyeliner. Read AGENT_START_HERE.md and FINAL_IMPLEMENTATION_SCENARIO_BUTI_AI_2026-10-12.md before coding.

Historical FINBUTI state remains below for context.

---

## 1. Layer Contract
- Git/GitHub = source of truth
- Graphify = structural map, now fresh (graph.json 2026-10-06 22:08 UTC after da0cc1f 21:42 UTC)
- Project Memory = independent state, now updated to FINBUTI
- Letta = optional memory layer
- Coding Agent = execution layer

## 2. Project Identity
- Repository: https://github.com/uname1370-create/giso4
- Branch: arena/01a0eecf-giso4
- HEAD: da0cc1f FINBUTI P1 Admin
- Previous FINBUTI commits: 274942f P0+P1, 4afbd2b remove specialist, da0cc1f admin
- Remote: origin/arena/01a0eecf-giso4 exists, up to date

## 3. Current Git State
```
## arena/01a0eecf-giso4
clean at da0cc1f
```
No forbidden paths modified, migrations additive idempotent.

## 4. FINBUTI Scope
P0 Completed: Mirror History → User Panel, 4 tabs ابرو/مو/آرایش/ناخن, زیبایی من grouping, public salon lux per 3d site.md
P1 Completed: service_key/is_featured_service in beauty_center_services, service_key in beauty_center_images, portfolio per-service, owner management, reservation linkage final_design_id/service_key/selected_style, admin services/portfolio/reservations/mirror + analytics all services
P1 Skipped by design: specialist_user_id only if needed, Bale Mirror Flow scope inactive
P2 Out of Scope: specialist table, staff table, wishlist, Instagram/Logo, AI boosting, images 800+, new arch, bot rewrite

## 5. Architecture
- giso/app.py: create_app()
- beauty_centers: registration, approval, services with service_key/is_featured_service, hours, gallery with service_key, reservations with mirror linkage, chat, feedback, promotions
- beauty_centers/pricing: services + working hours
- beauty_centers/reservations: reservation flow snapshot + mirror linkage
- buti_ai: eyebrow baseline + nail/hair_color/lip_shading generic, service_catalog, upload/quality/detection/analysis/generation/validation/final, history buti_ai_final_designs, consultant, centers enrichment
- panel_user: overview, زیبایی من (beauty_centers_list,reservations,center_chats,analyses), beauty_center owner
- panel: admin beauty_centers tabs requests/published/paused/services/portfolio/reservations/mirror/promotions/feedback/settings/dashboard

## 6. Important Rules
Code Truth, Reuse > Extend > New, no parallel systems, no eyebrow baseline mod, no bot.py/bot_edu/web/main.py refactor, no hard-coded API keys, no fallback as AI, migrations additive, luxury minimal per 3d site.md, specialist not part, Bale only if active

## 7. Graphify Findings
graph.json 2026-10-06 22:08 UTC after da0cc1f 21:42 UTC — fresh for FINBUTI. Nodes 7755, links 24200, communities 241. Includes service_key/is_featured_service, mirror history, admin tabs.

## 8. Decisions
- Extend panel_user, not parallel analysis module
- Luxury minimal per 3d site.md, selective 3D only if real value else CSS/SVG
- service_key/is_featured_service migration additive
- Reservation snapshot preserved + mirror linkage
- Admin extended with 4 new tabs
- Specialist removed per 4afbd2b
- Bale left as P2

## 9. Completed Work
Freshness Audit, P0 User Panel, P0 Public Detail Lux, P1 Service-Level Data, P1 Owner/Admin, Security/Performance/SEO/A11y/Responsive/Regression, Graph+Memory updated

## 10. Next Actions
- Bale Mirror if scope active: adapter only in giso/buti_ai/bale_handlers reusing service_catalog/generic_service
- specialist_user_id only if real need
- Keep graphify fresh via graphify update

## 11. Validations
- SECRET_KEY=test python -m venv test: app create_app() → list 200, admin 302, analyses 302→login
- Migrations: beauty_center_services cols include service_key/is_featured_service, images include service_key
- No secrets, no data loss


## 12. Current Buti AI Implementation Handoff — 2026-10-12

### Product decision
- Four target services: `brow`, `lip_shading`, `blush`, `eyeliner`.
- Eyebrow and lip use the main AI/inpainting path. Blush and eyeliner start with deterministic local preview, then provider integration only after real benchmark.
- Recommended provider chain: Cloudflare inpainting → AvalAI image edit → local preview.
- Hoosha is not a production provider until an official server-to-server image-edit/mask API, auth, pricing and SLA are verified.

### Required implementation contracts
- Add cost ledger, provider attempt tracking, user charge, idempotency key, quota and circuit breaker before public launch.
- Offline output must have `local_preview` status and must never be presented as real AI output.
- Keep Buti AI logic inside `giso/buti_ai/`; do not refactor `giso/bot.py`, `bot_edu/`, `web/` or `main.py` without explicit authorization.
- Heavy image generation must run through a queue/worker, not the main Bale handler or a long synchronous web request.

### Canonical documents
- `project_memory/letta/AGENT_START_HERE.md`
- `project_memory/letta/FINAL_IMPLEMENTATION_SCENARIO_BUTI_AI_2026-10-12.md`
- `project_memory/letta/BOOTSTRAP_PROMPT.md`
