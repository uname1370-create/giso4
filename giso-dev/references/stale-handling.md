# Stale Source Handling

## Source-of-truth order

1. **Live code** — always.
2. **Project guides** (`PROJECT_GUIDE.md`, `GISO_GUIDE.md`) — contracts, laws,
   regression history; verify each cited section against code.
3. **Project Memory** (`project_memory/letta/`) — decisions, boundaries,
   where-last-left-off; may lag code.
4. **Graphify** (`graphify-out/`) — navigation aid only, and only when its
   "Built from commit" equals current HEAD.

## Divergence protocol

- Code vs guide/memory/graph disagree → code wins; record the divergence in
  the plan's "Divergences found" line (source, what it says, what code says).
- Never silently drop a stale source; never silently "fix" the stale source.
- Updating `project_memory/` or `graphify-out/` is a separate, explicit task:
  suggest it in the final report, execute only on explicit instruction.

## Re-derivation on staleness

When phase-0 marks the graph STALE or docs STALE:
- Re-derive structure with the discovery-method procedure (folder rule,
  blueprint read, import walk, sibling read).
- In the report, replace stale-source claims with evidence from this session.
- Note which stale source should be refreshed (and how: `graphify update .`
  for the graph; guide edits are user-directed).
