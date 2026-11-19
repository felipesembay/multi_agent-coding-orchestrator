"""V2-SEC-005: Credential store with keyring and in-memory backend; zero SQLite secret leaks."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from keyring.backends.fail import Keyring as FailKeyring
from keyring.backends.null import Keyring as NullKeyring

from orchestrator import project_store
from orchestrator.secrets import (
    CredentialStore,
    CredentialStoreError,
    InMemoryKeyringBackend,
    KeyringUnavailableError,
    bind_provider_credential,
    format_credential_ref,
    parse_credential_ref,
    remove_provider_credential,
)


def test_in_memory_keyring_crud_round_trip() -> None:
    backend = InMemoryKeyringBackend()
    store = CredentialStore(backend=backend)

    ref = store.set_credential("openrouter", "pc-or-1", "sk-or-v1-sentinel-secret-999")
    assert ref == "multi-agent-orchestrator:openrouter:pc-or-1"
    assert parse_credential_ref(ref) == ("multi-agent-orchestrator", "openrouter:pc-or-1")
    assert store.has_credential(ref) is True
    assert store.get_credential(ref) == "sk-or-v1-sentinel-secret-999"

    assert store.delete_credential(ref) is True
    assert store.get_credential(ref) is None
    assert store.has_credential(ref) is False
    assert store.delete_credential(ref) is False


@pytest.mark.parametrize("bad_backend", [FailKeyring(), NullKeyring()])
def test_fail_or_null_keyring_backend_fails_closed(bad_backend) -> None:
    store = CredentialStore(backend=bad_backend)
    with pytest.raises(KeyringUnavailableError):
        store.set_credential("openrouter", "pc-1", "sk-secret")
    with pytest.raises(KeyringUnavailableError):
        store.get_credential("multi-agent-orchestrator:openrouter:pc-1")
    with pytest.raises(KeyringUnavailableError):
        store.delete_credential("multi-agent-orchestrator:openrouter:pc-1")


def test_backend_exception_never_leaks_secret_in_error_message() -> None:
    sentinel = "sk-or-top-secret-never-leak"
    broken = InMemoryKeyringBackend()
    broken.set_password = Mock(side_effect=RuntimeError(f"DBus error while saving {sentinel}"))  # type: ignore[method-assign]
    store = CredentialStore(backend=broken)

    with pytest.raises(KeyringUnavailableError) as caught:
        store.set_credential("openrouter", "pc-1", sentinel)
    assert sentinel not in str(caught.value)


def test_invalid_inputs_and_refs_are_rejected() -> None:
    store = CredentialStore(backend=InMemoryKeyringBackend())
    with pytest.raises(CredentialStoreError):
        store.set_credential("openrouter", "pc-1", "   ")
    with pytest.raises(CredentialStoreError):
        format_credential_ref("INVALID ADAPTER", "pc-1")
    with pytest.raises(CredentialStoreError):
        format_credential_ref("openrouter", "bad id with spaces")
    with pytest.raises(CredentialStoreError):
        parse_credential_ref("no-colon-separator")
    with pytest.raises(CredentialStoreError):
        parse_credential_ref(":empty-service")


def test_bind_and_remove_provider_credential_never_writes_secret_to_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_file = tmp_path / "events.db"
    monkeypatch.setenv("ORCH_DB", str(db_file))
    sentinel = "sk-or-v1-ultra-secret-sentinel-key-424242"

    with project_store.connection() as conn:
        conn.execute(
            """INSERT INTO provider_configs(id, kind, adapter, display_name, enabled)
               VALUES ('pc-openrouter', 'model_provider', 'openrouter', 'OpenRouter Personal', 1)"""
        )
        conn.commit()

    store = CredentialStore(backend=InMemoryKeyringBackend())
    ref = bind_provider_credential("pc-openrouter", sentinel, store=store)
    assert ref == "multi-agent-orchestrator:openrouter:pc-openrouter"
    assert store.get_credential(ref) == sentinel

    with project_store.connection() as conn:
        row = conn.execute(
            "SELECT credential_ref, settings FROM provider_configs WHERE id='pc-openrouter'"
        ).fetchone()
        assert row["credential_ref"] == ref
        assert sentinel not in row["settings"]

        audits = [
            dict(r)
            for r in conn.execute(
                "SELECT action, details FROM platform_audit ORDER BY id ASC"
            ).fetchall()
        ]
        assert any(a["action"] == "credential.set" for a in audits)

    # Full binary/text scan of SQLite file on disk must never contain sentinel
    raw_db_bytes = db_file.read_bytes()
    assert sentinel.encode("utf-8") not in raw_db_bytes

    removed = remove_provider_credential("pc-openrouter", store=store)
    assert removed is True
    assert store.get_credential(ref) is None

    with project_store.connection() as conn:
        row = conn.execute(
            "SELECT credential_ref FROM provider_configs WHERE id='pc-openrouter'"
        ).fetchone()
        assert row["credential_ref"] is None
        audits = [
            dict(r)
            for r in conn.execute(
                "SELECT action, details FROM platform_audit ORDER BY id ASC"
            ).fetchall()
        ]
        assert [a["action"] for a in audits] == ["credential.set", "credential.removed"]

    assert sentinel.encode("utf-8") not in db_file.read_bytes()
