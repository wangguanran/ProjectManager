# Default Execution TUI Design

**Goal:** Make the default local interactive CLI experience a dynamic terminal UI that shows a step list, current-step logs, and per-step timing across commands, while preserving a stable `--raw-output` mode for redirection and automation.

## Scope

- Add a new global flag: `--raw-output`.
- Default to a dynamic TUI for human-facing commands when running in a local interactive terminal.
- Show all command execution as a structured step tree with status, timing, and logs.
- Auto-follow the currently running step by default, while also allowing keyboard navigation, manual expansion, and log inspection of earlier steps.
- Reuse one execution/event model across commands instead of building per-command UIs.
- Replace the current optional `questionary`-only TUI path with a single `Textual`-based UI stack.

## Non-Goals

- No CI/web rendering parity in v1.
- No mouse-first workflow requirement in v1.
- No task cancellation / signal orchestration in v1; quitting the UI only detaches the renderer.
- No parallel build graph UI in v1; steps remain linearly ordered even if internal command output is noisy.
- No change to `--help`, `--version`, `--json`, or `--emit-plan` output formats.

## Product Decisions

### Rendering Modes

- `interactive_tui`:
  - Default for supported commands in a local interactive terminal.
  - Uses a `Textual` application with step list, log pane, and details pane.
- `raw_output`:
  - Enabled explicitly with `--raw-output`.
  - Also used automatically when stdin/stdout is not an interactive TTY.
  - Produces stable line-oriented output for redirection and scripts.
- `direct_output`:
  - Used for commands that must stay machine-readable or immediate:
    - `--help`
    - `--version`
    - `--json`
    - `--emit-plan`

### Command Coverage

- The new execution UI is the default shell for human-facing commands, including:
  - `project_build`
  - `project_pre_build`
  - `project_do_build`
  - `project_post_build`
  - `project_diff`
  - `po_apply`
  - `po_revert`
  - `po_new`
  - `po_update`
  - `po_del`
  - `po_clear`
  - `po_status`
  - `po_list`
  - `po_analyze`
  - `update`
  - `upgrade`
  - `project_new`
  - `project_del`
  - `board_new`
  - `board_del`
  - `doctor`
- Short commands with no meaningful execution graph still run through the same event model, but render as a single top-level step when appropriate.

### Existing `--tui` Flag

- Keep `--tui` accepted on `po_new` / `po_update` for backward compatibility in v1.
- Its behavior becomes redundant under the new default UI and should be treated as a compatibility alias, not as a separate renderer path.
- The old `questionary` flow should be retired once the `Textual` workflow fully covers the selection use case.

## Recommended UI Stack

- Primary library: `Textual`
- Reason:
  - Native support for full-screen terminal layouts
  - Better fit for list/detail panes, keyboard navigation, focus management, and live updates than `Rich` alone
  - Lower maintenance cost than building the whole interaction layer manually on `prompt_toolkit`

## UI Layout

### Main Layout

- Left pane: `Steps`
  - Full ordered step tree
  - Status icon, title, elapsed time, and nesting
  - Current step highlighted and auto-followed by default
- Right upper pane: `Logs`
  - Only the current step is auto-expanded by default
  - Live streaming log lines for the current step
  - Historical steps stay collapsed until explicitly expanded
- Right lower pane: `Details`
  - Step metadata:
    - start time
    - end time
    - elapsed time
    - command summary
    - exit code
    - short failure reason / summary

### Step States

- `pending`
- `running`
- `success`
- `failed`
- `skipped`

Each step must store:

- stable step id
- title
- parent step id (optional)
- state
- start timestamp
- end timestamp
- elapsed duration
- summary string
- log buffer
- command metadata (optional)

## Interaction Model

### Default Behavior

- Auto-follow is on by default.
- The active step automatically gains focus in the step list.
- Only the active step log is expanded automatically.
- When the active step changes, the log pane switches to the new step.

### Keyboard Controls

- `Up` / `Down`: move selected step
- `Enter` or `Space`: expand/collapse selected step log
- `f`: jump back to the currently running step and re-enable auto-follow
- `a`: toggle auto-follow
- `q`: detach the TUI and let the command continue in file logs / raw console fallback

### Failure Behavior

- On failure:
  - mark the failed step red
  - auto-focus the failed step
  - expand its logs
  - keep the UI on the final state screen instead of exiting immediately

## Raw Output Contract

`--raw-output` must:

- disable all dynamic rendering
- emit no ANSI cursor movement / full-screen control codes
- remain stable when piped to a file or another process

Suggested line format:

```text
STEP_START id=build.pre title="Pre-build"
LOG id=build.pre stream=stdout text="Applying selected POs..."
STEP_END id=build.pre state=success duration=1.24s
STEP_START id=build.main title="Build"
LOG id=build.main stream=stderr text="ninja: warning: ..."
STEP_END id=build.main state=failed duration=12.88s rc=1
```

