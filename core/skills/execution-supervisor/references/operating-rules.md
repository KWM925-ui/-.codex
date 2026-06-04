# Operating Rules

## Facts, Hypotheses, Inferences

- Facts:
  - directly supported by current code, current logs, current runs, or current
    artifacts
- Hypotheses:
  - candidate explanations not yet fully proven
- Inferences:
  - reasoning built on facts; label them explicitly

Never write a hypothesis as a fact in the ledger.

For Chinese-language user-facing reports, keep these categories separate but
label them in clear Chinese. Do not expose English process headings as the
default report style when Chinese can explain the same structure more clearly.

## Real Progress Standard

A round counts as real progress only if at least one happens:

- one candidate is uniquely locked
- one branch is demoted from equal-priority status
- the frontier moves one hop earlier or narrower
- the uncertainty is reduced to at most two adjacent candidates with one clear
  next discriminating read step

These do not count:

- rephrasing prior conclusions
- repeating already-locked exclusions
- broad architecture summaries
- adding new candidate sets after the frontier was already narrowed

## Anti-Drift Rules

- Do not reopen ruled-out branches unless fresh evidence contradicts the ledger.
- Do not widen back from two adjacent candidates to a large branch set.
- Do not use later evidence as if it were earlier evidence.
- Do not use post-publish or post-failure evidence as if it were pre-split
  producer evidence.
- Do not let consumer-side readouts replace writer-side responsibility when the
  writer chain is still accessible.

## Run/Patch Gate

- A formal run is allowed only when:
  - the phase allows it
  - and the ledger explicitly permits it
- A new patch is allowed only when:
  - the writer or branch is narrow enough
  - and the ledger explicitly upgrades to patch-candidate formation

Absence of a prohibition is not permission.
