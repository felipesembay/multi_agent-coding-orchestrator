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

## Consequências
Operador autorizou Python 3.12 em 2026-11-18 (Q3); verificar `langgraph-checkpoint-sqlite` com o alvo e LangGraph atual em V2-F0-005 antes de RES-002. Ambiente atual ainda Python 3.9.7.

## Decisão específica Q11 — 2026-11-18

Operador autorizou commits automáticos na worktree após cada tarefa aprovada, somente na branch agent/<run>, sem merge/push/deploy ou alteração da branch de origem por runs. Essa opção complementa checkpoints/ledger; não os substitui, não ocorre após toda tentativa/chamada e não dispensa inspeção/decisão de retomada. Implementação permanece pendente em V2-RES-001. O ADR integral continua proposto.
