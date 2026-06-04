# Global Control Map

This file is the machine-wide user-layer control map for Codex.
Keep it short. Read the referenced docs before large or long-running work.

## Always

- Load repository instructions from checked-in `AGENTS.md` or fallback project docs before acting.
- Keep global rules generic. Do not drag one project's acceptance contract into unrelated work.
- Prefer direct execution over idle planning, but do not patch or run before the current uncertainty is bounded enough.
- When the user's goal, constraints, success criteria, or risk tolerance are unclear, ask concise clarifying questions before starting substantive work. Do not guess the user's intent from habit or prior projects when the answer materially changes what should be done.
- When a request is vague, stop and ask; do not replace clarification with safe cleanup, documentation polish, tests, type hints, low-risk refactor, or other seemingly harmless work.
- When stopping to clarify, explicitly say that no files were changed and no substantive action was taken, unless a prior action in the same turn already changed something.
- Do not present experience, memory, or plausibility as fact. If a conclusion is not backed by fresh evidence or a clearly cited source, label it as an inference, assumption, or uncertainty.
- Default to clear Chinese "说人话" in user-facing replies: explain the concrete result, cause/effect, blocker, and next useful action; keep exact technical identifiers verbatim, but avoid English process labels and control-plane jargon when plain Chinese is clearer.

## Use Supervisor Mode When The Task Is Long-Running

Trigger the `execution-supervisor` skill when work is:

- multi-round or multi-session
- acceptance-style or certification-style
- debugging-heavy with expensive runs
- supervising another Codex session
- vulnerable to branch drift or repeated rediscovery

When supervisor mode is active:

- externalize a live frontier or ledger before new patches or formal runs
- keep `locked facts`, `hypotheses`, `inferences`, `blockers`, and `next actions` separate
- do not reopen ruled-out branches without fresh contradictory evidence
- expose those categories to the user in clear Chinese unless exact English labels are explicitly required

## Read These Docs On Demand

- `$CODEX_HOME/core/control_plane/README.md`
- `$CODEX_HOME/core/control_plane/global_execution_contract.md`
- `$CODEX_HOME/core/control_plane/stable_user_preferences.md`
- `$CODEX_HOME/core/control_plane/project_bootstrap.md`

## Source Priority

1. Current repo state and fresh evidence.
2. Project-specific checked-in docs and logs.
3. Global control docs and approved skills.
4. Session history and memories as recall aids, never as higher authority than current evidence.
