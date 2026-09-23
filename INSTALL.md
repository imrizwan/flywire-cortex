# Install

## Package

```bash
pip install -e .
# or: uv tool install .
```

## Circuit

```bash
flywire-cortex fetch --list-profiles
flywire-cortex fetch --profile seed
# heavier:
flywire-cortex fetch --profile codex
flywire-cortex fetch --profile full --yes
```

## Agent wiring

```bash
flywire-cortex install
```

Copies `skill/` into:

- `~/.cursor/skills/flywire-coding-cortex`
- `~/.openclaw/workspace/skills/flywire-coding-cortex` (and `~/.openclaw/skills/` when present)
- `~/.claude/skills/flywire-coding-cortex`

Writes MCP snippet to `~/.flywire-coding-cortex/mcp.snippet.json`.

## Verify

```bash
flywire-cortex status
flywire-cortex step --ms 20 --text "urgent hotfix failing test"
flywire-cortex signals
```
