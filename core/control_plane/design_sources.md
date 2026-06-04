# Design Sources

This file records where the current control-plane design came from so future
changes can distinguish stable principles from local improvisation.

## Official Sources

- OpenAI, "Unrolling the Codex agent loop"
  - Why used:
    - Confirms instruction layering and that Codex aggregates user instructions
      from machine-wide `AGENTS.md`, repository `AGENTS.md`, and configured
      fallback project docs.
  - Design impact:
    - Use `~/.codex/AGENTS.md` as a short global map.
    - Use repo docs for project-specific contracts.

- OpenAI Developers, "Configuration Reference"
  - Why used:
    - Confirms `developer_instructions`, `project_doc_fallback_filenames`,
      `features.memories`, and `memories.generate_memories`.
  - Design impact:
    - Persist generic developer-side behavior in `config.toml`.
    - Add project doc fallback filenames.
    - Enable memories.

- OpenAI Developers, "Memories"
  - Why used:
    - Confirms memories are a local recall layer, not a replacement for
      required rules in `AGENTS.md` or checked-in docs.
  - Design impact:
    - Keep durable rules in docs.
    - Treat `memories/` as generated state.

- OpenAI Developers, "Agent Skills"
  - Why used:
    - Confirms skills are the authoring format for reusable workflows and use
      progressive disclosure.
  - Design impact:
    - Put reusable workflows into skills instead of long always-on prompts.

- OpenAI Cookbook, "Using PLANS.md for multi-hour problem solving"
  - Why used:
    - Shows that `AGENTS.md` should tell Codex when to use a durable plan and
      that long projects need living documents.
  - Design impact:
    - Keep `AGENTS.md` as a short map and move long-running control into ledgers
      or plans.

## Local Historical Sources

- Generic patterns have been extracted from local long-running sessions and
  historical project control docs.
- The raw project-scoped source list and extracted notes now live under:
  - `private project_assets/<project>/control_plane_cases/design_source_extractions.md`
- That case file preserves the original session and project-document anchors
  without polluting the global control-plane document.

## Community Inspiration

- GitHub discussion: `openai/codex` discussion `#7296`
  - Why used:
    - Reinforces the split between generic global instructions and repository
      `AGENTS.md`.
  - Design impact:
    - Keep the global layer generic and project-local instructions in the repo.
  - Boundaries:
    - Do not copy another developer's prompt/profile setup wholesale.
    - Use the pattern, not the content.
