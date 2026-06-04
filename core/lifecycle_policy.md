# Core Lifecycle Policy

This file defines how authoritative core surfaces should be treated during
future productization.

## Current Rule

Core surfaces are split between:

- canonical reusable trees under `core/`
- a small set of authoritative root files that remain root-owned by design

The root-owned core files are not accidental residue. They are entry surfaces
for machine-wide behavior and should be governed explicitly.

## Governed Root Core Surfaces

- `AGENTS.md`
- `README.md`
- `config.toml`

## Allowed Actions

- add machine-readable registry metadata
- strengthen audit coverage
- tighten documentation and scope boundaries
- add compatibility-preserving mirrors only when there is a clear caller need

## Forbidden Actions Without A New Migration Phase

- relocating `AGENTS.md` away from the root while callers still expect it there
- relocating `config.toml` away from the root while Codex still reads it there
- rewriting root core files into project-specific contracts
- weakening global-vs-project scope boundaries for convenience

## Move Gate For A Future Phase

A root-owned core surface may move physically only if all are true:

1. the old entrypoint remains stable to callers
2. the manifest and registries are updated first
3. the audit script proves the contract before and after the move
4. no current caller still requires the legacy root path as the only entrypoint
5. the move improves boundary clarity instead of hiding core behavior
