# FlyWire Coding Cortex

**Pip-installable connector** for AI coding agents: install once, then every
Cursor / OpenClaw / Claude session can **run FlyWire-derived neurons** (leaky
integrate-and-fire on real synapse edges) and map population rates into
**coding drives** (implement, stop, reverse, steer, groom).

| | |
|---|---|
| **Code license** | MIT |
| **Circuit data** | FlyWire-derived, [CC BY-NC 4.0](data/DATA_LICENSE.md) |
| **Anatomy browser** | [FlyWire Codex](https://codex.flywire.ai/) |
| **Default seed** | 668 neurons · ~19k signed edges (FAFB v783 escape/steering subgraph) |

> **Honesty bar:** Wiring and contact counts come from public FlyWire data.
> Membrane dynamics, task→current encoding, and the rate→coding map are
> **models**. This does not claim biologically calibrated coding skill or that
> a fruit fly “understands” your codebase.

---

## Why this exists

Most agent “skills” are markdown instructions. This package is a
**pip-installable tool** plus an ambient skill/MCP connector so agents can
call a real runtime every session—without cloning a folder into every project.

```text
coding task
    │
    ▼
sense (risk / tests / urgency → currents)
    │
    ▼
LIF on FlyWire-derived circuit.json
    │
    ▼
population rates (gf, dnp09, mdn, loom, …)
    │
    ▼
CodingSignals (primary drive + clamps)
    │
    ▼
agent acts  ──verify──►  Hebbian coding memory
```

---

## Quick start

```bash
# From this repository
pip install -e .
# Optional (needed for --profile full):
# pip install -e ".[full]"

flywire-cortex fetch --profile seed
flywire-cortex install
flywire-cortex status
```

Smoke test:

```bash
flywire-cortex reset
flywire-cortex sense --text "urgent failing auth bug"
flywire-cortex step --ms 50
flywire-cortex signals
```

Example: giant-fiber stop drive

```bash
flywire-cortex reset
flywire-cortex stimulate gf --strength 0.5 --ms 80
flywire-cortex step --ms 10
flywire-cortex signals
# → primary: "gf", escape: true, stop: true
```

If `pip install` fails (SSL / corporate proxy), you can still run from source:

```powershell
$env:PYTHONPATH = "C:\path\to\flywire-coding-cortex\src"
python -m flywire_coding_cortex.cli status
```

---

## Install

### 1. Package

```bash
pip install flywire-coding-cortex          # when published to PyPI
# or
pip install -e .                          # from a clone
# or
uv tool install .
```

`pip install` **does not download** connectome dumps. Data is opt-in via `fetch`.

### 2. Circuit profile

```bash
flywire-cortex fetch --list-profiles
flywire-cortex fetch --profile seed       # default, offline after copy
```

### 3. Wire agents

```bash
flywire-cortex install
# or subset:
flywire-cortex install --targets cursor openclaw
```

Copies `skill/` into:

| Target | Path |
|---|---|
| Cursor | `~/.cursor/skills/flywire-coding-cortex/` |
| OpenClaw | `~/.openclaw/workspace/skills/flywire-coding-cortex/` (and `~/.openclaw/skills/` when present) |
| Claude | `~/.claude/skills/flywire-coding-cortex/` |

Also writes `~/.flywire-coding-cortex/mcp.snippet.json`.

### 4. Optional MCP connector (Cursor)

Add to your Cursor MCP config:

```json
{
  "mcpServers": {
    "flywire-coding-cortex": {
      "command": "flywire-cortex",
      "args": ["mcp"]
    }
  }
}
```

Then restart the agent session. Tools exposed:

| Tool | Purpose |
|---|---|
| `cortex_status` | Active profile + neuron/edge counts |
| `cortex_sense` | Task text → sensory currents |
| `cortex_step` | Advance LIF (`ms`, optional `text`) |
| `cortex_stimulate` | Stim a role group (`gf`, `dnp09`, …) |
| `cortex_signals` | Clamped coding drives JSON |
| `cortex_remember` | Query / strengthen / weaken memory |

---

## Download profiles

Choose (and later change) how much FlyWire data to pull. Profiles are cached
side-by-side under `~/.flywire-coding-cortex/profiles/<name>/`. `status` /
`step` always use the **active** profile.

| Profile | Approx size | Command | What you get |
|---|---|---|---|
| `seed` | ~0.3–5 MB | `flywire-cortex fetch` | Bundled curated subgraph (668 cells by default) |
| `codex` | ~60–300 MB | `flywire-cortex fetch --profile codex` | Public Codex gzipped CSVs + ETL rebuild |
| `full` | ~10.6 GB | `flywire-cortex fetch --profile full --yes` | Zenodo Feathers + ETL (explicit confirm) |

```bash
flywire-cortex fetch --list-profiles
flywire-cortex fetch --profile seed --force     # re-copy / switch back
flywire-cortex fetch --profile full --yes
flywire-cortex fetch --profile full --yes --include-synapses   # also ~9.5 GB synapse table
flywire-cortex status
```

**Rules:**

- Agents must **never** auto-run `full`. Ask the human first.
- `full` requires `--yes` and `pip install 'flywire-coding-cortex[full]'` (pandas + pyarrow).
- URLs live in [`data/manifest.json`](data/manifest.json) so mirrors can be edited without code changes.

Codex dump base (FAFB v783):

`https://storage.googleapis.com/flywire-data/codex/data/fafb/783`

---

## Every coding turn (agent loop)

The bundled skill instructs agents to run this loop (CLI or MCP):

1. **`status`** — ensure a circuit exists (`fetch --profile seed` if missing)
2. **`sense --text "…"`** — encode the task into currents (risk, test-red, urgency, ambiguity)
3. **`step --ms 50`** — run LIF on real edges
4. **`signals`** — read `primary` drive and clamps
5. **Act only under that primary drive** (see [Roles](#roles--coding-drives))
6. Apply [practices](#thinking-practices)
7. After verify: **`remember strengthen|weaken`**

LIF voltage/rates persist across separate CLI invocations in
`~/.flywire-coding-cortex/state/lif_state.json`. Use `flywire-cortex reset` to
clear between unrelated tasks.

---

## CLI reference

```text
flywire-cortex <command> …
```

| Command | Description |
|---|---|
| `fetch` | Download / activate a profile (`--profile`, `--list-profiles`, `--force`, `--yes`, `--include-synapses`) |
| `status` | Home path, active profile, neuron/edge/role counts |
| `sense` | Encode task text (or `--risk` / `--test-red` / `--urgency` / `--ambiguity`) |
| `step` | Advance simulation (`--ms`, optional `--text`) |
| `stimulate` | Stim a group: `gf`, `dnp09`, `mdn`, `lc4`, `lplc2`, `dng11`, `escw`, `dna01`, `dna02`, … |
| `signals` | Emit coding drives JSON (`--ms` to step first) |
| `reset` | Clear persisted LIF state |
| `remember` | `query` \| `strengthen` \| `weaken` \| `add-node` \| `add-edge` |
| `install` | Copy skills + print MCP snippet (`--targets`) |
| `mcp` | Run MCP stdio server |

### `remember` examples

```bash
flywire-cortex remember query --text "auth middleware"
flywire-cortex remember strengthen --pre concept:tests --post role:dnp09 --why "ci green"
flywire-cortex remember weaken --pre concept:migration --post role:dnp09 --why "broke prod"
flywire-cortex remember add-node --pre concept:oauth --label "OAuth flow"
flywire-cortex remember add-edge --pre concept:oauth --post role:lc4 --why "auth is high risk"
```

---

## Roles → coding drives

FlyWire-style role names are **coding lenses**. Rates come from the live sim;
the bridge picks a **winner-take-most** primary.

| Role | Drive | Agent should |
|---|---|---|
| `lc4` / `lplc2` | Risk / loom | Scan blast radius, security, regressions |
| `gf` | Escape / stop | Do not ship; halt feature work; unblocker |
| `dnp09` | Forward | Implement the requested change |
| `mdn` | Reverse | Revert / undo a bad direction |
| `dna01` / `dna02` | Steer | Write L vs R tradeoff, then choose |
| `dng11` | Groom | Cleanup, rename, lint-only |
| `escw` | Effort under pressure | Polish without scope creep |
| `ascending` | Proprioception | Read local conventions before inventing |
| `sensory` | External constraint | Honor ticket / failing test / user text |

Example `signals` payload:

```json
{
  "primary": "dnp09",
  "escape": false,
  "stop": false,
  "reverse": false,
  "walk_drive": 0.42,
  "nervous": 0.12,
  "support": ["lc4"],
  "rationale": "primary=dnp09 walk=0.42 nervous=0.12 mdn=0.0 gf=False"
}
```

---

## Thinking practices

Applied **on top of** rates (see `skill/practices.md`):

1. **Winner-take-most** — one primary drive per turn  
2. **Inhibition delay** — high risk → list blast radius before edits  
3. **Recurrent working set** — ≤5 active files/APIs  
4. **Hebbian writeback** — strengthen only after verify; weaken on failure  
5. **Sparse coding** — smallest change that satisfies the drive  
6. **Bilateral steer** — design forks get an explicit L/R paragraph  
7. **Proprioception first** — read neighbors before new patterns  
8. **Refractory** — after `gf` / `mdn`, no new feature drive that turn  
9. **Population scores** — prefer CLI sense scores over vibes  
10. **Consolidate** — end of session: 3 new + 1 weakened memory edges  

---

## Architecture

```text
flywire-coding-cortex/
  pyproject.toml
  README.md                 ← you are here
  INSTALL.md
  LICENSE                   ← MIT (code)
  data/
    circuit.seed.json       ← curated FlyWire subgraph (CC BY-NC)
    manifest.json           ← profile URLs / sizes
    DATA_LICENSE.md
  memory/
    seed-graph.json         ← starter coding-memory ontology
  skill/
    SKILL.md                ← Cursor / OpenClaw / Claude skill
    roles.md
    practices.md
  src/flywire_coding_cortex/
    cli.py                  ← entrypoint
    lif.py                  ← LIF on CSR adjacency
    sense.py                ← task → currents
    bridge.py               ← rates → CodingSignals
    memory.py               ← Hebbian graph
    paths.py                ← FLYWIRE_CORTEX_HOME helpers
    mcp_server.py
    install_skills.py
    assets/                 ← copies shipped in the wheel
    etl/
      download.py           ← fetch profiles
      build_circuit.py      ← Codex / Feather → circuit.json
```

### Runtime home (`FLYWIRE_CORTEX_HOME`)

Default: `~/.flywire-coding-cortex/`

| Path | Contents |
|---|---|
| `config.json` | Active profile name |
| `profiles/<name>/circuit.json` | Active wiring |
| `profiles/<name>/raw/` | Downloaded dumps (gitignored) |
| `state/lif_state.json` | Persisted voltages / rates / stims |
| `memory/graph.json` | Coding synapses (not FlyWire edges) |
| `mcp.snippet.json` | MCP config helper |

Override:

```bash
# bash
export FLYWIRE_CORTEX_HOME=/path/to/cortex-home

# PowerShell
$env:FLYWIRE_CORTEX_HOME = "D:\cortex-home"
```

### What is real vs modeled

| Real (measured / extracted) | Modeled |
|---|---|
| Neuron IDs, sides, types, roles in the subgraph | LIF τ, threshold, noise, weight scale |
| Signed synapse counts from Codex NT types | Task text → current injection |
| Graph adjacency used for spike propagation | Rate → coding-drive clamps |
| | Hebbian coding-memory edges |

---

## Environment & dependencies

- Python **≥ 3.10** (3.10+ recommended; annotations use modern syntax)
- Required: `numpy`
- Optional `[full]`: `pandas`, `pyarrow` (Zenodo Feather profile)

```bash
pip install -e ".[full]"
```

---

## Limitations (v1)

- Does **not** simulate the full ~139k-neuron brain every turn  
- Does **not** call live Codex apps (sign-in wall); uses static public files  
- Does **not** depend on DesktopFly or any overlay app  
- `full` downloads are large; confirm disk and network before `--yes`  
- MCP server is a minimal JSON-RPC subset (`initialize`, `tools/list`, `tools/call`)  

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `flywire-cortex` not found | `pip install -e .` or set `PYTHONPATH=…/src` and run `python -m flywire_coding_cortex.cli` |
| `circuit.seed.json missing` | Run `fetch --profile codex` once to rebuild, or ensure `data/circuit.seed.json` exists in the repo |
| Rates always zero across commands | Call `sense`/`stimulate` then `step`; state persists—use `reset` between unrelated tasks |
| `full` refuses to run | Pass `--yes`; install `[full]` extras |
| Skill not picked up | Re-run `flywire-cortex install`; start a **new** agent session |
| SSL errors on `pip install` | Fix certs / use a venv; interim: `PYTHONPATH` + `python -m …` |

---

## Citation & attribution

Please cite FlyWire when using or redistributing circuit extracts:

- Dorkenwald, S. et al. *Neuronal wiring diagram of an adult brain.* Nature 634, 124–138 (2024). https://doi.org/10.1038/s41586-024-07558-y  
- Schlegel, P. et al. *Whole-brain annotation and multi-connectome cell typing of Drosophila.* Nature 634, 139–152 (2024). https://doi.org/10.1038/s41586-024-07686-5  

Project sites: [flywire.ai](https://flywire.ai) · [codex.flywire.ai](https://codex.flywire.ai/)

Code in this repository is MIT. Derived JSON and downloaded dumps remain under
FlyWire’s **CC BY-NC 4.0** terms — see [data/DATA_LICENSE.md](data/DATA_LICENSE.md).

---

## Contributing / publishing

```bash
git clone <this-repo>
cd flywire-coding-cortex
pip install -e ".[full]"
flywire-cortex fetch --profile seed
flywire-cortex install
```

To rebuild the shipped seed from Codex dumps:

```bash
flywire-cortex fetch --profile codex --force
# copies rebuilt circuit into data/circuit.seed.json and package assets
```

When ready for GitHub/PyPI: tag a release, ensure `circuit.seed.json` is
committed, and document the CC BY-NC split in the release notes.
