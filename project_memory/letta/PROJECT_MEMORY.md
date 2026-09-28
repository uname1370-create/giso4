# Giso4 Project Memory

Last Update: 2026-09-27 (Asia/Tehran)
Last Agent: Arena.ai Agent Mode
Last Model: not recorded; this memory is intentionally model-agnostic.
Status: Project Memory and local Letta setup are prepared for handoff. The product scenario `آینه ابرو گیسو` has been documented in Project Memory, but no Giso feature/refactor/migration/scenario has been executed.

---

## 1. Layer Contract

Keep these layers separate:

- **Git/GitHub** = source of truth for code and tracked repository files.
- **Graphify** = structural/dependency map of code only; useful for navigation, not a replacement for code review or Project Memory.
- **Project Memory** = independent project state: architecture, rules, decisions, progress, known issues, current stage, and handoff.
- **Letta** = optional agent memory layer when actually initialized/used; local backend persistence was verified during setup.
- **Coding Agent** = execution/change layer.

---

## 2. Project Identity

- Repository: `https://github.com/uname1370-create/giso4`
- Arena branch: `arena/01a0e0b8-giso4`
- Local checked branch during setup: `arena/01a0e0b8-giso4`
- Local HEAD during memory setup: `c9b198cd8505f1e97c470aea4fae034948144548` (`Delete graphify-out directory`)
- Fetched remote branch HEAD during setup: `10017eccdd23292bab494a0cfe13cdda924a2c27` (`Create sena.md`)
- Repository was shallow/grafted in the setup workspace.
- Local working tree was behind the fetched remote branch. Do not blindly pull/reset/force-checkout; local untracked `graphify-out/` may conflict with remote tracked `graphify-out/`.

---

## 3. Current Git State at Last Memory Update

Observed status before committing memory setup:

```text
## arena/01a0e0b8-giso4
 M .gitignore
?? graphify-out/
?? project_memory/
?? tools/
```

Meaning:

- `.gitignore` was modified only to ignore local Letta dependency/env files.
- `project_memory/` and `tools/letta/` contain the Project Memory and Letta setup files intended for Git.
- `graphify-out/` exists locally as an untracked artifact and should not be committed unless explicitly requested.
- No files under `giso/`, `web/`, `bot_edu/`, or `main.py` were modified for the memory setup.

---

## 4. `sena.md` Status

- `sena.md` exists on the fetched remote branch `origin/arena/01a0e0b8-giso4`.
- Verified blob SHA during setup: `dee8def86cb376d431576ac858027320892eb2ce`.
- Size observed during setup: about `74044` bytes / `2242` lines.
- Local checkout at `c9b198c` did not contain `sena.md`.
- User correction: `sena.md` is **not** the final executable scenario. It is temporary conversation/review/analysis material.
- Do not execute `sena.md`.
- Do not implement features from `sena.md` unless the user later gives explicit final scenario scope.
- Do not choose another scenario file automatically.

High-level non-execution reading: `sena.md` discusses a possible “Giso Beauty Mirror / آینه زیبایی گیسو” direction involving analysis, service selection, image validation, AI service-specific analysis, preview/before-after, consultant, beauty centers, reservations, leads, wallet/credits, and panels. Treat this only as idea/audit material until the user defines the real final scenario.

---

## 5. Project Architecture

### Root

- `main.py`: unified launcher for education bot, education web, Giso web, and Giso bot watcher depending on env/token availability.
- `env_loader.py`: environment loader.
- `requirements.txt`: Python dependencies.
- `PROJECT_GUIDE.md`: high-level monorepo guide.
- `GISO_GUIDE.md`: detailed Giso architecture and rules.

### `giso/`

Active Giso product area when user later authorizes implementation. Important areas:

