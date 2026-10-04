"""Bounded model-based diagnosis and cost-aware active probe selection."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from .domain import ContractError, Fault, Observation, Probe, Target


@dataclass(frozen=True)
class Choice:
    probe: Probe
    information_bits: float
    score: float
    feasible_worlds: int


class DiagnosisModel:
    """Predict declared failure propagation and retain bounded simultaneous fault sets."""

    def __init__(self, target: Target, max_faults: int = 2):
        """Build worlds without access to fixture truth or runtime configuration values."""
        if isinstance(max_faults, bool) or not isinstance(max_faults, int) or max_faults not in {1, 2, 3}:
            raise ContractError("max_faults must be one, two, or three")
        self.target = target
        self.max_faults = max_faults
        self.ancestors = {service.id: self._ancestors(service.id) for service in target.services}
        self.faults: dict[str, Fault] = {}
        self.probes: dict[str, Probe] = {}
        for service in target.services:
            for kind, label in (
                ("unavailable", "endpoint unavailable"),
                ("local_failure", "local application failure"),
            ):
                key = f"{kind}/{service.id}"
                self.faults[key] = Fault(key, kind, service.id, None, f"{service.name}: {label}")
            key = f"http/{service.id}"
            self.probes[key] = Probe(key, "http", service.id, service.cost)
            if service.health_url:
                key = f"live/{service.id}"
                self.probes[key] = Probe(key, "live", service.id, service.cost)
        for binding in target.bindings:
            key = f"config/{binding.id}"
            self.faults[key] = Fault(
                key,
                "config_drift",
                binding.service,
                binding.id,
                f"{binding.service}: {binding.file}{binding.pointer} differs from intent",
            )
            self.probes[key] = Probe(key, "config", binding.id, binding.cost)
        total = sum(math.comb(len(self.faults), size) for size in range(max_faults + 1))
        if total > 50000:
            raise ContractError("Fault search exceeds 50,000 worlds; reduce target size or max_faults")
        self.worlds = [
            frozenset(items)
            for size in range(max_faults + 1)
            for items in combinations(self.faults, size)
            if self._compatible(items)
        ]
        self.initial_world_count = len(self.worlds)
        self.observations: list[Observation] = []
        self.observed: set[str] = set()
        self.impacts = {key: self.ancestors[fault.service] | {fault.service} for key, fault in self.faults.items()}

    def _ancestors(self, node: str) -> set[str]:
        parents = {source for source, child in self.target.dependencies if child == node}
        result = set(parents)
        while parents:
            parents = {source for source, child in self.target.dependencies if child in parents} - result
            result.update(parents)
        return result

    def _compatible(self, items: tuple[str, ...]) -> bool:
        seen: set[str] = set()
        for item in items:
            fault = self.faults[item]
            if fault.binding is None:
                if fault.service in seen:
                    return False
                seen.add(fault.service)
        return True

    def predict(self, world: frozenset[str], probe: Probe) -> str:
        """Map a fault world to one observable result under the manifest's required-edge model."""
        if probe.kind == "config":
            return "drift" if probe.id in world else "ok"
        unavailable = f"unavailable/{probe.subject}" in world
        if unavailable:
            return "unreachable"
        if probe.kind == "live":
            return "ok"
        return "failure" if any(probe.subject in self.impacts[fault] for fault in world) else "ok"

    def observe(self, observation: Observation) -> None:
        """Filter worlds by actual known results; unknown checks leave all worlds feasible."""
        if observation.probe_id not in self.probes or observation.probe_id in self.observed:
            raise ContractError("Observation must refer to a new declared probe")
        probe = self.probes[observation.probe_id]
        allowed = {"ok", "drift", "unknown"} if probe.kind == "config" else {"ok", "failure", "unreachable", "unknown"}
        if observation.outcome not in allowed:
            raise ContractError("Observation outcome does not match the probe contract")
        self.observations.append(observation)
        self.observed.add(observation.probe_id)
        if observation.outcome != "unknown":
            self.worlds = [world for world in self.worlds if self.predict(world, probe) == observation.outcome]

    def choose(self, remaining_cost: float) -> Choice | None:
        """Maximize deterministic outcome entropy per declared cost over unobserved probes."""
        if not self.worlds:
            return None
        weighted = [(world, 0.08 ** len(world)) for world in self.worlds]
        total = sum(weight for _, weight in weighted)
        choices = []
        for probe in self.probes.values():
            if probe.id in self.observed or probe.cost > remaining_cost + 1e-9:
                continue
            groups: dict[str, float] = defaultdict(float)
            for world, weight in weighted:
                groups[self.predict(world, probe)] += weight
            entropy = -sum((weight / total) * math.log2(weight / total) for weight in groups.values())
            if entropy > 1e-10:
                choices.append(Choice(probe, entropy, entropy / probe.cost, len(self.worlds)))
        return max(
            choices,
            key=lambda item: (item.score, item.information_bits, item.probe.id),
            default=None,
        )

    def minimal_worlds(self) -> list[frozenset[str]]:
        """Return subset-minimal explanations while preserving incomparable multi-fault diagnoses."""
        result: list[frozenset[str]] = []
        for world in sorted(self.worlds, key=lambda item: (len(item), tuple(sorted(item)))):
            if not any(previous <= world for previous in result):
                result.append(world)
        return result

    def report(self, reason: str, spent: float, budget: float) -> dict[str, Any]:
        """Expose conditional explanations, ambiguity, unsupported observations, and budget limits."""
        minimal = self.minimal_worlds()
        if not self.worlds:
            state = "model_conflict"
        elif minimal == [frozenset()]:
            state = (
                "healthy"
                if any(obs.probe_id == f"http/{self.target.entry}" and obs.outcome == "ok" for obs in self.observations)
                else "needs_evidence"
            )
        elif len(minimal) == 1:
            state = "diagnosed"
        else:
            state = "needs_evidence"
        candidates = sorted(set().union(*minimal)) if minimal else []
        confirmed = {obs.probe_id for obs in self.observations if obs.kind == "config" and obs.outcome == "drift"}
        faults = []
        for key in candidates:
            fault = self.faults[key]
            supporting = [
                obs.id
                for obs in self.observations
                if obs.outcome not in {"ok", "unknown"}
                and any(
                    key in world and self.predict(world - {key}, self.probes[obs.probe_id]) != obs.outcome
                    for world in minimal
                )
            ]
            faults.append(
                {
                    "id": key,
                    "kind": fault.kind,
                    "service": fault.service,
                    "binding": fault.binding,
                    "title": fault.title,
                    "directly_observed": key in confirmed
                    or any(
                        obs.probe_id == f"http/{fault.service}" and obs.outcome == "unreachable"
                        for obs in self.observations
                        if fault.kind == "unavailable"
                    ),
                    "evidence_ids": supporting,
                    "affected_services": sorted(self.impacts[key]),
                }
            )
        return {
            "state": state,
            "stop_reason": reason,
            "spent": round(spent, 6),
            "budget": budget,
            "max_faults": self.max_faults,
            "initial_worlds": self.initial_world_count,
            "feasible_worlds": len(self.worlds),
            "explanations": [sorted(world) for world in minimal[:20]],
            "explanation_count": len(minimal),
            "faults": faults,
            "unknown_probes": [obs.probe_id for obs in self.observations if obs.outcome == "unknown"],
            "remaining_probes": [key for key in self.probes if key not in self.observed],
            "model_note": (
                "Explanations depend on required dependency edges and the bounded fault catalog. "
                "Recovery must be tested."
            ),
        }
