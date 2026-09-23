"""Hebbian coding-memory graph (not fabricated FlyWire edges)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from .paths import ensure_memory, memory_path


def _load() -> dict[str, Any]:
    path = ensure_memory()
    return json.loads(path.read_text(encoding="utf-8"))


def _save(graph: dict[str, Any]) -> None:
    memory_path().write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")


def query(text: str, limit: int = 8) -> list[dict[str, Any]]:
    graph = _load()
    tokens = set(re.findall(r"[a-z0-9_/-]+", text.lower()))
    scored: list[tuple[float, dict[str, Any]]] = []
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    for e in graph.get("edges", []):
        pre, post = e.get("pre"), e.get("post")
        blob = f"{pre} {post} {e.get('why', '')} {nodes.get(pre, {}).get('label', '')} {nodes.get(post, {}).get('label', '')}".lower()
        hit = sum(1 for t in tokens if t in blob)
        if hit:
            scored.append((hit * float(e.get("weight", 1)), e))
    scored.sort(key=lambda x: -x[0])
    out = []
    for score, e in scored[:limit]:
        out.append(
            {
                "score": score,
                "pre": e.get("pre"),
                "post": e.get("post"),
                "weight": e.get("weight"),
                "why": e.get("why", ""),
                "pre_label": nodes.get(e.get("pre"), {}).get("label"),
                "post_label": nodes.get(e.get("post"), {}).get("label"),
            }
        )
    return out


def add_node(node_id: str, label: str, kind: str = "concept") -> dict[str, Any]:
    graph = _load()
    nodes = graph.setdefault("nodes", [])
    for n in nodes:
        if n["id"] == node_id:
            n["label"] = label
            n["kind"] = kind
            n["lastSeen"] = time.time()
            _save(graph)
            return n
    node = {"id": node_id, "label": label, "kind": kind, "lastSeen": time.time()}
    nodes.append(node)
    _save(graph)
    return node


def add_edge(pre: str, post: str, weight: float = 1.0, why: str = "") -> dict[str, Any]:
    graph = _load()
    edges = graph.setdefault("edges", [])
    for e in edges:
        if e.get("pre") == pre and e.get("post") == post:
            e["weight"] = float(weight)
            if why:
                e.setdefault("evidence", []).append(why)
                e["why"] = why
            _save(graph)
            return e
    edge = {"pre": pre, "post": post, "weight": float(weight), "why": why, "evidence": [why] if why else []}
    edges.append(edge)
    _save(graph)
    return edge


def strengthen(pre: str, post: str, delta: float = 0.25, why: str = "") -> dict[str, Any]:
    graph = _load()
    for e in graph.get("edges", []):
        if e.get("pre") == pre and e.get("post") == post:
            e["weight"] = float(e.get("weight", 1.0)) + float(delta)
            if why:
                e.setdefault("evidence", []).append(why)
                e["why"] = why
            _save(graph)
            return e
    return add_edge(pre, post, weight=1.0 + delta, why=why)


def weaken(pre: str, post: str, delta: float = 0.25, why: str = "") -> dict[str, Any]:
    graph = _load()
    for e in graph.get("edges", []):
        if e.get("pre") == pre and e.get("post") == post:
            e["weight"] = float(e.get("weight", 1.0)) - float(delta)
            if why:
                e.setdefault("evidence", []).append(f"weaken:{why}")
                e["why"] = why
            _save(graph)
            return e
    return add_edge(pre, post, weight=-abs(delta), why=why or "inhibitory")
