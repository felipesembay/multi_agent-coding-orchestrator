"""V2-RES-001: Step execution ledger and Git worktree tree digest."""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3

import pytest

from orchestrator import core, execution_manager as manager, execution_runner
from orchestrator.project_store import connection
from orchestrator.resilience import (
    StepLedger,
    complete_step_execution,
    compute_tree_digest,
    current_git_head,
    fail_step_execution,
    list_step_executions,
    start_step_execution,
)


def _init_git_repo(repo_dir: Path) -> None:
    from orchestrator import projects

    repo_dir.mkdir(parents=True, exist_ok=True)
    projects.git(repo_dir, "init", "--template=")
    (repo_dir / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    projects.git(repo_dir, "add", "--", "README.md")
    projects.git(repo_dir, "commit", "-m", "initial")


def test_tree_digest_detects_tracked_edits_and_untracked_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    head = current_git_head(repo)
    assert head is not None and len(head) == 40

    clean_digest = compute_tree_digest(repo)
    assert clean_digest is not None and len(clean_digest) == 64
    assert compute_tree_digest(repo) == clean_digest

    # Modify tracked file
    (repo / "README.md").write_text("# Modified\n", encoding="utf-8")
    modified_digest = compute_tree_digest(repo)
    assert modified_digest != clean_digest

    # Add untracked file
    untracked = repo / "new_file.py"
    untracked.write_text("x = 1\n", encoding="utf-8")
    untracked_digest_1 = compute_tree_digest(repo)
    assert untracked_digest_1 not in (clean_digest, modified_digest)

    # Modify untracked file content -> digest must change
    untracked.write_text("x = 2\n", encoding="utf-8")
    untracked_digest_2 = compute_tree_digest(repo)
    assert untracked_digest_2 != untracked_digest_1


def test_step_ledger_lifecycle_and_idempotency_key_uniqueness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCH_DB", str(tmp_path / "events.db"))
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    ledger = StepLedger()
    step_id = ledger.start(
        run_id="run-0123456789ab",
        node="impl",
        worktree=str(repo),
        task_id="T1",
        attempt=1,
        role="implementer",
        side_effects="worktree_write",
    )

    rows = list_step_executions("run-0123456789ab")
    assert len(rows) == 1
    assert rows[0]["id"] == step_id
    assert rows[0]["status"] == "started"
    assert rows[0]["idempotency_key"] == "run-0123456789ab:impl:T1:1"
    assert rows[0]["git_head_before"] is not None
    assert rows[0]["tree_digest_before"] is not None
    assert rows[0]["tree_digest_after"] is None

    # Duplicate (run_id, node, task_id, attempt) must fail closed on UNIQUE constraint
    with pytest.raises(sqlite3.IntegrityError):
        start_step_execution(
            run_id="run-0123456789ab",
            node="impl",
            task_id="T1",
            attempt=1,
            role="implementer",
            side_effects="worktree_write",
        )

    # Mutate worktree and complete
    (repo / "feature.py").write_text("print('ok')\n", encoding="utf-8")
    ledger.complete(step_id, worktree=str(repo))

    after = list_step_executions("run-0123456789ab")[0]
    assert after["status"] == "completed"
    assert after["tree_digest_after"] is not None
    assert after["tree_digest_after"] != after["tree_digest_before"]
    assert after["finished_at"] is not None

    # Completing an already completed step must fail
    with pytest.raises(ValueError, match="Open step_execution not found"):
        complete_step_execution(step_id)


def test_step_ledger_records_failed_and_needs_inspection_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCH_DB", str(tmp_path / "events.db"))
    s1 = start_step_execution(
        run_id="run-fail", node="impl", task_id="T1", attempt=1, side_effects="worktree_write"
    )
    fail_step_execution(s1, error="agent crashed", status="needs_inspection")
    row = list_step_executions("run-fail")[0]
    assert row["status"] == "needs_inspection"
    assert row["error"] == "agent crashed"


def test_workflow_execution_records_step_executions_and_links_usage_records(
    managed_case, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection, registry, _, project, request, worker, _ = managed_case
    _, digest = manager.configuration(project, workflow=selection, provider_registry=registry)
    response = manager.submit(
        project["id"],
        request["id"],
        manager.StartInput(
            confirmed=True, configuration_digest=digest, idempotency_key="res001-ledger-0001"
        ),
        workflow=selection,
        provider_registry=registry,
    )
    run_id = response["run_id"]
    worker.claim()
    row = manager.get_managed(run_id)
    monkeypatch.setenv("ORCH_DISPATCH_TOKEN", row["dispatch_token"])
    monkeypatch.setenv("ORCH_WORKER_ID", worker.id)
    with connection() as conn:
        conn.execute("UPDATE managed_runs SET pid=? WHERE run_id=?", (os.getpid(), run_id))
        conn.commit()

    assert execution_runner.run(run_id, provider_registry=registry) == 0

    steps = list_step_executions(run_id)
    assert [s["node"] for s in steps] == ["plan", "impl", "tests", "review"]
    assert [s["status"] for s in steps] == ["completed", "completed", "completed", "completed"]
    assert [s["side_effects"] for s in steps] == ["none", "worktree_write", "exec", "none"]
    assert all(s["git_head_before"] and s["tree_digest_before"] and s["tree_digest_after"] for s in steps)
    # impl modified the worktree, so tree_digest_after differs from tree_digest_before
    impl_step = steps[1]
    assert impl_step["tree_digest_after"] != impl_step["tree_digest_before"]

    with connection() as conn:
        usage_rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM usage_records WHERE run_id=? ORDER BY call_index ASC", (run_id,)
            ).fetchall()
        ]
    assert len(usage_rows) == 3
    assert [u["step_execution_id"] for u in usage_rows] == [steps[0]["id"], steps[1]["id"], steps[3]["id"]]
