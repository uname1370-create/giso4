# Example — «ابرو را درست کن»

> Teaching example of the PATH, not the answer. File names, behavior, and
> findings below reflect one historical state; re-derive everything from the
> current tree. If anything here contradicts the live code, the live code
> wins and this example silently goes stale.

## What the pipeline does for this request

**Understand.** "درست کن" is ambiguous: broken UI? broken preview image?
wrong landmark/mask output? missing save? One clarifying question
("دقیقااً کجا خرابه؟" + the observed symptom) or, if the symptom is given in
context, restate it as: domain = eyebrow (Buti AI mirror), surface = site
(`/analysis/mirror/...` — verify), layer = UI+logic+AI, expected = wizard
completes and shows a correct composite.

**Section identification.** Golden rule → `giso/buti_ai/` domain folder,
eyebrow service inside it. Read `buti_ai/__init__.py` for the blueprint prefix;
read `eyebrow/` files (flow, final design, image generation, upload,
landmarks, mask) and its templates + `static/buti_ai.js|css`. Grep
`giso/tests/` for eyebrow/mirror test names.

**Patterns.** Sibling services in the same module (hair color, lip, nail) are
the nearest neighbors: compare each seam (route shape, AI call entry, image
validation, result storage, panel hooks). The fix must extend what they do,
not invent a new flow.

**Dependencies/impact.** Shared AI runtime + Gemini proxy + credits; image
validation module; static assets shared by all mirror services; tests named
after the mirror stages.

**Council.** Security pass: upload path + image handling (validation is the
house control). Regression pass: changing a shared helper breaks every
sibling service's wizard → run all their tests, not just eyebrow's.

**Plan + Scope Lock.** Allowed: the eyebrow files + shared assets ONLY if the
fix genuinely needs them; forbidden: siblings' features, bot, panels, DB
schema unless a migration is explicitly part of the goal. Present, STOP.

**After approval.** Re-check HEAD; edit; run mirror test files +
`python -c "import giso.wsgi"`; `git diff` hunk-walk; regression sweep over
sibling services; final report + suggestions (graph/memory refresh) only.

The failure mode this example prevents: diving into eyebrow code on day one
because "the user said fix it" — the pipeline forces discovery, plan, and
approval first.
