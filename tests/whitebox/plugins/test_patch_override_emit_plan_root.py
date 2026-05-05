from src.plugins.patch_override import build_po_apply_plan, build_po_revert_plan


def _project_info(project_name: str, board_name: str, po_name: str) -> dict:
    return {project_name: {"board_name": board_name, "config": {"PROJECT_PO_CONFIG": po_name}}}


def _write_override(projects_path, board_name: str, po_name: str, rel_path: str) -> None:
    target = projects_path / board_name / "po" / po_name / "overrides" / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("override\n", encoding="utf-8")


def _actions_by_repo(plan: dict) -> dict:
    return {entry["repo"]: entry["actions"] for entry in plan["per_repo_actions"]}


def test_po_apply_emit_plan_keeps_root_actions_with_child_repositories(tmp_path, monkeypatch):
    workspace = tmp_path
    projects_path = workspace / "projects"
    repo1 = workspace / "repo1"
    repo1.mkdir()

    board_name = "board"
    po_name = "po1"
    project_name = "proj"
    _write_override(projects_path, board_name, po_name, "root.txt")
    _write_override(projects_path, board_name, po_name, "repo1/child.txt")

    monkeypatch.chdir(workspace)
    plan = build_po_apply_plan(
        {
            "projects_path": str(projects_path),
            "repositories": [(str(repo1), "repo1")],
            "po_configs": {},
        },
        _project_info(project_name, board_name, po_name),
        project_name,
    )

    actions = _actions_by_repo(plan)
    assert list(actions) == ["repo1", "root"]
    assert actions["repo1"][0]["path_in_repo"] == "child.txt"
    assert actions["root"][0]["path_in_repo"] == "root.txt"


def test_po_revert_emit_plan_keeps_root_actions_with_child_repositories(tmp_path, monkeypatch):
    workspace = tmp_path
    projects_path = workspace / "projects"
    repo1 = workspace / "repo1"
    repo1.mkdir()

    board_name = "board"
    po_name = "po1"
    project_name = "proj"
    _write_override(projects_path, board_name, po_name, "root.txt")
    _write_override(projects_path, board_name, po_name, "repo1/child.txt")

    monkeypatch.chdir(workspace)
    plan = build_po_revert_plan(
        {
            "projects_path": str(projects_path),
            "repositories": [(str(repo1), "repo1")],
            "po_configs": {},
        },
        _project_info(project_name, board_name, po_name),
        project_name,
    )

    actions = _actions_by_repo(plan)
    assert list(actions) == ["repo1", "root"]
    assert actions["repo1"][0]["path_in_repo"] == "child.txt"
    assert actions["root"][0]["path_in_repo"] == "root.txt"


def test_emit_plan_omits_empty_root_entry_with_child_repositories(tmp_path, monkeypatch):
    workspace = tmp_path
    projects_path = workspace / "projects"
    repo1 = workspace / "repo1"
    repo1.mkdir()

    board_name = "board"
    po_name = "po1"
    project_name = "proj"
    _write_override(projects_path, board_name, po_name, "repo1/child.txt")

    monkeypatch.chdir(workspace)
    plan = build_po_apply_plan(
        {
            "projects_path": str(projects_path),
            "repositories": [(str(repo1), "repo1")],
            "po_configs": {},
        },
        _project_info(project_name, board_name, po_name),
        project_name,
    )

    assert [entry["repo"] for entry in plan["per_repo_actions"]] == ["repo1"]
