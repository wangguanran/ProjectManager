import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _workflow_event_block(workflow: str, event_name: str) -> str:
    match = re.search(rf"(?ms)^  {re.escape(event_name)}:\n(?P<body>.*?)(?=^  \w|\Z)", workflow)
    assert match is not None, f"{event_name} event block missing"
    return match.group("body")


def test_auto_version_bump_dispatches_required_checks_after_bot_push() -> None:
    workflow = (ROOT / ".github/workflows/auto-version-bump.yml").read_text(encoding="utf-8")

    assert "actions: write" in workflow
    assert "workflow_dispatch:" in workflow
    assert "head_branch:" in workflow
    assert "base_branch:" in workflow
    assert "head_sha:" in workflow
    assert "id: commit" in workflow
    assert "pushed=true" in workflow
    assert "Validate dispatched final auto-version context" in workflow
    assert "Dispatch PR checks for bumped commit" in workflow
    assert "steps.commit.outputs.pushed == 'true'" in workflow
    assert 'gh workflow run "$workflow" --ref "$HEAD_BRANCH"' in workflow
    assert "python-app.yml pylint.yml mypy.yml" in workflow
    assert "gh workflow run auto-version-bump.yml" in workflow
    assert "gh workflow run auto-merge-pr.yml" in workflow
    assert "gh workflow run validate-main-pr-source.yml" in workflow
    assert '-f "head_sha=$HEAD_SHA"' in workflow


