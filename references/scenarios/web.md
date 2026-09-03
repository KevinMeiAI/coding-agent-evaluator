# Generated Webpage Evaluation

Use this scenario for landing pages, dashboards, interactive demos, calculators,
single-page utilities, and other browser-delivered artifacts. If the page has a
game loop, score it with `game.md` and use this file only for shared web quality.

## Hard gates

- The deliverable opens through the promised entry point.
- The page renders meaningful content rather than an empty, crashed, or placeholder state.
- The primary interaction requested by the prompt exists.
- Required local assets are present and resolvable.

A failed entry point or wholly missing primary interaction normally caps the result
at 59. Cosmetic defects do not trigger a hard gate.

## Requirement fit — 50 points

Derive checks from the prompt before inspecting behavior. A useful allocation is:

- 5–10 points: required format, entry point, and platform constraints.
- 25–35 points: named content and functional interactions.
- 5–15 points: prompt-specific visual, responsive, accessibility, or data needs.

Do not award unrequested production features merely because they are impressive.
Do not deduct for omitted features that the prompt never asked for unless they are
part of the minimum usable floor below.

## Correctness — 20 points

Check calculations, state transitions, data binding, event behavior, timing, and
consistency between displayed information and actual behavior. For simulations,
compare representative and boundary inputs with independently calculated expected
values. For data-driven pages, check loading, empty, error, and stale states when
they are relevant.

## Usability — 15 points

The minimum usable floor is:

- The main purpose is apparent without reading source code.
- Controls have understandable labels and usable hit targets.
- State and feedback are visible at the point of action.
- Core content remains usable at a desktop viewport and a narrow mobile viewport.
- Keyboard access and readable contrast are checked when the interaction warrants it.

Recommended baseline viewports are 1440×900 and 390×844. A polished visual style is
valuable only when the prompt calls for it or poor presentation obstructs use.

## Robustness — 10 points

Check for syntax/runtime errors, missing assets, repeated-use failures, invalid or
boundary input handling, resize behavior, and deterministic reset/restart behavior.
External-network dependencies should degrade intelligibly when offline if the prompt
implies standalone delivery.

## Delivery and claim consistency — 5 points

Check that the promised files exist, the documented entry point works, and final
claims match the artifact. Do not score the agent's tone here; communication quality
belongs in process analysis.

## Evidence plan

Prefer direct browser execution and capture:

- console and page errors;
- representative interaction outcomes;
- screenshots at desktop and mobile sizes;
- computed values or DOM state needed to verify correctness;
- reload and repeated-use behavior.

Static HTML/CSS/JavaScript inspection is useful supporting evidence, but it cannot
fully prove animation, responsive layout, event sequencing, or visual appearance.
If browser execution is unavailable, mark those checks `EX` or apply the `E1` cap;
do not silently treat source inspection as rendered proof.

