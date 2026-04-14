# Commit History Skip Design

**Goal:** Skip `commits/` patch application when a `git format-patch` file already references a commit SHA that exists in the target repository history.

**Scope**

- Only `src/plugins/po_plugins/commits.py` changes behavior.
- Only patches with a parseable `From <sha>` header are eligible.
- The check is exact-SHA only. Rebases, cherry-picks, and content-equivalent commits with different SHAs are not treated as already applied.

**Behavior**

- Before `git am`, parse the patch header for the original commit SHA.
- If no SHA is found, keep the current flow unchanged.
- If the SHA exists in the target repository history, skip `git am` for that patch.
- Record the skip in the applied record so later revert logic does not try to revert a commit that was never applied by this PO run.

**Non-Goals**

- No patch-id or content-equivalence detection.
- No changes to patch/override/custom plugin behavior.
- No changes to PO config syntax.

**Testing**

- Add a whitebox regression test covering a real Git repository where the formatted commit patch points to a commit already present in history.
- Verify `po_apply` succeeds, records the skip, and does not log a `git am` command for that patch.
