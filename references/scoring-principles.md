# Scoring principles

## Evaluation contract

Create the rubric from the original prompt before inspecting artifact behavior or trace outcomes. The frozen rubric must contain:

- primary and secondary scene;
- explicit requirements;
- necessary implied requirements;
- optional features;
- five fixed dimensions totaling 100 points;
- weighted checks and intended evidence methods;
- hard gates and potential score caps;
- any within-dimension reallocation and its reason.

Do not add a high-weight check merely because the artifact happens to implement it. Do not remove an expected check after discovering that it fails.

## Requirement sources

Label every check as one of:

- `explicit_prompt`: directly requested by the user;
- `necessary_implied`: required for the explicit task to be usable or logically complete;
- `quality_floor`: a minimal integrity or operability expectation for the artifact type;
- `optional_feature`: model-added or nice-to-have behavior.

Optional features receive no requirement-fulfillment points unless the prompt makes them relevant. A harmful optional feature may reduce usability, robustness, or claim consistency.

## Fixed dimensions

### Requirement fulfillment — 50

Allocate most points to explicit primary goals, then explicit supporting requirements, then the minimum implied operational loop. A typical distribution is:

- primary goals: 25-35;
- explicit supporting requirements: 10-20;
- necessary implied requirements: 5-10.

### Correctness and domain quality — 20

Evaluate logical, numerical, content, data, rule, reference-fidelity, and state correctness as appropriate to the scene.

### Usability and operational loop — 15

Evaluate whether a user can enter, act, receive feedback, complete the task, and repeat or continue when the prompt implies repetition.

### Robustness and boundary behavior — 10

Evaluate runtime/file integrity, representative boundary cases, repeated operations, dependency failures, and relevant viewport or scale changes.

### Delivery and claim consistency — 5

Evaluate correct files and entry points, necessary run instructions, and whether the final response accurately describes delivered and verified behavior.

## Calibration stance

Preserve case-specific judgment: derive the checks and their weights from the prompt rather than forcing every task into identical subchecks. Calibrate those judgments consistently:

- Judge explicit capability before polish. A requested capability earns full requirement-fulfillment credit when it demonstrably exists and works in the ordinary intended flow. Put localized correctness, usability, robustness, or presentation defects in the dimension that best represents their harm instead of automatically making the explicit requirement partial as well.
- Make a requirement partial when the restriction materially narrows the requested capability, blocks a common path, or requires a workaround that changes the intended workflow. Do not make it partial merely because an optional enhancement or a model-added subfeature is defective.
- Treat valid but extreme boundary errors, localized workflow friction with a clear workaround, and isolated educational/copy defects as material but usually medium issues. Reserve high severity for a core capability that is absent, unusable, or untrustworthy in the default/common workflow, has no reasonable workaround, or affects a broad portion of supported inputs.
- Score the requested artifact, not the ambition of the agent's final message. A broken model-added feature normally belongs in delivery/claim consistency; it affects a requested requirement only when it also harms that required behavior.
- Do not let evidence quantity substitute for product quality. Better direct evidence may resolve uncertainty, but it should not cause a new scoring philosophy.

Use these verdict anchors as a final reasonableness check, not as a replacement for weighted checks:

- `90–100`: all explicit core capabilities work in direct execution; remaining defects are localized, boundary-specific, cosmetic, or low-friction. Normally no high-severity result finding.
- `80–89`: the core task is complete, but a common workflow has a material defect, or several medium defects noticeably reduce trust or usability.
- `60–79`: at least one core capability is substantially impaired, unreliable in ordinary use, or only recoverable through a disruptive workaround; alternatively, defects are widespread across the main loop.
- `0–59`: a core capability is absent/unusable, the artifact is missing or broken, or a hard cap applies.

If the weighted total contradicts these anchors, revisit check scopes, duplicate deductions, and partial-credit proportions before finalizing. Keep the original weighted result only when the report gives a concrete task-specific reason for the apparent mismatch.

## Status and scoring

Use `pass`, `partial`, `fail`, `unverified`, or `not_applicable`.

- `pass`: the stated behavior is supported by sufficient evidence;
- `partial`: meaningful behavior works but the requirement is incomplete or restricted;
- `fail`: evidence contradicts or does not deliver the requirement;
- `unverified`: evidence could not establish behavior;
- `not_applicable`: the check does not apply and was reallocated before review.

