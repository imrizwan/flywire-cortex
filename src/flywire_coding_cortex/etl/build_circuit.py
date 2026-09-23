"""Build curated circuit.json from Codex CSVs or Zenodo Feathers."""
from __future__ import annotations

import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

CORE_TYPES = {
    "LC4": "lc4",
    "LPLC2": "lplc2",
    "DNp01": "gf",
    "DNa02": "dna02",
    "DNa01": "dna01",
    "DNp09": "dnp09",
    "DNg11": "dng11",
    "MDN": "mdn",
    "DNp02": "escw",
    "DNp04": "escw",
    "DNp11": "escw",
}
NT_SIGN = {"ACH": 1.0, "GABA": -1.0, "GLUT": -1.0, "DA": 0.5, "SER": 0.5, "OCT": 0.5}
MAX_PARTNERS = 330


def build_from_codex_dir(raw: Path, out: Path) -> dict[str, Any]:
    def rows(name: str):
        with gzip.open(raw / name, "rt", encoding="utf-8", errors="replace") as f:
            r = csv.reader(f)
            next(r)
            yield from r

    core: dict[str, str] = {}
    type_of: dict[str, str] = {}
    counts: dict[str, int] = defaultdict(int)
    for row in rows("consolidated_cell_types.csv.gz"):
        rid, ptype = row[0], row[1].strip()
        role = CORE_TYPES.get(ptype)
        if role:
            core[rid] = role
            type_of[rid] = ptype
            counts[ptype] += 1
    print("core populations:", dict(counts))
    if not counts.get("LC4") or not counts.get("LPLC2") or not counts.get("DNp01"):
        raise SystemExit("FATAL: missing a core population — check type names")

    klass: dict[str, tuple[str, str]] = {}
    for row in rows("classification.csv.gz"):
        klass[row[0]] = (row[2], row[6])

    pos: dict[str, tuple[float, float, float]] = {}
    for row in rows("coordinates.csv.gz"):
        rid = row[0]
        if rid in pos:
            continue
        p = row[1].strip("[]").split()
        if len(p) == 3:
            pos[rid] = (float(p[0]), float(p[1]), float(p[2]))

    partner_strength: dict[str, int] = defaultdict(int)
    strength_by_role: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows("connections.csv.gz"):
        pre, post, syn = row[0], row[1], int(row[3])
        pre_core, post_core = pre in core, post in core
        if pre_core and not post_core:
            partner_strength[post] += syn
            strength_by_role[core[pre]][post] += syn
        elif post_core and not pre_core:
            partner_strength[pre] += syn
            strength_by_role[core[post]][pre] += syn

    usable = lambda r: r in pos and r in klass
    ranked = [rid for rid, _ in sorted(partner_strength.items(), key=lambda kv: -kv[1]) if usable(rid)]
    partners: list[str] = []
    seen: set[str] = set()

    def take(cands: list[str], k: int) -> None:
        n = 0
        for r in cands:
            if r in seen or not usable(r):
                continue
            seen.add(r)
            partners.append(r)
            n += 1
            if n == k:
                break

    for role in ("gf", "dna01", "dna02", "dnp09", "dng11", "mdn", "escw"):
        take([r for r, _ in sorted(strength_by_role[role].items(), key=lambda kv: -kv[1])], 10)
    take([r for r in ranked if klass[r][0] == "ascending"], 24)
    take([r for r in ranked if klass[r][0] == "sensory"], 16)
    take(ranked, MAX_PARTNERS - len(partners))
    print("partner super_classes:", dict(Counter(klass[r][0] for r in partners)))

    members = list(core.keys()) + partners
    member_idx = {rid: i for i, rid in enumerate(members)}
    edges: list[list[float]] = []
    nt_missing = 0
    for row in rows("connections.csv.gz"):
        pre, post = row[0], row[1]
        i, j = member_idx.get(pre), member_idx.get(post)
        if i is None or j is None:
            continue
        syn, nt = int(row[3]), row[4].strip().upper()
        sign = NT_SIGN.get(nt)
        if sign is None:
            sign, nt_missing = 1.0, nt_missing + 1
        edges.append([i, j, round(syn * sign, 1)])
    print(f"circuit edges: {len(edges)} (unknown nt on {nt_missing})")

    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    zs = [p[2] for p in pos.values()]
    cx, cy, cz = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2
    scale = 20.0 / max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))

    def norm(p: tuple[float, float, float]) -> list[float]:
        return [
            round((p[0] - cx) * scale, 3),
            round(-(p[1] - cy) * scale, 3),
            round(-(p[2] - cz) * scale, 3),
        ]

    neurons = []
    for rid in members:
        sc, side = klass.get(rid, ("", ""))
        p = norm(pos[rid]) if rid in pos else [0.0, 0.0, 0.0]
        neurons.append(
            {
                "id": rid,
                "type": type_of.get(rid, sc or "?"),
                "role": core.get(rid, "other"),
                "side": side,
                "pos": p,
            }
        )
    circuit = {
        "neurons": neurons,
        "edges": edges,
        "source": "FlyWire Codex FAFB v783 connections.csv (syn>=5, signed by nt_type)",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(circuit, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {out}: {len(neurons)} neurons, {len(edges)} edges")
    return circuit


def build_from_feather_dir(raw: Path, out: Path) -> dict[str, Any]:
    """Build a curated circuit using proofread_connections Feather + cell types if present.

    Falls back to requiring Codex cell-type CSVs in the same raw dir (downloaded
    automatically alongside Feathers when missing).
    """
    import pandas as pd

    conn_path = raw / "proofread_connections_783.feather"
    if not conn_path.exists():
        raise FileNotFoundError(f"Missing {conn_path}")

    # Need cell types — pull Codex types if absent
    types_gz = raw / "consolidated_cell_types.csv.gz"
    class_gz = raw / "classification.csv.gz"
    coords_gz = raw / "coordinates.csv.gz"
    if not types_gz.exists():
        from .download import download_file, load_manifest

        base = load_manifest()["profiles"]["codex"]["base_url"].rstrip("/")
        for name in (
            "consolidated_cell_types.csv.gz",
            "classification.csv.gz",
            "coordinates.csv.gz",
            "connections.csv.gz",
        ):
            dest = raw / name
            if not dest.exists():
                download_file(f"{base}/{name}", dest, label=name)

    # Prefer Codex thresholded connections for role ETL consistency when present;
    # otherwise synthesize a connections.csv.gz-like stream from Feather.
    if (raw / "connections.csv.gz").exists():
        return build_from_codex_dir(raw, out)

    df = pd.read_feather(conn_path)
    # Normalize column names across releases
    cols = {c.lower(): c for c in df.columns}
    pre_c = cols.get("pre_root_id") or cols.get("pre") or cols.get("from") or list(df.columns)[0]
    post_c = cols.get("post_root_id") or cols.get("post") or cols.get("to") or list(df.columns)[1]
    syn_c = cols.get("syn_count") or cols.get("synapse_count") or cols.get("count")
    if syn_c is None:
        for c in df.columns:
            if "syn" in c.lower() or "count" in c.lower():
                syn_c = c
                break
    if syn_c is None:
        raise SystemExit(f"Cannot find synapse count column in {list(df.columns)}")

    tmp_conn = raw / "connections.csv.gz"
    subset = df[[pre_c, post_c, syn_c]].copy()
    subset.columns = ["pre", "post", "syn"]
    with gzip.open(tmp_conn, "wt", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pre_root_id", "post_root_id", "neuropil", "syn_count", "nt_type"])
        for pre, post, syn in subset.itertuples(index=False, name=None):
            syn_i = int(syn)
            if syn_i < 5:
                continue
            w.writerow([str(pre), str(post), "", syn_i, "ACH"])
    return build_from_codex_dir(raw, out)
