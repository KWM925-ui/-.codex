# Rules Layer

`default.rules` is the live rule file.

Current policy:

- an empty `default.rules` means no live project-specific command allowances are
  intentionally active at the global layer
- project-specific allowances belong in the relevant repository or private
  project overlay, not in this portable global default
- historical rule archives are intentionally excluded from the public export
