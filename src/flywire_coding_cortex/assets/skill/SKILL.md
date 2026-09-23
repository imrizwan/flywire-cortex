---
name: flywire-coding-cortex
description: >-
  Runs FlyWire-derived LIF neurons via the flywire-cortex connector and maps
  population rates to coding drives. Use when coding, debugging, or when the
  user mentions FlyWire cortex, connectome thinking, or flywire-cortex.
---

# FlyWire Coding Cortex

Install once (`pip install flywire-coding-cortex`), then use
`flywire-cortex` / MCP in every session.

**This is not a metaphor-only skill.** You must call the CLI (or MCP tools)
so real connectome edges are stepped. Do not invent biological fidelity.

## Ensure installed

If `flywire-cortex` is missing:

```bash
pip install flywire-coding-cortex
# or from a clone: pip install -e .
flywire-cortex fetch --profile seed
flywire-cortex install
```

Never auto-run `--profile full` (~10.6 GB). Ask the user before `codex` or `full`.

## Every coding turn

1. `flywire-cortex status` — auto-hint if circuit missing; `fetch --profile seed` if needed
2. `flywire-cortex sense --text "<task>"` — task → sensory currents
3. `flywire-cortex step --ms 50` — run LIF on real edges
4. `flywire-cortex signals` — read primary drive + clamps
5. **Act only under the primary drive** (see [roles.md](roles.md))
6. Follow [practices.md](practices.md) (winner-take-most, inhibition delay, sparse diffs)
7. After verify: `flywire-cortex remember strengthen|weaken …`

Optional MCP tools: `cortex_status`, `cortex_sense`, `cortex_step`, `cortex_stimulate`, `cortex_signals`, `cortex_remember`.

## Profiles

| Profile | Size | Command |
|---|---|---|
| seed | ~MB | `flywire-cortex fetch` |
| codex | ~60–300 MB | `flywire-cortex fetch --profile codex` |
| full | ~10.6 GB | `flywire-cortex fetch --profile full --yes` |

## Hard rules

- One primary drive per turn
- After high risk / `gf` stop: list blast radius before edits
- Strengthen memory only when tests/user verification pass
- Cite FlyWire data as CC BY-NC derived; dynamics are a model
