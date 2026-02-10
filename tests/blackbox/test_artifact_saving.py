"""Blackbox tests for artifact saving rules (proposed)."""

from __future__ import annotations

import glob
from pathlib import Path

from .conftest import run_cli
from .conftest import workspace_a as _workspace_a


def _latest_artifacts_dir(root: Path, project: str) -> Path:
    pattern = root / ".cache" / "build" / project / "*" / "artifacts"
    candidates = sorted(Path(p) for p in glob.glob(str(pattern)))
    assert candidates
    return candidates[-1]


def _format_rules(rules: list[str]) -> str:
    if not rules:
        return ""
    if len(rules) == 1:
        return rules[0]
    return " \\\n ".join(rules)


def _set_project_config(root: Path, project: str, updates: dict[str, str]) -> None:
    ini_path = root / "projects" / "boardA" / "boardA.ini"
    lines = ini_path.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    in_section = False
    pending = dict(updates)
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            if in_section and pending:
                for key, value in pending.items():
                    updated.append(f"{key} = {value}")
                pending.clear()
            in_section = line.strip("[]") == project
            updated.append(line)
            continue

        if in_section:
            replaced = False
            for key in list(pending.keys()):
                if line.replace(" ", "").startswith(f"{key}="):
                    updated.append(f"{key} = {pending.pop(key)}")
                    replaced = True
                    break
            if replaced:
                continue

        updated.append(line)

    if in_section and pending:
        for key, value in pending.items():
            updated.append(f"{key} = {value}")

    ini_path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def test_artifact_001_fixed_path_rule(workspace_a: Path) -> None:
    out_dir = workspace_a / "out" / "bin"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "app.bin").write_text("bin", encoding="utf-8")

    rules = _format_rules(["path:out/bin/app.bin:bin/"])
    _set_project_config(workspace_a, "projA", {"PROJECT_BUILD_ARTIFACTS": rules})

    result = run_cli(["project_build", "projA"], cwd=workspace_a, check=False)
    assert result.returncode == 0

    artifacts_dir = _latest_artifacts_dir(workspace_a, "projA")
    assert (artifacts_dir / "bin" / "app.bin").exists()


def test_artifact_002_glob_rule(workspace_a: Path) -> None:
    out_dir = workspace_a / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "alpha.whl").write_text("a", encoding="utf-8")
    (out_dir / "beta.whl").write_text("b", encoding="utf-8")

    rules = _format_rules(["glob:out/*.whl:wheels/"])
    _set_project_config(workspace_a, "projA", {"PROJECT_BUILD_ARTIFACTS": rules})

    result = run_cli(["project_build", "projA"], cwd=workspace_a, check=False)
    assert result.returncode == 0

    artifacts_dir = _latest_artifacts_dir(workspace_a, "projA")
    assert (artifacts_dir / "wheels" / "alpha.whl").exists()
    assert (artifacts_dir / "wheels" / "beta.whl").exists()


def test_artifact_003_regex_rule_with_roots(workspace_a: Path) -> None:
    logs_dir = workspace_a / "logs"
    (logs_dir / "sub").mkdir(parents=True, exist_ok=True)
    (logs_dir / "build.log").write_text("log", encoding="utf-8")
    (logs_dir / "sub" / "extra.log").write_text("log2", encoding="utf-8")

    rules = _format_rules([r"regex@logs:.*\\.log$:logs/"])
    _set_project_config(workspace_a, "projA", {"PROJECT_BUILD_ARTIFACTS": rules})

    result = run_cli(["project_build", "projA"], cwd=workspace_a, check=False)
    assert result.returncode == 0

    artifacts_dir = _latest_artifacts_dir(workspace_a, "projA")
    assert (artifacts_dir / "logs" / "build.log").exists()
    assert (artifacts_dir / "logs" / "sub" / "extra.log").exists()


def test_artifact_004_manifest_rule(workspace_a: Path) -> None:
    out_dir = workspace_a / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "artifact.txt").write_text("data", encoding="utf-8")
    logs_dir = workspace_a / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "build.log").write_text("log", encoding="utf-8")

    manifest = workspace_a / "artifacts.manifest"
    manifest.write_text("out/artifact.txt\nlogs/build.log\n", encoding="utf-8")

    rules = _format_rules(["manifest:artifacts.manifest:bundle/"])
    _set_project_config(workspace_a, "projA", {"PROJECT_BUILD_ARTIFACTS": rules})

    result = run_cli(["project_build", "projA"], cwd=workspace_a, check=False)
    assert result.returncode == 0

    artifacts_dir = _latest_artifacts_dir(workspace_a, "projA")
    assert (artifacts_dir / "bundle" / "out" / "artifact.txt").exists()
    assert (artifacts_dir / "bundle" / "logs" / "build.log").exists()


def test_artifact_005_reject_unsafe_relpaths(workspace_a: Path) -> None:
    manifest = workspace_a / "artifacts.manifest"
    manifest.write_text("../secret.txt\n", encoding="utf-8")

    rules = _format_rules(["manifest:artifacts.manifest:bundle/"])
    _set_project_config(workspace_a, "projA", {"PROJECT_BUILD_ARTIFACTS": rules})

    result = run_cli(["project_build", "projA"], cwd=workspace_a, check=False)
    assert result.returncode != 0