The exact textual shape can evolve, but it must stay line-oriented and machine-safe.

## Execution Event Model

### New Shared Runtime Layer

Introduce a shared execution/event abstraction under `src/` that sits between command logic and presentation.

Responsibilities:

- create / nest steps
- record lifecycle transitions
- stream log lines
- stream command events
- expose one API for:
  - `Textual` renderer
  - raw-output renderer
  - existing log file sink

### Core Event Types

- `step_started`
- `step_log`
- `step_command_started`
- `step_command_finished`
- `step_finished`
- `session_summary`

### Integration Points

The first integration points should be the existing command runners:

- `src/plugins/po_plugins/runtime.py`
  - `execute_command()`
- `src/plugins/project_builder.py`
  - `_run_cmd()`
- command orchestrators:
  - `project_build()`
  - `po_apply()`
  - `po_revert()`
  - `update()` / `upgrade()`

These are already the places where command boundaries and stage boundaries exist, so they are the cheapest places to emit step events without rewriting the business logic first.

## Command-to-Step Mapping

### `project_build`

Top-level steps:

- validate / setup
- clean (optional)
- sync (optional)
- validation hooks (optional)
- pre-build
- pre-build hooks (optional)
- build hooks (optional)
- build
- post-build hooks (optional)
- post-build
- artifact collection

### `po_apply`

Top-level steps per PO:

- apply commits
- apply patches
- apply overrides
- apply custom copies
- finalize applied records

Substeps may be created per patch/override/command when useful, but the UI should not create thousands of visible nodes for large repos in v1. Fine-grained command details belong in the log pane and details pane first.

### `po_new` / `po_update`

The Textual app should support a pre-execution selection phase:

- scan modified files
- present multi-select list
- choose action (`patches`, `overrides`, `remove`, `skip`)
- preview result
- confirm
- transition into normal execution-step mode

This replaces the current `questionary`-based branch.

## Logging and File Output

- Existing file logging under `.cache/logs/` must stay.
- The new UI is not the source of truth for post-run diagnostics; logs on disk remain the durable record.
- Structured command logging (`CMD_JSON`) should continue, but the execution event layer should become the canonical in-process representation.

## Error Handling

- If the Textual app cannot start in an interactive terminal, fall back to raw output automatically.
- `--raw-output` must never fail because the UI dependency is missing.
- If the UI layer crashes mid-run:
  - the command must continue
  - execution must downgrade to raw output or file-log-only mode
  - the process exit code must still reflect the underlying command result

## Dependency Changes

- Add `textual` as the new optional/default terminal UI dependency.
- Remove `questionary` once `po_new` / `po_update` are migrated and no other code depends on it.
- Update install hints and docs accordingly.

## Files Expected To Change

- `src/__main__.py`
  - add global `--raw-output`
  - choose renderer mode before command execution
- `src/tui_utils.py`
  - replace `questionary`-specific helpers with generic terminal UI capability helpers
- `src/log_manager.py`
  - keep file logging intact; optionally add a bridge into the event layer
- `src/plugins/project_builder.py`
  - emit build/session steps
- `src/plugins/patch_override.py`
  - emit PO steps and retire the old `questionary` branch
- `src/plugins/po_plugins/runtime.py`
  - emit subprocess command events
- `pyproject.toml`
  - add `textual`
  - remove `questionary` once migration is complete
- tests:
  - new whitebox coverage for event model and command adapters
  - new TUI/raw-output command-mode tests
- docs:
  - command reference
  - getting started / TUI install notes
  - test cases

## Testing

### Whitebox

- Event model:
  - step lifecycle
  - nested steps
  - elapsed timing capture
  - failure propagation
- Renderer selection:
  - interactive default
  - forced raw mode
  - direct output bypass for `--help`, `--version`, `--json`, `--emit-plan`
- Command adapter tests for:
  - `project_build`
  - `po_apply`
  - `update`

### Integration / Blackbox

- interactive-terminal detection path
- `--raw-output` output stability
- no ANSI full-screen control sequences in raw mode
- default commands still return the same exit codes as before
- failure case keeps the failed step visible and logs accessible

## Open Risks

- Replacing `questionary` means the `po_new` / `po_update` UX must be rebuilt, not merely restyled.
- Streaming subprocess output into a live UI without starving the event loop needs careful buffering.
- Existing tests that assume plain stdout/stderr may need explicit `--raw-output` or direct-output bypass rules.

## Recommended Delivery Order

1. Introduce renderer mode selection and `--raw-output`.
2. Add the shared execution event model.
3. Add a minimal `Textual` app that can render static steps and live updates.
4. Migrate `project_build` and `po_apply` first.
5. Migrate `po_revert`, `update`, and the CRUD-style commands.
6. Retire the old `questionary` branch and update docs/tests.
