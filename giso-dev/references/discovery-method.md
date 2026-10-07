# Discovery Method — locating the section in the CURRENT tree

Goal: end with a concrete file inventory for the target feature, derived from
the live tree — never from memory of a previous session.

## 1. Expected anchors (verify, never trust)

The repo is expected to contain these top-level anchors: `giso/` (main Flask
app + bot + AI), `bot_edu/` (education bot, restricted), `web/` (education
site, decoupled), `main.py` (launcher), `PROJECT_GUIDE.md`, `GISO_GUIDE.md`,
`project_memory/letta/`, `graphify-out/`. If an anchor is missing or renamed,
the map has changed: list what you actually see and adapt; report the gap.
Confirm by `ls` of the repo root, not from this file.

## 2. Domain → folder (the golden rule)

Project convention (GISO_GUIDE §11.2 "هر ماژول در پوشهٔ خودش"): a feature's
code lives in a folder named after its domain, e.g. a hair/eyebrow service
lives in `giso/<service-domain>/`, market in `giso/marketplace/`. Confirm by:
- `Get-ChildItem giso -Directory` and match the domain name;
- if no folder matches, grep the domain word across `giso/`, `bot_edu/`,
  `web/` (exclude `venv`, `__pycache__`, `graphify-out/cache`) and follow the
  strongest cluster of hits.

## 3. Blueprint discovery

Read the module's `__init__.py`: the Flask `Blueprint` gives the `url_prefix`
and which submodules it imports. This is the module's public surface — start
reading from `routes.py` outward.

## 4. Module file conventions

Modules of this project follow a shape like (all optional, verify per module):
`schema.py` (tables + migrations), `routes.py` (blueprint views),
`services.py` (logic), `bot_handlers.py` (Bale/Telegram flow), `panel*/`
(admin+user panel views), `templates/<module>/`, `static/<module>.js|css`.
A feature request may touch any subset; decide from the request, list each
touched file with a one-line reason in the plan.

## 5. Cross-module discovery

- **Imports**: from each target file, list what it imports (project-internal
  only). Each internal import is a dependency edge to record.
- **Shared DB**: business data lives in `giso/data/giso.db` (single source of
  truth for site+bot); `bot_edu/data/bot.db` holds shared config tables
  (e.g. `giso_config`, `giso_admins`). Check the target's `schema.py` for
  which DB it reads/writes and whether it touches shared tables.
- **Notifications**: modules hook `panel/modules/notifications`
  (event → notification). Check whether the feature emits or consumes
  notifications.
- **AI runtime**: AI features route through `giso/ai_runtime*` and the
  Gemini proxy manager; check provider/credit coupling when touching AI code.
- **Siblings**: list the module's sibling services/features and read one
  sibling end-to-end (routes→services→schema→templates) to establish the
  house pattern.

## 6. Graph / Memory / Docs as accelerators (not truth)

- Graphify: only when fresh (phase-0 result). Use `GRAPH_REPORT.md`
  community hubs and suggested questions to find cross-community bridges.
- Project Memory: read scenario/decision files naming the target domain
  (`CODE_BOUNDARY_RULES_*`, `SCENARIO_*`) for boundary rules that constrain
  the change.
- Guides: `PROJECT_GUIDE.md` § (system map + laws), `GISO_GUIDE.md` § (modules,
  notifications, regression contracts §9, development rules §11). Verify each
  cited section against code before relying on it; mark STALE sections.
