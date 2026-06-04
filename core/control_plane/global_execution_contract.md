# Global Execution Contract

This file defines reusable execution rules that should survive across projects.
Project-specific acceptance criteria belong in repository docs, not here.

## 1. Core Invariants

- Evidence before conclusion.
- Facts, hypotheses, inferences, blockers, and next actions stay separate.
- Clarify before acting when the user's goal, constraints, success criteria, or
  risk tolerance are materially unclear.
- Do not infer the user's intent from habit, prior projects, or agent
  experience when a wrong guess would change the work.
- When a request is vague, stop and ask. Do not replace clarification with
  safe cleanup, documentation polish, tests, type hints, low-risk refactor, or
  other seemingly harmless work.
- When stopping to clarify, state whether any file or substantive action has
  already happened. If nothing was changed, say that plainly.
- Do not present memory, experience, or plausibility as fact. Unsupported
  claims must be labeled as inference, assumption, or uncertainty.
- Root-cause narrowing beats symptom patching.
- Keep the active frontier narrow. Do not widen unless fresh evidence breaks the
  current chain.
- Prefer one falsifiable candidate over several loosely plausible ones.
- Freeze already validated-good behavior unless new evidence directly
  contradicts it.
- Minimize patch surface and run pollution.

## 2. When To Externalize Control

Externalize a ledger, frontier, or plan when work is any of:

- multi-round
- multi-session
- acceptance or certification style
- expensive to validate
- supervising another agent
- vulnerable to drift, repeated rediscovery, or patch sprawl

When this trigger fires, use the `execution-supervisor` workflow instead of
trusting chat memory alone.

## 3. Phase Gates

Recommended generic phases:

1. Startup and boundary check
2. First truth ledger
3. Earliest-split locking
4. Producer or writer chain locking
5. Single minimal patch candidate
6. Low-pollution validation
7. Repeatability and widening
8. Acceptance packaging

Do not skip from broad diagnosis to patch or run without locking the current
frontier tightly enough.

## 4. Patch Gate

Before writing a patch, record:

- current hypothesis
- why it outranks competing hypotheses
- expected positive effect
- likely negative effect or blast radius
- what fresh evidence would confirm it
- what fresh evidence would falsify it
- how to rollback or stop the branch if falsified

If this table does not exist yet, the patch is not ready.

## 5. Run Gate

Before a formal run:

- ensure the current hypothesis is specific enough to test
- ensure the run is not duplicating an already disproved experiment
- ensure stale processes, stale data, or stale output directories cannot pollute
  the result
- define the exact artifacts and metrics required to judge the run
- define what counts as progress, regression, and inconclusive output

If the run cannot change the decision boundary, it is probably a waste.

## 6. Reporting Contract

Default reporting shape for non-trivial rounds:

- locked facts
- open hypotheses
- current blocker or frontier
- next minimal action

If the user asks for pass or fail, answer directly. Do not replace a verdict
with vague optimism.

For Chinese-language project work, the visible report should use clear Chinese
by default. The structure above still matters internally, but do not make the
user read English process labels such as "Locked facts", "Hypotheses",
"Inferences", "Blockers", "Next actions", "frontier", or "gate" when a
plain Chinese sentence is clearer. Keep exact technical identifiers verbatim
and explain their meaning in Chinese.

## 7. Source Policy

- Use fresh local evidence for current repository state.
- Use primary or official sources for unstable technical facts.
- Use session archives and memories as recall aids, not as authority.
- If a project has checked-in instructions, they outrank recollection from old
  threads.
- If evidence is not strong enough for a direct conclusion, say so plainly and
  either gather stronger evidence or ask the user for the missing decision.

## 8. Anti-Drift Rules

- Do not re-prove already locked exclusions unless contradicted.
- Do not broaden from one bounded chain back to an entire subsystem without
  fresh evidence.
- Do not claim completion because the direction feels right.
- Do not confuse better narration with progress.

## 9. Continuation Rule

Long tasks should be able to continue from a minimal user prompt such as
"continue" only if the current ledger and frontier are already externalized.
If they are not, fix the control surface before asking the user to manage
continuity manually.

## 10. Worktree Anchor Remap

When a live ledger or archived evidence points to code anchors from:

- a clean snapshot
- a sibling workspace
- an older line map
- or a stale pre-edit file state

do not patch or narrow against those coordinates blindly.

First remap the live frontier to the current active worktree by:

- locating the same semantic shell in the current file
- confirming nearby variables, logs, and branch guards still match
- and only then continuing frontier narrowing or patch formation

This is especially important in dirty repositories where a correct frontier can
survive while exact line numbers drift.
