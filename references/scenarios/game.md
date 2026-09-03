# Generated Game Evaluation

Use this scenario when the requested artifact has a win/lose, score, survival,
progression, or repeatable challenge loop. For a physics toy or interactive demo
without meaningful challenge or outcome, use the webpage scenario and apply the
interactive-simulation guidance below.

## Hard gates

- The game launches through the promised entry point.
- A player can enter and affect the game state.
- A complete playable loop exists: start, play, outcome or progression, and replay
  or continuation as appropriate to the prompt.
- The primary mechanics named in the prompt are present.

If the artifact is only a static scene, mockup, or non-playable shell, cap at 59.
If it launches but lacks a complete loop, it normally cannot exceed 69.

## Requirement fit — 50 points

Allocate prompt-derived checks across:

- required genre, theme, format, controls, and platform;
- named mechanics, entities, levels, progression, score, or win/lose conditions;
- requested sound, art direction, multiplayer, persistence, or special effects.

Do not make “fun” or advanced art a hidden requirement. Score those only when the
prompt asks for them, while still applying the minimum clarity and feedback floor.

## Correctness — 20 points

Check collision and hit detection, scoring, lives/health, timers, spawn logic,
progression, win/lose transitions, restart state, and frame-rate or delta-time logic.
Test both successful and failing player paths plus at least one boundary condition.

## Usability — 15 points

Check that controls are discoverable, input feels responsive, important state is
visible, feedback explains player actions, and the player can start and restart
without reloading unless that behavior was explicitly requested. For touch-capable
deliverables, test touch targets and accidental page scrolling.

## Robustness — 10 points

Check repeated restarts, simultaneous inputs, focus loss, resize behavior, asset
loading, rapid clicks/keypresses, long-running timers, and terminal-state cleanup.
Look for duplicated loops, listeners, entities, audio, or stale state after restart.

## Delivery and claim consistency — 5 points

Confirm all required files and assets exist, the entry instructions are accurate,
and the final response does not claim mechanics or tests that are absent.

## Direct play evidence

Actual play is required for high-confidence dynamic scores. Exercise:

1. launch and initial instructions;
2. the main control path;
3. an outcome or meaningful progression event;
4. restart or replay;
5. at least one failure or edge path.

Automated DOM or state probes may support direct play but do not replace checking
visible feedback and control feel. Without runtime evidence, dynamic mechanics are
limited to `E1` or `EX` under the evidence policy.

Record all six gameplay phases in `execution_evidence.gameplay_phases`: launch,
meaningful input response, progression, attempted failure, terminal state, and
replay. “Attempted failure” means the player actively used the controls and still
reached a failure condition; waiting without input can verify terminal detection but
does not verify playability, responsiveness, or an attempted failure path. Set
`active_controls_used: true` on a passing attempted-failure phase.

### Input responsiveness and reachability

Do not infer control quality from event delivery alone. Measure or visibly establish:

- the state change caused by one ordinary input and by a short rapid-input burst;
- the time and distance envelope available before the first meaningful obstacle or
  deadline;
- whether that reachable envelope covers the positions or reactions demanded by
  representative generated challenges;
- whether input feedback remains visible and coherent at normal and rapid rates.

For motion controlled by delta time, compare units and magnitudes across velocity,
acceleration, displacement, obstacle speed, and the time to collision. A control can
fire on every click yet remain functionally inert. A test must fail when the input
effect is reduced enough that ordinary generated challenges become unreachable.

Set `scene.time_sensitive_controls` explicitly. When true, fill
`execution_evidence.control_response` with the single-input effect, rapid-input
effect, available response window, required challenge envelope, conclusion, and run
IDs. Quantitative measurements are preferred; when they are impractical, record a
specific visible behavioral observation rather than “felt responsive.”

### Procedural or randomized mechanics

Set `scene.procedural_or_randomized` explicitly. When true, include variation
coverage for each core random/procedural factor that can affect completion. Exercise
the unmodified distribution plus at least three representative cases spanning a
nominal region and a boundary or risk region. Use the game mechanic's natural
categories rather than mechanically forcing numeric low/mid/high labels.

If runtime execution is unavailable, leave variation coverage empty, record the
limitation, and keep affected checks `unverified`/`EX`; do not invent samples.

Fixed seeds, stubbed RNG, forced spawn positions, and patched difficulty are
`controlled_diagnostic` evidence. They are useful for reproducibility and root-cause
analysis, but a favorable fixed case cannot establish default playability. Compare
the player's reachable response envelope with the generated challenge range and
report unreachable regions even if one controlled case succeeds.

### Discriminating assertions

For every passing core dynamic check, record a plausible severe failure model and
the assertion that would detect it. Ask: “Would this test still pass if the mechanic
were present but almost ineffective?” Main-loop assertions should establish
meaningful input response, progression, active-play failure, terminal transition,
and replay state—not merely canvas size, absence of console errors, or survival for a
short interval.

For a provisional game score of 90 or above, perform a separate adversarial review
after the initial score. Challenge at least one assumption about control magnitude,
timing, randomness, progression, or replay using a new run or a materially different
analysis. This may be a second evaluator pass; it does not require a subagent.

## Interactive-simulation subtype

For simulations without a real challenge loop, do not invent game requirements.
Replace win/lose and fun checks with input-to-state correctness, temporal behavior,
reset/replay, displayed model consistency, and visual feedback. A projectile-motion
demonstrator is usually this subtype, not a game.
