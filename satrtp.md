# satrtp.md — Agent Instructions (VS Code + Cline + Gemini)

Project root (user machine): `C:\Users\Sadeghy\Desktop\giso 3`
All paths below are relative to this root unless they start with `C:\`.

## 0. Scope

- Services in scope: **eyebrow** and **lip** (`lip-shading`) only.
- Scenarios to review: eyebrow flow and lip flow. Other services (nail, hair color, rouge, eyeliner) are out of scope.
- Task: review the project **live** (running app), report **all** issues found in scope, then fix them.
- Language: this file is English. Final reports to the user are in **Persian**.

## 1. Hard rules

1. Code is the source of truth. Docs and graph are secondary; on conflict, read the code and report the divergence.
2. Locked: `bot_edu\`, `web\`, `main.py`. Do not edit without explicit user instruction.
3. `giso\bot.py`: local fix only (1–2 lines). No refactor, no split.
4. Do not edit or delete: `graphify-out\` (except by running `graphify update .`), `project_memory\`, `giso\data\` (`.env`, `giso.db`, `backup\`, `recovery\`, `uploads\`), `bot_edu\data\`, the venv, `.git\`. These hold real keys and real data on the user's machine.
5. Never write keys, tokens, passwords, or private photos into any file, log, or report. Never print values from `giso\data\.env`.
6. No live AI calls unless the user asks. Tests use mocks. A local preview is never reported as a real AI result.
7. No commit or push without user approval. Uncommitted changes do not appear on GitHub.
8. Stop and ask before: any mission-phase change, new dependency, new file outside scope, schema change, deleting or restoring tracked files, or any change to `bot_edu\` or `web\`.
9. Imports: absolute with `giso.` prefix (`from giso.x import y`). Do not add relative imports in `giso\` modules.
10. Preserve each file's line endings (CRLF or LF). Do not reformat unrelated lines.
11. Fixes must be minimal and must not break existing structure. Optimise only code you touch.
12. AI panel: opening the panel must not change any provider, model, slot, or enabled state. Discovery never changes `selected_model`. Auto-fill fills only empty eligible slots and never overwrites a manually set slot. The output-evaluation slot is never auto-set on provider add.

## 2. Reading order (graph first, then docs)

1. `graphify-out\GRAPH_REPORT.md` — communities, hubs, freshness ("Built from commit"). Compare with `git rev-parse HEAD`. If they differ, the graph is stale: say so.
2. `graphify-out\graph.json` (~15 MB) — query by node or edge only. Do not load the whole file. Treat INFERRED edges (~11%) as hypotheses; confirm with a real import or call in code.
3. `GISO_GUIDE.md` (if present in the project root) — §1 architecture, §11 rules, §25 AI, §29 review findings (2026-10-15). Earlier §28 numbers may be outdated.
4. `project_memory\letta\AGENT_START_HERE.md` — latest handoff and reading order.
5. `project_memory\letta\BOOTSTRAP_PROMPT.md`, `PROJECT_MEMORY.md`, `CODE_BOUNDARY_RULES_BUTI_AI.md`.
6. `project_memory\letta\FINAL_IMPLEMENTATION_SCENARIO_BUTI_AI_2026-10-12.md` — mandatory flow for eyebrow and lip (section "قرارداد نهایی آپلود، تحلیل و پیشنهاد مدل"; search for `lip`).
7. `project_memory\letta\SCENARIO_BEAUTY_MIRROR_EYEBROW.md` — user path §3, screen steps §5 (steps 1–10), AI prompts §6.
8. `project_memory\letta\TECHNICAL_DESIGN_BUTI_AI_MVP.md`.
9. `giso-dev\SKILL.md` and `giso-dev\references\*` (see section 3).

## 3. Skill per part (`giso-dev\SKILL.md`)

Always first: the `giso-dev\SKILL.md` pipeline. Run `giso-dev\references\phase-0-freshness.md` before any analysis.

| Part | Code location | Skill / reference |
|---|---|---|
| Freshness, graph check | `graphify-out\`, `git` | `giso-dev\references\phase-0-freshness.md`, `giso-dev\references\stale-handling.md` |
| Section discovery | `giso\buti_ai\` | `giso-dev\references\discovery-method.md` |
| Patterns to mimic | `giso\buti_ai\eyebrow\`, `giso\buti_ai\lip\` | `giso-dev\references\patterns-extraction.md` |
| Eyebrow example | `giso\buti_ai\eyebrow\` | `giso-dev\examples\example-eyebrow.md` |
| Lip flow | `giso\buti_ai\lip\`, `giso\buti_ai\routes.py` | `giso-dev\references\patterns-extraction.md` (mirror eyebrow) |
| Output evaluation (judge) | `giso\buti_ai\output_judge.py` | `giso-dev\references\council-checklists.md` (security, regression) |
| AI panel, categories | `giso\panel\modules\ai.py`, `giso\panel\modules\ai_categories.py`, `giso\panel\templates\modules\ai.html` | `giso-dev\references\discovery-method.md`, `giso-dev\references\scope-lock-template.md` |
| Providers, discovery | `giso\ai_models_registry.py`, `giso\ai_discovery.py`, `giso\ai_consumer_map.py` | `giso-dev\references\patterns-extraction.md` |
| Site consultant (text) | `giso\special_assistant.py`, `giso\buti_ai\consultant.py` | `giso-dev\references\discovery-method.md` |
| Shared services | `giso\buti_ai\services.py`, `image_validation.py`, `mask_recolor.py`, `mediapipe_landmarks.py`, `downloads.py`, `schema.py`, `service_catalog.py` | `giso-dev\references\discovery-method.md`, `giso-dev\references\test-regression.md` |
| Tests | `giso\tests\test_buti_ai_*.py`, `giso\tests\test_ai_*.py` | `giso-dev\references\test-regression.md` |

Each change: Plan + Scope Lock (`giso-dev\references\scope-lock-template.md`), then user approval of that plan, then a minimal edit, tests, diff review, regression check, and final report.

## 4. Live review procedure

**Environment:** Python **3.12** (same as the production server in `deploy\UBUNTU_SETUP.md`). Use `.\.venv\Scripts\python.exe` for every command, never bare `python`. mediapipe is NOT in `requirements.txt`; eyebrow/lip trusted masks need it installed separately (see section 5). Install `requirements.txt` first.

**SECRET_KEY:** the app and the tests refuse to start without a `SECRET_KEY` environment variable (`giso\config.py`). Set it in the same terminal before running them, using a value the user chooses. Never write it to a file. Example (PowerShell): `$env:SECRET_KEY="<user-chosen-value>"`

**Start the app** (from `C:\Users\Sadeghy\Desktop\giso 3`):
- Site only: `.\.venv\Scripts\python.exe giso\app.py` → `http://127.0.0.1:5001`
- All services (dev): `.\.venv\Scripts\python.exe main.py`. Do not change its behaviour.

