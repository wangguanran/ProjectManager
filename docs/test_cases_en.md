# ProjectManager Test Cases (Based on Code Logic)

## Common Test Data

### Dataset A: Single Repo + Basic projects Structure
1. Create and enter a temporary workspace, for example: `mkdir -p /tmp/pm_case_a && cd /tmp/pm_case_a`.
2. Copy or clone the ProjectManager code into this directory, and ensure `python -m src` works.
3. Initialize Git and create one commit (for po_apply / project_diff):
   1) `git init`
   2) `printf "baseline" > baseline.txt`
   3) `git add baseline.txt && git commit -m "init"`
4. Create a basic projects tree:
   1) `mkdir -p projects/common`
   2) `cat > projects/common/common.ini <<'INI'`
      
      `[common]`
      `PROJECT_PLATFORM = platA`
      `PROJECT_CUSTOMER = custA`
      `PROJECT_PO_CONFIG = po_base`
      
      `[po-po_base]`
      `PROJECT_PO_DIR = custom`
      `PROJECT_PO_FILE_COPY = cfg/*.ini:out/cfg/ \\\n       data/*:out/data/`
      
      `INI`
   3) `mkdir -p projects/boardA`
   4) `cat > projects/boardA/boardA.ini <<'INI'`
      
      `[boardA]`
      `PROJECT_NAME = boardA`
      `PROJECT_PO_CONFIG = po_base`
      
      `[projA]`
      `PROJECT_NAME = projA`
      `PROJECT_PLATFORM = platA`
      `PROJECT_CUSTOMER = custA`
      `PROJECT_PO_CONFIG = po_base po_extra`
      
      `[projA-sub]`
      `PROJECT_NAME = projA_sub`
      `PROJECT_PO_CONFIG = po_sub`
      
      `INI`
   5) `mkdir -p projects/boardA/po/po_base/{patches,overrides,custom/cfg,custom/data}`
   6) `printf "k=v" > projects/boardA/po/po_base/custom/cfg/sample.ini`
   7) `printf "data" > projects/boardA/po/po_base/custom/data/sample.dat`
5. If you need patch/override fixtures:
   1) Create a file: `printf "line1" > src/tmp_file.txt`
   2) Commit it: `git add src/tmp_file.txt && git commit -m "add tmp file"`
   3) Modify it: `printf "line1\nline2" > src/tmp_file.txt`
   4) Generate a patch: `git diff -- src/tmp_file.txt > projects/boardA/po/po_base/patches/tmp_file.patch`
   5) Prepare an override file (keep relative path): `mkdir -p projects/boardA/po/po_base/overrides/src && cp src/tmp_file.txt projects/boardA/po/po_base/overrides/src/tmp_file.txt`

### Dataset B: Manifest Multi-Repo (for _find_repositories / project_diff)
1. Create and enter a workspace, for example: `mkdir -p /tmp/pm_case_b && cd /tmp/pm_case_b`.
2. Create multiple repos:
   1) `mkdir -p repo1 repo2`
   2) `git -C repo1 init && printf "r1" > repo1/a.txt && git -C repo1 add a.txt && git -C repo1 commit -m "r1"`
   3) `git -C repo2 init && printf "r2" > repo2/b.txt && git -C repo2 add b.txt && git -C repo2 commit -m "r2"`
3. Create `.repo/manifest.xml`:
   1) `mkdir -p .repo/manifests`
   2) `cat > .repo/manifest.xml <<'XML'`
      
      `<manifest>`
      `  <project name="repo1" path="repo1" />`
      `  <project name="repo2" path="repo2" />`
      `</manifest>`
      
      `XML`
4. Add a minimal `projects` directory (you can reuse Dataset A step 4).

---

## 1. CLI & Argument Parsing (src/__main__.py)

