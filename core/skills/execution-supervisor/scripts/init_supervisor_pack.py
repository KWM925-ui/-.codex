#!/usr/bin/env python3
import argparse
from pathlib import Path
import textwrap


def write_text(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists; rerun with --force to overwrite")
    path.write_text(content, encoding="utf-8")


def render_readme(project: str, workspace: str, session: str, objective: str) -> str:
    session_line = session if session else "(not set yet)"
    objective_line = objective if objective else "TBD"
    return textwrap.dedent(
        f"""\
        # {project} Supervisor Pack

        Purpose: externalize the rolling supervisor state that should not live
        only inside one chat thread.

        Project:

        - `{project}`

        Workspace:

        - `{workspace}`

        Primary child session:

        - `{session_line}`

        Objective:

        - {objective_line}

        Read order at the start of every supervised round:

        1. `supervisor_ledger.md`
        2. `state_machine.md`
        3. `child_execution_protocol.md`
        4. `round_self_checklist.md`

        Use rules:

        - Treat `supervisor_ledger.md` as the live source of truth.
        - Do not work from memory when the pack exists.
        - Do not reopen branches already demoted by the ledger unless fresh
          evidence contradicts the ledger.
        - Do not run formal validations or write new patches until the ledger
          explicitly allows them.
        """
    )


def render_ledger(project: str, workspace: str, session: str) -> str:
    return textwrap.dedent(
        f"""\
        # {project} Supervisor Ledger

        ## Task Identity

        - Project: `{project}`
        - Workspace: `{workspace}`
        - Primary child session: `{session or "(not set yet)"}`

        ## Locked Facts

        - None yet.

        ## Newly Locked This Round

        - None yet.

        ## Newly Demoted This Round

        - None yet.

        ## Current Frontier

        - only valid current frontier:
        - TODO

        ## Only Question Next Round

        Only valid next question:

        - TODO

        ## Forbidden Next Round

        - No formal run
        - No new patch
        - No patch-surface expansion
        - No reopening demoted branches as equal-priority
        - No broad architectural summaries when the frontier is narrower

        ## Promotion Gate

        Promotion from this frontier is allowed only if one of the following is
        true:

        - one earlier producer or writer is uniquely locked
        - or the uncertainty is reduced to exactly two adjacent candidates with
          one explicit discriminating next read step
        - or the pack is explicitly upgraded to patch-candidate formation
        """
    )


def render_state_machine() -> str:
    return textwrap.dedent(
        """\
        # Supervisor State Machine

        This state machine prevents a long-running task from sliding back into a
        generic workflow.

        ## Global Invariants

        - Fresh evidence only.
        - No broad reset or revert.
        - Facts, hypotheses, and inferences remain separated.
        - Do not reopen ruled-out branches unless fresh evidence contradicts the
          ledger.

        ## Phases

        ### `S0: Startup Compliance`
        Goal:
        - establish repo or task state
        - complete must-read items
        - build first truth ledger
        Promotion rule:
        - first bounded frontier exists

        ### `S1: Earliest-Split Locking`
        Goal:
        - reduce broad subsystem suspicion to one bounded chain
        Promotion rule:
        - frontier narrowed to one local chain

        ### `S2: Producer-Chain Locking`
        Goal:
        - identify the earliest producer or writer layer inside the winning chain
        Promotion rule:
        - one chain wins, or only two adjacent candidates remain

        ### `S3: Writer/Branch/Hunk Locking`
        Goal:
        - lock the specific writer, branch, or hunk
        Promotion rule:
        - unique writer or branch locked, or two adjacent candidates remain

        ### `S4: Patch Candidate Formation`
        Goal:
        - form exactly one minimal patch candidate and one impact table
        Promotion rule:
        - candidate plus confirmation and falsification plan exist

        ### `S5: Low-Pollution Validation`
        Goal:
        - run one clean validation round after hygiene
        Promotion rule:
        - candidate confirmed or falsified cleanly

        ### `S6: Repeatability`
        Goal:
        - prove repeatability before widening
        Promotion rule:
        - repeated clean evidence exists

        ### `S7: Widening`
        Goal:
        - broader scenes or broader workload after baseline is stable
        Promotion rule:
        - no longer a one-case success

        ### `S8: Acceptance Packaging`
        Goal:
        - build the formal evidence package
        Promotion rule:
        - all blocking acceptance items are satisfied

        ## Current Phase

        Current phase: `S0`

        ## Phase-Specific Allowed Actions

        Allowed:
        - read code
        - read logs
        - narrow uncertainty
        - update the ledger

        Forbidden:
        - formal run
        - new patch
        - widening the search space without narrowing the current frontier first
        """
    )


def render_protocol() -> str:
    return textwrap.dedent(
        """\
        # Child Execution Protocol

        Follow this protocol every round until the ledger explicitly changes it.

        ## Round Start

        1. Read `supervisor_ledger.md`.
        2. Restate only:
           - locked facts
           - current frontier
           - forbidden actions
           - required output shape

        ## During The Round

        1. Solve only the ledger's current question.
        2. Prefer direct discriminating reads over broad exploration.
        3. Do not re-prove already locked exclusions.
        4. Do not drift into system-overview mode.
        5. Classify new evidence as:
           - strengthens current frontier
           - contradicts ledger

        ## Output Contract

        Use the exact section headers requested by the current round.
        For critical technical points, prefer:

        - `log field -> variable -> function -> code location -> branch meaning`

        ## Progress Standard

        A round counts as real progress only if:

        - the frontier shrinks
        - or one branch is demoted
        - or one producer, writer, branch, or hunk is uniquely locked

        These do not count:

        - broad summaries
        - rephrasing prior conclusions
        - same-granularity restatements

        ## Run/Patch Gate

        No formal run and no new patch unless both:

        - the phase allows it
        - and the ledger explicitly allows it

        ## Round End

        Before closing the round:

        1. run the checklist mentally
        2. update the ledger
        3. only then emit the final structured answer
        """
    )


def render_checklist() -> str:
    return textwrap.dedent(
        """\
        # Round Self-Checklist

        ## Boundary Checks

        - Did I reopen a ruled-out chain as if it were still equal-priority?
        - Did I drift from the current frontier into a larger search space?
        - Did I use a later readout as if it were an earlier producer?
        - Did I write a hypothesis as a fact?
        - Did I leave the round without narrowing the frontier?

        ## Grain-Size Checks

        - Did I move the frontier one level earlier or narrower?
        - If not unique, did I reduce the uncertainty to at most two adjacent
          candidates?
        - Did I explicitly state why the losing candidate is downstream?

        ## Required Ledger Delta

        Before closing the round, update:

        - `Locked Facts`
        - `Newly Locked This Round`
        - `Newly Demoted This Round`
        - `Current Frontier`
        - `Only Question Next Round`
        - `Forbidden Next Round`
        - `Promotion Gate`
        """
    )


def render_activation(root: Path) -> str:
    pack = str(root)
    return textwrap.dedent(
        f"""\
        # Activation Instruction For A Child Session

        Send the following message to the child session when enabling supervisor mode:

        ```text
        从这一轮开始进入外部 supervisor 模式，直到我明确解除为止。

        每轮开始前，先按这个顺序完整读取并遵守：
        1. `{pack}/supervisor_ledger.md`
        2. `{pack}/state_machine.md`
        3. `{pack}/child_execution_protocol.md`
        4. `{pack}/round_self_checklist.md`

        要求：
        - 把 `supervisor_ledger.md` 当成当前 live source of truth
        - 不准跳过 ledger 直接按记忆工作
        - 不准回退到 ledger 已排除的候选集合
        - 每轮结束前必须先按 checklist 自检，再更新 ledger，再输出本轮结果
        - 在 ledger 没显式放行前，不准开新正式 run，不准写新补丁

        现在先只做一件事：
        先读取上述 4 个文件，然后用 4 行话复述：
        1. 当前 locked facts
        2. 当前 frontier
        3. 当前 forbidden actions
        4. 本轮 output shape

        在这 4 行复述完成前，不要做别的。
        ```
        """
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a generic supervisor pack.")
    parser.add_argument("--root", required=True, help="Directory to create the pack in.")
    parser.add_argument("--project", required=True, help="Project or task name.")
    parser.add_argument("--workspace", required=True, help="Primary workspace path.")
    parser.add_argument("--session", default="", help="Primary child session jsonl path.")
    parser.add_argument("--objective", default="", help="Optional objective summary.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    files = {
        "README.md": render_readme(args.project, args.workspace, args.session, args.objective),
        "supervisor_ledger.md": render_ledger(args.project, args.workspace, args.session),
        "state_machine.md": render_state_machine(),
        "child_execution_protocol.md": render_protocol(),
        "round_self_checklist.md": render_checklist(),
        "activate_supervisor_mode.md": render_activation(root),
    }

    for name, content in files.items():
        write_text(root / name, content, args.force)

    print(f"Created supervisor pack at {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
