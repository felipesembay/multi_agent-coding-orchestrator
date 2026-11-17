"""The documentation gate must reject broken handoffs, independently of this repo."""
import subprocess

import pytest

from scripts.check_docs import check_docs


@pytest.fixture
def repository(tmp_path):
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True)

    git("init")
    (tmp_path / "orchestrator").mkdir()
    (tmp_path / "orchestrator/core.py").write_text("# fixture\n")
    git("add", ".")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "fixture")
    commit_date = git("log", "-1", "--format=%cs").stdout.strip()
    (tmp_path / "docs/planning").mkdir(parents=True)
    (tmp_path / "docs/handoff").mkdir()
    (tmp_path / "docs/planning/BACKLOG.md").write_text("| V2-DOC-001 | Fixture |\n")
    (tmp_path / "docs/handoff/CURRENT_STATE.md").write_text("Atualizado: {}\n".format(commit_date))
    (tmp_path / "README.md").write_text("[Backlog](docs/planning/BACKLOG.md) V2-DOC-001\n")
    return tmp_path


def test_valid_links_ids_and_date(repository):
    (repository / "docs/page.md").write_text("# Visão geral\n# Visão geral\n")
    (repository / "README.md").write_text(
        "[Page](docs/page.md#visão-geral) [Duplicate](docs/page.md#visão-geral-1)\n"
        "[Web](https://example.invalid/absent) ` [Example](absent) `\n"
        "```markdown\n[Example](absent)\n```\n"
    )
    assert check_docs(repository) == []


@pytest.mark.parametrize("content,expected", [
    ("[Absent](missing.md)", "link quebrado"),
    ("[Anchor](docs/planning/BACKLOG.md#missing)", "âncora inexistente"),
    ("V2-DOC-999", "ID desconhecido V2-DOC-999"),
])
def test_rejects_broken_documentation(repository, content, expected):
    (repository / "README.md").write_text(content)
    assert any(expected in error for error in check_docs(repository))


@pytest.mark.parametrize("date_text", ["2000-01-01", "2026-99-99", "missing"])
def test_rejects_stale_or_invalid_handoff(repository, date_text):
    (repository / "docs/handoff/CURRENT_STATE.md").write_text("Atualizado: " + date_text)
    assert any("data" in error for error in check_docs(repository))


def test_reports_missing_required_files(repository):
    (repository / "docs/handoff/CURRENT_STATE.md").unlink()
    assert any("obrigatório ausente" in error for error in check_docs(repository))
    (repository / "docs/planning/BACKLOG.md").unlink()
    assert any("BACKLOG.md" in error for error in check_docs(repository))


def test_reference_links_and_parentheses(repository):
    (repository / "docs/page(1).md").write_text("# Page\n")
    (repository / "README.md").write_text(
        '[Inline](docs/page(1).md)\n[Reference][page]\n\n'
        '[page]: <docs/page(1).md> "Title"\n'
    )
    assert check_docs(repository) == []
    (repository / "README.md").write_text('[Broken][page]\n\n[page]: missing.md\n')
    assert any("link quebrado missing.md" in error for error in check_docs(repository))
