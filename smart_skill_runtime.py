from __future__ import annotations
from smart_canonical_identity import canonical_root

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from smart_agent_runtime import SmartAgentRuntime, sha256_file, sha256_json
from smart_agent_skill_orchestration import AGENTS, LANES
from smart_skill_adapter_registry import build_registry as build_adapter_registry

SCHEMA = "SMART_SKILL_RUNTIME_V1"
QUARANTINE_LANE = "retained_quarantine_no_current_lane"


def _owner_map() -> dict[str, str]:
    owners: dict[str, str] = {}
    for agent, config in AGENTS.items():
        lane_name = config.get("lane")
        if lane_name is None:
            continue
        for capability in LANES[lane_name]["capabilities"]:
            if capability in owners:
                raise ValueError(f"duplicate capability owner: {capability}")
            owners[capability] = agent
    return owners


OWNERS = _owner_map()
ALL_CAPABILITIES = tuple(sorted(OWNERS))
QUARANTINED_CAPABILITIES = frozenset(LANES[QUARANTINE_LANE]["capabilities"])
PERTINENT_CAPABILITIES = tuple(sorted(set(ALL_CAPABILITIES) - QUARANTINED_CAPABILITIES))


@dataclass(frozen=True)
class CapabilityRegistration:
    capability: str
    agent_owner: str
    lane: str
    authority: str
    pertinent: bool
    callable: bool
    execution_mode: str
    external_source_executed: bool
    direct_named_skill_execution: bool
    semantic_binding_kind: str
    native_targets: tuple[str, ...]


