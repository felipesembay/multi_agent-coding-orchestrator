import json
import sys
from unittest.mock import patch

import pytest

from orchestrator.cli import main


@pytest.mark.parametrize(
    "status, expected_exit",
    [
        ("ready_for_human_review", 0),
        ("blocked", 1),
        ("running", 1),
    ],
)
def test_run_exit_code(status, expected_exit, monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["orchestrator", "run", "--repo", "/tmp/demo", "--scope", "/tmp/scope.md"],
    )

    result = {
        "run_id": "run-test",
        "status": status,
        "worktree": "/tmp/demo-worktree",
        "task_index": 0,
        "review": {},
    }

    with patch("orchestrator.cli.execute", return_value=result):
        if expected_exit:
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == expected_exit
        else:
            main()

    output = json.loads(capsys.readouterr().out)
    assert output["status"] == status


def test_resume_blocked_exit_code(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["orchestrator", "resume", "--run-id", "run-test"],
    )

    with patch(
        "orchestrator.cli.resume",
        return_value={"run_id": "run-test", "status": "blocked"},
    ):
        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 1
