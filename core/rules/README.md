# Rules Layer

`default.rules` is the live rule file.

Current policy:

- an empty `default.rules` means no live project-specific command allowances are
  intentionally active at the global layer
- project-specific allowances belong in the project repository or a private
  project overlay
- historical local rule archives are intentionally omitted from the public
  export

Archive note:

- this public package exposes only the live generic rule surface
- do not reconstruct local project command allowances from public defaults
