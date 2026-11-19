"""Persist per-call usage_records with redacted raw telemetry and call_id deduplication.

Follows ADR-0006 and TOKEN_ACCOUNTING.md:
- Unavailable usage keeps token counts and costs as NULL (never 0).
- Integrates with V2-WF-010 by using call_id as usage_records.id and preserving retry_of.
- Redacts sensitive keys and truncates raw_usage to <= 8192 bytes (RNF4).
"""
from __future__ import annotations

import json
import re
from datetime import datetime,timezone
from typing import Any, Optional

from ..project_store import connection
from ..providers.base import AgentCall

_SENSITIVE_KEY_RE = re.compile(
    r"(^|_|-)(key|token|secret|password|credential|authorization|cookie|bearer)(_|-|$)",
    re.I,
)
_MAX_RAW_BYTES = 8192


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            key_str = str(k)
            if _SENSITIVE_KEY_RE.search(key_str):
                result[key_str] = "[REDACTED]"
            else:
                result[key_str] = _redact_value(v)
        return result
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    text = str(value)
    return text[:512]


def redact_raw_usage(raw: Optional[dict]) -> str:
    if not isinstance(raw, dict) or not raw:
        return "{}"
    cleaned = _redact_value(raw)
    serialized = json.dumps(cleaned, ensure_ascii=False, sort_keys=True)
    if len(serialized.encode("utf-8")) <= _MAX_RAW_BYTES:
        return serialized
    return json.dumps({"_truncated": True}, ensure_ascii=False)


def record_usage(
    *,
    run_id: str,
    call: AgentCall,
    billing_mode: Optional[str] = None,
    provider_config_id: Optional[str] = None,
    step_execution_id: Optional[str] = None,
    project_id: Optional[str] = None,
    retry_of: Optional[str] = None,
    estimated_cost_usd: Optional[float] = None,
    price_entry_id: Optional[str] = None,
    currency: str = "USD",
) -> None:
    if not run_id:
        return
    effective_billing = billing_mode or call.billing_mode or "unknown"
    effective_model = call.model_reported if call.model_reported is not None else call.model
    raw_json = redact_raw_usage(call.usage.raw)
    from .pricing import estimate_for_call,timestamp
    call_start=call.started_at if call.started_at is not None else datetime.now(timezone.utc)
    started_at=timestamp(call_start)

    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT 1 FROM usage_records WHERE id=?", (call.call_id,)
        ).fetchone()
        if existing is not None:
            conn.commit()
            return
        if estimated_cost_usd is None and price_entry_id is None and currency=='USD':
            estimated_cost_usd,price_entry_id=estimate_for_call(call,billing_mode=effective_billing,at=call_start,conn=conn)
        resolved_project = project_id
        if resolved_project is None:
            row = conn.execute(
                "SELECT project_id FROM managed_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if row is not None:
                resolved_project = row["project_id"]
        next_idx_row = conn.execute(
            "SELECT COALESCE(MAX(call_index), 0) + 1 FROM usage_records WHERE run_id=?",
            (run_id,),
        ).fetchone()
        call_index = int(next_idx_row[0]) if next_idx_row is not None else 1

        conn.execute(
            """INSERT INTO usage_records(
                id, run_id, step_execution_id, project_id, role, provider_config_id,
                adapter, model, call_index, duration_ms, input_tokens, output_tokens,
                cache_read_tokens, cache_write_tokens, reasoning_tokens, token_source,
                billing_mode, reported_cost_usd, estimated_cost_usd, price_entry_id,
                currency, error_kind, retry_of, raw_usage, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                call.call_id,
                run_id,
                step_execution_id,
                resolved_project,
                call.role,
                provider_config_id,
                call.provider,
                effective_model,
                call_index,
                call.duration_ms,
                call.usage.input_tokens,
                call.usage.output_tokens,
                call.usage.cache_read_tokens,
                call.usage.cache_write_tokens,
                call.usage.reasoning_tokens,
                call.usage.source,
                effective_billing,
                call.usage.reported_cost_usd,
                estimated_cost_usd,
                price_entry_id,
                currency,
                call.error_code,
                retry_of,
                raw_json,
                started_at,
            ),
        )
        conn.commit()
