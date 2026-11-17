# ADR-0007 — Checkpoints LangGraph + ledger de efeitos colaterais

- **Status:** proposto · **Data:** 2026-11-17 · **Tarefas:** V2-RES-*

## Contexto
Runs gerenciados interrompidos não podem ser retomados. Chamadas de agente modificam a worktree e consomem quota; repeti-las às cegas duplica efeitos.

## Decisão
1. `langgraph-checkpoint-sqlite` (`SqliteSaver`) em arquivo separado, `thread_id = run_id`, checkpoint após cada nó.
2. Ledger `step_executions` gravado **antes** (`started`, com `git HEAD` e digest da árvore) e **depois** (`completed`) de cada nó com efeito colateral.
3. Na retomada: nó `completed` → usa checkpoint; nó `started` sem `completed` → `needs_inspection`: compara digest atual com `tree_digest_before`; se igual, pode repetir com aprovação humana; se diferente, exige decisão humana (aceitar estado atual e ir para review, descartar alterações via comando explícito, ou abortar).
4. Testes são idempotentes por natureza (re-executáveis); reviewer read-only pode ser repetido automaticamente.
5. Retomada sempre requer confirmação humana no MVP.

## Alternativas rejeitadas
| Alternativa | Motivo |
|---|---|
| Só checkpoints LangGraph | Não sabe se uma chamada externa ocorreu parcialmente |
| Replay de eventos (como `resume` legado) | Já existe para CLI; frágil para grafos configuráveis |
| Commit automático na worktree após cada passo | Mais simples para diff, mas altera histórico da branch; avaliar como opção (Q11) |

## Consequências
Verificar compatibilidade de `langgraph-checkpoint-sqlite` com Python 3.9 e LangGraph 0.6.x (hipótese: versões recentes exigem ≥3.10).
