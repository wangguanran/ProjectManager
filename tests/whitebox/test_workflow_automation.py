from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_auto_version_bump_dispatches_required_checks_after_bot_push() -> None:
    workflow = (ROOT / ".github/workflows/auto-version-bump.yml").read_text(encoding="utf-8")

    assert "actions: write" in workflow
    assert "id: commit" in workflow
    assert "pushed=true" in workflow
    assert "Dispatch PR checks for bumped commit" in workflow
    assert "steps.commit.outputs.pushed == 'true'" in workflow
    assert 'gh workflow run "$workflow" --ref "$HEAD_BRANCH"' in workflow
    assert "python-app.yml pylint.yml mypy.yml" in workflow
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
