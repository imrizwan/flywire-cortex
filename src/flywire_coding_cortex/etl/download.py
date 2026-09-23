"""Download profile assets into the user cache."""
from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any

from ..paths import bundled_manifest, bundled_seed_circuit, profile_dir


def load_manifest() -> dict[str, Any]:
    return json.loads(bundled_manifest().read_text(encoding="utf-8"))


def list_profiles() -> dict[str, Any]:
    return load_manifest()["profiles"]


def download_file(url: str, dest: Path, *, label: str = "") -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"Downloading {label or dest.name} …")
    urllib.request.urlretrieve(url, tmp)  # noqa: S310 — curated manifest URLs
    tmp.replace(dest)
    print(f"  -> {dest} ({dest.stat().st_size:,} bytes)")


def fetch_seed(*, force: bool = False) -> Path:
    dest = profile_dir("seed") / "circuit.json"
    if dest.exists() and not force:
        return dest
    seed = bundled_seed_circuit()
    if seed is None:
        raise FileNotFoundError(
            "circuit.seed.json missing. Build it with: flywire-cortex fetch --profile codex"
        )
    shutil.copy2(seed, dest)
    meta = {
        "profile": "seed",
        "source": "bundled circuit.seed.json",
        "neurons": _count_neurons(dest),
    }
    (profile_dir("seed") / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return dest


def fetch_codex(*, force: bool = False) -> Path:
    from .build_circuit import build_from_codex_dir

    raw = profile_dir("codex") / "raw"
    circuit = profile_dir("codex") / "circuit.json"
    if circuit.exists() and not force:
        return circuit
    manifest = load_manifest()["profiles"]["codex"]
    base = manifest["base_url"].rstrip("/")
    raw.mkdir(parents=True, exist_ok=True)
    for f in manifest["files"]:
        name = f["name"]
        dest = raw / name
        if dest.exists() and not force:
            continue
        download_file(f"{base}/{f['path']}", dest, label=name)
    build_from_codex_dir(raw, circuit)
    meta = {
        "profile": "codex",
        "source": base,
        "neurons": _count_neurons(circuit),
    }
    (profile_dir("codex") / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    # also refresh bundled seed for packaging workflows
    seed_out = bundled_seed_circuit()
    if seed_out is None:
        seed_out = Path(__file__).resolve().parents[3] / "data" / "circuit.seed.json"
    seed_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(circuit, seed_out)
    assets = Path(__file__).resolve().parents[1] / "assets" / "circuit.seed.json"
    assets.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(circuit, assets)
    return circuit


def fetch_full(*, force: bool = False, include_synapses: bool = False, yes: bool = False) -> Path:
    if not yes:
        raise SystemExit(
            "Profile 'full' downloads ~10.6 GB. Re-run with --yes to confirm:\n"
            "  flywire-cortex fetch --profile full --yes\n"
            "Optional largest synapse table: add --include-synapses"
        )
    try:
        import pandas as pd  # noqa: F401
        import pyarrow  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Profile 'full' needs: pip install 'flywire-coding-cortex[full]'"
        ) from exc

    from .build_circuit import build_from_feather_dir

    raw = profile_dir("full") / "raw"
    circuit = profile_dir("full") / "circuit.json"
    if circuit.exists() and not force:
        return circuit
    manifest = load_manifest()["profiles"]["full"]
    raw.mkdir(parents=True, exist_ok=True)
    for f in manifest["files"]:
        if f.get("optional") and not include_synapses:
            print(f"Skipping optional {f['name']} (pass --include-synapses to fetch)")
            continue
        dest = raw / f["name"]
        if dest.exists() and not force:
            continue
        download_file(f["url"], dest, label=f"{f['name']} (~{f.get('approx_bytes', 0):,} B)")
    build_from_feather_dir(raw, circuit)
    meta = {
        "profile": "full",
        "source": manifest.get("record_url"),
        "neurons": _count_neurons(circuit),
        "include_synapses": include_synapses,
    }
    (profile_dir("full") / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return circuit


def _count_neurons(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data.get("neurons", []))
