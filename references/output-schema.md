# Output schema

## Required files

Write outputs to a separate task-owned directory:

- `evaluation-report.md` — human-readable report;
- `evaluation-result.json` — machine-readable source of truth;
- `agent-flow.mmd` — editable action flow when trace data exists;
- `agent-flow.png` and `agent-flow.svg` — rendered forms when supported.

## JSON top level

```json
{
  "schema_version": "1.2",
  "evaluation": {
    "id": "task-slug",
    "created_at": "ISO-8601"
  },
  "inputs": {},
  "scene": {},
  "rubric": {},
  "execution_evidence": {},
  "result": {},
  "process_analysis": {},
  "flow_diagram": {}
}
```

### Inputs

Include the exact original prompt and resolved artifact/trace metadata. Each optional input includes `path`, `provided`, `discovery_method`, and `confidence`.

### Scene

Use a primary scene of `web`, `game`, `file-processing`, or `general`. Add `subtype` and `secondary` scenes when relevant. For `game`, include `procedural_or_randomized: true|false` and `time_sensitive_controls: true|false`.

### Rubric

Include:

- `frozen_before_artifact_review`;
- five fixed dimensions and their possible points;
- hard gates;
- weighted checks;
- within-dimension reallocations;
- potential score caps.

Every check includes `id`, `title`, `dimension`, `requirement_source`, `weight`, `status`, `earned`, `evidence_level`, `evidence`, `reason`, `behavior` (`static` or `dynamic`), `core`, `default_path`, and `evidence_run_ids`. `E3` checks must cite at least one execution run. Static checks must set `default_path: false`.

Every hard gate includes `id`, `status`, `behavior`, `default_path`, `evidence_run_ids`, and `reason`. A passing dynamic default-path gate must cite representative default evidence.

### Execution evidence

Use:

```json
{
  "applicable": true,
  "runs": [
    {
      "id": "run-default-1",
      "mode": "default_unmodified",
      "representative_of_default": true,
      "semantic_overrides": [],
      "controlled_factors": [],
      "instrumentation": [],
      "entry_point": "index.html",
      "outcome": "mixed",
      "observations": ["Game launched and accepted Space input."]
    }
  ],
  "discrimination_checks": [],
  "gameplay_phases": [],
  "variation_coverage": [],
  "control_response": {},
  "adversarial_review": {"status": "not_required", "reason": "Provisional game score below 90."},
  "limitations": []
}
```

`mode` is `default_unmodified`, `observational_instrumentation`, or `controlled_diagnostic`; follow [evidence-policy.md](evidence-policy.md). Runs are chronological. When execution is applicable and possible, the first run must be `default_unmodified`.

For each passing core dynamic check, add a `discrimination_checks` item with `check_id`, `failure_model`, `assertion`, `would_fail_if_failure_present: true`, and `evidence_run_ids`.

For games, `gameplay_phases` contains exactly one item for each of `launch`, `meaningful_input_response`, `progression`, `attempted_failure`, `terminal_state`, and `replay`; each item includes `status`, `evidence_run_ids`, and a concrete `observation`. A passing `attempted_failure` item also includes `active_controls_used: true`.

When `scene.time_sensitive_controls` is true, `control_response` includes `status`, `single_input_effect`, `rapid_input_effect`, `available_response_window`, `required_challenge_envelope`, `reason`, and `evidence_run_ids`. A passing control response must cite successful representative default evidence.

When `scene.procedural_or_randomized` is true and execution produced runs, `variation_coverage` contains one item per completion-relevant factor. Each item includes `factor`, `conclusion`, `reason`, and at least three `cases`. A case includes `kind` (`default_sample`, `nominal`, `boundary`, or `risk`), `label`, `outcome`, and `evidence_run_ids`; the set must include a default sample and a boundary or risk case. If execution is unavailable, leave it empty and explain the limitation.

For a provisional game score of 90 or above, set `adversarial_review.status` to `completed`, set `performed_after_provisional_score: true`, and include one or more `challenges`. Each challenge includes `hypothesis`, `method`, `outcome`, and `evidence_run_ids`. Otherwise use `status: not_required` with a reason.

### Result

Include:

- `score_before_cap`;
- `score_cap` or `null`;
- `cap_reasons`;
- `final_score`;
- `verdict`;
- `evidence_coverage`;
- `confidence` with reasons;
- five `dimension_scores`;
- result findings;
- unverified items.

### Process analysis

Use `status: completed` or `unavailable`. For completed analysis include platform, metrics, and issues. Every issue has `user_visible` set to `true`, `false`, or `unknown`; do not include a `direct_impact` field. Every non-observation issue needs timestamped verbatim evidence.

### Flow diagram

Record status and relative or absolute paths for generated Mermaid, PNG, and SVG files. Missing render formats are allowed when their renderer is unavailable; state the reason.

## Markdown report

Use this order:

1. Evaluation inputs
2. Executive result
3. Frozen scoring contract
4. Execution evidence and test adequacy
5. Result score by dimension
6. Hard gates and caps
7. Findings and evidence
8. Unverified items and confidence
9. Coding-process issues
10. User-visible process issues
11. Agent action-flow diagram
12. Prioritized recommendations

Keep artifact findings separate from process issues. Quote trace text only in process sections. Link generated files with absolute local paths when the host supports them.

## Final conversation response

State:

- final score and verdict;
- evidence coverage and confidence;
- count of result findings;
- count of process issues;
- count of user-visible process issues;
- links to the report, JSON, and available diagram files.

Do not repeat the full report in the conversation.
