# ADR-0001 — Evoluir a v1, não reescrever

- **Status:** proposto · **Data:** 2026-11-17 · **Autor:** Claude · **Tarefas:** todas

## Contexto
A v1 tem 72 testes Python e 32 de frontend passando, cobre concorrência, idempotência, órfãos, validação de caminhos e CSRF ([auditoria](../CURRENT_STATE_AUDIT.md)). Essas garantias são caras de reconstruir.

## Decisão
Manter Python, FastAPI, LangGraph, SQLite, worker separado da API, fila em `managed_runs`, worktree por run e contratos HTTP/CLI existentes. A v2 é introduzida por extração e extensão (strangler), com testes de caracterização antes de cada refatoração.

## Alternativas rejeitadas
| Alternativa | Motivo |
|---|---|
| Reescrever backend em Rust/TypeScript junto com o shell Tauri | Perde garantias testadas; LangGraph é Python-first |
| Trocar SQLite por Postgres | App local de um usuário; aumenta complexidade de distribuição |
| Executar workflow dentro do processo FastAPI | Quebra a invariante de API reiniciável sem matar runs |

## Consequências
Distribuição desktop exige empacotar Python (sidecar). Python 3.9 (EOL out/2025) passa a ser restrição; ver [OPEN_QUESTIONS](../../planning/OPEN_QUESTIONS.md) Q3.

## Validação
Suítes atuais continuam verdes após cada tarefa de F1/F2.
