from pathlib import Path


def test_requirements_include_textual_and_not_questionary():
    requirements = Path("requirements.txt").read_text(encoding="utf-8").splitlines()

    normalized = {line.strip() for line in requirements if line.strip() and not line.lstrip().startswith("#")}

    assert "textual>=0.61.0" in normalized
    assert "rich>=13.7.0" in normalized
    assert all("questionary" not in line for line in normalized)
