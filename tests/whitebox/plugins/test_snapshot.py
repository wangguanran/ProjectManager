"""
Tests for snapshot plugin operations.
"""

import json
import os
import subprocess
import sys


class TestSnapshot:
    def setup_method(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.plugins.snapshot import snapshot_create, snapshot_validate

        self.snapshot_create = snapshot_create
        self.snapshot_validate = snapshot_validate

    def test_snapshot_create_is_deterministic(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)

        subprocess.run(
            ["git", "init"], cwd=str(tmp_path), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=str(tmp_path),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=str(tmp_path),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        (tmp_path / "a.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "a.txt"], cwd=str(tmp_path), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        subprocess.run(
            ["git", "commit", "-m", "base"],
            cwd=str(tmp_path),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        projects_root = tmp_path / "projects"
        projects_root.mkdir(parents=True, exist_ok=True)
        env = {
            "root_path": str(tmp_path),
            "projects_path": str(projects_root),
            "repositories": [(str(tmp_path), "root")],
        }
        projects_info = {
            "projA": {
                "board_name": "boardA",
                "config": {"PROJECT_PO_CONFIG": "po1 po2 -po3"},
            }
        }

        assert self.snapshot_create(env, projects_info, "projA") is True
        out1 = capsys.readouterr().out
        assert self.snapshot_create(env, projects_info, "projA") is True
        out2 = capsys.readouterr().out

        assert out1 == out2
        payload = json.loads(out1)
        assert payload["schema_version"] == 1
        assert payload["project_name"] == "projA"
        assert payload["pos"] == ["po1", "po2"]
        assert payload["repositories"][0]["name"] == "root"
        assert payload["repositories"][0]["path"] == "."
        assert len(payload["repositories"][0]["head"]) == 40

    def test_snapshot_validate_detects_repo_head_drift(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)

        subprocess.run(["git", "init"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), check=True)

        (tmp_path / "a.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "a.txt"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=str(tmp_path), check=True)

        projects_root = tmp_path / "projects"
        projects_root.mkdir(parents=True, exist_ok=True)
        env = {
            "root_path": str(tmp_path),
            "projects_path": str(projects_root),
            "repositories": [(str(tmp_path), "root")],
        }
        projects_info = {
            "projA": {
                "board_name": "boardA",
                "config": {"PROJECT_PO_CONFIG": "po1"},
            }
        }

        snap_path = tmp_path / "snapshot.json"
        assert self.snapshot_create(env, projects_info, "projA", out=str(snap_path)) is True
        assert snap_path.is_file()

        # Move HEAD forward.
        (tmp_path / "a.txt").write_text("base\nchange\n", encoding="utf-8")
        subprocess.run(["git", "add", "a.txt"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "commit", "-m", "change"], cwd=str(tmp_path), check=True)

        result = self.snapshot_validate(env, projects_info, str(snap_path), json=True)
        assert result is False
        report = json.loads(capsys.readouterr().out)
        assert report["operation"] == "snapshot_validate"
        assert report["status"] == "drift"
        assert any(item.get("status") == "head_mismatch" for item in report["drift"]["repos"])
