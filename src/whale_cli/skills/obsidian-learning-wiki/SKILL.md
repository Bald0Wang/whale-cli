---
name: obsidian-learning-wiki
description: Build, update, and inspect an Obsidian-compatible learning Wiki with Markdown pages, wikilinks, and an explicit knowledge map. Works with Whale CLI tools and standalone Codex workspaces.
---

# Obsidian Learning Wiki

Use this skill when someone asks for an Obsidian learning vault, learning Wiki, wikilinks, a knowledge graph, or a reviewable learning map.

## First decide the working mode

### Whale CLI mode

Use this mode only when the `KnowledgeMap`, `LearningWikiStatus`, `LearningWiki`, `OpenLearningWiki`, or `SyncToObsidianVault` tools are available.

1. Explain that the source graph lives in `.whale_cli/learning/state.json`, while the readable Vault export defaults to `learning-wiki/`.
2. Use `KnowledgeMap` to add or correct themes and explicit relationships before synchronizing. A theme is not yet a useful Wiki page: use `LearningWiki(action="outline")` to record its definition, mechanism, key terms, minimum practice, pitfalls, questions, and verified sources.
3. Call `LearningWikiStatus` before writing when the current export is unknown.
4. Use `LearningWiki(action="init")` for a new Vault and `LearningWiki(action="sync")` after graph changes. These actions write files and need approval in Safe mode.
5. For explicit local conversation retention, use `LearningWiki(action="set_auto_capture", enabled=true)`. Future completed turns are written below `conversations/` as user input plus final reply only. Disable it with `enabled=false`; never claim it records tool transcripts, attachments, or hidden reasoning.
6. Use `OpenLearningWiki` only after approval. It registers the generated folder as an Obsidian Vault and opens `index.md` or a requested concept page.
7. The WebUI graph is a two-level view: topic overview first, then the selected topic's LLM-Wiki structure. Do not use mastery as a graph label; it belongs to learner self-assessment, reviews, and reports.
8. For an existing external Vault, require an explicit path or `OBSIDIAN_VAULT_PATH`, then use `SyncToObsidianVault`. It writes only below `Whale Learning Wiki/` and needs separate approval. When the path or environment variable is already supplied, call the tool directly and treat its copied-files result as verification; do not use Bash to inspect the external Vault.

### Standalone Codex mode

Use this mode when the Whale-specific tools are unavailable.

1. Resolve a concrete Vault path. Prefer an explicit user path, then `OBSIDIAN_VAULT_PATH`; do not guess or write into an unrelated Vault.
2. For a new Wiki in the current workspace, use `learning-wiki/` and create `.obsidian/app.json` with `{}` plus `index.md`, `purpose.md`, `log.md`, and `concepts/`.
3. Give every concept its own `concepts/<slug>.md` page. Use YAML frontmatter for title, kind, mastery, and updated date.
4. Express relationships only with normal Obsidian links such as `[[python-basics|Python Basics]]`. State whether a link is a prerequisite, related concept, or evidence in visible Markdown sections.
5. Keep an `index.md` that links to the active concepts and a `log.md` that records generated or edited pages. Do not overwrite learner notes outside the generated Wiki folder.
6. Use the global `obsidian` Skill's filesystem-first workflow to read, search, create, and patch notes. Opening the desktop application is optional and requires approval.

## Quality checks

- Verify every wikilink target exists before claiming the graph is complete.
- Keep concept titles learner-facing; IDs and filenames may be machine-friendly.
- Do not invent mastery, prerequisites, or evidence. Ask when the learner has not provided enough information.
- Do not claim that an external LLM Wiki app, Obsidian plugin, or community contribution is installed or synchronized unless it was explicitly configured.