**Eyebrow route base:** `/analysis/mirror/eyebrow`
- `GET/POST /eyebrow` → model and intensity selection
- `POST /eyebrow/model`
- `GET/POST /eyebrow/upload` → POST 1 must return **200** with the recommendation card (not 302)
- `POST /eyebrow/validate-photo` → quality check and recommendation JSON
- `POST /eyebrow/finalize` with `analysis_confirmed=1` and `final_style` → generation
- `GET /eyebrow/final`, `POST /eyebrow/final/retry`
- `GET /eyebrow/download/image`, `GET /eyebrow/download/report.pdf`
- `GET/POST /eyebrow/centers`, `POST /eyebrow/consultant`

**Lip route base:** `/analysis/mirror/lip-shading` (same flow as eyebrow, via the generic `<service_slug>` routes)
- `/lip-shading`, `/lip-shading/model`, `/lip-shading/upload`, `/lip-shading/validate-photo`, `/lip-shading/finalize`, `/lip-shading/final`, `/lip-shading/download/image`, `/lip-shading/download/report.pdf`, `/lip-shading/centers`, `/lip-shading/consultant`

**Steps per scenario (both services):**
1. Load each page; record HTTP status, redirects, template errors, console errors.
2. Walk the flow in order: model → upload → preview → validate/quality → analysis → two options (Giso suggestion / manual) → user confirmation → final generation → before/after → download (image and PDF) → centers → consultant.
3. Check: POST 1 of upload shows the recommendation (200); POST 2 with `analysis_confirmed=1` uses the same `final_style`; ownership check on candidate and session; no path traversal on download.
4. Check honesty labels: a local preview must not be labelled as AI output.
5. Output evaluation: after generation, the judge (`giso\buti_ai\output_judge.py`) must run for eyebrow and lip. Expected rule: reject only when a model answers `only_target_changed: false`. Fail open when no model is configured, all models error, the answer is unreadable, or the model refuses. At most 2 models are tried. Nail and hair are pixel-only (no judge).
6. Panel check (admin `/admin` → AI): four categories shown (text, image analysis, image generation, output evaluation). Each has its exact options and an "all models" dropdown. Opening the panel changes no state.

