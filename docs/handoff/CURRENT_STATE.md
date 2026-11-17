# Estado atual

Atualizado: 2026-11-17 · Por: Codex (V2-DOC-001)

## Repositório
- Branch: `dev` (criada pelo operador). Último commit: `83cebe8` ("Criação da pasta do FrontEnd e Atualização do README.").
- **WIP não commitado pré-existente** (não criado nesta sessão): tema claro/escuro (`ThemeToggle.tsx`, `styles/theme.css`), exclusão lógica de projeto (`DeleteProject.tsx`, `projects.delete_project`, migração 3 `projects.deleted_at`), testes correspondentes e e2e `theme-and-delete.spec.ts`, alterações em README e frontend/README.
- Criado nesta sessão (somente documentação): `AGENTS.md`, `CLAUDE.md`, `docs/README.md`, `docs/architecture/**`, `docs/specifications/**`, `docs/design/**`, `docs/planning/**`, `docs/handoff/**`; seção "Evolução planejada" do README.

## Testes (2026-11-17, com o WIP presente)
| Comando | Resultado |
|---|---|
| `ORCH_DB=<tmp> python -m pytest -q -p no:cacheprovider` | 72 passed, 1 warning |
| `npx vitest run` (frontend) | 32 passed (6 arquivos) |
| Build, lint, e2e | não executados nesta sessão |

## Funcionalidade
v1 conforme [CURRENT_STATE_AUDIT.md](../architecture/CURRENT_STATE_AUDIT.md). **Nenhuma funcionalidade v2 implementada.**

## Ambiente observado
Python 3.9.7 (.venv), LangGraph 0.6.11, Node 22.18.0; CLIs `claude` 2.1.92, `codex` 0.166.0, `agy` 1.5.1, `ollama`; Rust/cargo presentes; Tauri CLI ausente.

## Implementação de infraestrutura v2 — V2-DOC-001
- `done`: `scripts/check_docs.py`, com `tests/test_check_docs.py` (9 casos), revisados independentemente por Codex `review_doc001` em 2026-11-17.
- Valida links locais/âncoras, definições por referência, IDs completos do backlog e data de CURRENT_STATE contra último commit de código. Sem rede e sem dependências novas.
- Testes finais: 81 pytest passed, 1 warning de depreciação LangGraph; 32 vitest passed; build e lint do frontend passaram; `python scripts/check_docs.py` passou. E2E não executado.
- A suíte pytest ficou bloqueada no TestClient dentro do sandbox; interrompida e repetida com autorização automática fora dele, passando em 8,18 s. Nenhum agente CLI real invocado nos testes.
- WIP original preservado; sem commits, merge, push ou deploy. Únicos arquivos novos de código desta sessão: `scripts/check_docs.py` e `tests/test_check_docs.py`.
- V2-F0-001 `blocked`: operador decidiu preservar WIP sem commit. V2-F0-002 `blocked`: operador informará decisões depois. Q2–Q12 seguem sem resposta; núcleo v2 não iniciado.

## Sessão atual — baseline em dev
- Operador autorizou implementação e commits em `dev` após testes; sem integração na main/master. Orientação anterior de não commitar foi substituída.
- V2-F0-001 revisada e aprovada por `review_baseline_dev`; baseline pronto para commit autorizado em dev. Baseline: 81 pytest / 32 vitest, build e lint verdes. Q2–Q12 continuam pendentes, sem impedir CORE-001 após baseline.