- `giso/app.py`: Flask app and route registration; installs final analysis override.
- `giso/wsgi.py`: production WSGI entrypoint; also installs final analysis override.
- `giso/base.py`: central DB/config helpers such as `get_giso_db_conn` and `get_bot_db_conn`.
- `giso/db_core.py`, `giso/db_engine.py`: managed DB/SQLite/Postgres boundary.
- `giso/models.py`: SQLAlchemy models and migration/init logic.
- `giso/config.py`: Flask config and superadmin identity logic.
- `giso/security.py`: CSRF/rate-limit/audit/security headers.
- `giso/bot.py`: large Giso Bale bot; do not refactor/split.
- `giso/analysis.py`: smart hair/skin analysis routes and AI flow.
- `giso/analysis_final_override.py`: active runtime patch for final analysis.
- AI layers: `ai_brain.py`, `ai_runtime.py`, `ai_runtime_policy.py`, `ai_config.py`, `ai_models_registry.py`, `ai_discovery.py`, `ai_health.py`.
- `giso/prompts/`: AI prompts.
- `giso/panel/`: admin/superadmin panel modules.
- `giso/panel_user/`: normal user dashboard modules.
- `giso/shop/`: shop routes/checkout/channel bridge/bot/panel logic.
- `giso/marketplace/`: C2C hair marketplace.
- `giso/beauty_centers/`: beauty center directory/chat/reservation/pricing/bot integration.
- `giso/wallet*.py`: wallet, missions, Balepay, receipts.
- `giso/templates/`, `giso/static/`: public/admin/user templates and assets.
- `giso/tests/`: independent test scripts.

### `bot_edu/`

Education Bale bot and shared Giso bridge files. Project guides mark this area locked unless explicitly requested.

### `web/`

Separate education Flask website. Project guides mark this area locked unless explicitly requested.

### `deploy/`

Deployment/systemd/nginx/server docs and service files.

---

## 6. Important Directories and Rules

| Path | Purpose | Rule |
|---|---|---|
| `giso/` | Active Giso product code | Modify only when user authorizes implementation |
| `giso/bot.py` | Large Bale bot | Do not refactor/split |
| `giso/data/` | Runtime DB/data/uploads/local env | Do not commit secrets/DB/uploads |
| `giso/prompts/` | AI prompts | Change only with explicit prompt task |
| `bot_edu/` | Education bot/shared bridge | Locked unless explicitly requested |
| `web/` | Education website | Locked unless explicitly requested |
| `main.py` | Unified launcher | Read-only during memory/setup phase |
| `graphify-out/` | Graphify structural map | Do not commit/regenerate unless requested |
| `tools/letta/` | Local Letta CLI setup | Tooling only, not Giso runtime |
| `project_memory/letta/` | Durable Project Memory | Read before work, update after work |
| `sena.md` | Temporary discussion/analysis material | Not final scenario; do not execute |

Core rules:

- Stay on branch `arena/01a0e0b8-giso4` in this Arena session.
- Check `git status --short --branch` before modifications.
- Do not run `sena.md` or any scenario until the user explicitly gives the final scenario.
- Do not make functional Giso changes during memory/setup work.
- Do not store secrets, DB files, uploads, runtime logs, `node_modules`, or Letta local backend data in Git.

---

## 7. Graphify Findings

Graphify must remain separate from Project Memory.

Local `graphify-out/` in the setup workspace:

- Exists locally but is untracked at local HEAD.
- Local report said it was built from commit `36856ba2`.

Fetched remote branch:

- Tracks `graphify-out/` files.
- Remote report said it was built from commit `c9b198cd`.
- Some local and remote Graphify blobs differed.

Observed graph stats:

- Nodes: `7755`
- Links/edges: `24200`
- Hyperedges: `0`
- Manifest entries: `371`
- Communities: `241`
- Confidence counts:
  - `EXTRACTED`: `21462`
  - `INFERRED`: `2738`

Coverage limitations:

- code-oriented / cluster-only output
- no HTML nodes observed
- no TXT/Markdown nodes observed
- prompt/template/scenario content is not represented as content knowledge

Rule: use Graphify as a navigation map, then verify in source. Do not treat `INFERRED` edges as facts without code verification.

---

## 8. Letta Setup

Local isolated Letta tooling is under `tools/letta/`.