| Case ID | Module | Title | Preconditions | Steps | Expected Result | Priority | Type |
|---|---|---|---|---|---|---|---|
| CLI-001 | CLI/Arg Parsing | `--help` shows operations and plugin flags | Dataset A completed | 1. Run `python -m src --help`.<br>2. Check the `supported operations` list.<br>3. Check plugin flag descriptions (e.g., `--keep-diff-dir`, `--short`). | Help output includes registered operations and available flags, properly formatted. | P1 | Functional |
| CLI-002 | CLI/Arg Parsing | `--version` reads pyproject.toml | Dataset A completed | 1. Run `python -m src --version`.<br>2. Compare with `project.version` in `pyproject.toml`. | Output starts with the pyproject version. It may include a build suffix like `+g<shortsha>` when git/build metadata is available. | P1 | Functional |
| CLI-003 | CLI/Arg Parsing | Exact operation match executes | Dataset A completed | 1. Run `python -m src po_list projA --short`.<br>2. Observe output. | Command executes successfully; only PO names are printed; no “Unknown operation” error. | P0 | Functional |
| CLI-004 | CLI/Arg Parsing | Fuzzy match (prefix) auto-corrects | Dataset A completed | 1. Run `python -m src buil projA`.<br>2. Observe console/log output. | Fuzzy match message appears and `project_build` is executed; no unknown-op exit. | P1 | Compatibility |
| CLI-005 | CLI/Arg Parsing | Fuzzy match ambiguity warning | Dataset A completed | 1. Run `python -m src po projA`.<br>2. Observe console output. | Ambiguous operation warning shows candidate matches; best match is executed. | P2 | Compatibility |
| CLI-006 | CLI/Arg Parsing | Unknown operation suggestions | Dataset A completed | 1. Run `python -m src unknown_op projA`. | Error shows unknown operation and possible suggestions or available list; non-zero exit. | P1 | Negative |
| CLI-007 | CLI/Arg Parsing | `--short` parsed as boolean flag | Dataset A completed | 1. Run `python -m src po_list projA --short`.<br>2. Observe output. | Only PO names are printed; no patch/override details. | P1 | Functional |
| CLI-008 | CLI/Arg Parsing | Unsupported flag triggers TypeError | Dataset A completed | 1. Run `python -m src po_list projA --unknown-flag 1`. | TypeError occurs when calling the operation; process exits with error. | P1 | Negative |
| CLI-009 | CLI/Arg Parsing | Missing required args show error | Dataset A completed | 1. Run `python -m src project_new`. | Error states missing required arguments and exits non-zero. | P0 | Negative |

## 2. Config Loading & Project Index (src/__main__.py)

