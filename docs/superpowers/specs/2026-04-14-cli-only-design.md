# CLI-Only Design

**Goal:** Remove the repository's AI- and agent-facing features so ProjectManager ships as a CLI-only tool focused on project, build, patch, snapshot, and doctor workflows.

**Scope**

- Remove all `ai_*` commands from the CLI surface.
- Remove the `mcp_server` command and its implementation.
- Remove AI helper code under `src/ai/`.
- Remove AI/MCP tests, docs, sample environment configuration, and AI-specific dependencies.

**Behavior**

- `python -m src --help` must no longer list `ai_review`, `ai_explain`, `ai_docs`, `ai_test`, `ai_index`, `ai_search`, or `mcp_server`.
- Importing the CLI should no longer register or depend on AI/MCP modules.
- The package metadata should no longer advertise or install `crewai` or related AI-only support.
- User-facing docs and test cases should describe only the remaining CLI capabilities.

**Non-Goals**

- No replacement compatibility shims for removed commands.
- No refactor of unrelated CLI commands.
- No change to TUI support (`questionary`) or existing non-AI workflows.

**Files To Remove Or Update**

- Remove: `src/ai/`
- Remove: `src/plugins/ai_review.py`
- Remove: `src/plugins/ai_explain.py`
- Remove: `src/plugins/ai_docs.py`
- Remove: `src/plugins/ai_test.py`
- Remove: `src/plugins/ai_semantic_search.py`
- Remove: `src/plugins/mcp_server.py`
- Remove matching AI/MCP tests under `tests/whitebox/plugins/` and `tests/whitebox/test_llm_embeddings.py`
- Update: `src/__main__.py`, `pyproject.toml`, `.env.example`, `docs/test_cases_en.md`, `docs/en/user-guide/command-reference.md`, `docs/zh/user-guide/command-reference.md`, and `TODO.md`
- Update: `.github/workflows/publish-release.yml` to drop AI release-summary generation

**Testing**

- Add a blackbox CLI assertion that `--help` no longer advertises removed commands.
- Run CLI/whitebox suites that cover remaining command registration and command help.
