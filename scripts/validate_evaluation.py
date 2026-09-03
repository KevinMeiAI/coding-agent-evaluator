#!/usr/bin/env python3
"""Validate coding-agent-evaluator JSON scoring and evidence invariants."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


FIXED_DIMENSIONS = {
    "requirement_fulfillment": 50,
    "correctness_domain_quality": 20,
    "usability_operational_loop": 15,
    "robustness_boundary_behavior": 10,
    "delivery_claim_consistency": 5,
}
SCHEMA_VERSION = "1.2"
CHECK_STATUSES = {"pass", "partial", "fail", "not_applicable", "unverified"}
EVIDENCE_LEVELS = {"E3", "E2", "E1", "E0", "EX"}
BEHAVIORS = {"static", "dynamic"}
EXECUTION_MODES = {
    "default_unmodified",
    "observational_instrumentation",
    "controlled_diagnostic",
}
RUN_OUTCOMES = {"pass", "fail", "mixed", "inconclusive"}
GAMEPLAY_PHASES = {
    "launch",
    "meaningful_input_response",
    "progression",
    "attempted_failure",
    "terminal_state",
    "replay",
}
PHASE_STATUSES = {"pass", "partial", "fail", "unverified"}
VARIATION_KINDS = {"default_sample", "nominal", "boundary", "risk"}
VARIATION_CONCLUSIONS = {"pass", "partial", "fail", "unverified"}
VERDICTS = {"excellent_pass", "full_pass", "partial_pass", "fail"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
SEVERITIES = {"critical", "high", "medium", "low", "observation"}
USER_VISIBLE_VALUES = {True, False, "unknown"}
USER_VISIBLE_SURFACES = {
    "assistant-message",
    "progress-update",
    "ask-user",
    "permission-request",
    "final-response",
}
ATTRIBUTIONS = {"model", "tool", "harness", "environment", "mixed", "unknown"}
TOLERANCE = 0.11


class Validator:
    def __init__(self, document: Any, base_dir: Path) -> None:
        self.document = document
        self.base_dir = base_dir
        self.errors: list[str] = []
        self.execution: dict[str, Any] = {}
        self.runs_by_id: dict[str, dict[str, Any]] = {}
        self.scene_primary: str | None = None
        self.procedural_or_randomized = False
        self.time_sensitive_controls = False

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def require_dict(self, value: Any, path: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            self.error(path, "must be an object")
            return {}
        return value

    def require_list(self, value: Any, path: str) -> list[Any]:
        if not isinstance(value, list):
            self.error(path, "must be an array")
            return []
        return value

    def number(self, value: Any, path: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            self.error(path, "must be a number")
            return 0.0
        return float(value)

    def validate(self) -> list[str]:
        root = self.require_dict(self.document, "$")
        for key in (
            "schema_version",
            "evaluation",
            "inputs",
            "scene",
            "rubric",
            "execution_evidence",
            "result",
            "process_analysis",
            "flow_diagram",
        ):
            if key not in root:
                self.error("$", f"missing required key {key!r}")
        if root.get("schema_version") != SCHEMA_VERSION:
            self.error("$.schema_version", f"must equal {SCHEMA_VERSION!r}")

        inputs = self.require_dict(root.get("inputs"), "$.inputs")
        prompt = inputs.get("original_prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            self.error("$.inputs.original_prompt", "must contain the exact non-empty prompt")

        scene = self.require_dict(root.get("scene"), "$.scene")
        self.scene_primary = scene.get("primary")
        if self.scene_primary not in {"web", "game", "file-processing", "general"}:
            self.error("$.scene.primary", "must be web, game, file-processing, or general")
        if self.scene_primary == "game":
            procedural = scene.get("procedural_or_randomized")
            if not isinstance(procedural, bool):
                self.error("$.scene.procedural_or_randomized", "must be true or false for game scenes")
            else:
                self.procedural_or_randomized = procedural
            time_sensitive = scene.get("time_sensitive_controls")
            if not isinstance(time_sensitive, bool):
                self.error("$.scene.time_sensitive_controls", "must be true or false for game scenes")
            else:
                self.time_sensitive_controls = time_sensitive

        self.execution = self.validate_execution(
            self.require_dict(root.get("execution_evidence"), "$.execution_evidence")
        )

        rubric = self.require_dict(root.get("rubric"), "$.rubric")
        if rubric.get("frozen_before_artifact_review") is not True:
            self.error("$.rubric.frozen_before_artifact_review", "must be true")
        dimensions = self.require_list(rubric.get("dimensions"), "$.rubric.dimensions")
        checks_by_dimension = self.validate_dimensions(dimensions)
        self.validate_hard_gates(self.require_list(rubric.get("hard_gates", []), "$.rubric.hard_gates"))

        result = self.require_dict(root.get("result"), "$.result")
        self.validate_execution_cross_checks(checks_by_dimension, result)
        self.validate_result(result, checks_by_dimension, rubric)
        self.validate_process(self.require_dict(root.get("process_analysis"), "$.process_analysis"))
        self.validate_flow(self.require_dict(root.get("flow_diagram"), "$.flow_diagram"))
        return self.errors

    def validate_string_list(self, value: Any, path: str) -> list[str]:
        items = self.require_list(value, path)
        normalized: list[str] = []
        for index, item in enumerate(items):
            if not isinstance(item, str) or not item.strip():
                self.error(f"{path}[{index}]", "must be a non-empty string")
            else:
                normalized.append(item)
        return normalized

    def validate_run_ids(self, value: Any, path: str, *, require_nonempty: bool = False) -> list[str]:
        run_ids = self.validate_string_list(value, path)
        if require_nonempty and not run_ids:
            self.error(path, "must cite at least one execution run")
        if len(run_ids) != len(set(run_ids)):
            self.error(path, "must not contain duplicate run IDs")
        for run_id in run_ids:
            if run_id not in self.runs_by_id:
                self.error(path, f"references unknown execution run {run_id!r}")
        return run_ids

    def has_representative_run(self, run_ids: list[str]) -> bool:
        return any(
            self.runs_by_id.get(run_id, {}).get("representative_of_default") is True
            and self.runs_by_id.get(run_id, {}).get("mode")
            in {"default_unmodified", "observational_instrumentation"}
            for run_id in run_ids
        )

    def has_successful_representative_run(self, run_ids: list[str]) -> bool:
        return any(
            self.runs_by_id.get(run_id, {}).get("outcome") in {"pass", "mixed"}
            and self.runs_by_id.get(run_id, {}).get("representative_of_default") is True
            and self.runs_by_id.get(run_id, {}).get("mode")
            in {"default_unmodified", "observational_instrumentation"}
            for run_id in run_ids
        )

    def validate_execution(self, execution: dict[str, Any]) -> dict[str, Any]:
        applicable = execution.get("applicable")
        if not isinstance(applicable, bool):
            self.error("$.execution_evidence.applicable", "must be true or false")
            applicable = False
        limitations = self.validate_string_list(
            execution.get("limitations", []), "$.execution_evidence.limitations"
        )
        runs = self.require_list(execution.get("runs"), "$.execution_evidence.runs")
        for index, raw_run in enumerate(runs):
            path = f"$.execution_evidence.runs[{index}]"
            run = self.require_dict(raw_run, path)
            run_id = run.get("id")
            if not isinstance(run_id, str) or not run_id.strip():
                self.error(path + ".id", "must be a non-empty string")
                continue
            if run_id in self.runs_by_id:
                self.error(path + ".id", "duplicate execution run ID")
                continue
            self.runs_by_id[run_id] = run
            mode = run.get("mode")
            if mode not in EXECUTION_MODES:
                self.error(path + ".mode", f"invalid execution mode {mode!r}")
            representative = run.get("representative_of_default")
            if not isinstance(representative, bool):
                self.error(path + ".representative_of_default", "must be true or false")
            semantic_overrides = self.validate_string_list(
                run.get("semantic_overrides"), path + ".semantic_overrides"
            )
            controlled_factors = self.validate_string_list(
                run.get("controlled_factors"), path + ".controlled_factors"
            )
            instrumentation = self.validate_string_list(
                run.get("instrumentation"), path + ".instrumentation"
            )
            observations = self.validate_string_list(
                run.get("observations"), path + ".observations"
            )
            if not observations:
                self.error(path + ".observations", "must contain at least one concrete observation")
            if not isinstance(run.get("entry_point"), str) or not run.get("entry_point", "").strip():
                self.error(path + ".entry_point", "must be a non-empty string")
            if run.get("outcome") not in RUN_OUTCOMES:
                self.error(path + ".outcome", "must be pass, fail, mixed, or inconclusive")
            if mode == "default_unmodified":
                if representative is not True:
                    self.error(path + ".representative_of_default", "default_unmodified runs must be representative")
                if semantic_overrides or controlled_factors:
                    self.error(path, "default_unmodified runs cannot have semantic overrides or controlled factors")
            elif mode == "observational_instrumentation":
                if semantic_overrides:
                    self.error(path + ".semantic_overrides", "observational runs cannot change artifact semantics")
                if controlled_factors:
                    self.error(path + ".controlled_factors", "observational runs cannot control behavior factors")
                if not instrumentation:
                    self.error(path + ".instrumentation", "observational runs must declare their instrumentation")
            elif mode == "controlled_diagnostic":
                if representative is not False:
                    self.error(path + ".representative_of_default", "controlled diagnostics cannot represent default behavior")
                if not semantic_overrides and not controlled_factors:
                    self.error(path, "controlled diagnostics must declare an override or controlled factor")
        if applicable and runs:
            first_run = runs[0] if isinstance(runs[0], dict) else {}
            if first_run.get("mode") != "default_unmodified":
                self.error("$.execution_evidence.runs[0].mode", "the first execution run must be default_unmodified")
        if applicable and not runs and not limitations:
            self.error("$.execution_evidence.limitations", "explain why applicable execution has no runs")
        if not applicable and runs:
            self.error("$.execution_evidence.runs", "must be empty when execution is not applicable")
        return execution

    def validate_dimensions(self, dimensions: list[Any]) -> dict[str, list[dict[str, Any]]]:
        found: dict[str, list[dict[str, Any]]] = {}
        for index, raw_dimension in enumerate(dimensions):
            path = f"$.rubric.dimensions[{index}]"
            dimension = self.require_dict(raw_dimension, path)
            dim_id = dimension.get("id")
            if dim_id not in FIXED_DIMENSIONS:
                self.error(path + ".id", f"unknown dimension {dim_id!r}")
                continue
            if dim_id in found:
                self.error(path + ".id", "duplicate dimension")
                continue
            possible = self.number(dimension.get("possible"), path + ".possible")
            if abs(possible - FIXED_DIMENSIONS[dim_id]) > TOLERANCE:
                self.error(path + ".possible", f"must equal {FIXED_DIMENSIONS[dim_id]}")
            checks = self.require_list(dimension.get("checks"), path + ".checks")
            normalized: list[dict[str, Any]] = []
            check_ids: set[str] = set()
            for check_index, raw_check in enumerate(checks):
                check_path = f"{path}.checks[{check_index}]"
                check = self.require_dict(raw_check, check_path)
                required_fields = (
                    "id",
                    "title",
                    "dimension",
                    "requirement_source",
                    "weight",
                    "status",
                    "earned",
                    "evidence_level",
                    "evidence",
                    "reason",
                    "behavior",
                    "core",
                    "default_path",
                    "evidence_run_ids",
                )
                for field in required_fields:
                    if field not in check:
                        self.error(check_path, f"missing required key {field!r}")
                check_id = check.get("id")
                if not isinstance(check_id, str) or not check_id:
                    self.error(check_path + ".id", "must be a non-empty string")
                elif check_id in check_ids:
                    self.error(check_path + ".id", "duplicate check id within dimension")
                else:
                    check_ids.add(check_id)
                if check.get("dimension") != dim_id:
                    self.error(check_path + ".dimension", f"must equal {dim_id!r}")
                weight = self.number(check.get("weight"), check_path + ".weight")
                earned = self.number(check.get("earned"), check_path + ".earned")
                if weight < 0:
                    self.error(check_path + ".weight", "cannot be negative")
                if earned < -TOLERANCE or earned - weight > TOLERANCE:
                    self.error(check_path + ".earned", "must be between zero and weight")
                status = check.get("status")
                if status not in CHECK_STATUSES:
                    self.error(check_path + ".status", f"invalid status {status!r}")
                behavior = check.get("behavior")
                if behavior not in BEHAVIORS:
                    self.error(check_path + ".behavior", "must be static or dynamic")
                evidence_level = check.get("evidence_level")
                if evidence_level not in EVIDENCE_LEVELS:
                    self.error(check_path + ".evidence_level", f"invalid level {evidence_level!r}")
                if evidence_level == "E0" and earned > TOLERANCE:
                    self.error(check_path + ".earned", "E0 checks cannot earn points")
                if evidence_level == "E1" and earned - (0.6 * weight) > TOLERANCE:
                    self.error(check_path + ".earned", "E1 checks are capped at 60% of weight")
                if behavior == "dynamic" and status == "pass" and evidence_level != "E3":
                    self.error(check_path + ".evidence_level", "passing dynamic checks require E3 evidence")
                if status in {"fail", "unverified", "not_applicable"} and earned > TOLERANCE:
                    self.error(check_path + ".earned", f"{status} checks cannot earn points")
                if status == "pass" and earned + TOLERANCE < weight:
                    self.error(check_path + ".earned", "pass checks must earn full weight")
                if not isinstance(check.get("evidence"), list):
                    self.error(check_path + ".evidence", "must be an array")
                if not isinstance(check.get("core"), bool):
                    self.error(check_path + ".core", "must be true or false")
                default_path = check.get("default_path")
                if not isinstance(default_path, bool):
                    self.error(check_path + ".default_path", "must be true or false")
                elif behavior == "static" and default_path:
                    self.error(check_path + ".default_path", "static checks cannot be default-path checks")
                run_ids = self.validate_run_ids(
                    check.get("evidence_run_ids"),
                    check_path + ".evidence_run_ids",
                    require_nonempty=evidence_level == "E3",
                )
                cited_outcomes = {self.runs_by_id.get(run_id, {}).get("outcome") for run_id in run_ids}
                if evidence_level == "E3" and status == "pass" and not cited_outcomes.intersection({"pass", "mixed"}):
                    self.error(check_path + ".evidence_run_ids", "a passing E3 check needs a pass or mixed run")
                if evidence_level == "E3" and status == "fail" and not cited_outcomes.intersection({"fail", "mixed"}):
                    self.error(check_path + ".evidence_run_ids", "a failing E3 check needs a fail or mixed run")
                if (
                    status == "pass"
                    and behavior == "dynamic"
                    and default_path is True
                    and not self.has_successful_representative_run(run_ids)
                ):
                    self.error(
                        check_path + ".evidence_run_ids",
                        "passing default-path dynamics need successful representative default evidence",
                    )
                normalized.append(check)
            if abs(sum(float(c.get("weight", 0)) for c in normalized if isinstance(c.get("weight"), (int, float))) - possible) > TOLERANCE:
                self.error(path + ".checks", "check weights must sum to the dimension possible points")
            found[dim_id] = normalized
        missing = set(FIXED_DIMENSIONS) - set(found)
        if missing:
            self.error("$.rubric.dimensions", "missing dimensions: " + ", ".join(sorted(missing)))
        return found

    def validate_hard_gates(self, gates: list[Any]) -> None:
        for index, raw_gate in enumerate(gates):
            path = f"$.rubric.hard_gates[{index}]"
            gate = self.require_dict(raw_gate, path)
            for field in ("id", "status", "behavior", "default_path", "evidence_run_ids", "reason"):
                if field not in gate:
                    self.error(path, f"missing required key {field!r}")
            if gate.get("status") not in {"pass", "fail", "unverified"}:
                self.error(path + ".status", "must be pass, fail, or unverified")
            if not isinstance(gate.get("id"), str) or not gate.get("id"):
                self.error(path + ".id", "must be a non-empty string")
            behavior = gate.get("behavior")
            if behavior not in BEHAVIORS:
                self.error(path + ".behavior", "must be static or dynamic")
            default_path = gate.get("default_path")
            if not isinstance(default_path, bool):
                self.error(path + ".default_path", "must be true or false")
            elif behavior == "static" and default_path:
                self.error(path + ".default_path", "static gates cannot be default-path gates")
            if self.scene_primary == "game" and behavior == "dynamic" and default_path is not True:
                self.error(path + ".default_path", "dynamic game hard gates must cover the default path")
            if not isinstance(gate.get("reason"), str) or not gate.get("reason", "").strip():
                self.error(path + ".reason", "must be a non-empty string")
            run_ids = self.validate_run_ids(
                gate.get("evidence_run_ids"),
                path + ".evidence_run_ids",
                require_nonempty=behavior == "dynamic" and gate.get("status") == "pass",
            )
            if (
                behavior == "dynamic"
                and gate.get("status") == "pass"
                and default_path is True
                and not self.has_successful_representative_run(run_ids)
            ):
                self.error(
                    path + ".evidence_run_ids",
                    "passing dynamic default-path gates need representative default evidence",
                )

    def validate_execution_cross_checks(
        self,
        checks_by_dimension: dict[str, list[dict[str, Any]]],
        result: dict[str, Any],
    ) -> None:
        all_checks = [check for checks in checks_by_dimension.values() for check in checks]
        if any(check.get("behavior") == "dynamic" for check in all_checks):
            if self.execution.get("applicable") is not True:
                self.error(
                    "$.execution_evidence.applicable",
                    "must be true when the rubric contains dynamic checks",
                )
        checks_by_id: dict[str, dict[str, Any]] = {}
        for check in all_checks:
            check_id = check.get("id")
            if isinstance(check_id, str):
                if check_id in checks_by_id:
                    self.error("$.rubric.dimensions", f"duplicate check ID across dimensions: {check_id!r}")
                checks_by_id[check_id] = check

        discrimination = self.require_list(
            self.execution.get("discrimination_checks"),
            "$.execution_evidence.discrimination_checks",
        )
        discrimination_by_check: dict[str, list[dict[str, Any]]] = {}
        for index, raw_item in enumerate(discrimination):
            path = f"$.execution_evidence.discrimination_checks[{index}]"
            item = self.require_dict(raw_item, path)
            check_id = item.get("check_id")
            if not isinstance(check_id, str) or not check_id:
                self.error(path + ".check_id", "must be a non-empty string")
            elif check_id not in checks_by_id:
                self.error(path + ".check_id", f"references unknown check {check_id!r}")
            else:
                discrimination_by_check.setdefault(check_id, []).append(item)
            for field in ("failure_model", "assertion"):
                if not isinstance(item.get(field), str) or not item.get(field, "").strip():
                    self.error(path + f".{field}", "must be a non-empty string")
            if not isinstance(item.get("would_fail_if_failure_present"), bool):
                self.error(path + ".would_fail_if_failure_present", "must be true or false")
            self.validate_run_ids(
                item.get("evidence_run_ids"), path + ".evidence_run_ids", require_nonempty=True
            )

        passing_core_dynamic = [
            check
            for check in all_checks
            if check.get("status") == "pass"
            and check.get("behavior") == "dynamic"
            and check.get("core") is True
        ]
        for check in passing_core_dynamic:
            items = discrimination_by_check.get(check.get("id"), [])
            if not items:
                self.error(
                    "$.execution_evidence.discrimination_checks",
                    f"missing discriminating assertion for passing core dynamic check {check.get('id')!r}",
                )
            elif not any(item.get("would_fail_if_failure_present") is True for item in items):
                self.error(
                    "$.execution_evidence.discrimination_checks",
                    f"check {check.get('id')!r} needs an assertion that would fail for the stated failure model",
                )

        successful_dynamic = [
            check
            for check in all_checks
            if check.get("status") in {"pass", "partial"} and check.get("behavior") == "dynamic"
        ]
        successful_dynamic_has_representative = any(
            self.has_successful_representative_run(check.get("evidence_run_ids", []))
            for check in successful_dynamic
        )
        confidence = result.get("confidence")
        if (
            successful_dynamic
            and not successful_dynamic_has_representative
            and isinstance(confidence, dict)
            and confidence.get("level") == "high"
        ):
            self.error(
                "$.result.confidence.level",
                "controlled-only dynamic success cannot support high confidence",
            )

        phases = self.require_list(
            self.execution.get("gameplay_phases"), "$.execution_evidence.gameplay_phases"
        )
        if self.scene_primary == "game":
            seen_phases: dict[str, str] = {}
            for index, raw_phase in enumerate(phases):
                path = f"$.execution_evidence.gameplay_phases[{index}]"
                phase = self.require_dict(raw_phase, path)
                phase_name = phase.get("phase")
                if phase_name not in GAMEPLAY_PHASES:
                    self.error(path + ".phase", f"invalid gameplay phase {phase_name!r}")
                elif phase_name in seen_phases:
                    self.error(path + ".phase", "duplicate gameplay phase")
                else:
                    seen_phases[phase_name] = phase.get("status")
                status = phase.get("status")
                if status not in PHASE_STATUSES:
                    self.error(path + ".status", "must be pass, partial, fail, or unverified")
                run_ids = self.validate_run_ids(
                    phase.get("evidence_run_ids"),
                    path + ".evidence_run_ids",
                    require_nonempty=status in {"pass", "partial"},
                )
                if status == "pass" and not self.has_successful_representative_run(run_ids):
                    self.error(path + ".evidence_run_ids", "passing gameplay phases need representative default evidence")
                if not isinstance(phase.get("observation"), str) or not phase.get("observation", "").strip():
                    self.error(path + ".observation", "must be a non-empty string")
                if phase_name == "attempted_failure":
                    if not isinstance(phase.get("active_controls_used"), bool):
                        self.error(path + ".active_controls_used", "must be true or false")
                    elif status == "pass" and phase.get("active_controls_used") is not True:
                        self.error(
                            path + ".active_controls_used",
                            "a passing attempted-failure phase requires active control use",
                        )
            missing_phases = GAMEPLAY_PHASES - set(seen_phases)
            if missing_phases:
                self.error(
                    "$.execution_evidence.gameplay_phases",
                    "missing phases: " + ", ".join(sorted(missing_phases)),
                )
            final_score = result.get("final_score")
            if isinstance(final_score, (int, float)) and final_score >= 80:
                nonpassing = sorted(name for name, status in seen_phases.items() if status != "pass")
                if nonpassing or missing_phases:
                    self.error(
                        "$.result.final_score",
                        "a game score of 80 or above requires every gameplay phase to pass",
                    )
        elif phases:
            self.error("$.execution_evidence.gameplay_phases", "must be empty outside game scenes")

        variations = self.require_list(
            self.execution.get("variation_coverage"), "$.execution_evidence.variation_coverage"
        )
        if (
            self.scene_primary == "game"
            and self.procedural_or_randomized
            and self.runs_by_id
            and not variations
        ):
            self.error(
                "$.execution_evidence.variation_coverage",
                "procedural or randomized games require variation coverage",
            )
        for index, raw_variation in enumerate(variations):
            path = f"$.execution_evidence.variation_coverage[{index}]"
            variation = self.require_dict(raw_variation, path)
            if not isinstance(variation.get("factor"), str) or not variation.get("factor", "").strip():
                self.error(path + ".factor", "must be a non-empty string")
            if variation.get("conclusion") not in VARIATION_CONCLUSIONS:
                self.error(path + ".conclusion", "must be pass, partial, fail, or unverified")
            if not isinstance(variation.get("reason"), str) or not variation.get("reason", "").strip():
                self.error(path + ".reason", "must be a non-empty string")
            cases = self.require_list(variation.get("cases"), path + ".cases")
            if len(cases) < 3:
                self.error(path + ".cases", "must contain at least three representative cases")
            kinds: set[str] = set()
            for case_index, raw_case in enumerate(cases):
                case_path = f"{path}.cases[{case_index}]"
                case = self.require_dict(raw_case, case_path)
                kind = case.get("kind")
                if kind not in VARIATION_KINDS:
                    self.error(case_path + ".kind", f"invalid variation kind {kind!r}")
                else:
                    kinds.add(kind)
                if not isinstance(case.get("label"), str) or not case.get("label", "").strip():
                    self.error(case_path + ".label", "must be a non-empty string")
                if case.get("outcome") not in RUN_OUTCOMES:
                    self.error(case_path + ".outcome", "must be pass, fail, mixed, or inconclusive")
                run_ids = self.validate_run_ids(
                    case.get("evidence_run_ids"), case_path + ".evidence_run_ids", require_nonempty=True
                )
                if kind == "default_sample" and not self.has_representative_run(run_ids):
                    self.error(case_path + ".evidence_run_ids", "default samples need representative default evidence")
            if "default_sample" not in kinds:
                self.error(path + ".cases", "must include a default_sample case")
            if not kinds.intersection({"boundary", "risk"}):
                self.error(path + ".cases", "must include a boundary or risk case")

        if self.scene_primary == "game" and self.time_sensitive_controls:
            control = self.require_dict(
                self.execution.get("control_response"), "$.execution_evidence.control_response"
            )
            status = control.get("status")
            if status not in PHASE_STATUSES:
                self.error("$.execution_evidence.control_response.status", "must be pass, partial, fail, or unverified")
            for field in (
                "single_input_effect",
                "rapid_input_effect",
                "available_response_window",
                "required_challenge_envelope",
                "reason",
            ):
                if not isinstance(control.get(field), str) or not control.get(field, "").strip():
                    self.error(f"$.execution_evidence.control_response.{field}", "must be a non-empty string")
            run_ids = self.validate_run_ids(
                control.get("evidence_run_ids"),
                "$.execution_evidence.control_response.evidence_run_ids",
                require_nonempty=status in {"pass", "partial", "fail"},
            )
            if status == "pass" and not self.has_successful_representative_run(run_ids):
                self.error(
                    "$.execution_evidence.control_response.evidence_run_ids",
                    "a passing control response needs successful representative default evidence",
                )
            final_score = result.get("final_score")
            if isinstance(final_score, (int, float)) and final_score >= 80 and status != "pass":
                self.error(
                    "$.result.final_score",
                    "a time-sensitive game score of 80 or above requires control response to pass",
                )

        adversarial = self.require_dict(
            self.execution.get("adversarial_review"), "$.execution_evidence.adversarial_review"
        )
        status = adversarial.get("status")
        if status not in {"completed", "not_required"}:
            self.error("$.execution_evidence.adversarial_review.status", "must be completed or not_required")
        score_before = result.get("score_before_cap")
        review_required = self.scene_primary == "game" and isinstance(score_before, (int, float)) and score_before >= 90
        if review_required and status != "completed":
            self.error(
                "$.execution_evidence.adversarial_review.status",
                "provisional game scores of 90 or above require an adversarial review",
            )
        if status == "not_required":
            if not isinstance(adversarial.get("reason"), str) or not adversarial.get("reason", "").strip():
                self.error("$.execution_evidence.adversarial_review.reason", "must explain why review is not required")
        elif status == "completed":
            if adversarial.get("performed_after_provisional_score") is not True:
                self.error(
                    "$.execution_evidence.adversarial_review.performed_after_provisional_score",
                    "must be true",
                )
            challenges = self.require_list(
                adversarial.get("challenges"), "$.execution_evidence.adversarial_review.challenges"
            )
            if not challenges:
                self.error("$.execution_evidence.adversarial_review.challenges", "must not be empty")
            for index, raw_challenge in enumerate(challenges):
                path = f"$.execution_evidence.adversarial_review.challenges[{index}]"
                challenge = self.require_dict(raw_challenge, path)
                for field in ("hypothesis", "method", "outcome"):
                    if not isinstance(challenge.get(field), str) or not challenge.get(field, "").strip():
                        self.error(path + f".{field}", "must be a non-empty string")
                self.validate_run_ids(
                    challenge.get("evidence_run_ids"), path + ".evidence_run_ids", require_nonempty=True
                )

    def validate_result(
        self,
        result: dict[str, Any],
        checks_by_dimension: dict[str, list[dict[str, Any]]],
        rubric: dict[str, Any],
    ) -> None:
        dimension_scores = self.require_list(result.get("dimension_scores"), "$.result.dimension_scores")
        score_map: dict[str, tuple[float, float]] = {}
        for index, raw_score in enumerate(dimension_scores):
            path = f"$.result.dimension_scores[{index}]"
            score = self.require_dict(raw_score, path)
            dim_id = score.get("id")
            if dim_id not in FIXED_DIMENSIONS:
                self.error(path + ".id", f"unknown dimension {dim_id!r}")
                continue
            if dim_id in score_map:
                self.error(path + ".id", "duplicate dimension score")
                continue
            earned = self.number(score.get("earned"), path + ".earned")
            possible = self.number(score.get("possible"), path + ".possible")
            if abs(possible - FIXED_DIMENSIONS[dim_id]) > TOLERANCE:
                self.error(path + ".possible", f"must equal {FIXED_DIMENSIONS[dim_id]}")
            expected = sum(
                float(check.get("earned", 0))
                for check in checks_by_dimension.get(dim_id, [])
                if isinstance(check.get("earned"), (int, float))
            )
            if abs(earned - expected) > TOLERANCE:
                self.error(path + ".earned", f"must equal check total {expected:g}")
            score_map[dim_id] = (earned, possible)
        if set(score_map) != set(FIXED_DIMENSIONS):
            self.error("$.result.dimension_scores", "must contain all five fixed dimensions exactly once")

        score_before = self.number(result.get("score_before_cap"), "$.result.score_before_cap")
        expected_before = sum(value[0] for value in score_map.values())
        if abs(score_before - expected_before) > TOLERANCE:
            self.error("$.result.score_before_cap", f"must equal dimension total {expected_before:g}")

        cap = result.get("score_cap")
        if cap is not None:
            cap_value = self.number(cap, "$.result.score_cap")
            if cap_value < 0 or cap_value > 100:
                self.error("$.result.score_cap", "must be null or between 0 and 100")
        else:
            cap_value = 100.0
        final_score = self.number(result.get("final_score"), "$.result.final_score")
        expected_final = round(min(score_before, cap_value))
        if abs(final_score - expected_final) > TOLERANCE:
            self.error("$.result.final_score", f"must equal rounded capped score {expected_final}")
        if final_score < 0 or final_score > 100 or abs(final_score - round(final_score)) > TOLERANCE:
            self.error("$.result.final_score", "must be an integer from 0 to 100")

        expected_verdict = (
            "excellent_pass"
            if final_score >= 90
            else "full_pass"
            if final_score >= 80
            else "partial_pass"
            if final_score >= 60
            else "fail"
        )
        verdict = result.get("verdict")
        if verdict not in VERDICTS:
            self.error("$.result.verdict", f"invalid verdict {verdict!r}")
        elif verdict != expected_verdict:
            self.error("$.result.verdict", f"score requires {expected_verdict!r}")

        gates = rubric.get("hard_gates", [])
        nonpassing_gate = any(isinstance(gate, dict) and gate.get("status") != "pass" for gate in gates)
        if nonpassing_gate and verdict in {"full_pass", "excellent_pass"}:
            self.error("$.result.verdict", "all hard gates must pass for full_pass or excellent_pass")

        all_checks = [check for checks in checks_by_dimension.values() for check in checks]
        applicable = [check for check in all_checks if check.get("status") != "not_applicable"]
        denominator = sum(float(check.get("weight", 0)) for check in applicable)
        numerator = sum(
            float(check.get("weight", 0))
            for check in applicable
            if check.get("evidence_level") in {"E3", "E2"}
        )
        expected_coverage = round(100 * numerator / denominator) if denominator else 0
        coverage = self.number(result.get("evidence_coverage"), "$.result.evidence_coverage")
        if abs(coverage - expected_coverage) > 1.0:
            self.error("$.result.evidence_coverage", f"must match strong-evidence coverage {expected_coverage}%")

        confidence = self.require_dict(result.get("confidence"), "$.result.confidence")
        if confidence.get("level") not in CONFIDENCE_LEVELS:
            self.error("$.result.confidence.level", "must be high, medium, or low")
        if not isinstance(confidence.get("reasons"), list) or not confidence.get("reasons"):
            self.error("$.result.confidence.reasons", "must be a non-empty array")
        if coverage < 50 and confidence.get("level") != "low":
            self.error("$.result.confidence.level", "coverage below 50% requires low confidence")

        if not isinstance(result.get("cap_reasons"), list):
            self.error("$.result.cap_reasons", "must be an array")
        if cap is not None and not result.get("cap_reasons"):
            self.error("$.result.cap_reasons", "must explain a non-null cap")
        for field in ("findings", "unverified_items"):
            if not isinstance(result.get(field), list):
                self.error(f"$.result.{field}", "must be an array")

    def validate_process(self, process: dict[str, Any]) -> None:
        status = process.get("status")
        if status not in {"completed", "unavailable"}:
            self.error("$.process_analysis.status", "must be completed or unavailable")
            return
        if status == "unavailable":
            if not isinstance(process.get("reason"), str) or not process.get("reason"):
                self.error("$.process_analysis.reason", "must explain why analysis is unavailable")
            return

        if not isinstance(process.get("platform"), str) or not process.get("platform"):
            self.error("$.process_analysis.platform", "must be a non-empty string")
        if not isinstance(process.get("metrics"), dict):
            self.error("$.process_analysis.metrics", "must be an object")
        issues = self.require_list(process.get("issues"), "$.process_analysis.issues")
        for index, raw_issue in enumerate(issues):
            path = f"$.process_analysis.issues[{index}]"
            issue = self.require_dict(raw_issue, path)
            if issue.get("severity") not in SEVERITIES:
                self.error(path + ".severity", "invalid severity")
            if issue.get("user_visible") not in USER_VISIBLE_VALUES:
                self.error(path + ".user_visible", "must be true, false, or 'unknown'")
            if "visibility" in issue:
                self.error(path + ".visibility", "legacy field is not allowed; use user_visible")
            if "direct_impact" in issue:
                self.error(path + ".direct_impact", "field is no longer allowed")
            if issue.get("attribution") not in ATTRIBUTIONS:
                self.error(path + ".attribution", "invalid attribution")
            if not isinstance(issue.get("surfaces"), list):
                self.error(path + ".surfaces", "must be an array")
            if issue.get("user_visible") is True:
                visible_surfaces = set(issue.get("surfaces", [])) & USER_VISIBLE_SURFACES
                if not visible_surfaces:
                    self.error(path + ".surfaces", "user-visible issues need a user-facing surface")
            evidence = self.require_list(issue.get("evidence"), path + ".evidence")
            if issue.get("severity") != "observation" and not evidence:
                self.error(path + ".evidence", "non-observation issues need verbatim evidence")
            for evidence_index, raw_item in enumerate(evidence):
                evidence_path = f"{path}.evidence[{evidence_index}]"
                item = self.require_dict(raw_item, evidence_path)
                if not item.get("timestamp"):
                    self.error(evidence_path + ".timestamp", "is required")
                if not item.get("quote"):
                    self.error(evidence_path + ".quote", "is required")
                if not item.get("actor"):
                    self.error(evidence_path + ".actor", "is required")
                if not item.get("event_type"):
                    self.error(evidence_path + ".event_type", "is required")
                if item.get("event_index") is None and item.get("source_line") is None and not item.get("event_id"):
                    self.error(evidence_path, "needs event_index, source_line, or event_id")

    def validate_flow(self, flow: dict[str, Any]) -> None:
        status = flow.get("status")
        if status not in {"generated", "unavailable"}:
            self.error("$.flow_diagram.status", "must be generated or unavailable")
            return
        if status == "unavailable":
            if not flow.get("reason"):
                self.error("$.flow_diagram.reason", "must explain why the flow is unavailable")
            return
        paths = self.require_dict(flow.get("paths"), "$.flow_diagram.paths")
        if not paths.get("mermaid"):
            self.error("$.flow_diagram.paths.mermaid", "is required for a generated flow")
        for label, value in paths.items():
            if value in (None, ""):
                continue
            if not isinstance(value, str):
                self.error(f"$.flow_diagram.paths.{label}", "must be a string or null")
                continue
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = self.base_dir / candidate
            if not candidate.exists():
                self.error(f"$.flow_diagram.paths.{label}", f"file does not exist: {candidate}")


def self_test_document(base_dir: Path) -> dict[str, Any]:
    dimensions = []
    scores = []
    for dim_id, possible in FIXED_DIMENSIONS.items():
        check = {
            "id": f"{dim_id}-1",
            "title": "Fixture check",
            "dimension": dim_id,
            "requirement_source": "self-test",
            "weight": possible,
            "status": "pass",
            "earned": possible,
            "evidence_level": "E2",
            "evidence": ["validator fixture"],
            "reason": "Fixture is internally consistent.",
            "behavior": "static",
            "core": False,
            "default_path": False,
            "evidence_run_ids": [],
        }
        dimensions.append({"id": dim_id, "possible": possible, "checks": [check]})
        scores.append({"id": dim_id, "earned": possible, "possible": possible})
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluation": {"id": "self-test", "created_at": "2026-01-01T00:00:00Z"},
        "inputs": {"original_prompt": "self-test"},
        "scene": {"primary": "general"},
        "rubric": {"frozen_before_artifact_review": True, "dimensions": dimensions, "hard_gates": []},
        "execution_evidence": {
            "applicable": False,
            "runs": [],
            "discrimination_checks": [],
            "gameplay_phases": [],
            "variation_coverage": [],
            "adversarial_review": {
                "status": "not_required",
                "reason": "The fixture contains only static checks.",
            },
            "limitations": [],
        },
        "result": {
            "score_before_cap": 100,
            "score_cap": None,
            "cap_reasons": [],
            "final_score": 100,
            "verdict": "excellent_pass",
            "evidence_coverage": 100,
            "confidence": {"level": "high", "reasons": ["Complete fixture evidence."]},
            "dimension_scores": scores,
            "findings": [],
            "unverified_items": [],
        },
        "process_analysis": {"status": "unavailable", "reason": "No trace in fixture."},
        "flow_diagram": {"status": "unavailable", "reason": "No trace in fixture."},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test and not args.json_path:
        parser.error("provide JSON_PATH or --self-test")

    if args.self_test:
        base_dir = Path.cwd()
        document = self_test_document(base_dir)
        label = "built-in fixture"
    else:
        if not args.json_path.is_file():
            print(f"error: file does not exist: {args.json_path}", file=sys.stderr)
            return 2
        try:
            document = json.loads(args.json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot read JSON: {exc}", file=sys.stderr)
            return 2
        base_dir = args.json_path.resolve().parent
        label = str(args.json_path)

    errors = Validator(document, base_dir).validate()
    if errors:
        print(f"[FAIL] {label}: {len(errors)} validation error(s)", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"[OK] {label}: evaluation JSON is internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
