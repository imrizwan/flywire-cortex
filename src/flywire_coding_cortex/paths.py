"""Resolve home cache, package assets, and active circuit paths."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent.parent


def home() -> Path:
    override = os.environ.get("FLYWIRE_CORTEX_HOME")
    if override:
        p = Path(override).expanduser().resolve()
    else:
        p = Path.home() / ".flywire-coding-cortex"
    p.mkdir(parents=True, exist_ok=True)
    (p / "profiles").mkdir(exist_ok=True)
    (p / "memory").mkdir(exist_ok=True)
    (p / "state").mkdir(exist_ok=True)
    return p


def config_path() -> Path:
    return home() / "config.json"


def load_config() -> dict:
    path = config_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"active_profile": "seed"}


def save_config(cfg: dict) -> None:
    config_path().write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def active_profile() -> str:
    return str(load_config().get("active_profile", "seed"))


def set_active_profile(name: str) -> None:
    cfg = load_config()
    cfg["active_profile"] = name
    save_config(cfg)


def profile_dir(name: str) -> Path:
    d = home() / "profiles" / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def circuit_path(profile: str | None = None) -> Path:
    name = profile or active_profile()
    return profile_dir(name) / "circuit.json"


def memory_path() -> Path:
    return home() / "memory" / "graph.json"


def state_path() -> Path:
    return home() / "state" / "lif_state.json"


def bundled_seed_circuit() -> Path | None:
    for p in (
        REPO_ROOT / "data" / "circuit.seed.json",
        PACKAGE_ROOT / "assets" / "circuit.seed.json",
    ):
        if p.is_file():
            return p
    return None


def bundled_manifest() -> Path:
    for p in (
        REPO_ROOT / "data" / "manifest.json",
        PACKAGE_ROOT / "assets" / "manifest.json",
    ):
        if p.is_file():
            return p
    raise FileNotFoundError("manifest.json not found")


def bundled_skill_dir() -> Path:
    for p in (REPO_ROOT / "skill", PACKAGE_ROOT / "assets" / "skill"):
        if (p / "SKILL.md").is_file():
            return p
    raise FileNotFoundError("skill/SKILL.md not found")


def bundled_memory_seed() -> Path:
    for p in (
        REPO_ROOT / "memory" / "seed-graph.json",
        PACKAGE_ROOT / "assets" / "seed-graph.json",
    ):
        if p.is_file():
            return p
    raise FileNotFoundError("memory/seed-graph.json not found")


def ensure_memory() -> Path:
    dest = memory_path()
    if not dest.exists():
        shutil.copy2(bundled_memory_seed(), dest)
    return dest
