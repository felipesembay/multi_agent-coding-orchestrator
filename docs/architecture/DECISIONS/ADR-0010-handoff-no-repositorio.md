# ADR-0010 — Handoff e documentação persistente no repositório

- **Status:** proposto · **Data:** 2026-11-17 · **Tarefas:** V2-DOC-*

## Contexto
Agentes diferentes (Claude, Codex, Antigravity) desenvolverão este projeto; qualquer um pode esgotar contexto ou quota.

## Decisão
- `docs/planning/IMPLEMENTATION_PLAN.md` é o ponto de entrada; `AGENTS.md` e `CLAUDE.md` na raiz apontam para ele.
- Tarefas com IDs estáveis `V2-<ÁREA>-<NNN>`, status no [BACKLOG](../../planning/BACKLOG.md).
- Protocolo obrigatório em [AGENT_HANDOFF.md](../../handoff/AGENT_HANDOFF.md); `SESSION_LOG.md` append-only.
- Atualização **incremental**: o agente atualiza o handoff a cada marco (tarefa concluída, teste verde, decisão), não só no fim, para sobreviver a corte de contexto.
- Produto: para runs do orquestrador, handoff gerado **deterministicamente** a partir de eventos e ledger (sem chamada de LLM), garantindo continuidade mesmo sem tokens.

## Alternativas rejeitadas
| Alternativa | Motivo |
|---|---|
| Memória em ferramenta externa ou histórico de chat | Dependente de fornecedor; não versionado |
| Issues GitHub como fonte única | Requer rede/conta; offline-first é requisito |
