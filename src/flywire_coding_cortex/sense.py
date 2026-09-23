"""Map a coding task description into sensory currents on the circuit."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SenseScores:
    risk: float = 0.0
    ambiguity: float = 0.0
    test_red: float = 0.0
    urgency: float = 0.0
    loom_l: float = 0.0
    loom_r: float = 0.0

    def as_inputs(self) -> dict[str, float]:
        return {
            "risk": self.risk,
            "ambiguity": self.ambiguity,
            "test_red": self.test_red,
            "urgency": self.urgency,
            "loom_l": max(self.loom_l, self.risk * 0.8),
            "loom_r": max(self.loom_r, self.risk * 0.8),
        }


_RISK = re.compile(
    r"\b(security|auth|password|token|migrat|delet|drop|prod|payment|leak|xss|sql)\b",
    re.I,
)
_TEST = re.compile(r"\b(fail|red|broken|bug|error|exception|regress)\b", re.I)
_AMB = re.compile(r"\b(maybe|unclear|refactor|redesign|should we|options?|trade-?off)\b", re.I)
_URG = re.compile(r"\b(urgent|asap|hotfix|blocker|p0|sev[-\s]?1)\b", re.I)


def sense_text(
    text: str,
    *,
    risk: float | None = None,
    ambiguity: float | None = None,
    test_red: float | None = None,
    urgency: float | None = None,
) -> SenseScores:
    t = text or ""
    scores = SenseScores(
        risk=_clamp(risk if risk is not None else _hit(_RISK, t, 0.55)),
        ambiguity=_clamp(ambiguity if ambiguity is not None else _hit(_AMB, t, 0.45)),
        test_red=_clamp(test_red if test_red is not None else _hit(_TEST, t, 0.65)),
        urgency=_clamp(urgency if urgency is not None else _hit(_URG, t, 0.7)),
    )
    if max(scores.risk, scores.ambiguity, scores.test_red, scores.urgency) < 0.05:
        scores.urgency = 0.15
    return scores


def _hit(rx: re.Pattern[str], text: str, weight: float) -> float:
    return weight if rx.search(text) else 0.0


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))
