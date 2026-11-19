"""Credential storage backed by OS keyring; secrets never enter SQLite, logs, or events.

Follows ADR-0008 and PROVIDER_SYSTEM.md §6.5:
- SQLite stores only a logical credential_ref (`service:username`, e.g.
  `multi-agent-orchestrator:openrouter:<config_id>`).
- Secrets are read at call time from the keyring backend.
- If no usable keyring backend is available (e.g., keyring.backends.fail.Keyring),
  operations fail closed with KeyringUnavailableError instead of falling back to
  plaintext files.
"""
from __future__ import annotations

import json
import re
from typing import Optional

import keyring
from keyring.backend import KeyringBackend
from keyring.backends.fail import Keyring as FailKeyring
from keyring.backends.null import Keyring as NullKeyring
from keyring.errors import KeyringError, PasswordDeleteError

from .. import projects
from ..project_store import connection

DEFAULT_KEYRING_SERVICE = "multi-agent-orchestrator"
_REF_PART_RE = re.compile(r"^[a-zA-Z0-9._:@/-]{1,128}$")


class CredentialStoreError(RuntimeError):
    """Base error for credential operations; never contains secret values."""


class KeyringUnavailableError(CredentialStoreError):
    """Raised when no functional OS keyring backend is available."""


class InMemoryKeyringBackend(KeyringBackend):
    """Deterministic in-memory keyring backend for automated tests (never touches OS D-Bus)."""

    priority = 1

    def __init__(self) -> None:
        super().__init__()
        self._storage: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> Optional[str]:
        return self._storage.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._storage[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self._storage:
            raise PasswordDeleteError("Credential not found")
        del self._storage[(service, username)]


def format_credential_ref(
    adapter: str, config_id: str, *, service: str = DEFAULT_KEYRING_SERVICE
) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", adapter):
        raise CredentialStoreError("Invalid adapter identifier for credential reference")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", config_id):
        raise CredentialStoreError("Invalid provider config identifier for credential reference")
    if not _REF_PART_RE.fullmatch(service) or ":" in service:
        raise CredentialStoreError("Invalid keyring service name")
    username = f"{adapter}:{config_id}"
    return f"{service}:{username}"


def parse_credential_ref(credential_ref: str) -> tuple[str, str]:
    if not isinstance(credential_ref, str) or ":" not in credential_ref:
        raise CredentialStoreError("Invalid credential_ref format")
    service, _, username = credential_ref.partition(":")
    if (
        not service
        or not username
        or not _REF_PART_RE.fullmatch(service)
        or not _REF_PART_RE.fullmatch(username)
    ):
        raise CredentialStoreError("Invalid credential_ref format")
    return service, username


class CredentialStore:
    """Safe wrapper over a keyring backend that refuses fail/null backends and never logs secrets."""

    def __init__(
        self,
        *,
        backend: Optional[KeyringBackend] = None,
        service: str = DEFAULT_KEYRING_SERVICE,
    ) -> None:
        self._backend = backend
        self._service = service

    def _active_backend(self) -> KeyringBackend:
        backend = self._backend if self._backend is not None else keyring.get_keyring()
        if isinstance(backend, (FailKeyring, NullKeyring)):
            raise KeyringUnavailableError(
                "No OS keyring backend available; configure Secret Service/libsecret or inject a backend"
            )
        return backend

    def set_credential(self, adapter: str, config_id: str, secret: str) -> str:
        if not isinstance(secret, str) or not secret.strip():
            raise CredentialStoreError("Credential secret cannot be empty")
        ref = format_credential_ref(adapter, config_id, service=self._service)
        service, username = parse_credential_ref(ref)
        backend = self._active_backend()
        try:
            backend.set_password(service, username, secret)
        except Exception:
            raise KeyringUnavailableError("Could not store credential in OS keyring") from None
        return ref

    def get_credential(self, credential_ref: str) -> Optional[str]:
        service, username = parse_credential_ref(credential_ref)
        backend = self._active_backend()
        try:
            return backend.get_password(service, username)
        except Exception:
            raise KeyringUnavailableError("Could not read credential from OS keyring") from None

    def has_credential(self, credential_ref: Optional[str]) -> bool:
        if not credential_ref:
            return False
        value = self.get_credential(credential_ref)
        return bool(value and value.strip())

    def delete_credential(self, credential_ref: str) -> bool:
        service, username = parse_credential_ref(credential_ref)
        backend = self._active_backend()
        try:
            existing = backend.get_password(service, username)
            if existing is None:
                return False
            backend.delete_password(service, username)
            return True
        except PasswordDeleteError:
            return False
        except KeyringError:
            raise KeyringUnavailableError("Could not delete credential from OS keyring") from None
        except Exception:
            raise KeyringUnavailableError("Could not delete credential from OS keyring") from None


def bind_provider_credential(
    config_id: str,
    secret: str,
    *,
    store: CredentialStore,
) -> str:
    """Save secret in keyring and store only credential_ref in provider_configs + audit log."""
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id, adapter FROM provider_configs WHERE id=?", (config_id,)
        ).fetchone()
        if row is None:
            raise CredentialStoreError("Provider configuration not found")
        ref = store.set_credential(row["adapter"], row["id"], secret)
        conn.execute(
            "UPDATE provider_configs SET credential_ref=? WHERE id=?",
            (ref, row["id"]),
        )
        projects.audit(
            conn,
            "credential.set",
            None,
            provider_config_id=row["id"],
            adapter=row["adapter"],
            credential_ref=ref,
        )
        conn.commit()
    return ref


def remove_provider_credential(
    config_id: str,
    *,
    store: CredentialStore,
) -> bool:
    """Remove secret from keyring and clear credential_ref in provider_configs + audit log."""
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id, adapter, credential_ref FROM provider_configs WHERE id=?",
            (config_id,),
        ).fetchone()
        if row is None:
            raise CredentialStoreError("Provider configuration not found")
        ref = row["credential_ref"]
        removed = False
        if ref:
            removed = store.delete_credential(ref)
        conn.execute(
            "UPDATE provider_configs SET credential_ref=NULL WHERE id=?",
            (row["id"],),
        )
        projects.audit(
            conn,
            "credential.removed",
            None,
            provider_config_id=row["id"],
            adapter=row["adapter"],
        )
        conn.commit()
    return removed