class SmartSkillRuntime:
    """Fail-closed registry and invocation layer for SMART-MEGA capabilities.

    Third-party source trees remain source-only. Pertinent capabilities are exposed
    through bounded native adapters; quarantined non-pertinent references are
    intentionally not callable.
    """

    def __init__(self, root: str | Path, phase: str = "AUTO"):
        self.root = Path(root).resolve()
        self.agent_runtime = SmartAgentRuntime(self.root) if str(phase).upper() == "AUTO" else SmartAgentRuntime(self.root, phase=phase)
        self.phase = self.agent_runtime.phase
        self._registrations = self._build_registrations()
        self.adapter_registry = build_adapter_registry(self.root)
        if self.adapter_registry["gate"]["status"] != "PASS":
            raise RuntimeError(f"skill adapter registry invalid: {self.adapter_registry['gate']}")
        self._adapter_by_name = {
            row["capability_id"]: row for row in self.adapter_registry["adapters"]
        }

    def _build_registrations(self) -> dict[str, CapabilityRegistration]:
        registrations: dict[str, CapabilityRegistration] = {}
        for capability, owner in OWNERS.items():
            lane_name = str(AGENTS[owner]["lane"])
            lane = LANES[lane_name]
            pertinent = lane_name != QUARANTINE_LANE
            targets = tuple(str(x) for x in lane["native_targets"])
            if pertinent and not targets:
                raise RuntimeError(f"pertinent capability has no native target: {capability}")
            registrations[capability] = CapabilityRegistration(
                capability=capability,
                agent_owner=owner,
                lane=lane_name,
                authority=str(lane["authority"]),
                pertinent=pertinent,
                callable=pertinent,
                execution_mode="BOUNDED_NATIVE_ADAPTER" if pertinent else "SOURCE_ONLY_QUARANTINE",
                external_source_executed=False,
                direct_named_skill_execution=False,
                semantic_binding_kind="METHODOLOGY_ALIAS_TO_NATIVE_ROLE_PROBE" if pertinent else "SOURCE_REFERENCE_ONLY",
                native_targets=targets,
            )
        if set(registrations) != set(ALL_CAPABILITIES) or len(registrations) != 41:
            raise RuntimeError("capability registry is incomplete")
        return registrations

    def registrations(self) -> list[dict[str, Any]]:
        return [asdict(self._registrations[name]) for name in sorted(self._registrations)]

    def registration(self, capability: str) -> CapabilityRegistration:
        if capability not in self._registrations:
            raise KeyError(f"unknown SMART capability: {capability}")
        return self._registrations[capability]

    def invoke(self, capability: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        registration = self.registration(capability)
        binding = self._adapter_by_name[capability]
        if (
            binding["agent_owner"] != registration.agent_owner
            or binding["callable"] != registration.callable
            or binding["execution_mode"] != registration.execution_mode
            or binding["binding_sha256"] != sha256_json({k: v for k, v in binding.items() if k != "binding_sha256"})
        ):
            raise RuntimeError(f"skill adapter binding mismatch: {capability}")
        if binding["state"] not in {"NATIVE_ADAPTER", "REFERENCE_ONLY"}:
            raise RuntimeError(f"unproved skill adapter state: {capability}")
        if not registration.callable:
            raise PermissionError(
                f"capability is intentionally non-pertinent and quarantined: {capability}"
            )
        if payload is not None and not isinstance(payload, dict):
            raise TypeError("capability payload must be an object when provided")
        # The adapter executes the owner's native probe now. This is an actual
        # function invocation, not a declarative PASS copied from a manifest.
        probe = self.agent_runtime._probe_for(registration.agent_owner)
        if not probe.get("pass"):
            raise RuntimeError(f"native adapter failed for {capability}: {probe}")
        targets = []
        for relative in registration.native_targets:
            path = self.root / relative
            if not path.exists():
                raise FileNotFoundError(f"native target missing for {capability}: {relative}")
            if path.is_file():
                targets.append({"path": relative.replace("\\", "/"), "sha256": sha256_file(path)})
            else:
                targets.append({"path": relative.replace("\\", "/"), "kind": "directory"})
        evidence = {
            "capability": capability,
            "agent_owner": registration.agent_owner,
            "lane": registration.lane,
            "execution_mode": registration.execution_mode,
            "probe_id": probe.get("probe_id"),
            "executed_functions": list(probe.get("executed_functions", [])),
            "native_targets": targets,
            "external_source_executed": False,
            "direct_named_skill_execution": False,
            "semantic_binding_kind": registration.semantic_binding_kind,
            "payload_shape": sorted(payload.keys()) if payload else [],
            "adapter_state": binding["state"],
            "adapter_binding_sha256": binding["binding_sha256"],
            "adapter_registry_sha256": self.adapter_registry["registry_sha256"],
            "native_probe_result_sha256": sha256_json(probe),
            "external_source_state": binding["external_source_state"],
            "decision_effect": binding["decision_effect"],
            "predictive_weight_authorized": False,
            "freeze_mutation_authorized": False,
            "status": "PASS",
        }
        evidence["invocation_sha256"] = sha256_json(evidence)
        return evidence

    def execute_gate(self) -> dict[str, Any]:
        critical_before = self.agent_runtime._critical_hashes()
        rows: list[dict[str, Any]] = []
        for capability in ALL_CAPABILITIES:
            registration = self.registration(capability)
            if registration.callable:
                invocation = self.invoke(capability, {"gate": "functional"})
                row = {**asdict(registration), "invocation": invocation, "status": "PASS"}
            else:
                row = {
                    **asdict(registration),
                    "invocation": None,
                    "status": "NON_PERTINENT_QUARANTINED",
                    "reason": "No current SMART-MEGA functional gap justifies activation; source retained for research reference only.",
                }
            rows.append(row)
        critical_after = self.agent_runtime._critical_hashes()
        callable_rows = [r for r in rows if r["callable"]]
        quarantined_rows = [r for r in rows if not r["callable"]]
        checks = {
            "all_41_registered": len(rows) == 41 and len({r["capability"] for r in rows}) == 41,
            "all_pertinent_callable": len(callable_rows) == 37 and all(r["status"] == "PASS" and r["invocation"] for r in callable_rows),
            "each_pertinent_invoked_individually": all(r["invocation"]["capability"] == r["capability"] and r["invocation"]["invocation_sha256"] for r in callable_rows),
            "all_nonpertinent_explicitly_quarantined": len(quarantined_rows) == 4 and all(r["status"] == "NON_PERTINENT_QUARANTINED" for r in quarantined_rows),
            "external_source_never_executed": all(not r["external_source_executed"] for r in rows),
            "no_direct_named_skill_execution_is_claimed": all(not r["direct_named_skill_execution"] for r in rows),
            "pertinent_bindings_are_explicit_native_aliases": all(r["semantic_binding_kind"] == "METHODOLOGY_ALIAS_TO_NATIVE_ROLE_PROBE" for r in callable_rows),
            "native_targets_present": all(all((self.root / p).exists() for p in r["native_targets"]) for r in callable_rows),
            "canonical_state_unchanged": critical_before == critical_after,
            "f07_adapter_registry_pass": self.adapter_registry["gate"]["status"] == "PASS",
            "f07_external_sources_quarantined": self.adapter_registry["summary"]["external_quarantined_sources"] == 21 and self.adapter_registry["summary"]["external_executions"] == 0,
            "f07_no_unproven_active_native": self.adapter_registry["summary"]["active_native"] == 0,
            "f07_per_invocation_binding_consumed": all(
                row["invocation"]["adapter_binding_sha256"] == self._adapter_by_name[row["capability"]]["binding_sha256"]
                and row["invocation"]["adapter_state"] == "NATIVE_ADAPTER"
                and row["invocation"]["native_probe_result_sha256"]
                for row in callable_rows
            ),
        }
        document: dict[str, Any] = {
            "schema": SCHEMA,
            "phase": self.phase,
            "status": "PASS" if all(checks.values()) else "FAIL",
            "scope": "Per-capability methodology-alias resolution to bounded native role probes; this does NOT prove direct execution of the named third-party skill/library.",
            "claim_boundary": "A registered capability name is a methodology/reference binding. Direct named external-skill execution is false unless separately evidenced.",
            "checks": checks,
            "counts": {
                "registered": len(rows),
                "pertinent_callable": len(callable_rows),
                "nonpertinent_quarantined": len(quarantined_rows),
            },
            "capabilities": rows,
            "adapter_registry": self.adapter_registry,
            "critical_hashes_before": critical_before,
            "critical_hashes_after": critical_after,
        }
        document["sha256"] = sha256_json(document)
        return document


def write_gate(root: str | Path, output: str | Path = "SMART_SKILL_RUNTIME_PROOF.json", phase: str = "AUTO") -> dict[str, Any]:
    root = Path(root)
    output = Path(output)
    if not output.is_absolute():
        output = root / output
    result = SmartSkillRuntime(root).execute_gate() if str(phase).upper() == "AUTO" else SmartSkillRuntime(root, phase=phase).execute_gate()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    root = canonical_root()
    result = write_gate(root)
    print(json.dumps({"status": result["status"], "counts": result["counts"], "checks": result["checks"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
