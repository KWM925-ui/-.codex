# Control Plane

Purpose:

- Provide a reusable control system stronger than a one-off prompt.
- Keep global operating behavior stable across projects and new sessions.
- Separate durable global rules from project-specific contracts.

Canonical storage:

- `~/.codex/core/control_plane`

Compatibility surface:

- `~/.codex/control_plane` remains as a symlinked entrypoint for existing
  scripts, docs, and operator habits

Design basis:

- Official Codex docs support machine-wide `AGENTS.md`, repository `AGENTS.md`,
  additional fallback project docs, reusable skills, and optional memories.
- Official workflow guidance also recommends lightweight `AGENTS.md` plus
  stronger plan/ledger artifacts for long-running work.
- Local sessions show repeated need for: facts-vs-hypotheses separation,
  anti-drift phase gates, minimal-touch continuation, and stronger persistence
  than a single handoff prompt.
- Community practice suggests keeping the global layer generic while leaving
  project specifics to repository docs. That is used as inspiration only, not as
  a template to copy blindly.

## Layering

Layer 0: Config

- `~/.codex/config.toml`
- Persistent developer-side controls.
- Holds `developer_instructions`, `project_doc_fallback_filenames`, and memory
  settings.

Layer 1: Global map

- `~/.codex/AGENTS.md`
- Short machine-wide map, not a long manual.
- Tells Codex which control docs to open and when to enter supervisor mode.

Layer 2: Control documents

- `global_execution_contract.md`
- `stable_user_preferences.md`
- `project_bootstrap.md`
- `validation_status.md`
- `codex_home_governance.md`
- These contain the real reusable operating rules.

Layer 3: Skills

- `execution-supervisor`
- `project-bootstrap`
- Reusable workflow for ledgers, phase gates, child-session supervision, and
  anti-drift execution.
- Reusable workflow for installing project-local control assets and restarting
  work from a minimal prompt.

Layer 4: Project-local assets

- Repository `AGENTS.md`
- Project fallback docs
- Repo-specific plans, ledgers, supervisor packs, acceptance contracts

Layer 5: Generated recall

- `sessions/`
- `sessions_archive/`
- `memories/`
- Useful for recall and audit, but not authoritative over current evidence or
  checked-in project instructions.

## What Belongs Here

- Cross-project execution discipline
- Stable user preferences that apply beyond one repo
- Bootstrap guidance for new or resumed projects
- Machine-readable governance for the productized `~/.codex` home layout
- Reusable templates and activation patterns
- Reusable project-local task workflow for requirements, design,
  implementation, verification, active-session state, and lesson capture
- Regression harness templates and automated control-plane self-tests
- Operator-facing policy explanation for governed `~/.codex` surfaces
- Operator-facing doctor output for suggested safe action by governed surface
- Operator-facing batch governance report across all governed surfaces
- Operator-facing grouped work buckets for the current attention targets
- Operator-facing focused review for the reversible runtime target batch
- Operator-facing focused review for the tool-owned target batch
- Operator-facing continuity-safe planning review for archive-governed targets
- Governed migration-candidate contract and review surface
- Governed context-firewall contracts for context ingress, memory admission,
  compaction budgets, and untrusted-content handling
- Report-only context-firewall probe, profile comparison, and multi-session
  evaluation surfaces for testing filter strength before any runtime hook
- Deterministic context-curation CLI and focused firewall audit surface
- Operator-facing context-firewall review for source posture, relevance tiers,
  profile budgets, and current non-mutating integration status
- Report-only context-ingress probe over real session/tool records with raw
  content redacted from output
- Report-only offline agent end-to-end evals for controlled A/B, no-op and
  out-of-scope behavior, trajectory grading, attack/noise pressure, long-horizon
  quality drift, skills/plain-language ablation, context noise budgets, and
  regression gates
- Agent e2e implementation is split into a stable CLI entrypoint plus shared
  fixture/helper and real-runner modules, so adding eval cases does not keep
  growing one opaque script
- Real-runner eval presets for the already-validated smoke and current-full
  batches, so costly `codex exec` checks stay explicit, isolated, and repeatable
- Real-runner isolated homes use generated minimal safe config by default; when
  `--real-use-live-provider-config` is explicit, only the active provider
  fragment is copied into a temporary `CODEX_HOME`, secret values are not
  printed, and the temporary home is deleted after the run
- Optional stderr-only real-runner progress output, so long `codex exec` evals
  can show bounded progress without corrupting JSON or printing raw model output
- Optional real-runner fail-fast mode, so costly batches can stop after the
  first clear failure while preserving the stop reason in structured output
- One bounded acceptance entrypoint for the current control-plane proof set:
  `run_codex_home_acceptance.py` supports `--gate-profile` levels
  `quick`, `standard`, `full`, `release`, `real`, and `saturation`; the default
  `quick` gate keeps ordinary work fast, `release` adds public-export hygiene
  checks via `--export-root`, and real `codex exec` checks remain explicit
  through `--include-real-smoke`, `--gate-profile real`, or
  `--gate-profile saturation`
- `saturation` is intentionally heavy: it includes offline profile sweeps, the
  bounded `current-full` real-runner batch, and shell regression wrappers that
  run in temporary directories and clean those directories on exit
- Real smoke acceptance now has a safe-auth preflight: it only proceeds when a
  supported external auth environment variable such as `OPENAI_API_KEY` is
  present or when `--real-use-live-provider-config` is explicit, reports only
  safe metadata, and never copies full live config/auth material into the
  isolated eval home
- `summarize_supervisor_current_state.py` prints the latest supervisor
  frontier, only question, forbidden actions, and promotion gate without
  rewriting historical ledger evidence
- `project_task_workflow.py` creates and validates lightweight repository-local
  task packs under `.codex/tasks/`, with a separate confirmation step before
  implementation can start
- Shared Codex-home test fixtures and split context-firewall surface tests, so
  layout tests no longer own every control-plane surface fixture directly
- Canonical harnesses currently cover:
  - same-turn auto-advance
  - clean-snapshot to active-worktree anchor remap
  - repo-scale same-turn patch-and-run under dirty-worktree boundaries
  - late-phase same-turn repeatability-to-widening auto-run

## What Does Not Belong Here

- One repository's acceptance metrics
- One run's debug conclusions
- Project-specific algorithm contracts
- Generated logs or temporary probes
- Project-specific case evidence that can live under `project_assets/*`

## Recommended Read Order

For a new session:

1. `~/.codex/AGENTS.md`
2. This file
3. `stable_user_preferences.md`
4. `project_bootstrap.md`
5. `codex_home_governance.md` when the task is about `~/.codex` itself
6. Then repository instructions

For long-running debugging or acceptance work:

1. `~/.codex/AGENTS.md`
2. `global_execution_contract.md`
3. `execution-supervisor`
4. Repository instructions and current ledgers
5. `validation_status.md` when judging how much of the control plane is already
   proven vs still only partially proven

## Success Criteria

This control plane is working only if future sessions can:

- start from the same generic discipline without a custom mega-prompt
- distinguish global rules from project-specific rules
- enter supervisor mode automatically when the task demands it
- continue a project with minimal user nudging
- avoid re-opening already ruled-out branches unless fresh evidence forces it
- prove key continuation behaviors with repeatable local regression tests, not
  only by anecdotal session success