- Package: `@letta-ai/letta-code@0.33.2`
- Helper dependency: `ws@8.22.0`
- Node used during setup: `v22.22.3`
- npm used during setup: `10.9.8`
- Local binary: `./tools/letta/node_modules/.bin/letta`

Install notes:

- Normal install failed in the sandbox while rebuilding `node-pty` because Node headers could not be fetched.
- Successful install used `--ignore-scripts`.
- CLI commands such as `--version`, `--help`, `server --help`, and local backend agent operations worked.
- `node-pty` native module was not built, so interactive TUI/PTY behavior may be incomplete until a normal install/rebuild succeeds.
- Letta Cloud was not authenticated during setup; no API key/provider secret is stored in the repo.

Project Agent guidance:

- Use/create local Project Agent name: `giso4-project-memory`.
- This Agent is for persistent Project Memory only, not code execution.
- Import/refresh the repo memory files under an agent memory path such as `projects/giso4/`.
- Do not commit local Letta backend paths, local runtime agent IDs, or smoke-test memory artifacts.
- Local backend persistence and handoff behavior were verified during setup, but exact runtime IDs and machine-local paths are intentionally omitted from Git.

---

## 9. MCP / External Agent Access

- MCP is not required for a single local workflow that can read `project_memory/letta/` or use the local Letta CLI.
- External Coding Agents cannot read the local Letta Project Agent unless they share the same filesystem/local backend or an access layer is exposed.
- For cross-agent access outside this sandbox, use one of:
  - shared filesystem/local backend,
  - Letta App Server,
  - hosted/cloud Letta,
  - MCP/API integration.
- Hosted MCP endpoint from Letta docs: `https://api.letta.com/mcp`.
- Example config is in `tools/letta/mcp.hosted.example.json`; it contains placeholders only and must never contain real API keys.

---

## 10. Known Issues / Cautions

- Local checked branch is behind the fetched remote branch containing `sena.md` and tracked `graphify-out/`.
- Local untracked `graphify-out/` may block or complicate a future fast-forward.
- `sena.md` is temporary discussion/analysis material, not the final scenario.
- Letta install used `--ignore-scripts`; `node-pty` native module may be missing.
- Letta Cloud/provider execution is not configured by this repo setup.
- External Coding Agents need shared filesystem, App Server, Cloud, MCP, or API integration to read/update the same local Letta Project Agent directly.
- Graphify includes inferred edges and omits HTML/Markdown/prompt content nodes.
- `analysis_final_override.py` patches final analysis behavior from `app.py`/`wsgi.py`; runtime may differ from `analysis.py` body.
- Prior audit notes mention possible analysis override divergence around wallet/mission/finalization; re-verify before billing/finalization changes.
- AI provider/failover paths for runtime chat and analysis vision are not necessarily identical; verify before changing AI behavior.

---

## 11. Decisions

- Keep Project Memory separate from functional Giso code.
- Keep `project_memory/letta/` as durable, model-agnostic handoff state in Git.
- Keep `tools/letta/` as isolated local tooling, not root runtime dependencies.
- Keep Graphify as structural map only.
- Keep `sena.md` as temporary analysis/conversation material until the user defines the final scenario.
- Do not store local Letta backend data, local agent IDs, smoke-test artifacts, secrets, or runtime paths in Git.
- MCP remains optional; use it only when external cross-agent access requires it.

---

## 12. Completed Work

- Checked Git state before setup.
- Reviewed project guides and real repository structure.
- Verified `sena.md` exists on the fetched remote branch and is temporary discussion material only.
- Reviewed Graphify output and recorded scope/limitations.
- Installed local Letta CLI tooling under `tools/letta/`.
- Verified local Letta backend can persist memory across separate invocations.
- Created repo-local Project Memory files for future agents.
- Created instructions for future Letta Project Agent creation/import.
- Did not modify `giso/`, `web/`, `bot_edu/`, or `main.py`.
- Did not execute any scenario.
- Documented the technical MVP design for Buti AI in `project_memory/letta/TECHNICAL_DESIGN_BUTI_AI_MVP.md`.

