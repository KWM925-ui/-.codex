# Activation Patterns

## Existing Child Session

Use when the child already exists and has drift risk:

1. Update the pack first.
2. Send the activation message from `activate_supervisor_mode.md`.
3. Require the child to restate:
   - locked facts
   - current frontier
   - forbidden actions
   - output shape
   For Chinese-language work, require clear Chinese labels and cause/effect
   wording instead of English process headings.
4. Do not let the child continue work before this restatement.

## New Session Bootstrap

Use when starting a fresh session:

1. Scaffold the pack.
2. Put the pack path and workspace in the first message.
3. Require pack read order before any new analysis.
4. Make the initial round produce:
   - startup compliance
   - first truth ledger
   - current blocker
   - next bounded frontier

## Transfer Between Sessions

When changing from one supervising session to another:

- carry the pack, not a prose recap alone
- point the new session to the current ledger first
- require the new session to operate within the current frontier before adding
  new context

## When Not To Use Supervisor Mode

Supervisor mode is unnecessary for:

- one-shot coding tasks
- small isolated edits with low drift risk
- casual Q&A without multi-round state
