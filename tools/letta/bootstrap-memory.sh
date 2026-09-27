#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LETTA_BIN="$ROOT/tools/letta/node_modules/.bin/letta"
PROMPT_FILE="$ROOT/project_memory/letta/BOOTSTRAP_PROMPT.md"
if [[ ! -x "$LETTA_BIN" ]]; then
  echo "Letta CLI not installed. Run: npm install --prefix tools/letta --ignore-scripts --no-audit --no-fund" >&2
  exit 1
fi
if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Missing $PROMPT_FILE" >&2
  exit 1
fi
cd "$ROOT"
"$LETTA_BIN" --backend local --memfs -p "$(cat "$PROMPT_FILE")"
