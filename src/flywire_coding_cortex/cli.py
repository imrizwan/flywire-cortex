"""CLI: fetch, status, sense, step, stimulate, signals, remember, install, mcp."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import bridge, memory, sense
from .etl import download as dl
from .lif import Circuit, LIFSim
from .paths import (
    active_profile,
    circuit_path,
    home,
    load_config,
    set_active_profile,
    state_path,
)


def _sim(profile: str | None = None) -> LIFSim:
    path = circuit_path(profile)
    if not path.exists():
        if (profile or active_profile()) == "seed":
            dl.fetch_seed()
        else:
            raise SystemExit(
                f"No circuit for profile {profile or active_profile()}. "
                f"Run: flywire-cortex fetch --profile {profile or active_profile()}"
            )
    return LIFSim(Circuit.load(circuit_path(profile)))


_SIM: LIFSim | None = None


def _save_sim(sim: LIFSim) -> None:
    state_path().write_text(json.dumps(sim.to_state()) + "\n", encoding="utf-8")


def get_sim(reload: bool = False) -> LIFSim:
    global _SIM
    if _SIM is None or reload:
        _SIM = _sim()
        sp = state_path()
        if sp.exists() and not reload:
            try:
                _SIM.load_state(json.loads(sp.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, ValueError, KeyError):
                pass
    return _SIM


def cmd_fetch(args: argparse.Namespace) -> int:
    if args.list_profiles:
        profiles = dl.list_profiles()
        active = active_profile()
        for name, meta in profiles.items():
            mark = " (active)" if name == active else ""
            print(f"{name}{mark}: {meta.get('approx_size')} — {meta.get('label')}")
            print(f"  {meta.get('description')}")
        return 0

    profile = args.profile or "seed"
    if profile == "seed":
        path = dl.fetch_seed(force=args.force)
    elif profile == "codex":
        path = dl.fetch_codex(force=args.force)
    elif profile == "full":
        path = dl.fetch_full(
            force=args.force,
            include_synapses=args.include_synapses,
            yes=args.yes,
        )
    else:
        raise SystemExit(f"Unknown profile: {profile}")
    set_active_profile(profile)
    # new circuit → clear LIF state
    global _SIM
    _SIM = None
    sp = state_path()
    if sp.exists():
        sp.unlink()
    data = json.loads(path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "ok": True,
                "profile": profile,
                "circuit": str(path),
                "neurons": len(data["neurons"]),
                "edges": len(data["edges"]),
            },
            indent=2,
        )
    )
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    cfg = load_config()
    profile = cfg.get("active_profile", "seed")
    path = circuit_path(profile)
    info: dict = {
        "home": str(home()),
        "active_profile": profile,
        "circuit": str(path),
        "circuit_exists": path.exists(),
    }
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        roles: dict[str, int] = {}
        for n in data["neurons"]:
            roles[n.get("role", "?")] = roles.get(n.get("role", "?"), 0) + 1
        info.update(
            {
                "neurons": len(data["neurons"]),
                "edges": len(data["edges"]),
                "source": data.get("source"),
                "roles": roles,
            }
        )
    else:
        info["hint"] = "flywire-cortex fetch --profile seed"
    print(json.dumps(info, indent=2))
    return 0


def cmd_sense(args: argparse.Namespace) -> int:
    text = args.text or " ".join(args.words) or ""
    scores = sense.sense_text(
        text,
        risk=args.risk,
        ambiguity=args.ambiguity,
        test_red=args.test_red,
        urgency=args.urgency,
    )
    sim = get_sim()
    sim.set_inputs(**scores.as_inputs())
    _save_sim(sim)
    print(json.dumps({"text": text, "inputs": scores.as_inputs()}, indent=2))
    return 0


def cmd_step(args: argparse.Namespace) -> int:
    sim = get_sim()
    if args.text:
        scores = sense.sense_text(args.text)
        sim.set_inputs(**scores.as_inputs())
    out = sim.step(args.ms)
    _save_sim(sim)
    print(json.dumps(out, indent=2))
    return 0


def cmd_stimulate(args: argparse.Namespace) -> int:
    sim = get_sim()
    n = sim.stimulate_group(args.group, strength=args.strength, duration_ms=args.ms)
    if n == 0:
        raise SystemExit(f"Unknown or empty group: {args.group}. Try: {list(sim.groups)}")
    _save_sim(sim)
    print(json.dumps({"group": args.group, "neurons": n, "strength": args.strength, "ms": args.ms}, indent=2))
    return 0


def cmd_signals(args: argparse.Namespace) -> int:
    sim = get_sim()
    if args.ms:
        sim.step(args.ms)
    gf = sim.consume_gf()
    diff = sim.rates["dna_l"] - sim.rates["dna_r"]
    base = float(getattr(sim, "dna_baseline", 0.0))
    base += (diff - base) * (1.0 / 8.0)
    sim.dna_baseline = base
    sig = bridge.build_signals(sim.rates, gf_spike=gf, dna_baseline=base)
    _save_sim(sim)
    print(json.dumps(sig.to_dict(), indent=2))
    return 0


def cmd_reset(_: argparse.Namespace) -> int:
    global _SIM
    _SIM = None
    sp = state_path()
    if sp.exists():
        sp.unlink()
    print(json.dumps({"ok": True, "reset": True}, indent=2))
    return 0


def cmd_remember(args: argparse.Namespace) -> int:
    if args.action == "query":
        print(json.dumps(memory.query(args.text or ""), indent=2))
    elif args.action == "strengthen":
        print(json.dumps(memory.strengthen(args.pre, args.post, why=args.why or ""), indent=2))
    elif args.action == "weaken":
        print(json.dumps(memory.weaken(args.pre, args.post, why=args.why or ""), indent=2))
    elif args.action == "add-node":
        print(json.dumps(memory.add_node(args.pre, args.label or args.pre, args.kind or "concept"), indent=2))
    elif args.action == "add-edge":
        print(json.dumps(memory.add_edge(args.pre, args.post, why=args.why or ""), indent=2))
    else:
        raise SystemExit(f"Unknown remember action: {args.action}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    from .install_skills import install_all

    result = install_all(targets=args.targets)
    print(json.dumps(result, indent=2))
    return 0


def cmd_mcp(_: argparse.Namespace) -> int:
    from .mcp_server import run_stdio

    run_stdio()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="flywire-cortex",
        description="Run FlyWire-derived LIF neurons and map rates to coding-agent drives.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="Download / activate a circuit profile")
    f.add_argument("--profile", choices=["seed", "codex", "full"], default="seed")
    f.add_argument("--list-profiles", action="store_true")
    f.add_argument("--force", action="store_true")
    f.add_argument("--yes", action="store_true", help="Confirm full (~10.6 GB) download")
    f.add_argument("--include-synapses", action="store_true", help="Also fetch ~9.5 GB synapse Feather")
    f.set_defaults(func=cmd_fetch)

    s = sub.add_parser("status", help="Show active profile and circuit stats")
    s.set_defaults(func=cmd_status)

    se = sub.add_parser("sense", help="Encode a coding task into sensory currents")
    se.add_argument("words", nargs="*", help="Task text")
    se.add_argument("--text", default="")
    se.add_argument("--risk", type=float, default=None)
    se.add_argument("--ambiguity", type=float, default=None)
    se.add_argument("--test-red", dest="test_red", type=float, default=None)
    se.add_argument("--urgency", type=float, default=None)
    se.set_defaults(func=cmd_sense)

    st = sub.add_parser("step", help="Advance LIF simulation")
    st.add_argument("--ms", type=int, default=50)
    st.add_argument("--text", default="", help="Optional sense text before stepping")
    st.set_defaults(func=cmd_step)

    sm = sub.add_parser("stimulate", help="Optogenetic-style population stim")
    sm.add_argument("group", help="Role group: gf, dnp09, mdn, lc4, …")
    sm.add_argument("--strength", type=float, default=0.25)
    sm.add_argument("--ms", type=int, default=400)
    sm.set_defaults(func=cmd_stimulate)

    sg = sub.add_parser("signals", help="Emit clamped coding drives from rates")
    sg.add_argument("--ms", type=int, default=0, help="Optional step before reading")
    sg.set_defaults(func=cmd_signals)

    rs = sub.add_parser("reset", help="Clear persisted LIF state")
    rs.set_defaults(func=cmd_reset)

    rm = sub.add_parser("remember", help="Hebbian coding-memory graph")
    rm.add_argument("action", choices=["query", "strengthen", "weaken", "add-node", "add-edge"])
    rm.add_argument("--text", default="")
    rm.add_argument("--pre", default="")
    rm.add_argument("--post", default="")
    rm.add_argument("--why", default="")
    rm.add_argument("--label", default="")
    rm.add_argument("--kind", default="concept")
    rm.set_defaults(func=cmd_remember)

    ins = sub.add_parser("install", help="Wire Cursor / OpenClaw / Claude skills + print MCP snippet")
    ins.add_argument(
        "--targets",
        nargs="*",
        default=["cursor", "openclaw", "claude"],
        help="Subset of: cursor openclaw claude",
    )
    ins.set_defaults(func=cmd_install)

    m = sub.add_parser("mcp", help="Run MCP stdio connector")
    m.set_defaults(func=cmd_mcp)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        code = args.func(args)
    except BrokenPipeError:
        code = 0
    sys.exit(code or 0)


if __name__ == "__main__":
    main()
