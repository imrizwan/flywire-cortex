"""Leaky integrate-and-fire on a FlyWire-derived circuit JSON."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class Circuit:
    neurons: list[dict[str, Any]]
    edges: list[list[float]]
    source: str = ""

    @property
    def n(self) -> int:
        return len(self.neurons)

    @classmethod
    def load(cls, path: Path) -> "Circuit":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            neurons=data["neurons"],
            edges=data["edges"],
            source=str(data.get("source", "")),
        )


@dataclass
class LIFSim:
    circuit: Circuit
    weight_scale: float = 0.0008
    decay: float = 0.9512  # ~20 ms tau at 1 ms step
    threshold: float = 1.0
    refractory_ms: float = 2.0
    p_noise: float = 0.0022
    noise_kick: float = 0.42
    rate_alpha: float = 1.0 / 120.0
    inh_delay_ms: int = 4
    gap_junction_boost: float = 6.0
    rng: np.random.Generator = field(default_factory=lambda: np.random.default_rng(0))

    def __post_init__(self) -> None:
        n = self.circuit.n
        self.v = np.zeros(n, dtype=np.float64)
        self.refr = np.zeros(n, dtype=np.float64)
        self.baseline = np.zeros(n, dtype=np.float64)
        self.roles = [str(nr.get("role", "other")) for nr in self.circuit.neurons]
        self.types = [str(nr.get("type", "?")) for nr in self.circuit.neurons]
        self.sides = [str(nr.get("side", "")) for nr in self.circuit.neurons]
        self._build_groups()
        self._build_baselines()
        self._build_csr()
        self.inh_queue = np.zeros((self.inh_delay_ms + 1, n), dtype=np.float64)
        self.q_head = 0
        self.sim_ms = 0
        self.total_spikes = 0
        self.gf_latch = False
        self.rates = {
            "loom": 0.0,
            "dna_l": 0.0,
            "dna_r": 0.0,
            "mdn": 0.0,
            "fwd": 0.0,
            "groom": 0.0,
            "escw": 0.0,
            "pop": 0.0,
        }
        self.inputs = {
            "loom_l": 0.0,
            "loom_r": 0.0,
            "risk": 0.0,
            "ambiguity": 0.0,
            "test_red": 0.0,
            "urgency": 0.0,
            "air_puff": 0.0,
        }
        self._active_stims: list[dict[str, Any]] = []

    def _build_groups(self) -> None:
        self.loom_left: list[int] = []
        self.loom_right: list[int] = []
        self.gf: list[int] = []
        self.dna_l: list[int] = []
        self.dna_r: list[int] = []
        self.mdn: list[int] = []
        self.fwd: list[int] = []
        self.groom: list[int] = []
        self.escw: list[int] = []
        self.ascend: list[int] = []
        self.sens: list[int] = []
        for i, nr in enumerate(self.circuit.neurons):
            role = self.roles[i]
            side = self.sides[i]
            if role in ("lc4", "lplc2"):
                (self.loom_left if side == "left" else self.loom_right).append(i)
            elif role == "gf":
                self.gf.append(i)
            elif role in ("dna01", "dna02"):
                (self.dna_l if side == "left" else self.dna_r).append(i)
            elif role == "mdn":
                self.mdn.append(i)
            elif role == "dnp09":
                self.fwd.append(i)
            elif role == "dng11":
                self.groom.append(i)
            elif role == "escw":
                self.escw.append(i)
            elif role == "other":
                if self.types[i] == "ascending":
                    self.ascend.append(i)
                elif self.types[i] == "sensory":
                    self.sens.append(i)
        self.groups = {
            "gf": self.gf,
            "lc4": [i for i, r in enumerate(self.roles) if r == "lc4"],
            "lplc2": [i for i, r in enumerate(self.roles) if r == "lplc2"],
            "dnp09": self.fwd,
            "mdn": self.mdn,
            "dng11": self.groom,
            "escw": self.escw,
            "dna01": [i for i, r in enumerate(self.roles) if r == "dna01"],
            "dna02": [i for i, r in enumerate(self.roles) if r == "dna02"],
            "ascending": self.ascend,
            "sensory": self.sens,
        }

    def _build_baselines(self) -> None:
        for i, role in enumerate(self.roles):
            if role == "other":
                self.baseline[i] = float(self.rng.uniform(0.010, 0.070))
            elif role in ("lc4", "lplc2"):
                self.baseline[i] = 0.004
            elif role in ("dna01", "dna02", "mdn", "dng11", "escw"):
                self.baseline[i] = 0.036
            elif role == "dnp09":
                self.baseline[i] = 0.038
            else:
                self.baseline[i] = 0.002  # gf quiet unless driven

    def _build_csr(self) -> None:
        n = self.circuit.n
        counts = np.zeros(n, dtype=np.int32)
        for e in self.circuit.edges:
            counts[int(e[0])] += 1
        self.row_start = np.zeros(n + 1, dtype=np.int32)
        for i in range(n):
            self.row_start[i + 1] = self.row_start[i] + counts[i]
        m = len(self.circuit.edges)
        self.col_idx = np.zeros(m, dtype=np.int32)
        self.w = np.zeros(m, dtype=np.float64)
        fill = self.row_start.copy()
        for e in self.circuit.edges:
            pre, post = int(e[0]), int(e[1])
            weight = float(e[2]) * self.weight_scale
            electrical = self.roles[pre] in ("lc4", "lplc2") or (
                self.roles[pre] == "other" and self.types[pre] == "sensory"
            )
            if electrical and self.roles[post] == "gf":
                weight *= self.gap_junction_boost
            slot = int(fill[pre])
            self.col_idx[slot] = post
            self.w[slot] = weight
            fill[pre] += 1

    def set_inputs(self, **kwargs: float) -> None:
        for k, v in kwargs.items():
            if k in self.inputs:
                self.inputs[k] = float(v)

    def stimulate(self, indices: list[int], strength: float = 0.25, duration_ms: int = 400) -> None:
        if not indices:
            return
        self._active_stims.append(
            {
                "idx": [int(i) for i in indices if 0 <= int(i) < self.circuit.n],
                "strength": float(strength),
                "until": self.sim_ms + int(duration_ms),
            }
        )

    def stimulate_group(self, name: str, strength: float = 0.25, duration_ms: int = 400) -> int:
        idx = self.groups.get(name, [])
        self.stimulate(idx, strength=strength, duration_ms=duration_ms)
        return len(idx)

    def consume_gf(self) -> bool:
        flag = self.gf_latch
        self.gf_latch = False
        return flag

    def step(self, ms: int) -> dict[str, Any]:
        ms = max(0, int(ms))
        spiked_total = 0
        for _ in range(ms):
            self.sim_ms += 1
            self._active_stims = [s for s in self._active_stims if self.sim_ms < s["until"]]
            # leak + baseline + noise
            active = self.refr <= 0
            self.v[active] = self.v[active] * self.decay + self.baseline[active]
            self.v[~active] *= self.decay
            self.refr = np.maximum(0, self.refr - 1)
            noise_mask = (self.rng.random(self.circuit.n) < self.p_noise) & active
            self.v[noise_mask] += self.noise_kick

            # task / sensory currents
            loom = max(self.inputs["loom_l"], self.inputs["loom_r"], self.inputs["risk"])
            if loom > 0.001:
                gain = 0.30 * loom
                for i in self.loom_left:
                    self.v[i] += gain * (1.0 if self.inputs["loom_l"] or self.inputs["risk"] else 0.0)
                for i in self.loom_right:
                    self.v[i] += gain * (1.0 if self.inputs["loom_r"] or self.inputs["risk"] else 0.0)
            if self.inputs["test_red"] > 0.001:
                for i in self.sens:
                    self.v[i] += self.inputs["test_red"] * 0.10
            if self.inputs["ambiguity"] > 0.001:
                for i in self.ascend:
                    self.v[i] += self.inputs["ambiguity"] * 0.06
            if self.inputs["urgency"] > 0.001:
                for i in self.fwd:
                    self.v[i] += self.inputs["urgency"] * 0.05
            if self.inputs["air_puff"] > 0.001:
                for i in self.sens:
                    self.v[i] += self.inputs["air_puff"] * 0.12

            for stim in self._active_stims:
                for i in stim["idx"]:
                    self.v[i] += stim["strength"]

            # delayed inhibition
            slot = self.inh_queue[self.q_head]
            nz = slot != 0
            self.v[nz] = np.maximum(-2.0, self.v[nz] + slot[nz])
            slot[:] = 0

            fire = active & (self.v >= self.threshold)
            spiked = np.flatnonzero(fire)
            if spiked.size:
                self.v[spiked] = 0.0
                self.refr[spiked] = self.refractory_ms
                spiked_total += int(spiked.size)
                self.total_spikes += int(spiked.size)
                inh_slot = (self.q_head + self.inh_delay_ms) % self.inh_queue.shape[0]
                for i in spiked:
                    for k in range(self.row_start[i], self.row_start[i + 1]):
                        j = int(self.col_idx[k])
                        w = self.w[k]
                        if w >= 0:
                            self.v[j] = max(-2.0, self.v[j] + w)
                        else:
                            self.inh_queue[inh_slot, j] += w
                    if self.roles[int(i)] == "gf":
                        self.gf_latch = True
            self.q_head = (self.q_head + 1) % self.inh_queue.shape[0]
            self._update_rates(spiked)

        return {
            "sim_ms": self.sim_ms,
            "spikes": spiked_total,
            "total_spikes": self.total_spikes,
            "rates": dict(self.rates),
            "gf_latched": self.gf_latch,
            "n": self.circuit.n,
            "edges": len(self.circuit.edges),
        }

    def _update_rates(self, spiked: np.ndarray) -> None:
        c_loom = c_dl = c_dr = c_m = c_f = c_g = c_w = 0
        for i in spiked:
            role = self.roles[int(i)]
            if role in ("lc4", "lplc2"):
                c_loom += 1
            elif role in ("dna01", "dna02"):
                if int(i) in self.dna_l:
                    c_dl += 1
                else:
                    c_dr += 1
            elif role == "mdn":
                c_m += 1
            elif role == "dnp09":
                c_f += 1
            elif role == "dng11":
                c_g += 1
            elif role == "escw":
                c_w += 1
        a = self.rate_alpha

        def ema(key: str, count: int, denom: int) -> None:
            inst = count * 1000.0 / max(1, denom)
            self.rates[key] += (inst - self.rates[key]) * a

        ema("loom", c_loom, len(self.loom_left) + len(self.loom_right))
        ema("dna_l", c_dl, len(self.dna_l))
        ema("dna_r", c_dr, len(self.dna_r))
        ema("mdn", c_m, len(self.mdn))
        ema("fwd", c_f, len(self.fwd))
        ema("groom", c_g, len(self.groom))
        ema("escw", c_w, len(self.escw))
        ema("pop", int(spiked.size), self.circuit.n)

    def to_state(self) -> dict:
        return {
            "sim_ms": self.sim_ms,
            "total_spikes": self.total_spikes,
            "gf_latch": self.gf_latch,
            "v": self.v.tolist(),
            "refr": self.refr.tolist(),
            "rates": dict(self.rates),
            "inputs": dict(self.inputs),
            "q_head": self.q_head,
            "inh_queue": self.inh_queue.tolist(),
            "stims": self._active_stims,
            "dna_baseline": getattr(self, "dna_baseline", 0.0),
        }

    def load_state(self, state: dict) -> None:
        if not state or len(state.get("v", [])) != self.circuit.n:
            return
        self.sim_ms = int(state.get("sim_ms", 0))
        self.total_spikes = int(state.get("total_spikes", 0))
        self.gf_latch = bool(state.get("gf_latch", False))
        self.v = np.asarray(state["v"], dtype=np.float64)
        self.refr = np.asarray(state["refr"], dtype=np.float64)
        self.rates.update(state.get("rates") or {})
        self.inputs.update(state.get("inputs") or {})
        self.q_head = int(state.get("q_head", 0))
        iq = state.get("inh_queue")
        if iq is not None:
            self.inh_queue = np.asarray(iq, dtype=np.float64)
        self._active_stims = list(state.get("stims") or [])
        self.dna_baseline = float(state.get("dna_baseline", 0.0))