**Record each issue as:** `ID | scenario | step | file (relative path) | line | symptom | expected | fix | test`.

**Fix and verify:**
1. Write or update a test that reproduces the issue (mock providers only).
2. **Run tests only on a COPY of the project, never in the real folder.** Some tests delete real backup files (`giso\data\backup`, files named `giso_auto_*` and `giso_backup_*`) and change rows in the real `giso.db` and `bot_edu\data\bot.db`. Create the copy once:
   `robocopy "C:\Users\Sadeghy\Desktop\giso 3" "C:\Users\Sadeghy\Desktop\giso_test" /E /XD .venv`
   (robocopy exit codes 0–7 mean success.)
   Run tests from the copy, using the original venv:
   `cd "C:\Users\Sadeghy\Desktop\giso_test"` then `"C:\Users\Sadeghy\Desktop\giso 3\.venv\Scripts\python.exe" -m pytest giso\tests -q -p no:cacheprovider`
3. Related tests in the copy, for example `-k "buti_ai or ai_"`, plus `test_admin_ai_panel.py`, `test_ai_panel_model_categories.py`, `test_ai_output_judge.py`, `test_ai_autofill_slots.py`.
4. Make the minimal fix in the real folder, in the file that owns the behaviour. Then re-run the same tests in the copy after copying the changed file over.
5. Run `.\.venv\Scripts\python.exe -m py_compile` on changed files.
6. Check the diff: no unrelated lines, line endings preserved.
7. Never delete anything under `giso\data\` or `bot_edu\data\`. The copy folder may be deleted after use.

## 5. Known baseline (do not treat as new regressions)

- Current baseline at `36cafce` (Python 3.11 sandbox run, `SECRET_KEY` set, `requirements-landmarks.txt` restored): **45 failed, 789 passed, 4 skipped**. The landmarks test passes. The 45 failing tests are the same as the earlier baseline. Failing files are listed in `GISO_GUIDE.md` §29.5.
- A Python 3.12 run has not been done yet. Compare its result with this baseline before reporting.
- `requirements-landmarks.txt` is restored. Its own comment says `pip install -r requirements.txt -r requirements-landmarks.txt`, but that pulls `opencv-contrib-python` (dry-run verified), which the file warns against. Correct install: install the landmarks support packages without the mediapipe line, then `.\.venv\Scripts\python.exe -m pip install --no-deps "mediapipe==0.10.21"`. Fixing the file itself needs user approval. Report it if it comes up.
- Pre-existing failures in `test_ai_widget.py`, `test_bot_permission_fix.py`, and `test_buti_ai_eyebrow_inpainting_request.py` predate the AI rebuild.
- Before reporting a regression, compare with the baseline failure list.

## 6. Final report (Persian)

- Issues found (ID, scenario, file, symptom), grouped by eyebrow and lip.
- Fixes applied (file, problem, fix).
- Tests run (where, which Python version) and exact results.
- Live checks performed and results. State clearly which steps were not run (for example, live AI).
- Remaining issues and next steps.
- Remind the user: uncommitted changes will not appear on GitHub; ask for approval before any commit or push.
