"""OS keyring credential store with in-memory test backend (V2-SEC-005 / ADR-0008)."""
from .store import (
    DEFAULT_KEYRING_SERVICE,
    CredentialStore,
    CredentialStoreError,
    InMemoryKeyringBackend,
    KeyringUnavailableError,
    bind_provider_credential,
    format_credential_ref,
    parse_credential_ref,
    remove_provider_credential,
)

__all__ = [
    "DEFAULT_KEYRING_SERVICE",
    "CredentialStore",
    "CredentialStoreError",
    "InMemoryKeyringBackend",
    "KeyringUnavailableError",
    "bind_provider_credential",
    "format_credential_ref",
    "parse_credential_ref",
    "remove_provider_credential",
]
