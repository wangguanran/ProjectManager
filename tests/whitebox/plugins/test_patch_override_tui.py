import builtins


def test_prepare_po_textual_selection_maps_selected_files(monkeypatch, tmp_path):
    from src.plugins.patch_override import prepare_po_textual_selection

    projects_root = tmp_path / "projects"
    (projects_root / "boardA" / "po").mkdir(parents=True)

    env = {
        "projects_path": str(projects_root),
        "repositories": [(str(tmp_path / "repo1"), "repo1")],
    }
    projects_info = {
        "projA": {
            "board_name": "boardA",
            "board_path": "unused",
            "config": {},
        }
    }
    modified_files = [
        ("repo1", "alpha.txt", "M  (working)"),
        ("repo1", "beta.txt", "D  (deleted)"),
    ]

    monkeypatch.setattr("src.plugins.patch_override._scan_po_modified_files", lambda *_args, **_kwargs: modified_files)
    monkeypatch.setattr(
        "src.execution_textual.run_po_selection_dialog",
        lambda **_kwargs: {"status": "apply", "action": "remove", "selected_indexes": [1]},
    )

    result = prepare_po_textual_selection(env, projects_info, "projA", "po_tui", update_mode=True)

    assert result is not None
    assert result["status"] == "apply"
    assert result["action"] == "remove"
    assert result["selected_files"] == [modified_files[1]]
    assert result["po_path"].endswith("boardA/po/po_tui")


def test_po_new_consumes_preselected_skip_without_prompt(monkeypatch, tmp_path, capsys):
    from src.plugins.patch_override import po_new

    def _unexpected_input(_prompt=""):
        raise AssertionError("po_new should not prompt when a textual preselection is present")

    monkeypatch.setattr(builtins, "input", _unexpected_input)

    projects_root = tmp_path / "projects"
    (projects_root / "boardA").mkdir(parents=True)

    env = {
        "projects_path": str(projects_root),
        "repositories": [],
        "po_textual_selection": {
            "project_name": "projA",
            "po_name": "po_tui",
            "po_path": str(projects_root / "boardA" / "po" / "po_tui"),
            "status": "skip",
            "message": "Skipped selected files.",
        },
    }
    projects_info = {
        "projA": {
            "board_name": "boardA",
            "board_path": "unused",
            "config": {},
        }
    }

    assert po_new(env, projects_info, "projA", "po_tui") is True
    assert "Skipped selected files." in capsys.readouterr().out
    assert not (projects_root / "boardA" / "po" / "po_tui").exists()


def test_prepare_po_textual_selection_returns_noop_when_no_files(monkeypatch, tmp_path):
    from src.plugins.patch_override import prepare_po_textual_selection

    projects_root = tmp_path / "projects"
    (projects_root / "boardA" / "po").mkdir(parents=True)

    env = {
        "projects_path": str(projects_root),
        "repositories": [(str(tmp_path / "repo1"), "repo1")],
    }
    projects_info = {
        "projA": {
            "board_name": "boardA",
            "board_path": "unused",
            "config": {},
        }
    }

    monkeypatch.setattr("src.plugins.patch_override._scan_po_modified_files", lambda *_args, **_kwargs: [])

    result = prepare_po_textual_selection(env, projects_info, "projA", "po_empty")

    assert result is not None
    assert result["status"] == "noop"
    assert result["message"] == "No modified files found in any repository."
