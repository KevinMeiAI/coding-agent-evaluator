# Agent action-flow diagram

Create a concise chronological visual from task receipt through the agent's final response. Do not include post-delivery artifact-review findings unless requested.

## Content model

Adapt phases to the trace rather than forcing a fixed number or fixed column count. Common phases are intake, inspection, implementation, debugging, verification, and delivery, but merge, split, branch, or reorder them when the actual action history warrants it.

Aggregate repetitive low-level reads, edits, and tests while preserving:

- meaningful architecture or strategy changes;
- important failures and recoveries;
- user questions and permission interactions;
- verification limitations and verified successes;
- final completion claims.

Keep the default near 25 nodes or fewer. The final node is the original agent's delivery, not the evaluator's later review.

## Visual character

The rendered PNG/SVG should resemble a polished editorial process map or consulting-quality systems diagram, not a raw Mermaid export.

- Use a solid warm off-white page background (`#F5F2EA` or a close neutral), never transparent/black.
- Use dark navy primary text (`#172033`), muted slate secondary text (`#647184`), and a clean system sans-serif with Chinese fallback such as PingFang SC.
- Use generous whitespace, consistent alignment, rounded white phase panels, 14–22 px corner radii, subtle borders, and soft restrained shadows.
- Put a clear title and one-line scope subtitle at the top.
- When useful metrics exist, show a compact horizontal metric strip below the title: duration, tool calls, errors/retries, writes/edits, or another task-relevant metric. Do not invent metrics or force empty cards.
- Keep node copy short: one action headline plus at most two compact supporting lines. Avoid raw payloads and long quotations.
- Use thin neutral-gray connectors with clear arrowheads; minimize crossings.
- Place a small, quiet legend at the edge or bottom. It must not dominate the diagram.

Use this semantic palette consistently:

| Meaning | Fill | Border |
|---|---|---|
| normal action | `#E8F1FF` | `#3B82F6` |
| model/code problem | `#FDECEC` | `#D64545` |
| retry/risk/verification limitation | `#FFF4D6` | `#D89814` |
| verified success | `#E8F7EE` | `#2F9E5B` |
| final delivery | `#F1E9FF` | `#7C3AED` |
| neutral metric/note | `#F3F5F7` | `#A8B0BC` |

Do not prefix nodes with symbols such as `!` or `◉`. Only when an event is confidently user-visible, place a small purple `用户可见` capsule inside the node. Internal and unknown events receive no visibility decoration.

## Adaptive layout

Choose the layout from the information shape:

- use a landscape left-to-right phase map when the trace has a small or moderate number of sequential phases;
- use two chronological rows when a single row would make panels or text too narrow;
- use a vertical timeline or swimlane layout for genuinely long, branching, or actor-heavy traces;
- use branches only when the agent actually pursued alternatives or parallel paths.

The phase count determines the composition; it is not fixed at five. Favor a balanced landscape result when it remains readable, but do not compress complex traces into tiny columns. Avoid extremely tall, narrow output unless the chronology truly requires it.

Within each phase, align nodes to a simple grid and keep repeated spacing consistent. Make phase sequence and time range visible in panel headers. The reading order should be obvious without following every arrow individually.

## Rendering requirements

Always create editable Mermaid source as a semantic representation. The Mermaid file does not dictate the final composition.

For the final PNG/SVG:

- prefer a styled SVG/HTML render or a fully themed Mermaid render that meets this guide;
- do not accept the default Mermaid yellow subgraphs, transparent canvas, default typography, or uncontrolled portrait layout as the final visual;
- use at least 1,600 px output width for landscape diagrams and enough height to keep text comfortably readable;
- preserve a consistent visual system across tasks while allowing phase count, panel widths, rows, and branching to adapt;
- render both PNG and SVG when supported, and visually inspect the result at full size for clipping, overlap, illegible text, excessive empty space, or an awkward aspect ratio.

If available tools cannot produce a polished rendering, keep the Mermaid source, record the rendering limitation, and do not claim that an unstyled default export satisfies the visual deliverable.

## Preflight checklist

- Node order matches timestamps.
- Aggregation does not hide a meaningful failure or recovery.
- Only proven user-visible events carry the `用户可见` capsule.
- The final node is the original delivery.
- Style tokens and semantic colors match this guide.
- Layout is appropriate to the actual number and shape of phases.
- Background is opaque and light; text is readable; no node or legend is clipped.
- Generated files exist and are non-empty.
