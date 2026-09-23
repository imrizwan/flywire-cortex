"""Minimal MCP stdio server (JSON-RPC) for Cursor / agent connectors."""
from __future__ import annotations

import json
import sys
from typing import Any

from . import bridge, memory, sense
from .cli import _save_sim, get_sim
from .paths import active_profile, circuit_path, home


TOOLS = [
    {
        "name": "cortex_status",
        "description": "Show active FlyWire cortex profile and circuit stats",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "cortex_sense",
        "description": "Encode a coding task into sensory currents on the connectome",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "cortex_step",
        "description": "Advance the FlyWire-derived LIF simulation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ms": {"type": "integer", "default": 50},
                "text": {"type": "string"},
            },
        },
    },
    {
        "name": "cortex_stimulate",
        "description": "Stimulate a role population (gf, dnp09, mdn, …)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group": {"type": "string"},
                "strength": {"type": "number", "default": 0.25},
                "ms": {"type": "integer", "default": 400},
            },
            "required": ["group"],
        },
    },
    {
        "name": "cortex_signals",
        "description": "Read clamped coding drives from population rates",
        "inputSchema": {
            "type": "object",
            "properties": {"ms": {"type": "integer", "default": 0}},
        },
    },
    {
        "name": "cortex_remember",
        "description": "Query or update Hebbian coding memory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["query", "strengthen", "weaken"]},
                "text": {"type": "string"},
                "pre": {"type": "string"},
                "post": {"type": "string"},
                "why": {"type": "string"},
            },
            "required": ["action"],
        },
    },
]


def _result(obj: Any) -> dict[str, Any]:
    text = obj if isinstance(obj, str) else json.dumps(obj, indent=2)
    return {"content": [{"type": "text", "text": text}]}


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "cortex_status":
        path = circuit_path()
        info = {
            "home": str(home()),
            "active_profile": active_profile(),
            "circuit": str(path),
            "exists": path.exists(),
        }
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            info["neurons"] = len(data["neurons"])
            info["edges"] = len(data["edges"])
        return _result(info)
    if name == "cortex_sense":
        scores = sense.sense_text(arguments.get("text", ""))
        sim = get_sim()
        sim.set_inputs(**scores.as_inputs())
        _save_sim(sim)
        return _result(scores.as_inputs())
    if name == "cortex_step":
        sim = get_sim()
        text = arguments.get("text") or ""
        if text:
            sim.set_inputs(**sense.sense_text(text).as_inputs())
        out = sim.step(int(arguments.get("ms", 50)))
        _save_sim(sim)
        return _result(out)
    if name == "cortex_stimulate":
        sim = get_sim()
        n = sim.stimulate_group(
            arguments["group"],
            strength=float(arguments.get("strength", 0.25)),
            duration_ms=int(arguments.get("ms", 400)),
        )
        _save_sim(sim)
        return _result({"group": arguments["group"], "neurons": n})
    if name == "cortex_signals":
        sim = get_sim()
        ms = int(arguments.get("ms", 0))
        if ms:
            sim.step(ms)
        gf = sim.consume_gf()
        out = bridge.build_signals(sim.rates, gf_spike=gf).to_dict()
        _save_sim(sim)
        return _result(out)
    if name == "cortex_remember":
        action = arguments["action"]
        if action == "query":
            return _result(memory.query(arguments.get("text", "")))
        if action == "strengthen":
            return _result(
                memory.strengthen(
                    arguments.get("pre", ""),
                    arguments.get("post", ""),
                    why=arguments.get("why", ""),
                )
            )
        if action == "weaken":
            return _result(
                memory.weaken(
                    arguments.get("pre", ""),
                    arguments.get("post", ""),
                    why=arguments.get("why", ""),
                )
            )
    raise ValueError(f"Unknown tool: {name}")


def run_stdio() -> None:
    """Very small MCP subset: initialize, tools/list, tools/call."""

    def reply(msg_id: Any, result: Any) -> None:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}) + "\n")
        sys.stdout.flush()

    def error(msg_id: Any, message: str) -> None:
        sys.stdout.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32000, "message": message},
                }
            )
            + "\n"
        )
        sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = req.get("method")
        msg_id = req.get("id")
        params = req.get("params") or {}
        try:
            if method == "initialize":
                reply(
                    msg_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "flywire-coding-cortex", "version": "0.1.0"},
                    },
                )
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                reply(msg_id, {"tools": TOOLS})
            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments") or {}
                reply(msg_id, call_tool(name, arguments))
            elif method == "ping":
                reply(msg_id, {})
            else:
                if msg_id is not None:
                    error(msg_id, f"Method not found: {method}")
        except Exception as exc:  # noqa: BLE001 — surface to MCP client
            if msg_id is not None:
                error(msg_id, str(exc))
