# Letta setup for Giso4 Project Memory

This directory contains local Letta tooling for Project Memory. It is isolated from the Giso runtime and does not change Flask/Bot code paths.

## Installed package

- CLI package: `@letta-ai/letta-code`
- Resolved version used during setup: `0.33.2`
- Helper dependency: `ws@8.22.0`
- Node used during setup: `v22.22.3`
- npm used during setup: `10.9.8`

Install/refresh dependencies:

```bash
npm install --prefix tools/letta --ignore-scripts --no-audit --no-fund
```

Why `--ignore-scripts` was used in the setup sandbox: the normal install attempted to rebuild `node-pty` and failed while fetching Node headers. The CLI and local backend operations worked, but interactive TUI/PTY features may be incomplete until a normal install/rebuild succeeds on a machine with the needed prerequisites.

On a persistent machine/server with network access, run a normal install if full TUI/PTY support is needed:

```bash
npm install --prefix tools/letta --no-audit --no-fund
```

## What is committed

Committed setup files are only reproducible tooling and Project Memory bootstrap data:

- `tools/letta/package.json`
- `tools/letta/package-lock.json`
- `tools/letta/README.md`
- `tools/letta/bootstrap-memory.sh`
- `tools/letta/mcp.hosted.example.json`
- `project_memory/letta/*`

Not committed:

- `tools/letta/node_modules/`
- local Letta backend data
- local runtime agent IDs
- local backend paths
- smoke-test memory artifacts
- API keys or provider secrets

## Local commands

```bash
# Show CLI version/help
./tools/letta/node_modules/.bin/letta --version
./tools/letta/node_modules/.bin/letta --help

# Inspect repo context without creating an agent
./tools/letta/node_modules/.bin/letta --info

# List local backend agents
./tools/letta/node_modules/.bin/letta --backend local agents list --limit 20

# Create/reuse a project memory agent by name
./tools/letta/node_modules/.bin/letta --backend local agents create \
  --name giso4-project-memory \
  --personality blank \
  --description "Giso4 Project Memory agent" \
  --tags giso4,project-memory

# Export an agent's memory for inspection
./tools/letta/node_modules/.bin/letta --backend local memory export \
  --agent <agent-id> \
  --out <export-dir>

# Connect a provider when credentials are available
./tools/letta/node_modules/.bin/letta connect <provider>
```

## Project Memory seed

Read the structured repo memory first:

```bash
cat project_memory/letta/PROJECT_MEMORY.md
```

Recommended files to import into a Letta Project Agent named `giso4-project-memory`:

```text
project_memory/letta/PROJECT_MEMORY.md
project_memory/letta/PROJECT_MEMORY.json
project_memory/letta/BOOTSTRAP_PROMPT.md
project_memory/letta/UPDATE_TEMPLATE.md
```

A good destination inside the Letta agent MemFS is:

```text
projects/giso4/
```

The local backend persistence path was verified during setup, but machine-local runtime IDs and paths are intentionally omitted from Git. Recreate/reuse the Project Agent by name in each environment.

## MCP

See `mcp.hosted.example.json` for a hosted MCP configuration template. The template contains placeholders only; never commit real API keys.

MCP is not required for a single local workflow using this repo and local Letta CLI. MCP/App Server/Cloud becomes useful only when an external Coding Agent needs shared access to the same Project Memory agent.
