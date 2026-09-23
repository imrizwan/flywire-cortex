"""Clamp LIF population rates into coding-agent drives (SignalBuilder analogue)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CodingSignals:
    primary: str = "dnp09"
    escape: bool = False
    stop: bool = False
    reverse: bool = False
    walk_drive: float = 0.0
    groom_drive: float = 0.0
    wing_drive: float = 0.0
    nervous: float = 0.0
    turn_bias: float = 0.0
    arousal: float = 0.0
    support: list[str] = field(default_factory=list)
    rates: dict[str, float] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_signals(
    rates: dict[str, float],
    *,
    gf_spike: bool = False,
    dna_baseline: float = 0.0,
) -> CodingSignals:
    nervous = _clamp(rates.get("loom", 0.0) / 80.0)
    walk = _clamp(rates.get("fwd", 0.0) / 10.0, 0.0, 1.3)
    groom = rates.get("groom", 0.0) / 8.0
    wing = _clamp(rates.get("escw", 0.0) / 10.0, 0.0, 1.3)
    arousal = _clamp(rates.get("pop", 0.0) / 20.0)
    diff = rates.get("dna_l", 0.0) - rates.get("dna_r", 0.0)
    turn = _clamp((diff - dna_baseline) * 0.04, -1.0, 1.0)
    reverse = rates.get("mdn", 0.0) > 8.0
    escape = bool(gf_spike)
    stop = escape or nervous > 0.85

    scores = {
        "gf": 1.0 if escape or stop else nervous * 0.5,
        "mdn": 0.9 if reverse else 0.0,
        "dng11": _clamp(groom / 1.5),
        "dnp09": _clamp(walk / 1.3) + 0.05,
        "dna": abs(turn),
        "escw": wing,
        "lc4": nervous,
    }
    primary = max(scores, key=scores.get)
    if primary == "dna":
        primary = "dna01"
    if primary == "lc4" and not stop:
        primary = "dnp09" if walk >= 0.15 else "ascending"

    support = [
        k for k, v in sorted(scores.items(), key=lambda kv: -kv[1]) if k != primary and v > 0.2
    ][:3]
    rationale = (
        f"primary={primary} walk={walk:.2f} nervous={nervous:.2f} "
        f"mdn={rates.get('mdn', 0):.1f} gf={escape}"
    )
    return CodingSignals(
        primary=primary,
        escape=escape,
        stop=stop,
        reverse=reverse,
        walk_drive=walk,
        groom_drive=groom,
        wing_drive=wing,
        nervous=nervous,
        turn_bias=turn,
        arousal=arousal,
        support=support,
        rates=dict(rates),
        rationale=rationale,
    )


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))