def test_validate_main_source_branch_supports_dispatched_head_validation() -> None:
    workflow = (ROOT / ".github/workflows/validate-main-pr-source.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "head_branch:" in workflow
    assert "base_branch:" in workflow
    assert "head_sha:" in workflow
    assert "github.event.inputs.head_branch" in workflow
    assert "github.event.inputs.base_branch" in workflow
    assert "github.event.inputs.head_sha" in workflow


def test_validate_main_source_branch_uses_tested_release_version_gate() -> None:
    workflow = (ROOT / ".github/workflows/validate-main-pr-source.yml").read_text(encoding="utf-8")

    assert "EVENT_NAME: ${{ github.event_name }}" in workflow
    assert "EVENT_ACTION: ${{ github.event.action || '' }}" in workflow
    assert "python3 .github/scripts/validate_release_version.py" in workflow
    assert '--head-branch "$HEAD_BRANCH"' in workflow
    assert '--event-name "$EVENT_NAME"' in workflow
    assert '--event-action "$EVENT_ACTION"' in workflow


def test_auto_merge_pr_workflow_enables_merge_after_required_checks() -> None:
    workflow = (ROOT / ".github/workflows/auto-merge-pr.yml").read_text(encoding="utf-8")

    assert "pull_request_target:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "pr_number:" in workflow
    assert "head_sha:" in workflow
    assert "pull-requests: write" in workflow
    assert "contents: write" in workflow
    assert "actions: write" in workflow
    assert "github.event.pull_request.draft == false" in workflow
    assert "REPO: ${{ github.repository }}" in workflow
    assert 'gh pr view "$PR_NUMBER" --repo "$REPO"' in workflow
    assert (
        'gh pr merge "$PR_NUMBER" --repo "$REPO" --auto --squash --delete-branch --match-head-commit "$HEAD_SHA"'
        in workflow
    )


def test_auto_merge_pr_workflow_dispatch_skips_draft_prs_before_merge() -> None:
    workflow = (ROOT / ".github/workflows/auto-merge-pr.yml").read_text(encoding="utf-8")

    draft_check = 'is_draft="$(gh pr view "$PR_NUMBER" --repo "$REPO" --json isDraft --jq .isDraft)"'
    waiting_message = 'echo "PR #$PR_NUMBER is draft/WIP; waiting for gh pr ready before enabling auto-merge."'
    merge_command = (
        'gh pr merge "$PR_NUMBER" --repo "$REPO" --auto --squash --delete-branch --match-head-commit "$HEAD_SHA"'
    )

    assert draft_check in workflow
    assert waiting_message in workflow
    assert "id: enable" in workflow
    assert 'echo "skipped_draft=true" >> "$GITHUB_OUTPUT"' in workflow
    assert "if: steps.enable.outputs.skipped_draft != 'true'" in workflow
    assert f"{waiting_message}\n            exit 0" in workflow
    assert workflow.index(draft_check) < workflow.index(merge_command)


def test_auto_merge_pr_workflow_dispatches_release_watcher_for_github_token_merges() -> None:
    workflow = (ROOT / ".github/workflows/auto-merge-pr.yml").read_text(encoding="utf-8")

    assert "Dispatch release watcher for GitHub-token auto-merge" in workflow
    assert "GITHUB_TOKEN-created auto-merge pushes do not trigger push workflows" in workflow
    assert "workflow_dispatch is exempt" in workflow
    assert 'base_branch="$(gh pr view "$PR_NUMBER" --repo "$REPO" --json baseRefName --jq .baseRefName)"' in workflow
    assert "gh workflow run release-after-main-merge.yml" in workflow
    assert '--repo "$REPO"' in workflow
    assert '--ref "$base_branch"' in workflow
    assert '-f "target_ref=$base_branch"' in workflow
    assert '-f "pr_number=$PR_NUMBER"' in workflow
    assert '-f "pr_head_sha=$HEAD_SHA"' in workflow


def test_auto_merge_pr_workflow_rechecks_head_before_release_watcher_dispatch() -> None:
    workflow = (ROOT / ".github/workflows/auto-merge-pr.yml").read_text(encoding="utf-8")

    assert (
        workflow.count('current_head="$(gh pr view "$PR_NUMBER" --repo "$REPO" --json headRefOid --jq .headRefOid)"')
        == 2
    )
    assert (
        'echo "PR #$PR_NUMBER head moved from $HEAD_SHA to $current_head; skipping stale release watcher dispatch."'
        in workflow
    )


def test_required_pr_ci_workflows_run_for_all_main_pull_requests() -> None:
    for workflow_name in ("python-app.yml", "pylint.yml", "mypy.yml"):
        workflow = (ROOT / f".github/workflows/{workflow_name}").read_text(encoding="utf-8")
        pull_request_block = _workflow_event_block(workflow, "pull_request")

        assert 'branches: [ "main" ]' in pull_request_block or 'branches: ["main"]' in pull_request_block
        assert "paths:" not in pull_request_block


def test_release_after_main_merge_runs_on_main_push_and_tags_pyproject_version() -> None:
    workflow_path = ROOT / ".github/workflows/release-after-main-merge.yml"
    assert workflow_path.exists()

    workflow = workflow_path.read_text(encoding="utf-8")

    assert "push:" in workflow
    assert "- main" in workflow
    assert "contents: write" in workflow
    assert "actions: write" in workflow
    assert "tomllib" in workflow
    assert "pyproject.toml" in workflow
    assert 'tag = f"v{version}"' in workflow
    assert "Expected pyproject.toml project.version to be X.Y.Z" in workflow
    assert 'echo "tag=${tag}" >> "$GITHUB_OUTPUT"' in workflow


def test_release_after_main_merge_supports_dispatch_target_sha_and_pr_merge_wait() -> None:
    workflow = (ROOT / ".github/workflows/release-after-main-merge.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "target_sha:" in workflow
    assert "target_ref:" in workflow
    assert "pr_number:" in workflow
    assert "pr_head_sha:" in workflow
    assert "Resolve target main commit" in workflow
    assert "INPUT_TARGET_SHA" in workflow
    assert "INPUT_PR_NUMBER" in workflow
    assert "mergedAt" in workflow
    assert "mergeCommit" in workflow
    assert "target_sha=$merge_sha" in workflow
    assert 'echo "sha=${target_sha}" >> "$GITHUB_OUTPUT"' in workflow
    assert "Validate target commit is on main" in workflow
    assert "ref: ${{ steps.target.outputs.sha }}" in workflow
    assert "steps.target.outputs.skip != 'true' && steps.existing.outputs.skip != 'true'" in workflow


def test_release_after_main_merge_pr_watcher_concurrency_includes_expected_head() -> None:
    workflow = (ROOT / ".github/workflows/release-after-main-merge.yml").read_text(encoding="utf-8")

    assert (
        "group: release-after-main-merge-${{ github.event_name == 'workflow_dispatch' && "
        "github.event.inputs.target_sha != '' && github.event.inputs.target_sha || "
        "github.event_name == 'workflow_dispatch' && github.event.inputs.pr_number != '' && "
        "format('pr-{0}-{1}', github.event.inputs.pr_number, github.event.inputs.pr_head_sha) || github.sha }}"
        in workflow
    )


def test_release_after_main_merge_pr_watcher_timeout_fails_visibly() -> None:
    workflow = (ROOT / ".github/workflows/release-after-main-merge.yml").read_text(encoding="utf-8")

    assert (
        'echo "::error::PR #${INPUT_PR_NUMBER} was not merged before the release watcher timeout; '
        'release dispatch cannot be verified."' in workflow
    )
    assert "skip_reason=pr-not-merged" not in workflow


def test_release_after_main_merge_skips_existing_release_without_failure() -> None:
    workflow = (ROOT / ".github/workflows/release-after-main-merge.yml").read_text(encoding="utf-8")

    assert 'git ls-remote --exit-code --tags origin "refs/tags/${TAG}"' in workflow
    assert 'gh release view "$TAG"' in workflow
    assert "skip_reason=release-exists" in workflow
    assert "steps.existing.outputs.skip != 'true'" in workflow


def test_release_after_main_merge_recovers_existing_tag_without_release() -> None:
    workflow = (ROOT / ".github/workflows/release-after-main-merge.yml").read_text(encoding="utf-8")

    assert "tag_exists=true" in workflow
    assert "skip_reason=tag-exists-release-missing" in workflow
    assert 'if [ "$remote_tag_sha" != "$TARGET_SHA" ]; then' in workflow
    assert "refusing to dispatch publish-release.yml" in workflow
    assert "steps.existing.outputs.tag_exists != 'true'" in workflow
    assert "dispatching publish-release.yml." in workflow


def test_release_after_main_merge_reuses_publish_release_validation() -> None:
    workflow = (ROOT / ".github/workflows/release-after-main-merge.yml").read_text(encoding="utf-8")
    publish_release = (ROOT / ".github/workflows/publish-release.yml").read_text(encoding="utf-8")

    assert 'git tag "$TAG" "$TARGET_SHA"' in workflow
    assert 'git push origin "refs/tags/${TAG}"' in workflow
    assert 'gh workflow run publish-release.yml --ref "$TAG"' in workflow
    assert "twine upload" not in workflow
    assert "docker/build-push-action" not in workflow
    assert "  push:\n    tags:" in publish_release
    assert "  workflow_dispatch:" in publish_release
    assert "Validate pyproject version matches release tag" in publish_release


def test_publish_release_test_job_installs_console_script_before_pytest() -> None:
    workflow = (ROOT / ".github/workflows/publish-release.yml").read_text(encoding="utf-8")

    build_index = workflow.index("- name: Build project")
    install_index = workflow.index("- name: Install package entry point")
    test_index = workflow.index("- name: Run tests")

    assert build_index < install_index < test_index
    assert "source venv/bin/activate" in workflow
    assert "python -m pip install --no-deps --no-build-isolation -e ." in workflow
    assert "command -v projman" in workflow
