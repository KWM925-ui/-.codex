# Core Layer

`core/` contains reusable Codex assets that should remain generic across
projects.

Canonical subtrees:

- `control_plane/`
- `skills/`
- `rules/`
- `plugins/`

Compatibility:

- the root-level `control_plane`, `skills`, `rules`, and `plugins` paths are
  symlinks back into this layer
- the productized-home contract is recorded in
  `control_plane/codex_home_layout_manifest.json`
- root-owned core surfaces are registered in `core_surface_registry.json`
- root-owned core lifecycle and move gates are defined in
  `lifecycle_policy.md`
- the current filesystem can be checked with
  `control_plane/scripts/audit_codex_home_layout.py`

What belongs here:

- machine-wide maps and contracts
- reusable skills and plugins
- generic rule files
- regression harnesses for the control plane itself
- auditable context-firewall contracts and deterministic context-curation tools

What does not belong here:

- project-specific acceptance metrics
- project-specific supervisor packs
- frozen worktree evidence
- upstream mirrors tied to a specific debugging thread
