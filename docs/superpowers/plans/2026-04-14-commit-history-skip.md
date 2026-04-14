# Commit History Skip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skip `commits/` patch files when their `From <sha>` header already exists in the target repository history.

**Architecture:** Extend the commits PO plugin with a small header parser and an exact-SHA preflight check before `git am`. Keep applied-record and revert behavior aligned by marking these entries as skipped due to existing history.

**Tech Stack:** Python, pytest, Git CLI

---

### Task 1: Lock the regression with a whitebox test

**Files:**
- Modify: `tests/whitebox/plugins/test_patch_override.py`
- Test: `tests/whitebox/plugins/test_patch_override.py`

- [ ] **Step 1: Write the failing test**

```python
def test_po_apply_commit_patch_skips_when_commit_sha_exists_in_history(self):
    ...
    assert result is True
    assert record["commits"][0]["status"] == "already_in_history"
    assert record["commits"][0]["original_commit_sha"] == feature_sha
    assert not any("git am" in item.get("cmd", "") for item in record.get("commands", []))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/whitebox/plugins/test_patch_override.py::TestPatchOverrideApply::test_po_apply_commit_patch_skips_when_commit_sha_exists_in_history -v`
Expected: FAIL because current code falls through to `git am` and does not mark the commit as already present in history.

### Task 2: Implement exact-SHA preflight detection

**Files:**
- Modify: `src/plugins/po_plugins/commits.py`
- Modify: `src/plugins/patch_override.py`

- [ ] **Step 1: Add a patch-header SHA parser**

```python
def _extract_original_commit_sha(patch_text: str) -> str | None:
    match = re.search(r"^From ([0-9a-f]{40})\\b", patch_text, re.MULTILINE)
    return match.group(1) if match else None
```

- [ ] **Step 2: Check history before `git am`**

```python
original_commit_sha = _extract_original_commit_sha(patch_text)
if original_commit_sha and _repo_has_commit(patch_target, original_commit_sha):
    record["commits"].append(
        {
            "patch_file": os.path.relpath(patch_file, start=ctx.po_path),
            "targets": patch_targets,
            "status": "already_in_history",
            "original_commit_sha": original_commit_sha,
        }
    )
    continue
```

- [ ] **Step 3: Keep revert planning and execution from touching skipped entries**

```python
if entry.get("status") in {"already_applied", "already_in_history"}:
    continue
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `pytest tests/whitebox/plugins/test_patch_override.py::TestPatchOverrideApply::test_po_apply_commit_patch_skips_when_commit_sha_exists_in_history -v`
Expected: PASS

### Task 3: Update docs and verify the touched scope

**Files:**
- Modify: `docs/test_cases_en.md`
- Modify: `TODO.md`

- [ ] **Step 1: Document the new apply behavior**

```markdown
| PO-005c | PO Apply | Commit apply skips when patch SHA already exists in history | Commit patch prepared from an existing repo commit and left in repo history | 1. Export a commit to `po/<po>/commits/` with `git format-patch`.<br>2. Keep that commit in the target repo history.<br>3. Run `python -m src po_apply projA`. | The commit patch is skipped before `git am`; applied record marks it as already in history. |
```

- [ ] **Step 2: Mark the TODO item complete after verification**

```markdown
- [x] F-0013: Skip commit patches already present in target repo history by patch header SHA
```

- [ ] **Step 3: Run formatting and targeted verification**

Run: `make format && pytest tests/whitebox/plugins/test_patch_override.py -q`
Expected: formatting succeeds and the patch override whitebox suite passes.

- [ ] **Step 4: Commit**

```bash
git add TODO.md docs/test_cases_en.md docs/superpowers/specs/2026-04-14-commit-history-skip-design.md docs/superpowers/plans/2026-04-14-commit-history-skip.md tests/whitebox/plugins/test_patch_override.py src/plugins/po_plugins/commits.py src/plugins/patch_override.py
git commit -m "feat: skip commit patches already in history"
```
