import builtins
from types import SimpleNamespace


class _StubAsk:
    def __init__(self, value):
        self._value = value

    def ask(self):
        return self._value


class _StubQuestionary:
    def __init__(self, *, checkbox_value=None, select_value=None, confirm_value=None):
        self._checkbox_value = checkbox_value
        self._select_value = select_value
        self._confirm_value = confirm_value

    def checkbox(self, *_args, **_kwargs):
        return _StubAsk(self._checkbox_value)

    def select(self, *_args, **_kwargs):
        return _StubAsk(self._select_value)

    def confirm(self, *_args, **_kwargs):
        return _StubAsk(self._confirm_value)


def _fake_git_run_factory(*, working_file: str):
    def _run(cmd, cwd=None, capture_output=None, text=None, check=None):  # noqa: ARG001
        # Minimal subset used by po_new -> __get_modified_files.
        if cmd[:4] == ["git", "diff", "--name-only", "--cached"]:
            return SimpleNamespace(returncode=0, stdout="")
        if cmd[:4] == ["git", "ls-files", "--modified", "--others"]:
            return SimpleNamespace(returncode=0, stdout=f"{working_file}\n")
        if cmd[:3] == ["git", "ls-files", "--deleted"]:
            return SimpleNamespace(returncode=0, stdout="")
        if cmd[:3] == ["git", "status", "--porcelain"]:
            return SimpleNamespace(returncode=0, stdout=f"?? {working_file}\n")
        return SimpleNamespace(returncode=1, stdout="")

    return _run


def test_po_new_tui_skips_selected_files(monkeypatch, tmp_path, capsys):
    from src.plugins.patch_override import po_new

    # Auto-confirm creation prompt.
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "yes")

    # Provide one modified file via stubbed git commands.
    working_file = "tui_test_file.txt"
    monkeypatch.setattr(
        "src.plugins.patch_override.subprocess.run",
        _fake_git_run_factory(working_file=working_file),
    )

    # Stub TUI interactions: select the first file, then choose "skip".
    stub_q = _StubQuestionary(checkbox_value=[0], select_value="skip", confirm_value=False)
    monkeypatch.setattr("src.tui_utils.get_questionary", lambda **_kwargs: stub_q)

    projects_root = tmp_path / "projects"
    (projects_root / "boardA").mkdir(parents=True)

    repo_path = tmp_path / "repo1"
    repo_path.mkdir()

    env = {
        "projects_path": str(projects_root),
        "repositories": [(str(repo_path), "repo1")],
    }
    projects_info = {
        "projA": {
            "board_name": "boardA",
            "board_path": "unused-but-required",
            "config": {"PROJECT_PO_CONFIG": ""},
        }
    }

    assert po_new(env, projects_info, "projA", "po_tui", tui=True) is True

    out = capsys.readouterr().out
    assert "=== TUI File Selection for PO ===" in out
    assert "Skipped selected files." in out


def test_po_new_tui_errors_when_unavailable(monkeypatch, tmp_path, capsys):
    from src.plugins.patch_override import po_new
    from src.tui_utils import TuiUnavailable

    monkeypatch.setattr(builtins, "input", lambda _prompt="": "yes")

    working_file = "tui_test_file.txt"
    monkeypatch.setattr(
        "src.plugins.patch_override.subprocess.run",
        _fake_git_run_factory(working_file=working_file),
    )

    def _raise_unavailable(**_kwargs):
        raise TuiUnavailable('TUI dependency is not installed. Install it with: pip install -e ".[tui]"')

    monkeypatch.setattr("src.tui_utils.get_questionary", _raise_unavailable)

    projects_root = tmp_path / "projects"
    (projects_root / "boardA").mkdir(parents=True)

    repo_path = tmp_path / "repo1"
    repo_path.mkdir()

    env = {
        "projects_path": str(projects_root),
        "repositories": [(str(repo_path), "repo1")],
    }
    projects_info = {
        "projA": {
            "board_name": "boardA",
            "board_path": "unused-but-required",
            "config": {"PROJECT_PO_CONFIG": ""},
        }
    }

    assert po_new(env, projects_info, "projA", "po_tui", tui=True) is False

    out = capsys.readouterr().out
    assert "Install it with:" in out