Do not assign one universal percentage to every `partial`; explain the observed completion proportion. Use proportional anchors to avoid arbitrary severity drift:

- minor/localized restriction: retain roughly 80–90% of the affected check;
- material restriction with a usable workaround or boundary-limited correctness error: retain roughly 55–75%;
- major restriction affecting the normal path: retain roughly 20–50%;
- capability absent or contradicted: `fail`, earning zero.

These are calibration bands, not automatic formulas. Deviate when the task warrants it, but explain why. Keep check-level earned points to one decimal if needed. Sum dimensions, calculate `score_before_cap`, apply the most restrictive cap, then round the final score to an integer.

## Caps and verdicts

Typical caps:

- missing or wholly unusable artifact: 20;
- artifact opens but the core task cannot be executed: 39;
- one key explicit capability completely absent: 59;
- all core capabilities exist but the main workflow is substantially impaired by material defects: normally 60-79;
- all core capabilities work and defects are localized or have straightforward workarounds: normally 80 or above.

Verdicts:

- 90-100: `excellent_pass`;
- 80-89: `full_pass`;
- 60-79: `partial_pass`;
- 0-59: `fail`.

A hard-gate failure forbids `full_pass` and `excellent_pass`, regardless of the arithmetic score.

## Avoiding duplicate deductions

Assign a `root_cause_id` when several observations arise from one defect. Take the main deduction in the dimension that best represents the harm. Related checks may describe the same evidence but must not each subtract the full cost of the same root cause.

Separate harms may be scored separately. For example, an initialization error may reduce functionality, while a later false completion claim about that same feature may independently reduce claim consistency.

Before finalizing, create a compact mental or written deduction ledger by root cause:

1. identify the primary dimension and primary point deduction;
2. list any secondary deduction and the distinct additional harm it represents;
3. remove secondary deductions that merely restate the same consequence;
4. compare the total cost with the severity anchors below.

As a scale check, one medium root cause should not normally cost more than about five total points across the score, and one high root cause should not be scattered across several dimensions without an explicit independent-harm explanation. This is a consistency guard, not a fixed penalty schedule.

## Result-finding severity anchors

- `critical`: unusable or dangerous delivery, destructive behavior, severe security/privacy exposure, or irrecoverable corruption.
- `high`: a required core capability is missing or fails in the default/common path, results are broadly untrustworthy, or no practical workaround exists.
- `medium`: a reachable boundary or subset is wrong, an intended workflow has meaningful friction but a workaround exists, or a requested capability is locally restricted.
- `low`: cosmetic, copy, labeling, minor accessibility, or optional-feature defect with little effect on completing the task.
- `observation`: noteworthy evidence without enough support for a defect.

Severity describes user consequence, not implementation ugliness or the number of failed tool calls.

## Final scale audit

Before writing the result:

- compare the result against the verdict anchors;
- confirm that every deduction maps to an evidenced check and root cause;
- confirm that model-added extras did not displace requested functionality;
- confirm that an edge-case defect was not treated like a default-path failure without justification;
- confirm that evaluator/tool limitations lowered evidence coverage and confidence rather than being described as artifact defects;
- confirm that every passing core default-path dynamic check cites a representative unmodified or behavior-neutral run rather than only a controlled diagnostic;
- confirm that each core dynamic pass has a discriminating assertion capable of detecting a severely degraded implementation;
- for randomized or procedural behavior, compare the reachable response envelope with representative nominal and risk regions instead of generalizing from one favorable seed;
- for a provisional game score of 90 or above, complete the adversarial review and revise the score if its challenge changes the evidence;
- if the score would plausibly move by more than five points under another reasonable reading of the same evidence, narrow the ambiguous check, revisit duplicate deductions, and state the remaining judgment call.

## Fairness boundaries

- Score the requested task, not an imagined production system.
- Apply a minimum usable quality floor, not default production requirements.
- Do not use personal aesthetic taste as a correctness criterion.
- Do not reward verbosity, number of files, architectural complexity, or extra features by themselves.
- Do not penalize an efficient process when the artifact is excellent.
- Do not improve the result score because the trace appears disciplined.
- Do not lower the result score for missing trace data.
- Explain every deduction with artifact evidence or a clearly identified unverified status.
