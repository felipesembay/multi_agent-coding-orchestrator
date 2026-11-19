"""V2-OBS-001: Migration 5 and universal usage_records persistence."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from orchestrator import core, execution_manager as manager, execution_runner, project_store
from orchestrator.accounting.usage import record_usage, redact_raw_usage
from orchestrator.providers.base import AgentCall, InvocationResult, UsageReport
from orchestrator.providers.errors import InvocationFailure
from orchestrator.workflows.schema import FallbackBinding


def test_migration_5_creates_accounting_tables_and_enforces_constraints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_file = tmp_path / "obs001.db"
    monkeypatch.setenv("ORCH_DB", str(db_file))
    with project_store.connection() as conn:
        versions = [r[0] for r in conn.execute("SELECT version FROM platform_migrations ORDER BY version")]
        assert versions == [1, 2, 3, 4, 5]
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            if not r[0].startswith("sqlite_")
        }
        assert {
            "step_executions",
            "usage_records",
            "price_catalog_versions",
            "price_entries",
            "budgets",
            "budget_events",
        } <= tables

        # Unavailable token_source must reject non-null token counts or reported_cost_usd
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO usage_records(
                    id, run_id, role, adapter, call_index, duration_ms,
                    input_tokens, token_source, billing_mode
                ) VALUES ('c1', 'r1', 'planner', 'claude_code', 1, 10, 0, 'unavailable', 'unknown')"""
            )


def test_raw_usage_redaction_strips_secrets_and_bounds_size() -> None:
    raw = {
        "api_key": "sk-secret-value",
        "nested": {"bearer_token": "tok-123", "input_tokens": 42},
        "Authorization": "Bearer xyz",
    }
    redacted_str = redact_raw_usage(raw)
    assert "sk-secret-value" not in redacted_str
    assert "tok-123" not in redacted_str
    assert "xyz" not in redacted_str
    parsed = json.loads(redacted_str)
    assert parsed["api_key"] == "[REDACTED]"
    assert parsed["nested"]["bearer_token"] == "[REDACTED]"
    assert parsed["nested"]["input_tokens"] == 42

    huge = {"blob": "x" * 500, "items": [f"item-{i}-" + "y" * 200 for i in range(60)]}
    truncated_str = redact_raw_usage(huge)
    assert len(truncated_str.encode("utf-8")) <= 8192
    assert json.loads(truncated_str) == {"_truncated": True}


def test_every_legacy_call_and_fallback_records_usage_including_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCH_DB", str(tmp_path / "events.db"))
    for key in ("ORCH_PLANNER", "ORCH_IMPLEMENTER", "ORCH_PLANNER_MODEL", "ORCH_IMPLEMENTER_MODEL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ORCH_TEST_COMMAND", "pytest")
    monkeypatch.setattr(core.shutil, "which", lambda name, **kwargs: "/mock/" + name)

    plan_json = json.dumps(
        {"tasks": [{"id": "T1", "title": "Task", "instructions": "Do", "acceptance": ["ok"]}]}
    )
    agy_plan = json.dumps({"status": "SUCCESS", "response": plan_json})
    agent_responses = [
        SimpleNamespace(returncode=1, stdout="", stderr="usage limit reached"),
        SimpleNamespace(returncode=0, stdout=agy_plan, stderr=""),
        SimpleNamespace(returncode=0, stdout="implemented", stderr=""),
        SimpleNamespace(returncode=0, stdout='{"approved":true,"findings":[]}', stderr=""),
    ]

    def run(argv, **kwargs):
        if argv[0] in ("claude", "agy", "codex"):
            return agent_responses.pop(0)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    runner = Mock(side_effect=run)
    monkeypatch.setattr(core.subprocess, "run", runner)

    state: core.State = {
        "run_id": "run-0123456789ab",
        "worktree": str(tmp_path),
        "scope": "Build feature",
        "managed": True,
    }
    state.update(core.plan(state))
    state.update(core.implement(state))
    state.update(core.review(state))

    with project_store.connection() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM usage_records WHERE run_id=? ORDER BY call_index ASC",
                (state["run_id"],),
            ).fetchall()
        ]

    assert len(rows) == 4
    assert [r["call_index"] for r in rows] == [1, 2, 3, 4]
    assert [r["adapter"] for r in rows] == ["claude_code", "antigravity", "claude_code", "codex_cli"]
    assert [r["role"] for r in rows] == ["planner", "planner", "implementer", "reviewer"]
    assert [r["error_kind"] for r in rows] == ["quota_exhausted", None, None, None]
    assert rows[0]["retry_of"] is None
    assert rows[1]["retry_of"] == rows[0]["id"]
    assert all(r["token_source"] == "unavailable" for r in rows)
    assert all(r["input_tokens"] is None and r["output_tokens"] is None for r in rows)
    assert all(r["reported_cost_usd"] is None and r["estimated_cost_usd"] is None for r in rows)


