#!/usr/bin/env python3
"""Regression tests for execution-provenance validation."""

from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate_evaluation.py")
SPEC = importlib.util.spec_from_file_location("validate_evaluation", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR_MODULE)


def game_document() -> dict:
    document = VALIDATOR_MODULE.self_test_document(Path.cwd())
    document["scene"] = {
        "primary": "game",
        "procedural_or_randomized": True,
        "time_sensitive_controls": True,
    }

    core_check = document["rubric"]["dimensions"][0]["checks"][0]
    core_check.update(
        {
            "behavior": "dynamic",
            "core": True,
            "default_path": True,
            "evidence_level": "E3",
            "evidence_run_ids": ["run-default"],
        }
    )
    document["rubric"]["hard_gates"] = [
        {
            "id": "playable-loop",
            "status": "pass",
            "behavior": "dynamic",
            "default_path": True,
            "evidence_run_ids": ["run-default"],
            "reason": "The default run completed the loop.",
        }
    ]
    document["execution_evidence"] = {
        "applicable": True,
        "runs": [
            {
                "id": "run-default",
                "mode": "default_unmodified",
                "representative_of_default": True,
                "semantic_overrides": [],
                "controlled_factors": [],
                "instrumentation": [],
                "entry_point": "index.html",
                "outcome": "pass",
                "observations": ["A normal playthrough completed and restarted."],
            },
            {
                "id": "run-nominal",
                "mode": "controlled_diagnostic",
                "representative_of_default": False,
                "semantic_overrides": ["Fixed spawn sequence to a nominal case."],
                "controlled_factors": ["Nominal spawn position."],
                "instrumentation": [],
                "entry_point": "index.html",
                "outcome": "pass",
                "observations": ["The nominal generated case was reachable."],
            },
            {
                "id": "run-risk",
                "mode": "controlled_diagnostic",
                "representative_of_default": False,
                "semantic_overrides": ["Fixed spawn sequence to a risk case."],
                "controlled_factors": ["Boundary spawn position."],
                "instrumentation": [],
                "entry_point": "index.html",
                "outcome": "pass",
                "observations": ["The boundary generated case was reachable."],
            },
        ],
        "discrimination_checks": [
            {
                "check_id": core_check["id"],
                "failure_model": "Inputs are delivered but movement is too small to affect play.",
                "assertion": "A normal input burst crosses the required challenge envelope.",
                "would_fail_if_failure_present": True,
                "evidence_run_ids": ["run-default"],
            }
        ],
        "gameplay_phases": [],
        "variation_coverage": [
            {
                "factor": "generated obstacle position",
                "conclusion": "pass",
                "reason": "Default, nominal, and boundary regions were exercised.",
                "cases": [
                    {
                        "kind": "default_sample",
                        "label": "Unmodified generated sequence",
                        "outcome": "pass",
                        "evidence_run_ids": ["run-default"],
                    },
                    {
                        "kind": "nominal",
                        "label": "Nominal position",
                        "outcome": "pass",
                        "evidence_run_ids": ["run-nominal"],
                    },
                    {
                        "kind": "risk",
                        "label": "Boundary position",
                        "outcome": "pass",
                        "evidence_run_ids": ["run-risk"],
                    },
                ],
            }
        ],
        "control_response": {
            "status": "pass",
            "single_input_effect": "One input moved the player by a visible, measured amount.",
            "rapid_input_effect": "A short burst traversed the required vertical range.",
            "available_response_window": "The first obstacle allowed 2.8 seconds to react.",
            "required_challenge_envelope": "All sampled gaps were within the measured reachable range.",
            "reason": "Measured input response covered default and risk-region challenges.",
            "evidence_run_ids": ["run-default"],
        },
        "adversarial_review": {
            "status": "completed",
            "performed_after_provisional_score": True,
            "challenges": [
                {
                    "hypothesis": "A favorable default sample hides unreachable boundary positions.",
                    "method": "Force a risk-region spawn and compare it with the input envelope.",
                    "outcome": "The risk case remained reachable.",
                    "evidence_run_ids": ["run-risk"],
                }
            ],
        },
        "limitations": [],
    }
    for phase in sorted(VALIDATOR_MODULE.GAMEPLAY_PHASES):
        item = {
            "phase": phase,
            "status": "pass",
            "evidence_run_ids": ["run-default"],
            "observation": f"Observed {phase} during active default play.",
        }
        if phase == "attempted_failure":
            item["active_controls_used"] = True
        document["execution_evidence"]["gameplay_phases"].append(item)
    return document


class ExecutionEvidenceTests(unittest.TestCase):
    def validate(self, document: dict) -> list[str]:
        return VALIDATOR_MODULE.Validator(document, Path.cwd()).validate()

    def test_representative_game_evidence_passes(self) -> None:
        self.assertEqual(self.validate(game_document()), [])

    def test_favorable_controlled_case_cannot_prove_default_playability(self) -> None:
        document = copy.deepcopy(game_document())
        document["execution_evidence"]["runs"][0]["outcome"] = "fail"
        controlled_id = "run-nominal"
        core_check = document["rubric"]["dimensions"][0]["checks"][0]
        core_check["evidence_run_ids"] = [controlled_id]
        document["rubric"]["hard_gates"][0]["evidence_run_ids"] = [controlled_id]
        document["execution_evidence"]["discrimination_checks"][0]["evidence_run_ids"] = [controlled_id]
        for phase in document["execution_evidence"]["gameplay_phases"]:
            phase["evidence_run_ids"] = [controlled_id]
        document["execution_evidence"]["control_response"]["evidence_run_ids"] = [controlled_id]

        errors = self.validate(document)
        joined = "\n".join(errors)
        self.assertIn("passing default-path dynamics need successful representative default evidence", joined)
        self.assertIn("passing dynamic default-path gates need representative default evidence", joined)
        self.assertIn("controlled-only dynamic success cannot support high confidence", joined)
        self.assertIn("passing gameplay phases need representative default evidence", joined)

    def test_failed_default_run_cannot_be_laundered_into_a_pass(self) -> None:
        document = copy.deepcopy(game_document())
        document["execution_evidence"]["runs"][0]["outcome"] = "fail"

        errors = self.validate(document)
        joined = "\n".join(errors)
        self.assertIn("a passing E3 check needs a pass or mixed run", joined)
        self.assertIn("passing default-path dynamics need successful representative default evidence", joined)
        self.assertIn("passing dynamic default-path gates need representative default evidence", joined)
        self.assertIn("passing gameplay phases need representative default evidence", joined)

    def test_dynamic_pass_requires_direct_execution(self) -> None:
        document = game_document()
        document["rubric"]["dimensions"][0]["checks"][0]["evidence_level"] = "E2"

        errors = self.validate(document)
        self.assertIn(
            "passing dynamic checks require E3 evidence",
            "\n".join(errors),
        )

    def test_high_scoring_time_sensitive_game_requires_control_response_pass(self) -> None:
        document = game_document()
        document["execution_evidence"]["control_response"]["status"] = "fail"

        errors = self.validate(document)
        self.assertIn(
            "a time-sensitive game score of 80 or above requires control response to pass",
            "\n".join(errors),
        )

    def test_procedural_game_requires_variation_matrix(self) -> None:
        document = game_document()
        document["execution_evidence"]["variation_coverage"] = []

        errors = self.validate(document)
        self.assertIn(
            "procedural or randomized games require variation coverage",
            "\n".join(errors),
        )


if __name__ == "__main__":
    unittest.main()
