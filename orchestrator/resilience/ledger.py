"""Step execution ledger before/after workflow nodes (V2-RES-001 / ADR-0007).

Records `started` (with git_head_before and tree_digest_before) before invoking a
node and `completed` or `failed` (with tree_digest_after) when the node finishes.
Does not implement automatic resume (which belongs to V2-RES-002/003).
"""
from __future__ import annotations

from typing import Literal, Optional
import uuid

from ..project_store import connection

SideEffectKind = Literal["none", "worktree_write", "exec"]
StepStatusKind = Literal["started", "completed", "failed", "needs_inspection", "skipped"]


def format_step_idempotency_key(
    run_id: str,
    node: str,
    task_id: Optional[str],
    attempt: int,
) -> str:
    task_part = task_id if task_id is not None else "global"
    return f"{run_id}:{node}:{task_part}:{attempt}"


def next_step_attempt(
    run_id: str,
    node: str,
    task_id: Optional[str] = None,
) -> int:
    with connection() as conn:
        row = conn.execute(
            """SELECT COALESCE(MAX(attempt), 0) + 1
               FROM step_executions
               WHERE run_id=? AND node=? AND COALESCE(task_id, '')=COALESCE(?, '')""",
            (run_id, node, task_id),
        ).fetchone()
    return int(row[0]) if row is not None else 1


def classify_side_effects(
    *,
    stage_type: str,
    permission: Optional[str] = None,
    adapter: Optional[str] = None,
) -> SideEffectKind:
    if stage_type == "test":
        return "exec"
    if permission == "workspace_write":
        if adapter == "codex_cli":
            return "exec"
        return "worktree_write"
    return "none"


def start_step_execution(
    *,
    run_id: str,
    node: str,
    attempt: int = 1,
    task_id: Optional[str] = None,
    role: Optional[str] = None,
    side_effects: SideEffectKind = "none",
    git_head_before: Optional[str] = None,
    tree_digest_before: Optional[str] = None,
    step_execution_id: Optional[str] = None,
) -> str:
    if attempt < 1:
        raise ValueError("Step execution attempt must be >= 1")
    if side_effects not in ("none", "worktree_write", "exec"):
        raise ValueError(f"Invalid side_effects classification: {side_effects}")
    record_id = step_execution_id or f"step-{uuid.uuid4().hex[:16]}"
    idem_key = format_step_idempotency_key(run_id, node, task_id, attempt)

    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """INSERT INTO step_executions(
                id, run_id, node, task_id, attempt, role, idempotency_key,
                status, side_effects, git_head_before, tree_digest_before
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'started', ?, ?, ?)""",
            (
                record_id,
                run_id,
                node,
                task_id,
                attempt,
                role,
                idem_key,
                side_effects,
                git_head_before,
                tree_digest_before,
            ),
        )
        conn.commit()
    return record_id


def complete_step_execution(
    step_execution_id: str,
    *,
    tree_digest_after: Optional[str] = None,
) -> None:
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """UPDATE step_executions
               SET status='completed',
                   tree_digest_after=?,
                   finished_at=CURRENT_TIMESTAMP
               WHERE id=? AND status='started'""",
            (tree_digest_after, step_execution_id),
        )
        if cursor.rowcount == 0:
            conn.rollback()
            raise ValueError(f"Open step_execution not found: {step_execution_id}")
        conn.commit()


def fail_step_execution(
    step_execution_id: str,
    *,
    error: str,
    tree_digest_after: Optional[str] = None,
    status: Literal["failed", "needs_inspection"] = "failed",
) -> None:
    if status not in ("failed", "needs_inspection"):
        raise ValueError(f"Invalid failure status: {status}")
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """UPDATE step_executions
               SET status=?,
                   tree_digest_after=?,
                   error=?,
                   finished_at=CURRENT_TIMESTAMP
               WHERE id=? AND status='started'""",
            (status, tree_digest_after, (error or "")[:2500], step_execution_id),
        )
        if cursor.rowcount == 0:
            conn.rollback()
            raise ValueError(f"Open step_execution not found: {step_execution_id}")
        conn.commit()


def list_step_executions(run_id: str) -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM step_executions WHERE run_id=? ORDER BY rowid ASC",
            (run_id,),
        ).fetchall()
    return [dict(r) for r in rows]


class StepLedger:
    """Convenience helper tying worktree digest calculation to step_executions rows."""

    def __init__(self, *, digest_fn=None, head_fn=None) -> None:
        from .digest import compute_tree_digest, current_git_head

        self._digest_fn = digest_fn or compute_tree_digest
        self._head_fn = head_fn or current_git_head

    def start(
        self,
        *,
        run_id: str,
        node: str,
        worktree: Optional[str] = None,
        task_id: Optional[str] = None,
        attempt: int = 1,
        role: Optional[str] = None,
        side_effects: SideEffectKind = "none",
    ) -> str:
        git_head = self._head_fn(worktree) if worktree else None
        digest_before = self._digest_fn(worktree) if worktree else None
        return start_step_execution(
            run_id=run_id,
            node=node,
            task_id=task_id,
            attempt=attempt,
            role=role,
            side_effects=side_effects,
            git_head_before=git_head,
            tree_digest_before=digest_before,
        )

    def complete(self, step_execution_id: str, *, worktree: Optional[str] = None) -> None:
        digest_after = self._digest_fn(worktree) if worktree else None
        complete_step_execution(step_execution_id, tree_digest_after=digest_after)

    def fail(
        self,
        step_execution_id: str,
        *,
        error: str,
        worktree: Optional[str] = None,
        status: Literal["failed", "needs_inspection"] = "failed",
    ) -> None:
        digest_after = self._digest_fn(worktree) if worktree else None
        fail_step_execution(
            step_execution_id,
            error=error,
            tree_digest_after=digest_after,
            status=status,
        )