def test_workflow_fallback_populates_usage_records_table_without_duplicates(
    managed_case, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection, registry, _, project, request, worker, _ = managed_case
    original_get = registry.get
    manifest = original_get("fake").manifest.model_copy(
        update={"adapter": "backup", "billing_mode": "api_metered"}
    )

    def backup_invoke(req):
        return InvocationResult(
            text=json.dumps(
                {"tasks": [{"id": "T1", "title": "Write", "instructions": "Write", "acceptance": ["done"]}]}
            ),
            model_reported="provider/model-v1",
            usage=UsageReport(
                input_tokens=120,
                output_tokens=45,
                reported_cost_usd=0.0025,
                source="provider_reported",
                raw={"api_key": "super-secret-key", "prompt_tokens": 120},
            ),
        )

    def get(adapter: str):
        if adapter == "fake":
            provider = original_get(adapter)
            orig_invoke = provider.invoke

            def primary_invoke(req):
                if req.role == "planner":
                    raise InvocationFailure("quota_exhausted", safe_to_retry=True)
                return orig_invoke(req)

            provider.invoke = primary_invoke
            return provider
        return SimpleNamespace(manifest=manifest, invoke=backup_invoke)

    registry.get = get
    with project_store.connection() as conn:
        conn.execute(
            "INSERT INTO provider_configs(id,kind,adapter,display_name,enabled) VALUES('backup-cfg','agent_runtime','backup','Backup',1)"
        )
        conn.commit()

    selection.bindings["plan"].fallbacks = [
        FallbackBinding(provider_config_id="backup-cfg", model="frozen-backup", on=["quota_exhausted"])
    ]
    _, digest = manager.configuration(project, workflow=selection, provider_registry=registry)
    response = manager.submit(
        project["id"],
        request["id"],
        manager.StartInput(
            confirmed=True, configuration_digest=digest, idempotency_key="obs001-workflow-0001"
        ),
        workflow=selection,
        provider_registry=registry,
    )
    run_id = response["run_id"]
    worker.claim()
    row = manager.get_managed(run_id)
    monkeypatch.setenv("ORCH_DISPATCH_TOKEN", row["dispatch_token"])
    monkeypatch.setenv("ORCH_WORKER_ID", worker.id)
    with project_store.connection() as conn:
        conn.execute("UPDATE managed_runs SET pid=? WHERE run_id=?", (12345, run_id))
        conn.commit()
    monkeypatch.setattr("os.getpid", lambda: 12345)

    assert execution_runner.run(run_id, provider_registry=registry) == 0

    with project_store.connection() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM usage_records WHERE run_id=? ORDER BY call_index ASC", (run_id,)
            ).fetchall()
        ]

    # 1 failed primary plan + 1 backup plan + 1 impl + 1 review = 4 records
    assert len(rows) == 4
    assert all(r["project_id"] == project["id"] for r in rows)
    assert rows[0]["role"] == "planner" and rows[0]["error_kind"] == "quota_exhausted"
    assert rows[0]["token_source"] == "unavailable" and rows[0]["input_tokens"] is None
    assert rows[1]["role"] == "planner" and rows[1]["retry_of"] == rows[0]["id"]
    assert rows[1]["token_source"] == "provider_reported"
    assert rows[1]["billing_mode"] == "api_metered"
    assert rows[1]["input_tokens"] == 120 and rows[1]["output_tokens"] == 45
    assert rows[1]["reported_cost_usd"] == 0.0025
    assert rows[1]["model"] == "provider/model-v1"
    assert "super-secret-key" not in rows[1]["raw_usage"]
    assert json.loads(rows[1]["raw_usage"])["api_key"] == "[REDACTED]"

    # Re-recording with same call_id is idempotent and does not duplicate
    dup_call = AgentCall(
        call_id=rows[1]["id"],
        provider="backup",
        role="planner",
        duration_ms=10,
    )
    record_usage(run_id=run_id, call=dup_call)
    with project_store.connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM usage_records WHERE run_id=?", (run_id,)).fetchone()[0]
    assert count == 4
