# ADR-0008 — Credenciais no keyring do SO

- **Status:** proposto · **Data:** 2026-11-17 · **Tarefas:** V2-SEC-005, V2-PROV-001

## Contexto
OpenRouter e APIs diretas exigem chaves. CLIs mantêm autenticação própria e devem continuar assim.

## Decisão
Biblioteca Python `keyring` (Secret Service/libsecret no Ubuntu; Keychain e Credential Manager no futuro). SQLite guarda apenas `credential_ref` (`service`, `username`). Chave lida no momento da chamada, nunca serializada em eventos, logs, `config` de runs ou respostas HTTP. Sem backend de keyring disponível → recusar salvar e orientar (não cair para arquivo em texto puro). Fallback opcional por variável de ambiente explícita, documentado como menos seguro.

## Alternativas rejeitadas
| Alternativa | Motivo |
|---|---|
| Coluna criptografada no SQLite | Chave de criptografia teria de morar em algum lugar do disco |
| Tauri Stronghold | Prende segredos ao processo Rust; backend Python precisaria de IPC extra |
| Arquivo `.env` | Texto puro |

## Consequências
Sessões sem D-Bus (headless) não terão keyring; documentar.