---

## 13. Active Product Scenario — آینه ابرو گیسو

Scenario file:

```text
project_memory/letta/SCENARIO_BEAUTY_MIRROR_EYEBROW.md
```


Technical MVP design file:

```text
project_memory/letta/TECHNICAL_DESIGN_BUTI_AI_MVP.md
```

Current status:

- Product/UX scenario is documented.
- Technical MVP design is documented.
- No Giso code has been changed for this scenario yet.
- This scenario should be implemented only after explicit user approval for code changes.

Scenario summary:

```text
ورود سایت
→ آینه زیبایی گیسو
→ آینه ابرو
→ انتخاب مدل/سلیقه
→ آپلود عکس
→ بررسی کیفیت عکس
→ تحلیل هوشمند ابرو
→ نتیجه پیشنهادی
→ پیش‌نمایش قبل/بعد
→ مراکز مرتبط
→ رزرو
```

Product decisions:

- Route/name should be broad: **آینه ابرو گیسو**.
- Do not name the whole flow only **میکروبلید**; microblading is one technique, not the full product.
- Architecture must be modular: the Beauty Mirror/Buti AI capability lives primarily in **`giso/buti_ai/`** and must not be scattered across unrelated Giso modules.
- Product UI name can be Persian, but the technical module/folder name is **Buti AI / `buti_ai`**.
- Starting eyebrow options:
  - طبیعی و نچرال
  - میکروبلیدینگ ظریف
  - شیدینگ پودری
  - کامبینیشن
  - نمی‌دانم؛ گیسو پیشنهاد بدهد

Use existing Giso capacity when implementation starts, but keep ownership modular:

- `giso/buti_ai/` is the owner module for Beauty Mirror/Buti AI routes, services, templates, prompt orchestration, state, and scenario logic.
- `giso/analysis.py` may provide upload/analysis patterns only; do not move eyebrow mirror business logic there.
- `giso/ai_brain.py` may provide AI provider/vision integration only; keep scenario orchestration in `giso/buti_ai/`.
- `giso/prompts/` may hold prompt files only if this matches existing Giso conventions; names must clearly belong to `buti_ai`.
- `giso/beauty_centers/` is for center listing/reservation/lead connection only; do not make it the owner of mirror logic.

Constraints:

- Do not break current hair/skin analysis.
- Do not change `bot_edu/`, `web/`, or `main.py` for this scenario.
- Do not refactor/split `giso/bot.py`.
- Do not scatter Beauty Mirror code across unrelated modules; prefer `giso/buti_ai/` with thin integrations only.
- Execute stages in order: memory → technical MVP design → base wizard → AI analysis → preview/fallback → centers/reservation → panels/stats/wallet.
- `sena.md` remains temporary idea/audit material, not the final executable scenario by itself.

---

## 14. Next Action

Before real Giso work:

1. Run `git status --short --branch`.
2. Read `project_memory/letta/PROJECT_MEMORY.md` and `PROJECT_MEMORY.json`.
3. If using Letta Local, create/reuse an agent named `giso4-project-memory` and import/refresh the Project Memory files.
4. Carefully decide how to reconcile local branch with remote `origin/arena/01a0e0b8-giso4`, because local `graphify-out/` is untracked while remote tracks Graphify output.
5. Read `project_memory/letta/TECHNICAL_DESIGN_BUTI_AI_MVP.md` before code implementation.
6. Wait for explicit user approval before functional Giso code changes.
7. Do not execute `sena.md` or any other scenario until explicitly instructed.

---

## 15. Update Protocol

At the end of meaningful work:

1. Update this file and `PROJECT_MEMORY.json`.
2. Record branch, HEAD, and `git status --short --branch`.
3. Record durable architecture findings only after verification.
4. Keep Graphify findings separate from code-verified facts.
5. Record decisions and rationale.
6. Record known issues only if verified or clearly labeled as prior context.
7. Do not store secrets, credentials, DB files, uploads, logs, `node_modules`, local Letta backend data, local agent IDs, or smoke-test artifacts.