| Case ID | Module | Title | Preconditions | Steps | Expected Result | Priority | Type |
|---|---|---|---|---|---|---|---|
| CFG-001 | Config Load | Missing common.ini degrades gracefully | Rename/remove `projects/common/common.ini` | 1. Run any command (e.g., `python -m src po_list projA`).<br>2. Check logs. | Log warns common config missing; command still runs with empty common config. | P2 | Compatibility |
| CFG-002 | Config Load | common.ini loads [common] and [po-*] sections | Dataset A completed | 1. Run `python -m src po_list projA`.<br>2. Check logs for `Loaded po configurations`. | `po-po_base` appears in `po_configs`; `common` is loaded. | P1 | Functional |
| CFG-003 | Config Load | Inline comment stripping (# / ;) | Add `KEY = value # comment` to common.ini | 1. Run `python -m src po_list projA`.<br>2. Inspect loaded values (logs or debug). | Values exclude inline comments. | P2 | Functional |
| CFG-004 | Project Scan | projects directory missing | Temporarily rename `projects` | 1. Run `python -m src po_list projA`. | Log warns projects directory missing; command does not crash. | P1 | Negative |
| CFG-005 | Project Scan | Board without ini is skipped | Create empty `projects/boardEmpty/` | 1. Run `python -m src po_list projA`.<br>2. Check logs. | Log warns no ini found; board is ignored. | P2 | Compatibility |
| CFG-006 | Project Scan | Multiple ini files assert | Place two ini files in a board dir | 1. Run `python -m src po_list projA`. | Assertion error indicates multiple ini files; process stops. | P1 | Negative |
| CFG-007 | Project Scan | Duplicate keys in section cause skip | Put duplicate `PROJECT_NAME` in one section | 1. Run `python -m src po_list projA`.<br>2. Check logs. | Error logs duplicate key; that board is skipped. | P1 | Negative |
| CFG-008 | Config Merge | common + parent + child merge with PO concat | Dataset A completed | 1. Ensure `projA` and `projA-sub` exist.<br>2. Run `python -m src po_list projA-sub`.<br>3. Inspect effective config in logs. | Child inherits common and parent; `PROJECT_PO_CONFIG` is concatenated with space. | P1 | Functional |
| CFG-009 | Relationships | parent/children built correctly | Dataset A completed | 1. Inspect `projects_info` in logs. | `projA-sub` parent is `projA`; `projA` children includes `projA-sub`. | P2 | Functional |
| CFG-010 | Index Write | projects.json written per board | Dataset A completed | 1. Run a command (e.g., `python -m src po_list projA`).<br>2. Check `projects/boardA/projects.json`. | File contains board_name, last_updated, and projects list with configs. | P1 | Functional |

## 3. Repository Discovery (_find_repositories)

| Case ID | Module | Title | Preconditions | Steps | Expected Result | Priority | Type |
|---|---|---|---|---|---|---|---|
| REPO-001 | Repo Discovery | Single repo detects root | Dataset A completed | 1. Run `python -m src project_diff projA`.<br>2. Check `projects/repositories.json`. | `repositories` contains `name=root` with current path; `discovery_type=single`. | P1 | Functional |
| REPO-002 | Repo Discovery | Manifest multi-repo detection | Dataset B completed | 1. Run `python -m src project_diff projA` in dataset B root.<br>2. Check `projects/repositories.json`. | `repositories` includes manifest projects; `discovery_type=manifest`. | P1 | Functional |
| REPO-003 | Repo Discovery | Missing include logs warning | Add `<include name="missing.xml"/>` to manifest | 1. Run `python -m src project_diff projA`.<br>2. Check logs. | Warning about missing include; other repos still detected. | P2 | Compatibility |
| REPO-004 | Repo Discovery | No .repo and no .git | Run in a clean non-git directory | 1. Run `python -m src project_diff projA` in empty dir.<br>2. Check `projects/repositories.json`. | `repositories` empty; `discovery_type` empty; command does not crash. | P2 | Edge |

## 4. Hook Registration & Execution (src/hooks/*)

| Case ID | Module | Title | Preconditions | Steps | Expected Result | Priority | Type |
|---|---|---|---|---|---|---|---|
| HOOK-001 | Hook Reg | Global hooks sorted by priority | Use a small test script importing hooks | 1. Register two hooks with HIGH and LOW priorities.<br>2. Call `get_hooks`. | Hooks are ordered by priority (HIGH before LOW). | P2 | Functional |
| HOOK-002 | Hook Reg | Same-name hook overwrites | Same as above | 1. Register a hook, then register another with same name.<br>2. Check logs and list. | Log warns overwrite; only the latest hook remains. | P2 | Compatibility |
| HOOK-003 | Hook Query | Platform hooks merged with global | Same as above | 1. Register a global hook and a platform hook (platform=platA).<br>2. Call `get_hooks(HookType.BUILD, platform='platA')`. | Result contains both global and platform hooks, sorted by priority. | P1 | Functional |
| HOOK-004 | Hook Exec | Hook returning False stops execution | Same as above | 1. Register a hook returning False and another normal hook.<br>2. Run `execute_hooks`. | Execution stops at the False hook and returns False. | P1 | Negative |
| HOOK-005 | Hook Exec | Exception with stop_on_error=False continues | Same as above | 1. Register a hook that raises and a normal hook.<br>2. Run `execute_hooks(stop_on_error=False)`. | Error is logged; subsequent hook runs; overall returns True. | P2 | Compatibility |
| HOOK-006 | Hook Exec | execute_single_hook not found | Same as above | 1. Call `execute_single_hook` with a missing hook_name. | Returns success=False with error message. | P2 | Negative |
| HOOK-007 | Hook Validate | No-arg hook is invalid | Same as above | 1. Register a no-arg function.<br>2. Call `validate_hooks`. | Hook appears in invalid list; valid=False. | P2 | Functional |
| HOOK-008 | Hook Fallback | Platform failure falls back to global | Same as above | 1. Register platform hook returning False.<br>2. Register global hook returning True.<br>3. Call `execute_hooks_with_fallback(..., platform='platA')`. | Falls back to global hook and returns True. | P1 | Functional |

## 5. Board & Project Management (src/plugins/project_manager.py)

| Case ID | Module | Title | Preconditions | Steps | Expected Result | Priority | Type |
|---|---|---|---|---|---|---|---|
| PM-001 | Board | board_new succeeds with template | `projects/template/template.ini` and `projects/template/po` exist | 1. Run `python -m src board_new boardTest`.<br>2. Check `projects/boardTest/boardTest.ini` and `projects/boardTest/po`. | Board directory created; ini uses template with first section replaced; po dir copied. | P0 | Functional |
| PM-002 | Board | board_new succeeds without template | Temporarily rename `projects/template` | 1. Run `python -m src board_new boardNoTpl`.<br>2. Check ini and po structure.<br>3. Restore template dir. | Default ini content used; po dir contains `po_template/patches` and `overrides`. | P1 | Compatibility |
| PM-003 | Board | board_new rejects empty/./.. | None | 1. Run `python -m src board_new ""` and `python -m src board_new .` and `python -m src board_new ..`. | Error for each; no directories created. | P1 | Negative |
| PM-004 | Board | board_new rejects separators/absolute path | None | 1. Run `python -m src board_new a/b`.<br>2. Run `python -m src board_new /abs/path`. | Errors; no directories created. | P1 | Negative |
| PM-005 | Board | board_new rejects reserved names | None | 1. Run `python -m src board_new common`. | Error; no directory created. | P1 | Negative |
| PM-006 | Board | board_new fails if already exists | `projects/boardA` exists | 1. Run `python -m src board_new boardA`. | Error indicates already exists; no overwrite. | P1 | Negative |
| PM-007 | Board | board_del removes board and caches | `projects/boardTest` exists | 1. Run `python -m src board_del boardTest`.<br>2. Check `projects/boardTest` is gone.<br>3. Check `.cache/.../boardTest` is removed if present. | Board deleted; caches removed; projects index updated. | P0 | Functional |
| PM-008 | Board | board_del blocks protected boards | Provide env `protected_boards` containing boardA (via script) | 1. Call `board_del` with protected list. | Error says board is protected; no deletion. | P1 | Negative |
| PM-009 | Project | project_new success and ini appended | Dataset A completed | 1. Run `python -m src project_new projA-new` (ensure `projA` exists as parent).<br>2. Check `projects/boardA/boardA.ini` for new section appended. | New section appended; `PROJECT_NAME` composed from platform+project+customer; comments preserved. | P0 | Functional |
| PM-010 | Project | project_new cannot resolve board | Ensure no matching parent/prefix | 1. Run `python -m src project_new unknownProj`. | Error indicates board cannot be determined. | P1 | Negative |
| PM-011 | Project | project_new rejects same as board | boardA exists | 1. Run `python -m src project_new boardA`. | Error; ini not modified. | P1 | Negative |
| PM-012 | Project | project_new rejects duplicate | projA exists | 1. Run `python -m src project_new projA`. | Error indicates project exists; no ini change. | P1 | Negative |
| PM-013 | Project | project_del removes project and subprojects | Dataset A completed with `projA-sub` | 1. Run `python -m src project_del projA`.<br>2. Check ini: `projA` and `projA-sub` removed. | Main and subproject sections removed. | P0 | Functional |
| PM-014 | Project | project_del missing project message | Dataset A completed | 1. Run `python -m src project_del not_exist_proj`. | Message indicates project missing; ini not corrupted. | P2 | Compatibility |

## 6. Build & Diff (src/plugins/project_builder.py)

| Case ID | Module | Title | Preconditions | Steps | Expected Result | Priority | Type |
|---|---|---|---|---|---|---|---|
| BUILD-001 | Diff | Single repo diff structure | Dataset A completed with uncommitted changes | 1. Run `python -m src project_diff projA`.<br>2. Locate `.cache/build/projA/<timestamp>/diff_projA_<timestamp>.tar.gz`.<br>3. (Optional) Re-run with `--keep-diff-dir` to inspect `.cache/build/projA/<timestamp>/diff`. | Archive contains `diff/after diff/before diff/patch diff/commit`; in single-repo mode there is no repo-name subdir. | P1 | Functional |
| BUILD-002 | Diff | Multi-repo diff structure | Dataset B completed with changes in repos | 1. Run `python -m src project_diff projA`.<br>2. Locate `.cache/build/projA/<timestamp>/diff_projA_<timestamp>.tar.gz`.<br>3. (Optional) Re-run with `--keep-diff-dir` to inspect `.cache/build/projA/<timestamp>/diff`. | Archive (or kept diff dir) contains repo-name subdirs under `after/before/patch/commit` (e.g. `repo1/ repo2/`). | P1 | Functional |
| BUILD-003 | Diff | No changes => no patch files | Working tree clean | 1. Ensure `git status` shows clean.<br>2. Run `python -m src project_diff projA`.<br>3. Inspect archive (or `diff/patch` with `--keep-diff-dir`). | `changes_worktree.patch` and `changes_staged.patch` are not created (or are empty and thus omitted). | P2 | Edge |
| BUILD-004 | Diff | keep-diff-dir keeps original | Dataset A completed | 1. Run `python -m src project_diff projA --keep-diff-dir`.<br>2. Check diff directory still exists. | Diff dir remains after tar.gz creation. | P2 | Functional |
| BUILD-005 | Build Flow | Validation hook failure aborts | Register platform VALIDATION hook returning False | 1. Register hook via script.<br>2. Run `python -m src project_build projA`. | Build stops at validation stage and returns False. | P1 | Negative |
| BUILD-006 | Build Flow | Pre/Build/Post hook failure aborts | Register platform hook returning False | 1. Register PRE_BUILD/BUILD/POST_BUILD hook returning False.<br>2. Run `python -m src project_build projA`. | Build stops at failing stage with error log. | P1 | Negative |
| BUILD-007 | Build Flow | No platform skips hooks | Use project without PROJECT_PLATFORM | 1. Run `python -m src project_build <proj>` without platform. | No platform hooks executed; pre/do/post functions run. | P2 | Functional |
| BUILD-008 | Build Flow | Sync runs configured command | Dataset A completed | 1. Set `PROJECT_SYNC_CMD` for `projA`.<br>2. Run `python -m src project_build projA --sync --no-po --no-diff`.<br>3. Check marker/log output. | Sync command executes before build steps; build completes successfully. | P1 | Functional |
| BUILD-009 | Build Flow | Clean requires `--force` and excludes config | Dataset A completed | 1. Create untracked `junk.txt` and `.cache/po_applied/...` file.<br>2. Run `python -m src project_build projA --clean --no-po --no-diff`.<br>3. Re-run with `--clean --force`. | Without `--force`: command fails fast.<br>With `--force`: untracked junk is removed, but `projects/` and `.cache/po_applied/` remain. | P1 | Safety |
| BUILD-010 | Build Flow | Profile dispatch chooses full/single command | Dataset A completed | 1. Set `PROJECT_BUILD_FULL_CMD` and `PROJECT_BUILD_SINGLE_CMD` for `projA`.<br>2. Run `python -m src project_build projA --profile full --no-po --no-diff`.<br>3. Run `python -m src project_build projA --profile single --repo r1 --target t1 --no-po --no-diff`. | Runs the expected profile command; `{repo}` and `{target}` placeholders are formatted for single build. | P1 | Functional |

## 7. PO Parsing & Apply (src/plugins/patch_override.py)

| Case ID | Module | Title | Preconditions | Steps | Expected Result | Priority | Type |
|---|---|---|---|---|---|---|---|
| PO-001 | PO Config | parse_po_config basic parsing | None | 1. In Python REPL, run `from src.plugins.patch_override import parse_po_config`.<br>2. Call `parse_po_config("po1 po2 -po3 -po4[file1 file2]")`. | apply_pos has `po1`, `po2`; exclude_pos has `po3`; exclude_files has `po4` with file1/file2. | P1 | Functional |
| PO-002 | PO Apply | Empty PROJECT_PO_CONFIG returns True | Set PROJECT_PO_CONFIG empty | 1. Run `python -m src po_apply projA`. | Warns no PO config and returns True; no applied record created. | P2 | Edge |
| PO-003 | PO Apply | Missing board_name fails | Remove board_name in projects_info (via script) | 1. Call `po_apply` from script. | Returns False; log indicates board not found. | P1 | Negative |
| PO-004 | PO Apply | Already-applied PO is skipped | Create repo-root record `.cache/po_applied/<board>/<project>/<po>.json` | 1. Run `python -m src po_apply projA`. | Logs “already applied ... skipping”; no re-apply. | P2 | Compatibility |
| PO-005 | PO Apply | Patch apply success | Patch file prepared | 1. Run `python -m src po_apply projA`.<br>2. Verify file changes are applied. | `git apply` succeeds; applied record JSON captures commands and affected files. | P0 | Functional |
| PO-005b | PO Apply | Commit apply success (commits first) | Commit patch prepared under `po/<po>/commits/` via `git format-patch` | 1. Create a commit in target repo.<br>2. Export it to `projects/<board>/po/<po>/commits/`.<br>3. Reset repo to remove the commit.<br>4. Run `python -m src po_apply projA`. | `git am` succeeds and runs before `git apply`/overrides/custom; applied record JSON captures commit SHAs and affected files. | P1 | Functional |
| PO-006 | PO Apply | Patch failure aborts | Use a patch that doesn’t match repo | 1. Run `python -m src po_apply projA`. | Error logged; returns False; override/custom not executed. | P0 | Negative |
| PO-007 | PO Apply | Override copy success | Override file prepared | 1. Run `python -m src po_apply projA`.<br>2. Verify target file content matches override. | Override file copied successfully; log shows copy. | P1 | Functional |
| PO-008 | PO Apply | .remove deletes target file | Create `path/to/file.remove` under overrides | 1. Ensure target file exists.<br>2. Run `python -m src po_apply projA --force`. | Target file removed; log shows remove action. | P1 | Functional |
| PO-009 | PO Apply | exclude_files skips specified items | Add `po_base[file.remove]` to PROJECT_PO_CONFIG | 1. Run `python -m src po_apply projA`. | Specified file is skipped; no copy/remove executed. | P2 | Functional |
| PO-010 | PO Apply | Custom dir copies by config | Dataset A custom files prepared | 1. Run `python -m src po_apply projA`.<br>2. Check `out/cfg/sample.ini` and `out/data/sample.dat`. | Custom files copied to target paths. | P1 | Functional |
| PO-011 | PO Revert | Patch reverse success | PO-005 executed | 1. Run `python -m src po_revert projA`.<br>2. Verify changes are reverted. | `git apply --reverse` succeeds; file restored. | P1 | Functional |
| PO-011b | PO Revert | Commit revert success | PO-005b executed | 1. Run `python -m src po_revert projA`.<br>2. Verify the commit changes are undone. | Commits from `commits/` are reverted via `git revert`; applied record is removed. | P1 | Functional |
| PO-012 | PO Revert | Override revert for tracked file | Override target is Git-tracked | 1. Run `python -m src po_revert projA`. | File restored via `git checkout --`. | P1 | Functional |
| PO-013 | PO Revert | Override revert for untracked file | Override target is untracked | 1. Run `python -m src po_revert projA`. | File is deleted directly. | P1 | Functional |
| PO-014 | PO Revert | Custom revert warns manual cleanup | PROJECT_PO_FILE_COPY configured | 1. Run `python -m src po_revert projA`.<br>2. Check logs. | Warning indicates custom files may need manual cleanup; flow returns True. | P2 | Compatibility |

## 8. PO Create/Update/Delete/List (src/plugins/patch_override.py)

| Case ID | Module | Title | Preconditions | Steps | Expected Result | Priority | Type |
|---|---|---|---|---|---|---|---|
| PO-015 | PO Create | po_new rejects invalid name | Dataset A completed | 1. Run `python -m src po_new projA PO-INVALID`. | Error indicates name must match `po[a-z0-9_]*`. | P1 | Negative |
| PO-016 | PO Create | po_new force creates empty structure | Dataset A completed | 1. Run `python -m src po_new projA po_force --force`.<br>2. Check `projects/boardA/po/po_force/commits`, `patches`, and `overrides`. | Structure created successfully without prompts. | P1 | Functional |
| PO-017 | PO Create | po_new interactive selection | Workspace has modified/deleted files | 1. Run `python -m src po_new projA po_interactive`.<br>2. Select files and choose patch/override/remove. | Selected files are processed and files created accordingly. | P1 | Functional |
| PO-018 | PO Create | po_new with no repositories | `env['repositories']` empty (run in non-git dir) | 1. Run `python -m src po_new projA po_empty` in non-git dir. | “No git repositories found” message; no crash. | P2 | Edge |
| PO-019 | PO Update | po_update requires existing PO | Dataset A completed | 1. Create `po_update_target` first.<br>2. Run `python -m src po_update projA po_update_target --force`. | Update succeeds, reusing po_new flow. | P1 | Functional |
| PO-020 | PO Update | po_update fails if PO missing | Dataset A completed | 1. Run `python -m src po_update projA po_not_exists --force`. | Error: PO directory does not exist. | P1 | Negative |
| PO-021 | PO Delete | po_del removes directory and config | PO exists and is referenced | 1. Run `python -m src po_del projA po_base --force`.<br>2. Verify PO dir removed.<br>3. Verify PROJECT_PO_CONFIG no longer includes it. | PO directory deleted and config updated. | P0 | Functional |
| PO-022 | PO Delete | po_del cancelled by user | PO exists | 1. Run `python -m src po_del projA po_base`.<br>2. Enter `no`. | Deletion cancelled; PO directory and config unchanged. | P2 | Compatibility |
| PO-023 | PO List | po_list short names only | Dataset A completed | 1. Run `python -m src po_list projA --short`. | Only PO names printed. | P1 | Functional |
| PO-024 | PO List | po_list detailed output | Dataset A completed | 1. Run `python -m src po_list projA`. | Outputs commits, patches, overrides, and custom file lists. | P1 | Functional |

## 9. Utilities & Logging (src/utils.py / src/log_manager.py / src/profiler.py)

| Case ID | Module | Title | Preconditions | Steps | Expected Result | Priority | Type |
|---|---|---|---|---|---|---|---|
| UTIL-001 | Utils | get_version reads pyproject | Dataset A completed | 1. Run `python -c "from src.utils import get_version; print(get_version())"`.<br>2. Compare with `pyproject.toml`. | Output starts with the pyproject version. It may include a build suffix like `+g<shortsha>` when git/build metadata is available. | P2 | Functional |
| UTIL-002 | Utils | get_version fallback when missing | Temporarily rename `pyproject.toml` | 1. Run the command above.<br>2. Restore file name. | Output is `0.0.0-dev`. | P2 | Edge |
| UTIL-003 | Utils | get_filename creates directory | Remove `.cache/logs` | 1. Run `python -c "from src.utils import get_filename; print(get_filename('T_', '.log', '.cache/logs'))"`. | `.cache/logs` created; returned path contains timestamp. | P3 | Functional |
| UTIL-004 | Utils | list_file_path depth & filters | Create test tree | 1. Create `tmp/a/b/file.txt`.<br>2. Run `python -c "from src.utils import list_file_path; print(list(list_file_path('tmp', max_depth=1)))"`. | Output excludes paths deeper than depth 1. | P3 | Functional |
| LOG-001 | Logging | latest.log symlink created | Dataset A completed | 1. Run any command (e.g., `python -m src --help`).<br>2. Check `.cache/latest.log`. | Symlink exists and points to the latest log file. | P2 | Functional |
| PROF-001 | Profiler | ENABLE_CPROFILE toggles profiling | Use a script setting `builtins.ENABLE_CPROFILE=True` | 1. Call a function decorated with `@func_cprofile`. | cProfile stats appear in logs; process finishes normally. | P3 | Functional |

## 10. Artifact Saving Rules (src/plugins/project_builder.py)

### Proposed Rule Syntax

- `path:<src_relpath>:<dest_dir>/` (fixed path, single file or directory)
- `glob:<glob_pattern>:<dest_dir>/` (glob under workspace root)
- `regex@<root_relpath>:<regex_pattern>:<dest_dir>/` (regex match under search root)
- `manifest:<manifest_relpath>:<dest_dir>/` (each line is a relative path)

### Safety Requirements

- Only relative paths are allowed; reject absolute paths and `..` traversal.
- All saved artifacts use safe relpaths anchored in the project root.

| Case ID | Module | Title | Preconditions | Steps | Expected Result | Priority | Type |
|---|---|---|---|---|---|---|---|
| ART-001 | Artifact Save | Fixed path rule | Dataset A completed with `out/bin/app.bin` created | 1. Set `PROJECT_BUILD_ARTIFACTS = path:out/bin/app.bin:bin/` for `projA`.<br>2. Run `python -m src project_build projA`.<br>3. Inspect `.cache/build/projA/<timestamp>/artifacts`. | `bin/app.bin` exists under artifacts root. | P1 | Functional |
| ART-002 | Artifact Save | Glob rule collects multiple files | Dataset A completed with `out/*.whl` created | 1. Set `PROJECT_BUILD_ARTIFACTS = glob:out/*.whl:wheels/` for `projA`.<br>2. Run `python -m src project_build projA`.<br>3. Inspect artifacts root. | All matched wheel files are copied under `wheels/`. | P1 | Functional |
| ART-003 | Artifact Save | Regex rule with search root | Dataset A completed with `logs/**/*.log` created | 1. Set `PROJECT_BUILD_ARTIFACTS = regex@logs:.*\\.log$:logs/` for `projA`.<br>2. Run `python -m src project_build projA`.<br>3. Inspect artifacts root. | All log files under `logs/` copied to `logs/`, preserving subpaths. | P1 | Functional |
| ART-004 | Artifact Save | Manifest rule expands paths | Dataset A completed with `artifacts.manifest` listing files | 1. Create `artifacts.manifest` with `out/artifact.txt` and `logs/build.log`.<br>2. Set `PROJECT_BUILD_ARTIFACTS = manifest:artifacts.manifest:bundle/`.<br>3. Run `python -m src project_build projA`. | Manifest entries are copied under `bundle/` with relative paths preserved. | P1 | Functional |
| ART-005 | Artifact Save | Unsafe relpaths rejected | Dataset A completed with manifest entry `../secret.txt` | 1. Set `PROJECT_BUILD_ARTIFACTS = manifest:artifacts.manifest:bundle/` for `projA`.<br>2. Run `python -m src project_build projA`. | Command fails with error indicating unsafe path. | P1 | Negative |

## 11. Safety Dry-Run (project_diff / po_apply / po_revert)

| Case ID | Module | Title | Preconditions | Steps | Expected Result | Priority | Type |
|---|---|---|---|---|---|---|---|
| DRY-001 | Safety | `project_diff --dry-run` prints plan and does not write | Dataset A or B completed | 1. Run `python -m src project_diff projA --dry-run`.<br>2. Check filesystem for `.cache/build/.../diff`. | Logs show planned diff root/repositories; no `.cache/build/.../diff` directories are created. | P1 | Safety |
| DRY-002 | Safety | `po_apply --dry-run` prints plan and does not write | Dataset A completed with patches/overrides/custom configured | 1. Run `python -m src po_apply projA --dry-run`.<br>2. Check that repo files are unchanged. | Logs show planned `git apply`/copy/remove actions; no repo writes occur; no `po_applied` flag is created. | P0 | Safety |
| DRY-003 | Safety | `po_revert --dry-run` prints plan and does not write | Dataset A completed with applyable PO | 1. Run `python -m src po_revert projA --dry-run`.<br>2. Check that repo files are unchanged. | Logs show planned `git apply --reverse`/checkout/remove actions; no repo writes occur. | P0 | Safety |
